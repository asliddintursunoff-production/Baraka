"""Token encryption: Fernet key derived from DJANGO_SECRET_KEY with HKDF (no extra env var)."""

from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"bizpilot-google-tokens-v1",
        info=b"google-refresh-token",
    ).derive(settings.SECRET_KEY.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("token cannot be decrypted (secret key changed?)") from exc
