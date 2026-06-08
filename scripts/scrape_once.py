"""Run both electoral scrapers once and persist results.

Uses SQLite locally by default. In production, set DATABASE_URL to a
Supabase/Postgres connection string and the same database functions will write
there.
"""

from __future__ import annotations

import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import save_run, save_run_onpe
from onpe_scraper import scrape as scrape_onpe
from onpe_scraper import serialize
from pbi_scraper import PowerBIScraper


JNE_DEFAULT_URL = "https://web.jne.gob.pe/reporteactasobservadas/"


def _pbi_raw_payload(results: dict) -> dict:
    raw = {"_meta": {"timestamp": datetime.now().isoformat()}, "tables": [], "measures": []}
    for table in results.get("tables", []):
        descriptor = table.get("descriptor", {})
        raw["tables"].append(
            {
                "name": descriptor.get("name", ""),
                "columns": [col["name"] for col in table.get("columns", [])],
                "rows": table.get("rows", []),
            }
        )
    for measure in results.get("measures", []):
        descriptor = measure.get("descriptor", {})
        raw["measures"].append({"name": descriptor.get("name", ""), "value": measure.get("value")})
    return raw


async def run_onpe() -> None:
    print("Running ONPE scraper...")
    onpe_raw = await scrape_onpe()
    onpe_payload = {"_meta": {"timestamp": datetime.now().isoformat()}, **serialize(onpe_raw)}
    onpe_totals = onpe_payload.get("totals") or {}
    onpe_candidates = onpe_payload.get("candidates") or []
    print(
        "ONPE payload: "
        f"totales={'si' if onpe_totals else 'no'}, "
        f"candidaturas={len(onpe_candidates) if isinstance(onpe_candidates, list) else 0}"
    )
    if not onpe_totals and not onpe_candidates:
        print("WARNING: ONPE returned no totals or candidates; dashboard will keep latest valid ONPE snapshot.")
    onpe_run_id = save_run_onpe(onpe_payload)
    print(f"ONPE saved as run_id={onpe_run_id}")


async def run_jne() -> None:
    print("Running JNE Power BI scraper...")
    url = os.getenv("JNE_POWERBI_URL", JNE_DEFAULT_URL)
    wait_seconds = int(os.getenv("JNE_WAIT_SECONDS", "25"))
    scraper = PowerBIScraper(headless=True)
    jne_results = await scraper.scrape(url, wait_after_load=wait_seconds)
    print(
        "JNE payload: "
        f"tablas={len(jne_results.get('tables', []))}, "
        f"medidas={len(jne_results.get('measures', []))}"
    )
    jne_payload = _pbi_raw_payload(jne_results)
    jne_run_id = save_run(jne_payload, source="jne")
    print(f"JNE saved as run_id={jne_run_id}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run electoral scrapers once and persist results.")
    parser.add_argument(
        "--source",
        choices=["all", "onpe", "jne"],
        default=os.getenv("SCRAPE_SOURCE", "all"),
        help="Which source to scrape. Default: all.",
    )
    args = parser.parse_args()

    if args.source in ("all", "onpe"):
        await run_onpe()
    if args.source in ("all", "jne"):
        await run_jne()


if __name__ == "__main__":
    asyncio.run(main())
