"""Run both electoral scrapers once and persist results.

Uses SQLite locally by default. In production, set DATABASE_URL to a
Supabase/Postgres connection string and the same database functions will write
there.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

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


async def main() -> None:
    print("Running ONPE scraper...")
    onpe_raw = await scrape_onpe()
    onpe_payload = {"_meta": {"timestamp": datetime.now().isoformat()}, **serialize(onpe_raw)}
    onpe_run_id = save_run_onpe(onpe_payload)
    print(f"ONPE saved as run_id={onpe_run_id}")

    print("Running JNE Power BI scraper...")
    url = os.getenv("JNE_POWERBI_URL", JNE_DEFAULT_URL)
    wait_seconds = int(os.getenv("JNE_WAIT_SECONDS", "25"))
    scraper = PowerBIScraper(headless=True)
    jne_results = await scraper.scrape(url, wait_after_load=wait_seconds)
    jne_payload = _pbi_raw_payload(jne_results)
    jne_run_id = save_run(jne_payload, source="jne")
    print(f"JNE saved as run_id={jne_run_id}")


if __name__ == "__main__":
    asyncio.run(main())
