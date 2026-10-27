"""Download and extract the PlantVillage dataset from Kaggle."""

import argparse
import subprocess
import sys
from pathlib import Path


DATASET = "emmarex/plantdisease"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = PROJECT_ROOT / "PlantVillage"


def image_count() -> int:
    if not TARGET.exists():
        return 0
    return sum(1 for path in TARGET.rglob("*") if path.suffix.casefold() in {".jpg", ".jpeg", ".png"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PlantVillage from Kaggle into this Agrinox checkout.")
    parser.add_argument("--force", action="store_true", help="Download again even when PlantVillage images already exist.")
    args = parser.parse_args()

    existing = image_count()
    if existing and not args.force:
        print(f"PlantVillage is already available with {existing:,} images at {TARGET}")
        return 0

    command = [
        sys.executable, "-m", "kaggle", "datasets", "download", DATASET,
        "--path", str(PROJECT_ROOT), "--unzip",
    ]
    if args.force:
        command.append("--force")

    print(f"Downloading https://www.kaggle.com/datasets/{DATASET} ...")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        print("Download failed. Install requirements-data.txt and configure Kaggle authentication.", file=sys.stderr)
        return 1

    downloaded = image_count()
    if downloaded == 0:
        print(f"The download completed, but no images were found in {TARGET}.", file=sys.stderr)
        return 1
    print(f"PlantVillage is ready with {downloaded:,} images at {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
