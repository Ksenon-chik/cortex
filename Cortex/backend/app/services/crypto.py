from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.api_key_encryption_key.encode("utf-8"))


def encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str) -> str:
    # Backward-compatible fallback for legacy plaintext rows created before
    # at-rest encryption was introduced.
    if not value.startswith("gAAAA"):
        return value
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as err:
        raise ValueError("Stored API key cannot be decrypted") from err
