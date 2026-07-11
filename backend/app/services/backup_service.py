"""Respaldo de base de datos disparado desde la web.

Soporta SQLite (copia directa del archivo, util en desarrollo/demo) y
PostgreSQL (via `pg_dump`, requerido en produccion). El comando nunca se
arma con `shell=True` para evitar inyeccion; la contrasena se pasa por la
variable de entorno `PGPASSWORD`, nunca como argumento de linea de comandos.
"""

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.backup import BackupJob
from app.schemas.backup import BackupJobRead


def _to_read(row: BackupJob) -> BackupJobRead:
    return BackupJobRead(
        id=row.id,
        project_id=row.project_id,
        storage_profile_id=row.storage_profile_id,
        status=row.status,
        file_path=row.file_path,
        size_bytes=row.size_bytes,
        triggered_by=row.triggered_by,
        error=row.error,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class BackupService:
    def run_backup(self, db: Session, project_id: str, triggered_by: str | None, storage_profile_id: str | None = None) -> BackupJobRead:
        job = BackupJob(project_id=project_id, storage_profile_id=storage_profile_id, status="running", triggered_by=triggered_by)
        db.add(job)
        db.commit()
        db.refresh(job)

        backup_dir = Path(settings.backup_directory)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now().strftime("%Y%m%d%H%M%S")

        try:
            if settings.database_url.startswith("sqlite"):
                file_path = self._backup_sqlite(backup_dir, timestamp)
            else:
                file_path = self._backup_postgres(backup_dir, timestamp)
            job.status = "completed"
            job.file_path = str(file_path)
            job.size_bytes = file_path.stat().st_size
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)[:4000]
        job.finished_at = utc_now()
        db.commit()
        db.refresh(job)
        return _to_read(job)

    def list_backups(self, db: Session, project_id: str) -> list[BackupJobRead]:
        rows = db.query(BackupJob).filter(BackupJob.project_id == project_id).order_by(BackupJob.started_at.desc()).all()
        return [_to_read(row) for row in rows]

    def _backup_sqlite(self, backup_dir: Path, timestamp: str) -> Path:
        source_path = Path(self._sqlite_path(settings.database_url))
        if not source_path.exists():
            raise FileNotFoundError(f"No se encontro el archivo SQLite: {source_path}")
        destination = backup_dir / f"backup-{timestamp}-{source_path.name}"
        shutil.copyfile(source_path, destination)
        return destination

    def _backup_postgres(self, backup_dir: Path, timestamp: str) -> Path:
        if shutil.which("pg_dump") is None:
            raise RuntimeError("pg_dump no esta disponible en el PATH del servidor")
        connection = self._parse_postgres_url(settings.database_url)
        destination = backup_dir / f"backup-{timestamp}-{connection['dbname']}.dump"
        command = [
            "pg_dump",
            "--host", connection["host"],
            "--port", str(connection["port"]),
            "--username", connection["user"],
            "--format", "custom",
            "--file", str(destination),
            connection["dbname"],
        ]
        env = {**os.environ, "PGPASSWORD": connection["password"]}
        subprocess.run(command, check=True, env=env, capture_output=True, timeout=600)
        return destination

    def _sqlite_path(self, database_url: str) -> str:
        return database_url.split("///", maxsplit=1)[-1]

    def _parse_postgres_url(self, database_url: str) -> dict[str, object]:
        normalized = database_url.replace("postgresql+psycopg2://", "postgresql://")
        parsed = urlparse(normalized)
        if not parsed.username or parsed.password is None:
            raise ValueError("DATABASE_URL debe incluir usuario y clave para pg_dump")
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "user": unquote(parsed.username),
            "password": unquote(parsed.password),
            "dbname": parsed.path.lstrip("/"),
        }


backup_service = BackupService()
