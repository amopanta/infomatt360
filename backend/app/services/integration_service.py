"""Interoperabilidad con plataformas de donantes (ActivityInfo, TolaData u otras).

La especificacion original describe un modulo que, "al segundo exacto de
consolidarse una aprobacion", mapea las variables del registro y las
inyecta via REST en la plataforma nativa del donante. No existen APIs
publicas y estables verificables para ActivityInfo/TolaData que se puedan
codificar con certeza sin una cuenta real (cada organizacion tiene su
propio esquema de base de datos/columnas en esas plataformas) -- por eso
este modulo es un **conector saliente generico y configurable**: URL base
+ credenciales + mapeo de campos, apuntable a cualquiera de las dos
plataformas (o a otra) segun como se configure `IntegrationSource` /
`IntegrationMap`.

Igual que WhatsApp/WAHA: un fallo o ausencia de configuracion nunca
bloquea ni revierte la aprobacion del registro. Se registra en
`IntegrationJob` (ledger inmutable) para poder diagnosticar y reintentar
manualmente.
"""

import ipaddress
import json
import logging
import socket
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_text, encrypt_text
from app.models.integrations import IntegrationJob, IntegrationMap, IntegrationSource
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.schemas.integrations import (
    IntegrationJobCreate,
    IntegrationJobRead,
    IntegrationMapCreate,
    IntegrationMapRead,
    IntegrationSourceCreate,
    IntegrationSourceRead,
)

logger = logging.getLogger(__name__)

PUSH_TIMEOUT_SECONDS = 15


class UnsafeIntegrationUrlError(ValueError):
    """`base_url` resuelve a un destino no permitido (host interno/privado)."""


def _assert_safe_outbound_url(url: str) -> None:
    """Bloquea SSRF: rechaza esquemas distintos de http(s) y cualquier host
    que resuelva a una IP privada, loopback, link-local (incluye el
    servicio de metadatos de nube 169.254.169.254) o reservada.

    `IntegrationSource.base_url` es texto libre configurado por cualquier
    usuario con `integrations.donor_sync.manage`, y el envio ocurre desde
    la red del propio backend -- sin esta validacion, un proyecto podria
    usarlo para hacer que el servidor consulte servicios internos en su
    nombre.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeIntegrationUrlError(f"Esquema o host invalido en base_url: {url!r}")

    try:
        resolved = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        # No se pudo resolver: no hay forma de confirmar que apunte a un
        # destino privado, y la peticion saliente fallara de todos modos
        # (se maneja como cualquier otro error de red mas abajo).
        return

    for family, _type, _proto, _canonname, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeIntegrationUrlError(f"base_url resuelve a una direccion no permitida: {ip}")


def source_to_read(row: IntegrationSource) -> IntegrationSourceRead:
    return IntegrationSourceRead(
        id=row.id, project_id=row.project_id, name=row.name, source_type=row.source_type,
        base_url=row.base_url, config_json=row.config_json, status=row.status,
        has_credentials=bool(row.credentials_encrypted),
    )


def map_to_read(row: IntegrationMap) -> IntegrationMapRead:
    return IntegrationMapRead(
        id=row.id, source_id=row.source_id, template_id=row.template_id, name=row.name,
        target_table=row.target_table, fields_json=row.fields_json, filters_json=row.filters_json, status=row.status,
    )


def job_to_read(row: IntegrationJob) -> IntegrationJobRead:
    return IntegrationJobRead(
        id=row.id, source_id=row.source_id, map_id=row.map_id, reference_record_id=row.reference_record_id,
        mode=row.mode, status=row.status, last_result=row.last_result,
    )


class IntegrationService:
    def create_source(self, db: Session, payload: IntegrationSourceCreate) -> IntegrationSourceRead:
        data = payload.model_dump(exclude={"credentials"})
        row = IntegrationSource(**data)
        if payload.credentials:
            row.credentials_encrypted = encrypt_text(payload.credentials)
        db.add(row)
        db.commit()
        db.refresh(row)
        return source_to_read(row)

    def list_sources(self, db: Session, project_id: str) -> list[IntegrationSourceRead]:
        rows = db.query(IntegrationSource).filter(IntegrationSource.project_id == project_id).order_by(IntegrationSource.created_at.desc()).all()
        return [source_to_read(row) for row in rows]

    def get_source(self, db: Session, source_id: str) -> IntegrationSource | None:
        return db.query(IntegrationSource).filter(IntegrationSource.id == source_id).first()

    def create_map(self, db: Session, payload: IntegrationMapCreate) -> IntegrationMapRead:
        row = IntegrationMap(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return map_to_read(row)

    def list_maps(self, db: Session, source_id: str) -> list[IntegrationMapRead]:
        rows = db.query(IntegrationMap).filter(IntegrationMap.source_id == source_id).order_by(IntegrationMap.created_at.desc()).all()
        return [map_to_read(row) for row in rows]

    def create_job(self, db: Session, payload: IntegrationJobCreate) -> IntegrationJobRead:
        row = IntegrationJob(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return job_to_read(row)

    def list_jobs(self, db: Session, source_id: str) -> list[IntegrationJobRead]:
        rows = db.query(IntegrationJob).filter(IntegrationJob.source_id == source_id).order_by(IntegrationJob.created_at.desc()).all()
        return [job_to_read(row) for row in rows]

    def push_approved_record(self, db: Session, record: RuntimeRecord) -> IntegrationJobRead | None:
        """Envia un registro aprobado a la plataforma de donante configurada.

        No-op silencioso si la plantilla no tiene un `IntegrationMap`
        activo -- la mayoria de formularios no reportan a un donante
        externo. Nunca lanza: un fallo de red o de configuracion se
        registra en el ledger, no interrumpe la aprobacion.
        """
        integration_map = db.query(IntegrationMap).filter(
            IntegrationMap.template_id == record.template_id,
            IntegrationMap.status == "active",
        ).first()
        if integration_map is None:
            return None

        source = self.get_source(db, integration_map.source_id)
        if source is None or source.status != "active" or not source.base_url:
            return self._record_job(
                db, integration_map, reference_record_id=record.id,
                status_value="failed", result="La fuente de integracion no esta activa o no tiene URL configurada",
            )

        try:
            field_mapping: dict[str, str] = json.loads(integration_map.fields_json)
        except json.JSONDecodeError:
            return self._record_job(
                db, integration_map, reference_record_id=record.id,
                status_value="failed", result="El mapeo de campos (fields_json) no es JSON valido",
            )

        values = {
            row.field_name: self._parse_value(row.field_value_json)
            for row in db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id == record.id).all()
        }
        payload = {target_key: values.get(source_field) for source_field, target_key in field_mapping.items()}

        try:
            _assert_safe_outbound_url(source.base_url)
        except UnsafeIntegrationUrlError as exc:
            return self._record_job(
                db, integration_map, reference_record_id=record.id, source_id=source.id,
                status_value="failed", result=str(exc)[:500],
            )

        headers = {"Content-Type": "application/json"}
        if source.credentials_encrypted:
            headers["Authorization"] = f"Bearer {decrypt_text(source.credentials_encrypted)}"

        try:
            response = httpx.post(
                source.base_url, json=payload, headers=headers,
                timeout=PUSH_TIMEOUT_SECONDS, follow_redirects=False,
            )
            if response.status_code >= 400:
                return self._record_job(
                    db, integration_map, reference_record_id=record.id, source_id=source.id,
                    status_value="failed", result=f"HTTP {response.status_code}: {response.text[:500]}",
                )
            return self._record_job(
                db, integration_map, reference_record_id=record.id, source_id=source.id,
                status_value="sent", result=response.text[:500],
            )
        except httpx.HTTPError as exc:
            logger.warning("Fallo al enviar registro %s a la fuente %s: %s", record.id, source.id, exc)
            return self._record_job(
                db, integration_map, reference_record_id=record.id, source_id=source.id,
                status_value="failed", result=str(exc)[:500],
            )

    def _record_job(
        self, db: Session, integration_map: IntegrationMap, *, reference_record_id: str,
        status_value: str, result: str, source_id: str | None = None,
    ) -> IntegrationJobRead:
        row = IntegrationJob(
            source_id=source_id or integration_map.source_id,
            map_id=integration_map.id,
            reference_record_id=reference_record_id,
            mode="record_push",
            status=status_value,
            last_result=result,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return job_to_read(row)

    def _parse_value(self, raw_json: str) -> object:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            return raw_json


integration_service = IntegrationService()
