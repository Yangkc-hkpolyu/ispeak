# English examiner voice and local recording feedback

These files update the Group 9 Windows package named `ispeak-final-20261118`. The package already includes the Windows runtime, 3D character, Qwen base weights and trained LoRA adapter.

## Use Jenny in 720p and 1080p

1. Exit iSpeak. Copy `launch.py` and `app/speaking.env.example` from this update into the corresponding locations in the extracted package. If you have customized the launcher, merge the change by removing the conditional in `read_private_config()` that sets `SPEAKING_TTS_PROVIDER` to `qwen` in consultation mode.
2. If you have run the package before, open `%LOCALAPPDATA%\iSpeakStandalone\speaking.env`. Update or add these two lines and keep your own DashScope key and region. For a first installation, the launcher creates this profile from the updated example. Enter your own DashScope key there for recognition and conversation.

   ```dotenv
   SPEAKING_TTS_PROVIDER=edgetts
   SPEAKING_VOICE_EN=en-US-JennyNeural
   ```

## Enable the team's fine-tuned model

From the **extracted package root** (the folder containing `Start iSpeak.vbs`), run the following in PowerShell with `uv` installed. This installs the package's pinned inference libraries into the directory used by the recording feedback worker. It uses the package's own Python and model weights.

```powershell
$deps = Join-Path $env:LOCALAPPDATA 'iSpeakStandalone\data\voice-coach-deps'
uv pip install --python .\python\python.exe --target "$deps" --no-deps --only-binary :all: -r .\Source\requirements-voice-coach.txt
```

## Check the running app

Start your usual shortcut and select **Try voice**. On the 720p build, open [service status](http://localhost:8008/api/speaking/status) and check that `speech_provider` is `edgetts` and `speech_voice` is `en-US-JennyNeural`. The 1080p shortcuts use port `18008`.

Open [voice coach status](http://localhost:8008/api/speaking/voice-coach/status) on the same port and check for `ready: true`. Record a spoken answer, finish the practice, and open **Your speaking feedback**. A successful review shows **Fine-tuned voice advice**. The local Qwen2.5-1.5B model with the team's adapter uses estimated pace, pauses and recording level. Advice that fails the checks against those measurements is withheld. Speech recognition, examiner follow-ups and feedback on answer content continue to use the configured cloud services.
