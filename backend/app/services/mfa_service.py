import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.identity import User


class MfaService:
    def _fernet(self) -> Fernet:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
        return Fernet(key)

    def new_secret(self) -> str:
        return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

    def encrypt_secret(self, secret: str) -> str:
        return self._fernet().encrypt(secret.encode("ascii")).decode("ascii")

    def decrypt_secret(self, encrypted: str) -> str:
        try:
            return self._fernet().decrypt(encrypted.encode("ascii")).decode("ascii")
        except InvalidToken as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No fue posible leer la configuracion MFA") from exc

    def provisioning_uri(self, email: str, secret: str) -> str:
        label = quote(f"InfoMatt360:{email}")
        query = urlencode({"secret": secret, "issuer": "InfoMatt360", "algorithm": "SHA1", "digits": 6, "period": 30})
        return f"otpauth://totp/{label}?{query}"

    def verify_totp(self, user: User, code: str, *, consume: bool = True) -> bool:
        if not user.mfa_secret_encrypted or not code.isdigit() or len(code) != 6:
            return False
        secret = self.decrypt_secret(user.mfa_secret_encrypted)
        current = int(time.time()) // 30
        for counter in range(current - 1, current + 2):
            if hmac.compare_digest(self._totp(secret, counter), code):
                if consume and user.mfa_last_counter is not None and counter <= user.mfa_last_counter:
                    return False
                if consume:
                    user.mfa_last_counter = counter
                return True
        return False

    def generate_recovery_codes(self) -> tuple[list[str], str]:
        codes = [f"{secrets.token_hex(4)}-{secrets.token_hex(2)}" for _ in range(8)]
        hashes = [self._recovery_hash(code) for code in codes]
        return codes, json.dumps(hashes)

    def consume_recovery_code(self, user: User, code: str) -> bool:
        hashes = json.loads(user.mfa_recovery_hashes or "[]")
        candidate = self._recovery_hash(code.strip().lower())
        for index, stored in enumerate(hashes):
            if hmac.compare_digest(candidate, stored):
                hashes.pop(index)
                user.mfa_recovery_hashes = json.dumps(hashes)
                return True
        return False

    def _recovery_hash(self, code: str) -> str:
        return hmac.new(settings.secret_key.encode("utf-8"), code.lower().encode("utf-8"), hashlib.sha256).hexdigest()

    def _totp(self, secret: str, counter: int) -> str:
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(padded, casefold=True)
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        return f"{value:06d}"


mfa_service = MfaService()
