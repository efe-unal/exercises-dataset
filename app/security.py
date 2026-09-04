"""Password hashing and session tokens.

Both use the standard library: ``hashlib.scrypt`` for passwords (memory-hard,
so a stolen database resists offline cracking) and ``secrets`` for tokens.
That keeps the dependency list short, which matters for a project one person
maintains.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

# scrypt parameters. n=2**15 costs roughly 100ms and 32MB per hash on a small
# server — slow enough to blunt offline attacks, fast enough for a login.
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
# OpenSSL caps scrypt's memory at 32MB by default, which these parameters sit
# exactly on top of; the limit has to be raised explicitly or hashing fails.
_MAXMEM = 128 * _SCRYPT_N * _SCRYPT_R * 2

TOKEN_BYTES = 32
TOKEN_TTL = timedelta(days=30)

MIN_PASSWORD_LENGTH = 8


class WeakPassword(ValueError):
    """Raised when a password fails the minimum policy."""


def validate_password(password: str) -> None:
    """Reject passwords that are trivially weak.

    Deliberately minimal: length is the property that actually correlates with
    strength, and composition rules mostly push people toward 'Passw0rd!'.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )


def hash_password(password: str) -> str:
    """Return ``scrypt$n$r$p$salt$key``, all parameters included.

    Storing the parameters alongside the hash means they can be raised later
    without invalidating existing passwords.
    """
    validate_password(password)
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                         r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_BYTES,
                         maxmem=_MAXMEM)
    return "$".join(["scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P),
                     salt.hex(), key.hex()])


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against a stored hash, in constant time."""
    try:
        scheme, n, r, p, salt_hex, key_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(key_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
            maxmem=128 * int(n) * int(r) * 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def generate_token() -> tuple[str, str]:
    """Return ``(token, token_hash)``.

    The caller hands the token to the client and stores only the hash, so the
    database never holds anything that can be replayed. A plain SHA-256 is
    right here: the token is already 256 bits of entropy, so there is nothing
    for a slow hash to protect against.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    """Emails are matched case-insensitively; addresses are not case-sensitive
    in practice and treating them as such creates duplicate accounts."""
    return email.strip().lower()
