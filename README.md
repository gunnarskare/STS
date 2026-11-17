# STS

Initial Norwegian-to-English church translation prototype.

## Architecture

Mixer USB input → local Python audio capture → one OpenAI realtime translation session → English PCM audio and transcript → browser listeners.

OpenAI is the first provider. Local Whisper, translation and Piper remain planned alternatives. ChurchPresenter/STT informed the architecture; no source was copied.

## Run

Use Python 3.11+. Install requirements with `pip install -r requirements.txt`.
Linux may require the PortAudio system package. Select the mixer as the system default recording device, or set STS_AUDIO_DEVICE to its device name.

Set OPENAI_API_KEY in the server environment. Start with `uvicorn app:app --host 0.0.0.0 --port 8000`.
Open http://localhost:8000 or the server LAN address on a phone and press Listen live.

Starting the server immediately captures the selected input and sends audio to OpenAI, incurring API charges. Stop the server to stop capture and billing. /health reports status.

Use a trusted local network. This prototype has no authentication. Use a single server worker. API keys stay on the server. Audio and transcripts are held only in memory.

## Status and next work

This is a first integration prototype, not yet validated with live API audio.
Required before church use:
- Validate Norwegian dialects, translation accuracy and delay with real sermon recordings.
- Operator start/pause controls, input selection and QR code.
- Test mobile playback, lock screen and reconnect behavior.
- Session renewal, bounded-latency fanout with explicit discontinuities and automated recovery.
- Test multiple listeners on the church Wi-Fi.
- Add a local provider and deliberate API fallback controls.

Provider protocol reference: https://developers.openai.com/api/docs/guides/realtime-translation
