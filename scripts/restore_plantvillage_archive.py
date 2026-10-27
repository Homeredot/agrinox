"""Restore and extract the PlantVillage archive stored as Git LFS parts."""

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARTS_PATTERN = "PlantVillage.zip.part*"
TARGET = PROJECT_ROOT / "PlantVillage"


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore PlantVillage from the Git LFS archive parts.")
    parser.add_argument("--force", action="store_true", help="Extract even when PlantVillage already exists.")
    args = parser.parse_args()

    if TARGET.exists() and any(TARGET.rglob("*.JPG")) and not args.force:
        print(f"PlantVillage is already available at {TARGET}")
        return 0

    parts = sorted((PROJECT_ROOT / "data").glob(PARTS_PATTERN))
    if not parts:
        raise SystemExit("No PlantVillage LFS archive parts were found. Run 'git lfs pull' first.")

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
        archive_path = Path(temporary.name)
        for part in parts:
            with part.open("rb") as source:
                shutil.copyfileobj(source, temporary)

    try:
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(PROJECT_ROOT)
    finally:
        archive_path.unlink(missing_ok=True)

    print(f"PlantVillage restored from {len(parts)} Git LFS parts at {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
