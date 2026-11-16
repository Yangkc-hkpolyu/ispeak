# ispeak — IELTS / TOEFL speaking practice

ispeak is a domain-specific speaking-practice prototype with a cloud examiner, a talking avatar, a text-only preparation chat, practice reports, and optional local fine-tuned advice. It is not an official IELTS or TOEFL examiner.

## Group members — complete before submission

| English name | Student ID | Contribution |
| --- | --- | --- |
| **Add each group member** | **Add student ID** | **Describe contribution** |

Add a row for every member. Submit this source ZIP and a separate presentation slide file as required by the course.

## Features

- The integrated assessment report provides a four-dimension radar, answer-by-answer evidence and revisions, and a downloadable PDF. Reports use saved feedback without another model call. See `docs/SPEAKING_REPORTS.md`.
- Ask the tutor provides text-only, multi-turn preparation chat using the configured hosted Qwen model. Chat content is sent to that provider; refresh clears the conversation.
- Guided practice and mock tests use Qwen real-time speech recognition, hosted examiner responses, EdgeTTS, a local Wav2Lip checkpoint and WebRTC avatar media.
- The report estimates pace and pauses from recorded audio energy and ASR word count. A separate Qwen2.5-1.5B LoRA adapter generates optional advice from numeric metrics only, in a CPU subprocess. It is not a pronunciation assessment or official score.
- The Settings dialog provides a 0–1000 ms avatar video-delay control. Audio/video synchronization has not been independently verified after this adjustment and can still be noticeably wrong; a real listening test is necessary.

## Run on Windows

The supplied coursework ZIP contains local model weights and avatar assets, but deliberately excludes Python virtual environments, installed libraries, private keys and user recordings. A Git clone or GitHub source ZIP excludes the large runtime model and avatar files. The trained LoRA adapter is included under `experiments/voice-coach/adapter`.

For a Git clone, open this repository's Releases section, select v3.0.0, and download its model-assets ZIP. After installing the dependencies below, run this command with the actual downloaded archive path:

```powershell
.\.venv\Scripts\python.exe -s scripts/install_speaking_assets.py --archive "E:\Downloads\COMP4431_ispeak_model_assets.zip"
```

The installer checks the archive and model checksums before extracting the avatar assets. Skip this step when using the coursework ZIP with its existing model files.

Install dependencies before launching. The local model's isolated inference packages must also be installed. Use Windows x64, Python 3.12, a compatible NVIDIA GPU/driver and internet access. A microphone is required for spoken practice.

Open PowerShell inside the extracted `ispeak` directory. Check `python --version` is 3.12, or use the full path of a Python 3.12 executable in place of `python` below.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -r requirements-speaking.txt
.\.venv\Scripts\python.exe -s scripts/setup_voice_coach.py
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
Copy-Item speaking.env.example speaking.env
```

The CUDA 12.6 wheel needs a compatible NVIDIA driver. Consult https://pytorch.org/get-started/previous-versions/ if another build is necessary. The default local-model setup downloads the pinned Qwen base model and installs the included adapter. If using the coursework ZIP with its existing base weights, add `--base-dir speaking-models/voice-coach/base` to the setup command to avoid downloading those weights again. Internet access may still be needed for package installation. The optional `torchaudio` dependency is not required for the default CPU mel path. CUDA remains enabled for Wav2Lip when available.

Edit `speaking.env` and enter your own DashScope API key with the matching region and model access. The template uses the international endpoint and documents the Beijing endpoint. Requests may use account quota.

```powershell
.\start-speaking.bat
```

Open http://127.0.0.1:8008/ and permit the microphone. In PyCharm, select `.venv\Scripts\python.exe` as the project interpreter and run `run-speaking.py` from the project directory. The compiled frontend is included.

## Fine-tuning and evaluation

The local LoRA experiment used 608 synthetic, rule-generated training examples over two epochs. In 38 synthetic tests, heuristics flagged 27 base outputs and 3 adapter outputs; a separate runtime filter rejected the latter three. The examples share a generator, training was revised after earlier observations, and these flags are not independent real-world accuracy rates. Human evaluation on diverse real recordings remains needed. See `experiments/voice-coach/README.md`, `evaluation_v2.json`, and `docs/SPEAKING_VOICE_COACH.md`.

The earlier version passed a short cloud-chat check. After installing this package, verify the configured cloud account, speech recognition, playback, and audio/video sync on the presentation device.

The public project package intentionally excludes personal practice records and recordings. A separately supplied private backup can be restored into a fresh project while the application is stopped. Back up an existing `speaking-runtime` first to avoid overwriting newer sessions. Old browser session and video-delay settings remain compatible with the renamed application.

## Third-party components

The project adapts user-provided PolyInterview, LiveTalking and Wav2Lip materials and includes the Qwen base model and LoRA experiment. Sources, contributor attribution and license notices are in `THIRD_PARTY_SPEAKING.md`, `experiments/voice-coach/PROVENANCE.json` and the model license. The upstream open Wav2Lip version is for personal, research and non-commercial use.
