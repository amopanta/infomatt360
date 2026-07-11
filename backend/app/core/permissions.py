"""Catalogo central de permisos de InfoMatt360.

Mantener los nombres en un solo lugar evita que backend, frontend, seeders y
documentacion terminen usando permisos diferentes para la misma capacidad.
"""

PROJECT_READ = "projects.read"
IDENTITY_USERS_MANAGE = "identity.users.manage"
ORGANIZATIONS_MANAGE = "organizations.manage"
ORGANIZATIONS_BRANDING_MANAGE = "organizations.branding.manage"
BACKUPS_MANAGE = "backups.manage"
ERP_MANAGE = "erp.manage"

RECORDS_READ = "records.read"
RECORDS_WRITE = "records.write"
RECORDS_REVIEW = "records.review"
RECORDS_COORDINATE = "records.coordinate"
RECORDS_APPROVE = "records.approve"

REPORTS_EXPORT = "reports.export"
GIS_READ = "gis.read"
BUILDER_WRITE = "builder.write"
MESSAGES_READ = "messages.read"
MESSAGES_WRITE = "messages.write"
INTEGRATIONS_API_KEYS_MANAGE = "integrations.api_keys.manage"
INTEGRATIONS_DONOR_SYNC_MANAGE = "integrations.donor_sync.manage"

BULK_ADMIN_PERMISSIONS = {INTEGRATIONS_API_KEYS_MANAGE, RECORDS_WRITE}

METRICS_VIEW_PERMISSIONS = {
    IDENTITY_USERS_MANAGE,
    INTEGRATIONS_API_KEYS_MANAGE,
    RECORDS_APPROVE,
    RECORDS_WRITE,
}

# Union de todos los permisos individuales del catalogo. Se usa para construir
# el rol administrador inicial durante el instalador de primer arranque.
ALL_PERMISSIONS = {
    PROJECT_READ,
    IDENTITY_USERS_MANAGE,
    ORGANIZATIONS_MANAGE,
    ORGANIZATIONS_BRANDING_MANAGE,
    BACKUPS_MANAGE,
    ERP_MANAGE,
    RECORDS_READ,
    RECORDS_WRITE,
    RECORDS_REVIEW,
    RECORDS_COORDINATE,
    RECORDS_APPROVE,
    REPORTS_EXPORT,
    GIS_READ,
    BUILDER_WRITE,
    MESSAGES_READ,
    MESSAGES_WRITE,
    INTEGRATIONS_API_KEYS_MANAGE,
    INTEGRATIONS_DONOR_SYNC_MANAGE,
}
