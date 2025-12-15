import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend


# CRITICAL: Move this to environment variable in production!
SECRET_KEY = "74bd7aa5fe7cebe852e09b2e5a6496ddd22d47640110fda654b1cf4ff53a4e1c05ef3e1866f6db6d9c23188143af1214"  # Must match the Node.js SECRET_KEY

# please use salt....


def decrypt(encrypted_data: str, secret: str) -> str:
    """Decrypt AES-256-GCM encrypted data"""
    try:
        # Split the encrypted data: iv:authTag:encrypted
        parts = encrypted_data.split(':')
        if len(parts) != 3:
            raise ValueError("Invalid encrypted data format")

        iv_hex, auth_tag_hex, encrypted_hex = parts

        # Convert from hex
        iv = bytes.fromhex(iv_hex)
        auth_tag = bytes.fromhex(auth_tag_hex)
        encrypted = bytes.fromhex(encrypted_hex)

        # Derive key using Scrypt (matching Node.js scryptSync)
        kdf = Scrypt(
            salt=b'salt',  # Must match Node.js salt
            length=32,
            n=2**14,
            r=8,
            p=1,
            backend=default_backend()
        )
        key = kdf.derive(secret.encode())

        # Decrypt using AES-256-GCM
        aesgcm = AESGCM(key)
        # Combine encrypted data with auth tag for decryption
        ciphertext = encrypted + auth_tag
        decrypted = aesgcm.decrypt(iv, ciphertext, None)

        return decrypted.decode('utf8')
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


