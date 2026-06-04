"""Fast database preflight for deployment and GitHub Actions."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import _dsn_target_summary, _load_database_url, _with_required_ssl, get_conn


def main() -> None:
    database_url = _with_required_ssl(_load_database_url())
    print(f"Destino de base de datos: {_dsn_target_summary(database_url)}")

    conn = get_conn()
    if conn.is_postgres:
        row = conn.execute(
            "SELECT current_user AS current_user, current_database() AS current_database"
        ).fetchone()
        print(
            "Conexión Postgres OK: "
            f"user={row['current_user']}, database={row['current_database']}"
        )
    else:
        print("Conexión SQLite local OK.")
    conn.close()


if __name__ == "__main__":
    main()
