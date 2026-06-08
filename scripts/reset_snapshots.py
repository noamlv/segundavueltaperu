"""Reset electoral snapshot tables for a new monitoring phase.

This deletes ONPE/JNE historical captures from the configured database. Use only
when intentionally starting a fresh election monitoring window.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import _dsn_target_summary, _load_database_url, _with_required_ssl, get_conn, init_db


CHILD_TABLES = [
    "kpi_measures",
    "jje_detail",
    "actas_by_type",
    "jee_porcentaje",
    "onpe_totals",
    "onpe_mesas",
    "onpe_candidates",
]
TABLES = [*CHILD_TABLES, "scrape_runs"]


def _counts(conn) -> dict[str, int]:
    counts = {}
    for table in TABLES:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        counts[table] = int(row["n"] if row else 0)
    return counts


def _print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for table, count in counts.items():
        print(f"  {table}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset ONPE/JNE snapshot tables.")
    parser.add_argument(
        "--yes-reset-election-data",
        action="store_true",
        help="Required confirmation flag. Deletes all stored scraper snapshots.",
    )
    parser.add_argument(
        "--source",
        choices=["all", "onpe", "jne"],
        default="all",
        help="Which source to delete. Default: all.",
    )
    args = parser.parse_args()

    if not args.yes_reset_election_data:
        raise SystemExit("Refusing to delete data. Re-run with --yes-reset-election-data.")

    database_url = _with_required_ssl(_load_database_url())
    print(f"Destino de base de datos: {_dsn_target_summary(database_url)}")

    init_db()
    conn = get_conn()
    before = _counts(conn)
    _print_counts("Conteos antes del reinicio:", before)

    if args.source == "all":
        if conn.is_postgres:
            conn.execute("TRUNCATE TABLE scrape_runs RESTART IDENTITY CASCADE")
        else:
            for table in TABLES:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN (" + ",".join("?" for _ in TABLES) + ")", tuple(TABLES))
    else:
        run_rows = conn.execute("SELECT id FROM scrape_runs WHERE source = ?", (args.source,)).fetchall()
        run_ids = [int(row["id"]) for row in run_rows]
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            for table in CHILD_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE run_id IN ({placeholders})", tuple(run_ids))
            conn.execute(f"DELETE FROM scrape_runs WHERE id IN ({placeholders})", tuple(run_ids))

    conn.commit()
    after = _counts(conn)
    _print_counts("Conteos despues del reinicio:", after)
    conn.close()


if __name__ == "__main__":
    main()
