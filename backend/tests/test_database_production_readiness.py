from app.db.session import engine_options
from app.models.assignment import UserProjectAssignment


def test_non_sqlite_engine_uses_explicit_pool_options() -> None:
    options = engine_options("postgresql+psycopg2://user:pass@localhost:5432/db")

    assert options["pool_pre_ping"] is True
    assert options["pool_size"] >= 1
    assert options["max_overflow"] >= 0
    assert options["pool_timeout"] >= 1
    assert options["pool_recycle"] >= 60


def test_sqlite_engine_keeps_sqlite_connect_args_without_pool_options() -> None:
    options = engine_options("sqlite:///./local.db")

    assert options == {"connect_args": {"check_same_thread": False}}


def test_assignment_model_has_composite_authorization_indexes() -> None:
    indexes = {index.name: tuple(column.name for column in index.columns) for index in UserProjectAssignment.__table__.indexes}

    assert indexes["ix_assignments_user_project_status"] == ("user_id", "project_id", "status")
    assert indexes["ix_assignments_project_status_role"] == ("project_id", "status", "role_id")
