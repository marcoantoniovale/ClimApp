"""Aplica las migraciones de db/migrations (y opcionalmente las semillas de db/seeds).

Cada migración se aplica una sola vez, en orden de nombre, dentro de una transacción, y queda
registrada en la tabla schema_migrations. Las semillas son idempotentes y se aplican siempre
que se pide --seed.

La conexión se toma de la variable DATABASE_URL o del archivo ClimAppWeb/.env.

Uso:
  python scripts/migrate.py            # migraciones pendientes
  python scripts/migrate.py --seed     # migraciones pendientes + semillas
  python scripts/migrate.py --status   # solo muestra el estado
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

WEB_ROOT = Path(__file__).resolve().parents[2]  # ClimAppWeb/
MIGRATIONS = WEB_ROOT / "db" / "migrations"
SEEDS = WEB_ROOT / "db" / "seeds"
ENV_FILE = WEB_ROOT / ".env"

BOOTSTRAP = """
create table if not exists schema_migrations (
    nombre      text primary key,
    aplicada_at timestamptz not null default now()
);
alter table schema_migrations enable row level security;
"""


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "DATABASE_URL":
                url = value.strip().strip('"').strip("'")
    if not url:
        sys.exit(f"Falta DATABASE_URL (variable de entorno o {ENV_FILE}).")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", action="store_true", help="aplicar también db/seeds/*.sql")
    parser.add_argument("--status", action="store_true", help="solo mostrar el estado")
    args = parser.parse_args()

    with psycopg.connect(database_url()) as conn:
        conn.execute(BOOTSTRAP)
        conn.commit()
        applied = {row[0] for row in conn.execute("select nombre from schema_migrations")}
        pending = [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name not in applied]

        print(f"Aplicadas: {len(applied)}  Pendientes: {len(pending)}")
        if args.status:
            for p in pending:
                print(f"  pendiente: {p.name}")
            return

        for path in pending:
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("insert into schema_migrations (nombre) values (%s)", (path.name,))
            print(f"  aplicada: {path.name}")

        if args.seed:
            for path in sorted(SEEDS.glob("*.sql")):
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                print(f"  semilla: {path.name}")

        counts = conn.execute(
            "select (select count(*) from locations), (select count(*) from stations)").fetchone()
        print(f"locations: {counts[0]}  stations: {counts[1]}")


if __name__ == "__main__":
    main()
