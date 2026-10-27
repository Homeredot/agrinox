from io import BytesIO
from pathlib import Path
import secrets

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError


PROFILE_UPLOAD_ROOT = Path("uploads/profile")
MAX_PROFILE_IMAGE_BYTES = 4 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def save_profile_image(user_id: int, content: bytes, content_type: str | None) -> str:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPG, PNG, or WebP profile image")
    if not content or len(content) > MAX_PROFILE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Profile image must be smaller than 4 MB")
    try:
        source = Image.open(BytesIO(content))
        source.verify()
        source = Image.open(BytesIO(content))
        source = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="The selected file is not a valid image") from None

    source.thumbnail((900, 900), Image.Resampling.LANCZOS)
    PROFILE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    destination = PROFILE_UPLOAD_ROOT / f"user-{user_id}-{secrets.token_hex(8)}.jpg"
    source.save(destination, format="JPEG", quality=88, optimize=True)
    return str(destination)


def profile_image_file(path_value: str | None) -> Path:
    if not path_value:
        raise HTTPException(status_code=404, detail="Profile photo not found")
    path = Path(path_value).resolve()
    root = PROFILE_UPLOAD_ROOT.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Profile photo not found")
    return path


def delete_profile_image(path_value: str | None) -> None:
    if not path_value:
        return
    try:
        path = Path(path_value).resolve()
        root = PROFILE_UPLOAD_ROOT.resolve()
        if root in path.parents and path.is_file():
            path.unlink()
    except OSError:
        pass
