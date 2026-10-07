"""Verify and copy the committed Render runtime bundle to the paths the API reads."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "deploy" / "render-assets"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize() -> int:
    manifest_path = BUNDLE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest:
        raise ValueError("Render artifact manifest is empty")

    for relative, expected in manifest.items():
        relative_path = PurePosixPath(relative)
        if (relative_path.is_absolute() or "\\" in relative
                or ".." in relative_path.parts or relative_path.parts[0] != "ml"):
            raise ValueError("Unsafe Render artifact path in manifest")

        source = BUNDLE.joinpath(*relative_path.parts)
        target = ROOT.joinpath(*relative_path.parts)
        if source.is_symlink() or not source.is_file() or sha256(source) != expected:
            raise ValueError("Render artifact is missing or failed checksum validation")
        if target.exists():
            if target.is_symlink() or not target.is_file() or sha256(target) != expected:
                raise ValueError("Refusing to overwrite a different runtime artifact")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    return len(manifest)


if __name__ == "__main__":
    print(f"Verified runtime artifact files: {materialize()}")
