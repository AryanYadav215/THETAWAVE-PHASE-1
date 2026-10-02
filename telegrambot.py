"""
WeaveNet Phase 1 (Telegram version): voice note -> Sarvam STT -> LLM analysis -> reply.
Uses long polling, so no webhook, ngrok or business account is needed.

Run:  python telegram_bot.py
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]  # from @BotFather
SARVAM_KEY = os.environ["SARVAM_API_KEY"]
ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "sarvam-105b")  # or "sarvam-30b" (faster/cheaper)
TG = f"https://api.telegram.org/bot{TG_TOKEN}"

SYSTEM = """You are the WeaveNet assistant for small textile businesses in Bagru, Rajasthan
(dyers, block printers, suppliers, exporters). You receive the transcript of a voice note,
usually Hindi/Marwari mixed with English. Extract what the speaker said.

Return ONLY JSON with these keys:
- "language": language of the speaker ("hi", "en", ...)
- "intent": one of "stock_update", "new_order", "quality_issue", "payment", "delivery", "question", "other"
- "entities": list of objects like {"item": "indigo", "quantity": 22, "unit": "kg", "lot": null,
   "party": null, "date": null}. Use null for anything not said. Never invent values.
- "summary_en": one sentence in English
- "reply": a short, friendly reply in the SAME language and style the speaker used
   (Hindi in Devanagari if they spoke Hindi). Confirm what you understood. If something
   important is unclear, ask ONE short question. Do not give advice you cannot support."""


def send(chat_id: int, text: str) -> None:
    r = requests.post(f"{TG}/sendMessage",
                      json={"chat_id": chat_id, "text": text[:4000]}, timeout=30)
    if not r.ok:
        print("send failed:", r.status_code, r.text)


def download_voice(file_id: str, dest: Path) -> None:
    info = requests.get(f"{TG}/getFile", params={"file_id": file_id}, timeout=30).json()
    path = info["result"]["file_path"]
    audio = requests.get(f"https://api.telegram.org/file/bot{TG_TOKEN}/{path}", timeout=60)
    audio.raise_for_status()
    dest.write_bytes(audio.content)


def split_to_chunks(src: Path, outdir: Path, seconds: int = 28) -> list[Path]:
    """Sarvam's sync endpoint accepts max 30s: convert to 16k mono WAV and segment."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1",
         "-f", "segment", "-segment_time", str(seconds), str(outdir / "chunk_%03d.wav")],
        check=True, capture_output=True,
    )
    return sorted(outdir.glob("chunk_*.wav"))


def transcribe_chunk(path: Path, mode: str = "codemix") -> str:
    # mode: "codemix" (Hindi+English), "transcribe" (native script), "translate" (to English)
    with open(path, "rb") as f:
        r = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": SARVAM_KEY},
            files={"file": (path.name, f, "audio/wav")},
            data={"model": "saaras:v3", "mode": mode},
            timeout=60,
        )
    r.raise_for_status()
    return r.json().get("transcript", "")


def analyze(transcript: str) -> dict:
    r = requests.post(
        "https://api.sarvam.ai/v1/chat/completions",
        headers={"api-subscription-key": SARVAM_KEY},
        json={
            "model": ANALYSIS_MODEL,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": transcript},
            ],
        },
        timeout=90,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or ""
    # Be forgiving: grab the JSON object even if the model adds extra text or code fences.
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def handle_voice(chat_id: int, file_id: str) -> None:
    try:
        send(chat_id, "Sun raha hoon...")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "voice.ogg"
            download_voice(file_id, src)
            chunks = split_to_chunks(src, Path(d))
            transcript = " ".join(transcribe_chunk(c) for c in chunks).strip()
        if not transcript:
            send(chat_id, "Awaaz saaf nahi aayi. Kripya dobara bhejiye.")
            return
        result = analyze(transcript)
        print(json.dumps({"chat": chat_id, "transcript": transcript, **result}, ensure_ascii=False))
        send(chat_id,
             f"{result['reply']}\n\n"
             f"— Maine suna: \"{transcript}\"\n"
             f"— Type: {result['intent']}\n"
             f"— Details: {json.dumps(result['entities'], ensure_ascii=False)}")
    except Exception as e:
        print("handle_voice error:", repr(e))
        send(chat_id, "Kuch gadbad ho gayi. Thodi der baad dobara try kijiye.")


def main() -> None:
    print("Bot running. Send a voice note to your bot on Telegram. Ctrl+C to stop.")
    offset = None
    while True:
        try:
            r = requests.get(f"{TG}/getUpdates",
                             params={"timeout": 30, "offset": offset}, timeout=40).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id:
                    continue
                if "voice" in msg:
                    handle_voice(chat_id, msg["voice"]["file_id"])
                elif "audio" in msg:
                    handle_voice(chat_id, msg["audio"]["file_id"])
                elif "text" in msg:
                    send(chat_id, "Kripya voice note bhejiye. Main sun kar samjhunga.")
        except requests.RequestException as e:
            print("network error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()