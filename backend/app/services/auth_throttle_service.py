import hashlib
import hmac
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.identity import AuthThrottle


class AuthThrottleService:
    def __init__(self) -> None:
        self._redis_client: Any | None = None

    def _hash_identifier(self, identifier: str) -> str:
        return hmac.new(
            settings.secret_key.encode("utf-8"),
            identifier.strip().lower().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def is_blocked(self, db: Session, action: str, identifier: str) -> bool:
        if self._uses_redis():
            return self._redis_is_blocked(action, identifier)
        row = self._find(db, action, identifier)
        return bool(row and row.blocked_until and row.blocked_until > utc_now())

    def record_attempt(
        self,
        db: Session,
        action: str,
        identifier: str,
        *,
        maximum: int,
        window_minutes: int,
        block_minutes: int,
    ) -> bool:
        if self._uses_redis():
            return self._record_redis_attempt(
                db,
                action,
                identifier,
                maximum=maximum,
                window_minutes=window_minutes,
                block_minutes=block_minutes,
            )
        now = utc_now()
        row = self._find(db, action, identifier)
        if row is None:
            row = AuthThrottle(
                action=action,
                identifier_hash=self._hash_identifier(identifier),
                attempt_count=0,
                window_started_at=now,
            )
            db.add(row)
        elif row.blocked_until and row.blocked_until > now:
            return False
        elif row.window_started_at + timedelta(minutes=window_minutes) <= now:
            row.attempt_count = 0
            row.window_started_at = now
            row.blocked_until = None

        row.attempt_count += 1
        row.updated_at = now
        allowed = row.attempt_count <= maximum
        if not allowed:
            row.blocked_until = now + timedelta(minutes=block_minutes)
        db.commit()
        return allowed

    def clear(self, db: Session, action: str, identifier: str) -> None:
        if self._uses_redis():
            client = self._redis()
            base_key = self._redis_base_key(action, identifier)
            client.delete(f"{base_key}:count", f"{base_key}:blocked")
        row = self._find(db, action, identifier)
        if row:
            db.delete(row)
            db.commit()

    def _find(self, db: Session, action: str, identifier: str) -> AuthThrottle | None:
        return db.query(AuthThrottle).filter(
            AuthThrottle.action == action,
            AuthThrottle.identifier_hash == self._hash_identifier(identifier),
        ).first()

    def _uses_redis(self) -> bool:
        return settings.auth_throttle_backend.lower().strip() == "redis" and bool(settings.redis_url)

    def _redis(self) -> Any:
        if self._redis_client is None:
            try:
                from redis import Redis
            except ImportError as exc:  # pragma: no cover - depende de entorno productivo
                raise RuntimeError("Instale redis para usar AUTH_THROTTLE_BACKEND=redis") from exc
            self._redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis_client

    def reset_redis_client(self) -> None:
        self._redis_client = None

    def _redis_base_key(self, action: str, identifier: str) -> str:
        prefix = settings.auth_throttle_redis_prefix.rstrip(":")
        return f"{prefix}:{action}:{self._hash_identifier(identifier)}"

    def _redis_is_blocked(self, action: str, identifier: str) -> bool:
        return bool(self._redis().exists(f"{self._redis_base_key(action, identifier)}:blocked"))

    def _record_redis_attempt(
        self,
        db: Session,
        action: str,
        identifier: str,
        *,
        maximum: int,
        window_minutes: int,
        block_minutes: int,
    ) -> bool:
        client = self._redis()
        base_key = self._redis_base_key(action, identifier)
        blocked_key = f"{base_key}:blocked"
        if client.exists(blocked_key):
            return False

        count_key = f"{base_key}:count"
        attempt_count = int(client.incr(count_key))
        if attempt_count == 1:
            client.expire(count_key, max(window_minutes * 60, 1))

        allowed = attempt_count <= maximum
        if not allowed:
            client.setex(blocked_key, max(block_minutes * 60, 1), "1")
            self._record_block_snapshot(db, action, identifier, attempt_count, block_minutes)
        return allowed

    def _record_block_snapshot(self, db: Session, action: str, identifier: str, attempt_count: int, block_minutes: int) -> None:
        now = utc_now()
        row = self._find(db, action, identifier)
        if row is None:
            row = AuthThrottle(
                action=action,
                identifier_hash=self._hash_identifier(identifier),
                attempt_count=attempt_count,
                window_started_at=now,
            )
            db.add(row)
        row.attempt_count = attempt_count
        row.blocked_until = now + timedelta(minutes=block_minutes)
        row.updated_at = now
        db.commit()


auth_throttle_service = AuthThrottleService()
