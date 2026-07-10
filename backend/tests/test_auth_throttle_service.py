from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.models.identity import AuthThrottle
from app.services.auth_throttle_service import auth_throttle_service


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int | str] = {}

    def exists(self, key: str) -> bool:
        return key in self.values

    def incr(self, key: str) -> int:
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value

    def expire(self, key: str, _seconds: int) -> None:
        self.values.setdefault(key, 0)

    def setex(self, key: str, _seconds: int, value: str) -> None:
        self.values[key] = value

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)


def _session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_auth_throttle_redis_backend_without_url_uses_database() -> None:
    original_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    settings.auth_throttle_backend = "redis"
    settings.redis_url = ""
    engine, sessions = _session_factory()
    try:
        with sessions() as db:
            assert auth_throttle_service.record_attempt(
                db,
                "login-ip",
                "203.0.113.80",
                maximum=1,
                window_minutes=15,
                block_minutes=15,
            )
            assert db.query(AuthThrottle).count() == 1
    finally:
        settings.auth_throttle_backend = original_backend
        settings.redis_url = original_redis_url
        auth_throttle_service.reset_redis_client()
        Base.metadata.drop_all(bind=engine)


def test_auth_throttle_redis_backend_blocks_and_records_snapshot() -> None:
    original_backend = settings.auth_throttle_backend
    original_redis_url = settings.redis_url
    original_prefix = settings.auth_throttle_redis_prefix
    settings.auth_throttle_backend = "redis"
    settings.redis_url = "redis://example.test:6379/0"
    settings.auth_throttle_redis_prefix = "test:auth-throttle"
    auth_throttle_service._redis_client = FakeRedis()
    engine, sessions = _session_factory()
    try:
        with sessions() as db:
            assert auth_throttle_service.record_attempt(
                db,
                "login-ip",
                "203.0.113.81",
                maximum=2,
                window_minutes=15,
                block_minutes=15,
            )
            assert auth_throttle_service.record_attempt(
                db,
                "login-ip",
                "203.0.113.81",
                maximum=2,
                window_minutes=15,
                block_minutes=15,
            )
            assert not auth_throttle_service.record_attempt(
                db,
                "login-ip",
                "203.0.113.81",
                maximum=2,
                window_minutes=15,
                block_minutes=15,
            )
            assert auth_throttle_service.is_blocked(db, "login-ip", "203.0.113.81")
            snapshot = db.query(AuthThrottle).one()
            assert snapshot.attempt_count == 3
            assert snapshot.blocked_until is not None
            auth_throttle_service.clear(db, "login-ip", "203.0.113.81")
            assert not auth_throttle_service.is_blocked(db, "login-ip", "203.0.113.81")
            assert db.query(AuthThrottle).count() == 0
    finally:
        settings.auth_throttle_backend = original_backend
        settings.redis_url = original_redis_url
        settings.auth_throttle_redis_prefix = original_prefix
        auth_throttle_service.reset_redis_client()
        Base.metadata.drop_all(bind=engine)
