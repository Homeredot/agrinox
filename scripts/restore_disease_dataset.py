"""Restore and extract disease_dataset from its numbered Git LFS parts."""

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARTS_PATTERN = "disease_dataset.zip.part*"
TARGET = PROJECT_ROOT / "disease_dataset"
MARKER_CLASS = "Potato___Early_blight"


def find_dataset_root(extracted: Path) -> Path:
    candidates = [path.parent for path in extracted.rglob(MARKER_CLASS) if path.is_dir()]
    if not candidates:
        raise RuntimeError(f"Archive does not contain the expected {MARKER_CLASS} class.")
    return min(candidates, key=lambda path: len(path.relative_to(extracted).parts))


def normalize_nested_copy() -> None:
    duplicate = next((path for path in TARGET.iterdir() if path.is_dir() and (path / MARKER_CLASS).is_dir()), None)
    normalized = TARGET / "disease_dataset"
    if duplicate and duplicate != normalized:
        if normalized.exists():
            shutil.rmtree(normalized)
        duplicate.rename(normalized)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore the Agrinox disease_dataset from Git LFS parts.")
    parser.add_argument("--force", action="store_true", help="Replace the existing extracted dataset.")
    args = parser.parse_args()

    if TARGET.exists() and any(TARGET.rglob("*.JPG")) and not args.force:
        print(f"disease_dataset is already available at {TARGET}")
        return 0

    parts = sorted((PROJECT_ROOT / "data").glob(PARTS_PATTERN))
    if not parts:
        raise SystemExit("No disease_dataset LFS archive parts were found. Run 'git lfs pull' first.")

    if args.force and TARGET.exists():
        shutil.rmtree(TARGET)

    with tempfile.TemporaryDirectory(prefix="agrinox-restore-", dir=PROJECT_ROOT) as temporary:
        temporary_path = Path(temporary)
        archive_path = temporary_path / "disease_dataset.zip"
        with archive_path.open("wb") as archive:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, archive)

        extract_root = temporary_path / "extracted"
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extract_root)
        shutil.move(str(find_dataset_root(extract_root)), str(TARGET))
        normalize_nested_copy()

    print(f"disease_dataset restored from {len(parts)} Git LFS parts at {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
