from app.core.permissions import (
    BULK_ADMIN_PERMISSIONS,
    IDENTITY_USERS_MANAGE,
    INTEGRATIONS_API_KEYS_MANAGE,
    METRICS_VIEW_PERMISSIONS,
    RECORDS_APPROVE,
    RECORDS_WRITE,
)


def test_permission_catalog_keeps_stable_permission_names() -> None:
    assert IDENTITY_USERS_MANAGE == "identity.users.manage"
    assert INTEGRATIONS_API_KEYS_MANAGE == "integrations.api_keys.manage"
    assert RECORDS_WRITE == "records.write"
    assert RECORDS_APPROVE == "records.approve"


def test_permission_catalog_groups_operational_permissions() -> None:
    assert BULK_ADMIN_PERMISSIONS == {INTEGRATIONS_API_KEYS_MANAGE, RECORDS_WRITE}
    assert {
        IDENTITY_USERS_MANAGE,
        INTEGRATIONS_API_KEYS_MANAGE,
        RECORDS_APPROVE,
        RECORDS_WRITE,
    }.issubset(METRICS_VIEW_PERMISSIONS)
