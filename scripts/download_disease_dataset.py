"""Download and prepare the plant disease image dataset from Kaggle."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DATASET = "emmarex/plantdisease"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = PROJECT_ROOT / "disease_dataset"
MARKER_CLASS = "Potato___Early_blight"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def image_count() -> int:
    return sum(1 for path in TARGET.rglob("*") if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES) if TARGET.exists() else 0


def find_dataset_root(extracted: Path) -> Path:
    candidates = [path.parent for path in extracted.rglob(MARKER_CLASS) if path.is_dir()]
    if not candidates:
        raise RuntimeError(f"Downloaded files do not contain the expected {MARKER_CLASS} class.")
    return min(candidates, key=lambda path: len(path.relative_to(extracted).parts))


def normalize_nested_copy() -> None:
    duplicate = next((path for path in TARGET.iterdir() if path.is_dir() and (path / MARKER_CLASS).is_dir()), None)
    normalized = TARGET / "disease_dataset"
    if duplicate and duplicate != normalized:
        if normalized.exists():
            shutil.rmtree(normalized)
        duplicate.rename(normalized)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the disease_dataset used by Agrinox Plant Lens.")
    parser.add_argument("--force", action="store_true", help="Download again even when training images already exist.")
    args = parser.parse_args()

    existing = image_count()
    if existing and not args.force:
        print(f"disease_dataset is already available with {existing:,} images at {TARGET}")
        return 0

    if args.force and TARGET.exists():
        shutil.rmtree(TARGET)

    with tempfile.TemporaryDirectory(prefix="agrinox-dataset-", dir=PROJECT_ROOT) as temporary:
        command = [sys.executable, "-m", "kaggle", "datasets", "download", DATASET, "--path", temporary, "--unzip"]
        try:
            subprocess.run(command, check=True)
            source = find_dataset_root(Path(temporary))
            shutil.move(str(source), str(TARGET))
            normalize_nested_copy()
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            print(f"Dataset download failed: {exc}. Configure Kaggle authentication and try again.", file=sys.stderr)
            return 1

    downloaded = image_count()
    if downloaded == 0:
        print(f"The download completed, but no images were found in {TARGET}.", file=sys.stderr)
        return 1
    print(f"disease_dataset is ready with {downloaded:,} images at {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
