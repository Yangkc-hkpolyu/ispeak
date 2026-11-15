"""GPU mel must agree with the CPU features expected by Wav2Lip."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchaudio")

from backend.speaking.vendor.livetalking import audio


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
@pytest.mark.parametrize("kind", ["speech_like", "noise", "silence"])
def test_gpu_mel_matches_cpu(kind):
    rng = np.random.default_rng(91)
    t = np.arange(32000, dtype=np.float32) / 16000
    if kind == "speech_like":
        wav = (0.15 * np.sin(2 * np.pi * 220 * t) + 0.03 * rng.normal(size=t.size)).astype(np.float32)
    elif kind == "noise":
        wav = rng.normal(0, 0.05, size=t.size).astype(np.float32)
    else:
        wav = np.zeros(t.size, dtype=np.float32)
    maximum, mean = audio.melspectrogram_compare_gpu_cpu(wav, torch.device("cuda"))
    assert maximum < 0.005
    assert mean < 0.001
