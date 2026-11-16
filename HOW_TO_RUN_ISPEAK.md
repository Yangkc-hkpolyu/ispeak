# How to run ispeak on Windows

## Normal launch on this computer

1. Open this folder in File Explorer:

   `.\ispeak`

2. Double-click `start-speaking.bat`.

3. Keep the PowerShell/terminal window open. Wait until it prints:

   `ispeak: http://127.0.0.1:8008`

4. Open a current version of Chrome or Edge and visit:

   `http://127.0.0.1:8008/`

5. Allow microphone access when the browser asks. The microphone is required for recorded speaking practice.

6. When finished, return to the terminal window and press `Ctrl+C`. Closing that terminal window also stops ispeak.

## Launch from PowerShell instead

Open PowerShell and run:

```powershell
cd ".\ispeak"
.\start-speaking.bat
```

Then open `http://127.0.0.1:8008/` in Chrome or Edge.

## If this folder is copied to another computer

For a Git clone or GitHub source ZIP, follow the model-assets installation steps in `README.md` first. Large runtime models and avatar assets are distributed through the repository's Releases, separately from the source code.

The copied folder must include the model and avatar assets. Install 64-bit Python 3.12 and a compatible NVIDIA driver, then open PowerShell inside the copied `ispeak` folder and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -r requirements-speaking.txt
.\.venv\Scripts\python.exe -s scripts/setup_voice_coach.py --base-dir speaking-models/voice-coach/base
Copy-Item speaking.env.example speaking.env
```

Open `speaking.env` and add your own DashScope API key. Keep this file private and do not include it in a shared ZIP or Git repository. Then launch with `start-speaking.bat`.

## Quick checks when it does not start

- If the terminal says the virtual environment is missing, repeat the first-time setup above.
- If port 8008 is already in use, close the earlier ispeak terminal, or stop its Python process, and launch again.
- If the page does not open, confirm the terminal is still running and use exactly `http://127.0.0.1:8008/`.
- If recording is unavailable, use current Chrome or Edge and allow microphone access for `127.0.0.1`.
- If the avatar is slow or unavailable, check that the NVIDIA driver is installed and that the terminal reports CUDA is available.
- The optional Azure pronunciation assessment is not configured by default. This does not prevent normal Qwen transcription, chat, avatar playback, or local pace-and-pause feedback.
