"""Metricas HTTP livianas en memoria para operacion inicial."""

from __future__ import annotations

import time
from threading import Lock

MAX_LATENCY_SAMPLES = 1000


class MetricsService:
    def __init__(self) -> None:
        self._started_at = time.time()
        self._lock = Lock()
        self._total_requests = 0
        self._total_duration_ms = 0.0
        self._max_duration_ms = 0.0
        self._duration_samples_ms: list[float] = []
        self._by_status_family: dict[str, int] = {}
        self._by_status_code: dict[str, int] = {}
        self._by_path: dict[str, dict[str, float | int | list[float]]] = {}
        self._bulk_jobs: dict[str, int] = {
            "worker_cycles": 0,
            "picked": 0,
            "processed": 0,
            "failed": 0,
            "recovered_stale": 0,
            "failed_stale": 0,
            "retries_scheduled": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
        }

    def record_http_request(self, path: str, status_code: int, duration_ms: float) -> None:
        family = f"{status_code // 100}xx"
        status_key = str(status_code)
        with self._lock:
            self._total_requests += 1
            self._total_duration_ms += duration_ms
            self._max_duration_ms = max(self._max_duration_ms, duration_ms)
            self._append_sample(self._duration_samples_ms, duration_ms)
            self._by_status_family[family] = self._by_status_family.get(family, 0) + 1
            self._by_status_code[status_key] = self._by_status_code.get(status_key, 0) + 1
            path_metrics = self._by_path.setdefault(
                path,
                {
                    "requests": 0,
                    "total_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "last_status_code": 0,
                    "duration_samples_ms": [],
                },
            )
            path_metrics["requests"] = int(path_metrics["requests"]) + 1
            path_metrics["total_duration_ms"] = float(path_metrics["total_duration_ms"]) + duration_ms
            path_metrics["max_duration_ms"] = max(float(path_metrics["max_duration_ms"]), duration_ms)
            path_metrics["last_status_code"] = status_code
            self._append_sample(path_metrics["duration_samples_ms"], duration_ms)  # type: ignore[arg-type]

    def record_bulk_worker_cycle(
        self,
        *,
        picked: int = 0,
        processed: int = 0,
        failed: int = 0,
        recovered_stale: int = 0,
        failed_stale: int = 0,
    ) -> None:
        with self._lock:
            self._bulk_jobs["worker_cycles"] += 1
            self._bulk_jobs["picked"] += picked
            self._bulk_jobs["processed"] += processed
            self._bulk_jobs["failed"] += failed
            self._bulk_jobs["recovered_stale"] += recovered_stale
            self._bulk_jobs["failed_stale"] += failed_stale

    def record_bulk_job_completed(self) -> None:
        with self._lock:
            self._bulk_jobs["completed_jobs"] += 1

    def record_bulk_job_failed(self) -> None:
        with self._lock:
            self._bulk_jobs["failed_jobs"] += 1

    def record_bulk_job_retry_scheduled(self) -> None:
        with self._lock:
            self._bulk_jobs["retries_scheduled"] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            average_ms = self._total_duration_ms / self._total_requests if self._total_requests else 0.0
            global_percentiles = self._percentiles(self._duration_samples_ms)
            paths: dict[str, dict[str, float | int | dict[str, float]]] = {}
            for path, values in self._by_path.items():
                requests = int(values["requests"])
                total_duration = float(values["total_duration_ms"])
                samples = values.get("duration_samples_ms", [])
                paths[path] = {
                    "requests": requests,
                    "avg_duration_ms": round(total_duration / requests, 2) if requests else 0.0,
                    "max_duration_ms": round(float(values["max_duration_ms"]), 2),
                    "latency_percentiles_ms": self._percentiles(samples if isinstance(samples, list) else []),
                    "last_status_code": int(values["last_status_code"]),
                }
            return {
                "uptime_seconds": round(time.time() - self._started_at, 2),
                "total_requests": self._total_requests,
                "avg_duration_ms": round(average_ms, 2),
                "max_duration_ms": round(self._max_duration_ms, 2),
                "latency_percentiles_ms": global_percentiles,
                "by_status_family": dict(sorted(self._by_status_family.items())),
                "by_status_code": dict(sorted(self._by_status_code.items())),
                "by_path": dict(sorted(paths.items())),
            }

    def bulk_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._bulk_jobs)

    def prometheus_text(self) -> str:
        """Exporta metricas en formato de texto compatible con Prometheus."""
        http = self.snapshot()
        bulk = self.bulk_snapshot()
        lines = [
            "# HELP infomatt360_http_requests_total Total de requests HTTP observados.",
            "# TYPE infomatt360_http_requests_total counter",
            f"infomatt360_http_requests_total {http['total_requests']}",
            "# HELP infomatt360_http_request_duration_ms Duracion HTTP agregada en milisegundos.",
            "# TYPE infomatt360_http_request_duration_ms gauge",
            f"infomatt360_http_request_duration_ms{self._labels(stat='avg')} {http['avg_duration_ms']}",
            f"infomatt360_http_request_duration_ms{self._labels(stat='max')} {http['max_duration_ms']}",
        ]
        percentiles = http.get("latency_percentiles_ms", {})
        if isinstance(percentiles, dict):
            for name, value in sorted(percentiles.items()):
                lines.append(f"infomatt360_http_request_duration_ms{self._labels(stat=str(name))} {value}")

        by_status_family = http.get("by_status_family", {})
        if isinstance(by_status_family, dict):
            for family, count in sorted(by_status_family.items()):
                lines.append(f"infomatt360_http_requests_by_status_family_total{self._labels(family=str(family))} {count}")

        by_status_code = http.get("by_status_code", {})
        if isinstance(by_status_code, dict):
            for code, count in sorted(by_status_code.items()):
                lines.append(f"infomatt360_http_requests_by_status_code_total{self._labels(code=str(code))} {count}")

        by_path = http.get("by_path", {})
        if isinstance(by_path, dict):
            lines.extend([
                "# HELP infomatt360_http_requests_by_path_total Total de requests por ruta.",
                "# TYPE infomatt360_http_requests_by_path_total counter",
            ])
            for path, values in sorted(by_path.items()):
                if not isinstance(values, dict):
                    continue
                labels = self._labels(path=str(path))
                lines.append(f"infomatt360_http_requests_by_path_total{labels} {values.get('requests', 0)}")
                lines.append(f"infomatt360_http_request_duration_by_path_ms{self._labels(path=str(path), stat='avg')} {values.get('avg_duration_ms', 0)}")
                lines.append(f"infomatt360_http_request_duration_by_path_ms{self._labels(path=str(path), stat='max')} {values.get('max_duration_ms', 0)}")
                path_percentiles = values.get("latency_percentiles_ms", {})
                if isinstance(path_percentiles, dict):
                    for name, value in sorted(path_percentiles.items()):
                        lines.append(f"infomatt360_http_request_duration_by_path_ms{self._labels(path=str(path), stat=str(name))} {value}")

        lines.extend([
            "# HELP infomatt360_bulk_jobs_total Contadores operativos del worker bulk.",
            "# TYPE infomatt360_bulk_jobs_total counter",
        ])
        for name, value in sorted(bulk.items()):
            lines.append(f"infomatt360_bulk_jobs_total{self._labels(metric=name)} {value}")
        lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._started_at = time.time()
            self._total_requests = 0
            self._total_duration_ms = 0.0
            self._max_duration_ms = 0.0
            self._duration_samples_ms.clear()
            self._by_status_family.clear()
            self._by_status_code.clear()
            self._by_path.clear()
            for key in self._bulk_jobs:
                self._bulk_jobs[key] = 0

    def _append_sample(self, samples: list[float], duration_ms: float) -> None:
        samples.append(duration_ms)
        if len(samples) > MAX_LATENCY_SAMPLES:
            del samples[0 : len(samples) - MAX_LATENCY_SAMPLES]

    def _percentiles(self, samples: list[float]) -> dict[str, float]:
        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        ordered = sorted(samples)
        return {
            "p50": round(self._percentile(ordered, 50), 2),
            "p95": round(self._percentile(ordered, 95), 2),
            "p99": round(self._percentile(ordered, 99), 2),
        }

    def _percentile(self, ordered_samples: list[float], percentile: int) -> float:
        if len(ordered_samples) == 1:
            return ordered_samples[0]
        rank = (percentile / 100) * (len(ordered_samples) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(ordered_samples) - 1)
        weight = rank - lower
        return ordered_samples[lower] * (1 - weight) + ordered_samples[upper] * weight

    def _labels(self, **labels: str) -> str:
        if not labels:
            return ""
        rendered = ",".join(f'{key}="{self._label_value(value)}"' for key, value in sorted(labels.items()))
        return "{" + rendered + "}"

    def _label_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


metrics_service = MetricsService()
