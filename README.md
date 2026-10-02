# WeaveNet Phase 1: Voice Note Bot

Send a WhatsApp voice note in Hindi/English. The bot transcribes it (Sarvam Saaras v3),
extracts intent and items (Sarvam chat model), and replies in your language.

## 1. Install
```bash
pip install flask requests python-dotenv
# ffmpeg is required (sudo apt install ffmpeg  /  brew install ffmpeg)
```

## 2. Keys (.env)
```
SARVAM_API_KEY=...            # dashboard.sarvam.ai
WHATSAPP_TOKEN=...            # Meta access token
WHATSAPP_PHONE_NUMBER_ID=...  # from WhatsApp > API Setup
WHATSAPP_VERIFY_TOKEN=weavenet123   # any string; reuse in Meta webhook setup
WHATSAPP_APP_SECRET=...       # optional in dev, set in production
ANALYSIS_MODEL=sarvam-105b   # or sarvam-30b
```

## 3. WhatsApp setup (Meta)
1. developers.facebook.com -> Create App -> Business -> add **WhatsApp** product.
2. In API Setup, note the test phone number ID and token. Add your own number as a recipient.
3. Run the bot: `python app.py`
4. Expose it: `ngrok http 5000` (gives an https URL).
5. WhatsApp > Configuration > Webhook: callback `https://<ngrok-url>/webhook`,
   verify token = your `WHATSAPP_VERIFY_TOKEN`, subscribe to **messages**.
6. Message the test number first (opens the 24h window), then send a voice note.

## 4. Try these voice notes
- "Ramesh ke paas 22 kilo indigo bacha hai"
- "Germany se 500 meter indigo print ka order aaya hai, 18 din mein chahiye"
- "Lot 2291 ka rang thoda halka lag raha hai"

## Notes
- Sarvam's sync endpoint accepts max 30s, so the code splits audio into 28s chunks.
- Modes: `codemix` (Hindi+English mix), `transcribe` (native script), `translate` (to English).
- Saarika v2.5 is being deprecated; this uses `saaras:v3`.
- Right now results are printed as JSON log lines. Next step: save to SQLite.
- Everything (speech-to-text and analysis) runs on Sarvam with one API key.
- Telegram version (no business account needed): `telegram_bot.py` with `TELEGRAM_BOT_TOKEN` in .env.