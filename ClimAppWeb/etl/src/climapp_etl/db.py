"""Conexión a PostgreSQL (Supabase) y registro de corridas en ingestion_runs."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg

WEB_ROOT = Path(__file__).resolve().parents[3]  # ClimAppWeb/
ENV_FILE = WEB_ROOT / ".env"


def database_url() -> str:
    """DATABASE_URL del entorno o, si no está, de ClimAppWeb/.env."""
    url = os.environ.get("DATABASE_URL")
    if not url and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "DATABASE_URL":
                url = value.strip().strip('"').strip("'")
    if not url:
        sys.exit(f"Falta DATABASE_URL (variable de entorno o {ENV_FILE}).")
    return url


def connect() -> psycopg.Connection:
    """Conexión en autocommit: cada bloque de datos usa conn.transaction() explícito,
    y el registro de la corrida queda guardado aunque los datos fallen."""
    return psycopg.connect(database_url(), autocommit=True)


class Run:
    """Corrida en curso; el job actualiza filas, estado y detalle."""

    def __init__(self, run_id: int):
        self.id = run_id
        self.filas = 0
        self.estado = "ok"
        self.detalle: list[str] = []

    def warn(self, message: str) -> None:
        self.estado = "parcial"
        self.detalle.append(message)


@contextmanager
def track_run(conn: psycopg.Connection, conector: str):
    """Registra la corrida en ingestion_runs: 'en_curso' al inicio y el resultado al final."""
    run_id = conn.execute(
        "insert into ingestion_runs (conector) values (%s) returning id", (conector,)
    ).fetchone()[0]
    run = Run(run_id)
    try:
        yield run
    except Exception as exc:
        run.estado = "error"
        run.detalle.append(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        conn.execute(
            "update ingestion_runs set finished_at = now(), estado = %s, filas = %s, detalle = %s"
            " where id = %s",
            (run.estado, run.filas, "\n".join(run.detalle)[:4000] or None, run.id),
        )


def last_success(conn: psycopg.Connection, conector: str):
    """Inicio de la última corrida exitosa (ok o parcial) del conector, o None."""
    row = conn.execute(
        "select max(started_at) from ingestion_runs where conector = %s and estado in ('ok', 'parcial')",
        (conector,),
    ).fetchone()
    return row[0]
