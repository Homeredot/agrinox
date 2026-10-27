from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import qrcode
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import TwoFactorChallenge, User
from app.services.notifications import configured as email_configured, send_notification

CHALLENGE_MINUTES = 10
MAX_ATTEMPTS = 5


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _code_hash(token: str, code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{token}:{code}".encode(), hashlib.sha256).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret: str, at_time: int | None = None) -> str:
    counter = int((at_time if at_time is not None else time.time()) // 30)
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    now = int(time.time())
    return any(hmac.compare_digest(totp_code(secret, now + shift * 30), code) for shift in (-1, 0, 1))


def provisioning_uri(secret: str, email: str) -> str:
    issuer = "Agrinox"
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def qr_data_url(uri: str) -> str:
    image = qrcode.make(uri)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def create_challenge(
    db: Session,
    user: User,
    *,
    purpose: str,
    method: str,
    pending_secret: str | None = None,
) -> tuple[str, TwoFactorChallenge, dict | None]:
    now = datetime.now(timezone.utc)
    for previous in db.scalars(select(TwoFactorChallenge).where(
        TwoFactorChallenge.user_id == user.id,
        TwoFactorChallenge.purpose == purpose,
        TwoFactorChallenge.consumed_at.is_(None),
    )):
        previous.consumed_at = now

    raw_token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}" if method == "email" else None
    challenge = TwoFactorChallenge(
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        purpose=purpose,
        method=method,
        code_hash=_code_hash(raw_token, code) if code else None,
        pending_secret_encrypted=encrypt_secret(pending_secret) if pending_secret else None,
        expires_at=now + timedelta(minutes=CHALLENGE_MINUTES),
    )
    db.add(challenge)
    db.flush()
    db.commit()
    delivery = None
    if code:
        delivery = send_notification(
            db,
            user,
            category="security_updates",
            event_key=f"two-factor:{purpose}:{challenge.id}",
            subject_en="Your Agrinox verification code",
            body_en=f"Your verification code is {code}. It expires in {CHALLENGE_MINUTES} minutes. Never share this code with anyone.",
            subject_rw="Kode yawe yo kwemeza kuri Agrinox",
            body_rw=f"Kode yawe yo kwemeza ni {code}. Irangira mu minota {CHALLENGE_MINUTES}. Ntuzigere uyiha undi muntu.",
            force=True,
            store_in_app=False,
        )
    return raw_token, challenge, delivery


def verify_challenge(db: Session, token: str, code: str, purpose: str) -> tuple[TwoFactorChallenge, str | None]:
    challenge = db.scalar(select(TwoFactorChallenge).where(
        TwoFactorChallenge.token_hash == _token_hash(token),
        TwoFactorChallenge.purpose == purpose,
    ))
    if not challenge or challenge.consumed_at is not None:
        raise HTTPException(status_code=401, detail="This verification request is invalid or already used")
    if _utc(challenge.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="The verification code has expired")
    if challenge.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many incorrect codes. Start again")

    secret = decrypt_secret(challenge.pending_secret_encrypted) if challenge.pending_secret_encrypted else None
    if challenge.method == "email":
        valid = bool(challenge.code_hash and hmac.compare_digest(challenge.code_hash, _code_hash(token, code)))
    else:
        if not secret:
            user = db.get(User, challenge.user_id)
            secret = decrypt_secret(user.totp_secret_encrypted) if user and user.totp_secret_encrypted else None
        valid = bool(secret and verify_totp(secret, code))
    if not valid:
        challenge.attempts += 1
        db.commit()
        if challenge.attempts >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many incorrect codes. Start again")
        raise HTTPException(status_code=401, detail="Incorrect verification code")
    challenge.consumed_at = datetime.now(timezone.utc)
    db.commit()
    return challenge, secret


def masked_email(email: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local[:2]}{'*' * max(2, len(local) - 2)}@{domain}"


def status_view(user: User) -> dict:
    return {
        "enabled": user.two_factor_method in {"email", "authenticator"},
        "method": user.two_factor_method,
        "enabled_at": user.two_factor_enabled_at.isoformat() if user.two_factor_enabled_at else None,
        "email_configured": email_configured(),
        "masked_email": masked_email(user.email),
    }
