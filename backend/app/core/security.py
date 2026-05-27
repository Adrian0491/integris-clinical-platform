"""
Password hashing and RSA key management.
"""
from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings

# bcrypt context — auto-upgrades hashes on verify
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

# ---------------------------------------------------------------------------
# RSA key loading / auto-generation
# ---------------------------------------------------------------------------

_private_key_pem: str | None = None
_public_key_pem:  str | None = None


def _generate_dev_keypair() -> tuple[str, str]:
    """Generate a temporary RSA-2048 key pair (development only)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv_pem, pub_pem


def get_private_key_pem() -> str:
    """Return the RSA private key PEM string, generating one for dev if absent."""
    global _private_key_pem, _public_key_pem
    if _private_key_pem:
        return _private_key_pem

    settings = get_settings()
    priv = settings.get_private_key()
    pub  = settings.get_public_key()

    if priv and pub:
        _private_key_pem = priv
        _public_key_pem  = pub
    else:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "JWT_PRIVATE_KEY and JWT_PUBLIC_KEY must be set in production."
            )
        import warnings
        warnings.warn(
            "No JWT keys configured — generating a temporary RSA key pair. "
            "Run backend/scripts/generate_keys.py and set the keys in .env.",
            UserWarning,
            stacklevel=2,
        )
        _private_key_pem, _public_key_pem = _generate_dev_keypair()

    return _private_key_pem


def get_public_key_pem() -> str:
    """Return the RSA public key PEM string."""
    get_private_key_pem()   # ensures both keys are loaded/generated
    return _public_key_pem  # type: ignore[return-value]
