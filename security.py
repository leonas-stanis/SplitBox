import hashlib
import hmac
import os
import secrets
from pathlib import Path

SECRET_FILE = Path(__file__).with_name(".secret_key")
PBKDF2_ITERATIONS = 240_000


def get_secret_key() -> str:
    """Read SECRET_KEY, or create a local development secret once."""
    from_environment = os.environ.get("SECRET_KEY")
    if from_environment:
        return from_environment

    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()

    key = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(key, encoding="utf-8")
    SECRET_FILE.chmod(0o600)
    return key


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), password_hash)
