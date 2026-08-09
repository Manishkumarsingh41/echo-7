"""
ECHO-7 Stable Key Management
Paper Section 3.4: Encrypted Delta Sync - Key Management

Stable, user-controlled encryption key management.
Key is derived from user password or stored securely.
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional


class StableKeyManager:
    """
    Stable encryption key management for ECHO-7.
    Key is derived from user password or stored in secure location.
    """

    def __init__(self, key_file: str = "data/keys/echo_master.key"):
        self.key_file = key_file
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        self._key = None
        self._cipher = None

    def get_or_create_key(self, password: Optional[str] = None) -> bytes:
        """
        Get existing key or create one with password.

        Priority:
        1. If key file exists → load it
        2. If password provided → derive key from password
        3. Generate new key and save it
        """
        # 1. Try loading existing key
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                self._key = f.read()
                self._cipher = Fernet(self._key)
                return self._key

        # 2. Derive from password if provided
        if password:
            self._key = self._derive_key_from_password(password)
            self._save_key(self._key)
            self._cipher = Fernet(self._key)
            return self._key

        # 3. Generate new key
        self._key = Fernet.generate_key()
        self._save_key(self._key)
        self._cipher = Fernet(self._key)
        return self._key

    def _derive_key_from_password(self, password: str) -> bytes:
        """Derive encryption key from user password"""
        salt = b'echo_7_salt_12345678'  # In production: store salt separately

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def _save_key(self, key: bytes) -> None:
        """Save key to secure file"""
        with open(self.key_file, 'wb') as f:
            f.write(key)
        # Set restrictive permissions (Windows: owner-only)
        try:
            os.chmod(self.key_file, 0o600)
        except:
            pass  # Windows may not support chmod

    def get_cipher(self) -> Fernet:
        """Get Fernet cipher instance"""
        if self._cipher is None:
            self.get_or_create_key()
        return self._cipher

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data"""
        return self.get_cipher().encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data"""
        return self.get_cipher().decrypt(data)

    def export_public_key_info(self) -> str:
        """Export key fingerprint for device pairing"""
        key = self.get_or_create_key()
        fingerprint = hashlib.sha256(key).hexdigest()[:16]
        return f"ECHO-7 Key Fingerprint: {fingerprint}"

    def has_key(self) -> bool:
        """Check if key exists"""
        return os.path.exists(self.key_file)

    def delete_key(self) -> None:
        """Delete key file (caution: data will be unreadable)"""
        if os.path.exists(self.key_file):
            os.remove(self.key_file)
            self._key = None
            self._cipher = None


# Singleton instance
_key_manager = None


def get_key_manager() -> StableKeyManager:
    """Get singleton key manager instance"""
    global _key_manager
    if _key_manager is None:
        _key_manager = StableKeyManager()
    return _key_manager