"""Brand changes must retain checksum and path protections for released assets."""
import hashlib
import importlib.util
from pathlib import Path
import zipfile

import pytest


def installer(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/install_speaking_assets.py"
    spec = importlib.util.spec_from_file_location("asset_installer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path / "application")
    return module


def archive(tmp_path, wrapper="legacy-coursework", unsafe=False):
    path = tmp_path / "assets.zip"
    weights = b"verified checkpoint fixture"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(wrapper + "/speaking-models/wav2lip.pth", weights)
        package.writestr(wrapper + "/speaking-models/avatars/nora/avatar.json", "{}")
        if unsafe:
            package.writestr(wrapper + "/speaking-models/../../outside.txt", "must not be written")
    return path, {"asset_archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "file_sha256": hashlib.sha256(weights).hexdigest()}


@pytest.mark.parametrize("wrapper", ["legacy-coursework", "COMP4431_ispeak"])
def test_verified_assets_work_with_original_and_renamed_wrappers(tmp_path, monkeypatch, wrapper):
    module = installer(tmp_path, monkeypatch)
    path, manifest = archive(tmp_path, wrapper)
    module.install(path, manifest)
    assert (module.ROOT / "speaking-models/wav2lip.pth").read_bytes() == b"verified checkpoint fixture"
    assert (module.ROOT / "speaking-models/avatars/nora/avatar.json").is_file()


def test_archive_mismatch_and_path_escape_cannot_write_files(tmp_path, monkeypatch):
    module = installer(tmp_path, monkeypatch)
    path, manifest = archive(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        module.install(path, {**manifest, "asset_archive_sha256": "wrong"})
    assert not module.ROOT.exists()
    path, manifest = archive(tmp_path, unsafe=True)
    with pytest.raises(ValueError, match="Invalid asset path|escapes"):
        module.install(path, manifest)
    assert not module.ROOT.exists()


def test_existing_different_model_is_not_overwritten(tmp_path, monkeypatch):
    module = installer(tmp_path, monkeypatch)
    path, manifest = archive(tmp_path)
    existing = module.ROOT / "speaking-models/wav2lip.pth"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep existing model")
    with pytest.raises(ValueError, match="existing asset differs"):
        module.install(path, manifest)
    assert existing.read_bytes() == b"keep existing model"
    assert not (module.ROOT / "speaking-models/avatars/nora/avatar.json").exists()
