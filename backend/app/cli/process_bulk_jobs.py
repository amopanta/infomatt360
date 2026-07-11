"""Worker CLI para procesar lotes bulk encolados.

Uso:
    python -m app.cli.process_bulk_jobs --limit 50
    python -m app.cli.process_bulk_jobs --loop --sleep-seconds 5
"""

from __future__ import annotations

import argparse
import json
import time
from uuid import uuid4

from app.db.session import SessionLocal
from app.services.runtime_record_service import runtime_record_service


def process_once(limit: int, project_id: str | None = None, template_id: str | None = None, worker_id: str = "bulk-worker") -> dict[str, object]:
    with SessionLocal() as db:
        return runtime_record_service.process_queued_bulk_jobs(
            db,
            limit=limit,
            project_id=project_id,
            template_id=template_id,
            user_id="bulk-worker",
            worker_id=worker_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesa jobs bulk queued fuera del proceso web.")
    parser.add_argument("--limit", type=int, default=50, help="Maximo de jobs a tomar por ciclo. Default: 50.")
    parser.add_argument("--project-id", default=None, help="Filtra por proyecto.")
    parser.add_argument("--template-id", default=None, help="Filtra por plantilla.")
    parser.add_argument("--worker-id", default=None, help="Identificador del worker. Si no se envia, se genera uno.")
    parser.add_argument("--loop", action="store_true", help="Ejecuta ciclos continuos.")
    parser.add_argument("--sleep-seconds", type=float, default=5.0, help="Pausa entre ciclos en modo loop.")
    args = parser.parse_args()
    worker_id = args.worker_id or f"bulk-worker-{uuid4()}"

    while True:
        result = process_once(args.limit, project_id=args.project_id, template_id=args.template_id, worker_id=worker_id)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        if not args.loop:
            return 0
        time.sleep(max(args.sleep_seconds, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
