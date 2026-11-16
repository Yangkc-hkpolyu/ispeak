"""Install the checksum-pinned model and avatar from the GitHub release."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install(archive, manifest):
    if digest_file(archive) != manifest['asset_archive_sha256']:
        raise ValueError('Asset archive checksum mismatch; no files were installed.')
    destination = (ROOT / 'speaking-models').resolve()
    with zipfile.ZipFile(archive) as package:
        # Older verified releases can have a different outer project-folder name.
        # Resolve that wrapper from the archive, while keeping the pinned checksum
        # and every destination/path validation below.
        marker = '/speaking-models/'
        entries = [entry for entry in package.infolist() if not entry.is_dir()]
        prefixes = {entry.filename.split(marker, 1)[0] + marker for entry in entries if marker in entry.filename}
        if len(prefixes) != 1 or any(marker not in entry.filename for entry in entries):
            raise ValueError('Archive must contain one model-assets directory.')
        prefix = next(iter(prefixes))
        if PurePosixPath(prefix).is_absolute() or '..' in PurePosixPath(prefix).parts or '\\' in prefix:
            raise ValueError('Invalid model-assets archive root.')
        files = []
        seen = set()
        for entry in package.infolist():
            if entry.is_dir():
                continue
            if not entry.filename.startswith(prefix):
                raise ValueError('Archive contains a file outside speaking-models.')
            relative = PurePosixPath(entry.filename[len(prefix):])
            if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
                raise ValueError('Invalid asset path.')
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination) or target == destination:
                raise ValueError('Asset path escapes the model directory.')
            if stat.S_ISLNK(entry.external_attr >> 16) or target in seen:
                raise ValueError('Duplicate or symbolic-link asset.')
            seen.add(target)
            # Validate every entry and any existing destination before writing.
            with package.open(entry) as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            if relative.as_posix() == 'wav2lip.pth' and checksum != manifest['file_sha256']:
                raise ValueError('Checkpoint checksum differs from the source manifest.')
            if target.exists() and (not target.is_file() or digest_file(target) != checksum):
                raise ValueError('An existing asset differs: ' + str(relative))
            files.append((entry, target))
        if not {destination / 'wav2lip.pth', destination / 'avatars/nora/avatar.json'} <= seen:
            raise ValueError('Model or avatar manifest is missing.')
        for entry, target in files:
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.installing')
            with package.open(entry) as incoming, temporary.open('xb') as output:
                shutil.copyfileobj(incoming, output)
            temporary.replace(target)
    print(f'Verified and installed {len(files)} model/avatar files in {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Already downloaded model/assets ZIP')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'speaking-models/source.json').read_text(encoding='utf-8'))
    archive = args.archive
    if archive is None:
        archive = ROOT / '.downloads' / manifest['asset_archive']
        if not archive.is_file():
            if not shutil.which('gh'):
                parser.error('Download the ZIP from the GitHub Release, then use --archive PATH. See README.md.')
            archive.parent.mkdir(parents=True, exist_ok=True)
            # Numeric repository and asset IDs survive a repository/brand rename.
            temporary = archive.with_name(archive.name + '.downloading')
            endpoint = f"repositories/{manifest['repository_id']}/releases/assets/{manifest['asset_id']}"
            with temporary.open('wb') as output:
                subprocess.run(['gh', 'api', endpoint, '--header', 'Accept: application/octet-stream'],
                               stdout=output, check=True)
            temporary.replace(archive)
    install(archive.resolve(), manifest)


if __name__ == '__main__':
    main()
