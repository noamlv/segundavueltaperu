"""
Power BI Embedded Report Scraper
================================
Extracts data from public "Publish to web" Power BI reports using Playwright.

Intercepts the underlying JSON API calls (/public/reports/querydata) rather
than parsing the DOM, making it more reliable and comprehensive.

Usage:
    python pbi_scraper.py --url "https://app.powerbi.com/view?r=..."
    python pbi_scraper.py --url "https://web.jne.gob.pe/reporteactasobservadas/" --output ./data
    python pbi_scraper.py --url "..." --pages --visible
"""

import asyncio
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from playwright.async_api import async_playwright

from database import save_run


# ─── Constants ───────────────────────────────────────────────────────────────

QUERYDATA_ENDPOINTS = ("querydata",)
SCHEMA_ENDPOINTS = ("conceptualschema",)
MODELS_ENDPOINTS = ("modelsAndExploration",)

# Data type map: PBI type_num → readable name
PBI_DTYPE = {
    1: "string", 2: "int64", 3: "float64", 4: "int64",
    6: "bool", 7: "datetime64", 8: "string", 9: "string",
    10: "float64", 13: "float64",
}


# ─── PBI DSR (Data Shape Representation) Parser ──────────────────────────────

def _clean_pbi_number(raw: Any) -> Any:
    """Normalize Power BI number suffixes (D, L) and scientific notation."""
    if isinstance(raw, str):
        raw = raw.rstrip("LD")
        try:
            return int(raw) if "." not in raw and "E" not in raw.upper() else float(raw)
        except ValueError:
            pass
    return raw


def _parse_ph(ph: dict, select: list[dict] | None = None) -> list[dict]:
    """
    Parse a single Pivot Hierarchy (PH) from DSR v2.

    Each PH contains DM* entries (DM0, DM1, …) that form either:
      A) A measure with metadata (M0 + S, no C)  → 1 measure result
      B) A single-row measure (M0 only, no S, no C)  → 1 measure result
      C) A table spanning multiple DM* entries:
         - The first entry with "S" defines the schema
         - Entries with "C" contribute data rows (may span multiple DM* groups)
         - Entries with "Ø" are control segments and are skipped
         - Entries with "R" denote repeat (inherit previous row's values)
      D) A table where data lives in DM1+ (DM0 is a control segment with Ø)
    """
    # Collect all DM* entries across all groups in the PH
    all_dm = []
    for key in ph:
        if key.startswith("DM"):
            all_dm.extend(ph[key])

    if not all_dm:
        return []

    # Separate control vs data entries
    data_dm = [d for d in all_dm if "Ø" not in d]

    if not data_dm:
        return []

    # Find the schema entry (first data entry with "S")
    schema_dm = next((d for d in data_dm if "S" in d), None)
    if schema_dm is None:
        # Pure measures (M0 values, no segments)
        results = []
        for d in data_dm:
            if "M0" in d:
                results.append({
                    "type": "measure",
                    "value": _clean_pbi_number(d["M0"]),
                })
        return results

    segs = schema_dm.get("S", [])

    # CASE A: Measure with metadata (M0 + S, no C)
    if "M0" in schema_dm and "C" not in schema_dm:
        return [{
            "type": "measure",
            "value": _clean_pbi_number(schema_dm["M0"]),
        }]

    # CASE C/D: Table
    # Resolve column names from Select descriptor if available
    group_entries = [s for s in (select or []) if s.get("Kind") == 1]
    measure_entries = [s for s in (select or []) if s.get("Kind") == 2]

    columns = []
    group_idx = 0
    measure_idx = 0
    for s in segs:
        sname = s.get("N", "")
        dtype = PBI_DTYPE.get(s.get("T", 1), "string")
        display_name = s.get("Nme", "")
        if display_name:
            col_name = display_name
        elif sname.startswith("G") and group_idx < len(group_entries):
            col_name = group_entries[group_idx].get("Name", sname)
            group_idx += 1
        elif sname.startswith("M") and measure_idx < len(measure_entries):
            col_name = measure_entries[measure_idx].get("Name", sname)
            measure_idx += 1
        else:
            col_name = sname
        columns.append({"name": col_name, "ref": sname, "dtype": dtype})

    ncols = len(columns)
    rows = []

    for d in data_dm:
        cells = d.get("C")
        if cells is None:
            continue

        # Extract values from C (could be flat array or array of {"V": val})
        values = []
        if isinstance(cells, list):
            for c in cells:
                if isinstance(c, dict):
                    values.append(c.get("V"))
                else:
                    values.append(c)
        else:
            values = [cells]

        # Clean PBI number suffixes
        cleaned = [_clean_pbi_number(v) for v in values]

        # R is a bitmask: set bits indicate columns that are null in this row
        # (omitted from the C array for sparse data optimization)
        mask = d.get("R", 0)
        row: list = []
        ci = 0
        for col_idx in range(ncols):
            if mask & (1 << col_idx):
                row.append(None)
            else:
                row.append(cleaned[ci] if ci < len(cleaned) else None)
                ci += 1

        rows.append(row)

    if rows:
        return [{"type": "table", "columns": columns, "rows": rows}]

    return []


def parse_dsr(data: dict, select: list[dict] | None = None) -> list[dict]:
    """Parse DSR v2 from a querydata response body."""
    results = []
    for ds in data.get("DS", []):
        for ph in ds.get("PH", []):
            results.extend(_parse_ph(ph, select))
    return results


def parse_descriptor(select: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split descriptor Select into Kind=1 (groups) and Kind=2 (measures)."""
    groups, measures = [], []
    for s in select:
        kind = s.get("Kind", 0)
        entry = {
            "value": s.get("Value", ""),
            "name": s.get("Name", ""),
            "format": s.get("Format", ""),
            "subtotal": s.get("Subtotal", s.get("SubtotalEntity", [])),
        }
        if kind == 1:
            entry["group_keys"] = s.get("GroupKeys", [])
            groups.append(entry)
        else:
            measures.append(entry)
    return groups, measures


def extract_querydata_results(response_body: dict) -> list[dict]:
    """Unpack a querydata response into structured tables + measures."""
    extracted = []
    for res_idx, res in enumerate(response_body.get("results", [])):
        data = res.get("result", {}).get("data", {})
        dsr = data.get("dsr", {})
        descriptor = data.get("descriptor", {})
        if not dsr:
            continue

        select = descriptor.get("Select", [])
        groups, measures = parse_descriptor(select)

        # Build a readable name for this result
        name_parts = [m["name"] for m in (measures or groups)]
        desc_name = " | ".join(n for n in name_parts if n)

        for item in parse_dsr(dsr, select):
            item["descriptor"] = {
                "name": desc_name,
                "groups": groups,
                "measures": measures,
                "select_raw": select,
            }
            item["result_index"] = res_idx
            extracted.append(item)

    return extracted


# ─── Playwright Scraper ──────────────────────────────────────────────────────

class PowerBIScraper:
    """Scrape a Power BI 'Publish to web' report via Playwright."""

    def __init__(
        self,
        headless: bool = True,
        viewport: tuple[int, int] = (1920, 1080),
        timeout: int = 60000,
    ):
        self.headless = headless
        self.viewport = viewport
        self.timeout = timeout
        self._captured: list[dict] = []
        self._schema: Optional[dict] = None
        self._models: Optional[dict] = None

    async def _navigate(
        self, page, url: str
    ):
        """Navigate to URL (handles wrapper pages with iframes)."""
        print(f"  Loading {url} ...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
        except Exception as e:
            print(f"  Warning: {e}")

    async def scrape(
        self,
        url: str,
        wait_after_load: int = 25,
        screenshot_path: str | None = None,
    ) -> dict:
        """Load a Power BI report and capture data from all visuals."""
        self._captured = []
        self._schema = None
        self._models = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            page.on("response", lambda r: asyncio.ensure_future(self._on_response(r)))

            await self._navigate(page, url)

            print(f"  Waiting {wait_after_load}s for visuals ...")
            await page.wait_for_timeout(wait_after_load * 1000)

            if screenshot_path:
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"  Screenshot saved → {screenshot_path}")

            await browser.close()

        return self._compile()

    async def scrape_pages(
        self,
        url: str,
        wait_after_load: int = 15,
        wait_after_page: int = 10,
    ) -> dict:
        """
        Load the report and cycle through all available pages via postMessage.
        This triggers data loading for each page.
        """
        self._captured = []
        self._schema = None
        self._models = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
            )
            page = await context.new_page()
            page.on("response", lambda r: asyncio.ensure_future(self._on_response(r)))

            print(f"  Loading {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
            await page.wait_for_timeout(wait_after_load * 1000)

            # Try to get page names from the models
            page_names = self._get_page_names()
            if page_names:
                print(f"  Found {len(page_names)} pages: {[n['displayName'] for n in page_names]}")
                for pn in page_names:
                    pname = pn.get("name", "")
                    if not pname:
                        continue
                    print(f"  Switching to page '{pn.get('displayName', pname)}' ...")
                    try:
                        await page.evaluate(f"""
                        window.postMessage({{
                            action: 'setPage',
                            pageName: '{pname}'
                        }}, '*');
                        """)
                        await page.wait_for_timeout(wait_after_page * 1000)
                    except Exception as e:
                        print(f"    Warning: page switch failed: {e}")

            await browser.close()

        return self._compile()

    def _get_page_names(self) -> list[dict]:
        """Extract page names from cached models metadata."""
        if not self._models:
            return []
        exploration = self._models.get("exploration", {})
        sections = exploration.get("sections", [])
        return [
            {"name": s.get("name"), "displayName": s.get("displayName", s.get("name", ""))}
            for s in sections if s.get("name")
        ]

    async def _on_response(self, response):
        url = response.url
        try:
            if response.status != 200:
                return

            if any(ep in url for ep in QUERYDATA_ENDPOINTS):
                body = await response.body()
                self._captured.append(json.loads(body))
            elif any(ep in url for ep in SCHEMA_ENDPOINTS):
                body = await response.body()
                self._schema = json.loads(body)
            elif any(ep in url for ep in MODELS_ENDPOINTS):
                body = await response.body()
                self._models = json.loads(body)
        except Exception:
            pass

    def _compile(self) -> dict:
        tables, measures = [], []
        for resp in self._captured:
            for item in extract_querydata_results(resp):
                if item["type"] == "table":
                    tables.append(item)
                elif item["type"] == "measure":
                    measures.append(item)

        return {
            "tables": tables,
            "measures": measures,
            "schema": self._schema,
            "models": self._models,
        }


# ─── Output helpers ──────────────────────────────────────────────────────────

def tables_to_dataframes(results: dict) -> dict[str, pd.DataFrame]:
    """Convert scraped tables to named DataFrames."""
    dfs = {}
    for i, table in enumerate(results.get("tables", [])):
        desc = table.get("descriptor", {})
        name = f"{desc.get('name', '') or f'table_{i}'}_{i}"

        columns = [c["name"] for c in table.get("columns", [])]
        rows = table.get("rows", [])

        if not rows:
            continue

        # Deduplicate column names
        seen = {}
        clean = []
        for c in columns:
            key = c or "col"
            seen[key] = seen.get(key, -1) + 1
            clean.append(f"{key}_{seen[key]}" if seen[key] else key)

        df = pd.DataFrame(rows, columns=clean)
        for col in df.columns:
            try:
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().any():
                    df[col] = converted
            except (ValueError, TypeError):
                pass

        dfs[name] = df
    return dfs


def measures_to_dataframe(results: dict) -> pd.DataFrame:
    """Convert all KPI values to a single DataFrame."""
    measures = results.get("measures", [])
    if not measures:
        return pd.DataFrame()
    rows = []
    for m in measures:
        desc = m.get("descriptor", {})
        val = m.get("value")
        # Normalize any remaining PBI suffixes
        if isinstance(val, str):
            val = val.replace("L", "").replace("D", "")
            try:
                val = int(val) if "." not in val else float(val)
            except ValueError:
                pass
        rows.append({
            "measure": desc.get("name", ""),
            "value": val,
            "scraped_at": datetime.now().isoformat(),
        })
    return pd.DataFrame(rows).sort_values("measure").reset_index(drop=True)


def save_results(results: dict, output_dir: str | Path):
    """Save scraped data as CSV + JSON into output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 1. Raw JSON ──
    raw = {"_meta": {"timestamp": datetime.now().isoformat()}, "tables": [], "measures": []}
    for t in results.get("tables", []):
        d = t.get("descriptor", {})
        raw["tables"].append({
            "name": d.get("name", ""),
            "columns": [c["name"] for c in t.get("columns", [])],
            "rows": t.get("rows", []),
        })
    for m in results.get("measures", []):
        d = m.get("descriptor", {})
        raw["measures"].append({"name": d.get("name", ""), "value": m.get("value")})
    raw_path = out / f"raw_{ts}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    print(f"  Raw JSON → {raw_path}")

    # ── 2. CSVs per table ──
    dfs = tables_to_dataframes(results)
    for name, df in dfs.items():
        safe = re.sub(r"[^\w -]", "_", name).strip()
        csv_path = out / f"{safe}_{ts}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  Table → {csv_path}  ({len(df)} rows × {len(df.columns)} cols)")

    # ── 3. KPI measures CSV ──
    kpi_df = measures_to_dataframe(results)
    if not kpi_df.empty:
        csv_path = out / f"kpi_measures_{ts}.csv"
        kpi_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  KPIs  → {csv_path}  ({len(kpi_df)} measures)")

    # ── 4. Schema ──
    if results.get("schema"):
        path = out / f"schema_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results["schema"], f, indent=2, ensure_ascii=False)
        print(f"  Schema → {path}")

    # ── 5. Page metadata ──
    if results.get("models"):
        exp = results["models"].get("exploration", {})
        pages = [
            {"name": s.get("name"), "displayName": s.get("displayName")}
            for s in exp.get("sections", [])
        ]
        path = out / f"metadata_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pages": pages, "filters": exp.get("filters", [])},
                      f, indent=2, ensure_ascii=False)
        print(f"  Meta   → {path}")

    return raw_path


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Power BI Embedded (Publish to web) scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pbi_scraper.py --url "https://app.powerbi.com/view?r=..."
  pbi_scraper.py --url "https://web.jne.gob.pe/reporteactasobservadas/" -o data
  pbi_scraper.py --url "..." --pages --visible
  pbi_scraper.py --url "..." --repeat 300     # scrape every 5 minutes
""",
    )
    ap.add_argument("--url", "-u", required=True, help="Power BI report URL")
    ap.add_argument("--output", "-o", default="./pbi_output", help="Output directory")
    ap.add_argument("--visible", "-v", action="store_true", help="Show browser")
    ap.add_argument("--wait", "-w", type=int, default=25, help="Initial wait (s)")
    ap.add_argument("--pages", action="store_true", help="Cycle through all pages")
    ap.add_argument("--screenshot", "-s", action="store_true", help="Save screenshot of dashboard")
    ap.add_argument(
        "--repeat", "-r", type=int, default=0,
        help="Repeat every N seconds (monitoring mode)",
    )
    ap.add_argument("--db", action="store_true",
        help="Save to SQLite database (in data/electoral.db)",
    )
    args = ap.parse_args()

    def run_once(iteration: int = 0) -> dict:
        label = f" [iteration {iteration}]" if iteration else ""
        print(f"\n{'═' * 50}{label}")
        print("Power BI Scraper")
        print(f"{'═' * 50}{label}")

        scraper = PowerBIScraper(headless=not args.visible)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        screenshot_path = None
        if args.screenshot:
            Path(args.output).mkdir(parents=True, exist_ok=True)
            screenshot_path = str(Path(args.output) / f"screenshot_{ts}.png")

        if args.pages:
            results = asyncio.run(
                scraper.scrape_pages(args.url, wait_after_load=args.wait)
            )
        else:
            results = asyncio.run(
                scraper.scrape(args.url, wait_after_load=args.wait, screenshot_path=screenshot_path)
            )

        tables = results.get("tables", [])
        measures = results.get("measures", [])

        print(f"\n  Results: {len(tables)} tables, {len(measures)} KPIs")
        for i, t in enumerate(tables):
            cols = [c["name"] for c in t.get("columns", [])]
            d = t.get("descriptor", {})
            print(f"    [{i}] {d.get('name', '?'):55s} {len(t['rows']):>4}r × {len(cols)}c")

        print(f"  Saving → {args.output}/")
        raw_path = save_results(results, args.output)

        if args.db:
            raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
            run_id = save_run(raw)
            print(f"  DB    → data/electoral.db  (run_id={run_id})")

        print(f"  Done!{label}")
        return results

    # First run
    run_once()

    # Repeat mode
    if args.repeat > 0:
        iteration = 1
        print(f"\nMonitoring mode: scraping every {args.repeat}s (Ctrl+C to stop)")
        try:
            while True:
                import time
                time.sleep(args.repeat)
                run_once(iteration)
                iteration += 1
        except KeyboardInterrupt:
            print("\n  Monitoring stopped.")


if __name__ == "__main__":
    main()
