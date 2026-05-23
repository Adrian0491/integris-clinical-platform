#!/usr/bin/env python3
"""
Generate an RS256 key pair for JWT signing.

Usage:
    python backend/scripts/generate_keys.py

Copy the printed values into .env as JWT_PRIVATE_KEY and JWT_PUBLIC_KEY.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    # Flatten to single-line for .env compatibility
    private_oneline = private_pem.replace("\n", "\\n")
    public_oneline  = public_pem.replace("\n", "\\n")

    print("# Paste these two lines into your .env file:\n")
    print(f"JWT_PRIVATE_KEY={private_oneline}")
    print(f"JWT_PUBLIC_KEY={public_oneline}")


if __name__ == "__main__":
    main()
