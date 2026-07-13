"""Worker CLI para disparar tareas programadas (hoy: respaldos recurrentes).

Sin este worker, `ScheduledTask` solo guardaba la configuracion pero nadie
la ejecutaba -- ver `scheduler_service.run_due_tasks()`.

Uso:
    python -m app.cli.run_scheduled_tasks
    python -m app.cli.run_scheduled_tasks --loop --sleep-seconds 60
"""

from __future__ import annotations

import argparse
import json
import time

from app.db.session import SessionLocal
from app.services.scheduler_service import scheduler_service


def run_once(limit: int) -> dict[str, int]:
    with SessionLocal() as db:
        return scheduler_service.run_due_tasks(db, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta las tareas programadas (ScheduledTask) que ya vencieron.")
    parser.add_argument("--limit", type=int, default=50, help="Maximo de tareas a procesar por ciclo. Default: 50.")
    parser.add_argument("--loop", action="store_true", help="Ejecuta ciclos continuos.")
    parser.add_argument("--sleep-seconds", type=float, default=60.0, help="Pausa entre ciclos en modo loop. Default: 60.")
    args = parser.parse_args()

    while True:
        result = run_once(args.limit)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        if not args.loop:
            return 0
        time.sleep(max(args.sleep_seconds, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
