"""
ONPE Electoral Results Scraper
===============================
Extracts data from the ONPE electoral results API via direct HTTP calls.

Usage:
    python onpe_scraper.py --db
    python onpe_scraper.py --output ./data
    python onpe_scraper.py --repeat 3600   # every hour
"""

import asyncio
import json
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ONPE_HOST = os.getenv("ONPE_HOST", "resultadosegundavuelta.onpe.gob.pe").strip()
ONPE_MAIN_URL = os.getenv("ONPE_MAIN_URL", f"https://{ONPE_HOST}/main/presidenciales").strip()
BASE_API = os.getenv("ONPE_BASE_API", f"https://{ONPE_HOST}/presentacion-backend").strip()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-419,es;q=0.9",
    "Content-Type": "application/json",
    "Referer": ONPE_MAIN_URL,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def _parse_ts(ms: int) -> str:
    """Convert JS timestamp (ms) to ISO string."""
    return datetime.fromtimestamp(ms / 1000).isoformat()


async def fetch_json(client: httpx.AsyncClient, path: str) -> dict | list | None:
    url = f"{BASE_API}{path}"
    try:
        r = await client.get(url, timeout=15)
        if r.status_code == 200 and r.text:
            data = r.json()
            if data.get("success"):
                return data.get("data")
    except Exception:
        pass
    return None


async def scrape() -> dict:
    """Scrape ONPE data and return structured dict."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, http2=True) as client:
        # Visit main page to establish session
        await client.get(ONPE_MAIN_URL)

        # 1. Active process info
        process = await fetch_json(client, "/proceso/proceso-electoral-activo")

        # 2. Get election ID
        id_eleccion = 10
        if process and isinstance(process, dict):
            id_eleccion = process.get("idEleccionPrincipal", 10)

        # 3. Summary totals (KPIs)
        totals = await fetch_json(
            client,
            f"/resumen-general/totales?idEleccion={id_eleccion}&tipoFiltro=eleccion",
        )

        # 4. Mesa totals
        mesas = await fetch_json(client, "/mesa/totales?tipoFiltro=eleccion")

        # 5. Candidates / participants with votes
        candidates = await fetch_json(
            client,
            f"/eleccion-presidencial/participantes-ubicacion-geografica-nombre?idEleccion={id_eleccion}&tipoFiltro=eleccion",
        )

        # 6. Heatmap (national)
        heatmap = await fetch_json(
            client,
            f"/resumen-general/mapa-calor?idEleccion={id_eleccion}&tipoFiltro=total",
        )

        return {
            "process": process,
            "totals": totals,
            "mesas": mesas,
            "candidates": candidates,
            "heatmap": heatmap,
        }


def serialize(data: dict) -> dict:
    """Convert to a JSON-safe serializable dict."""
    def _safe(v):
        if v is None:
            return None
        if isinstance(v, (str, int, float, bool)):
            return v
        if isinstance(v, list):
            return [_safe(x) for x in v]
        if isinstance(v, dict):
            return {k: _safe(v) for k, v in v.items()}
        return str(v)
    return _safe(data)


def format_form_data(raw: dict) -> dict:
    """Map raw API data to the manual form structure.

    Returns a dict matching the Google Form fields:
      Sección 2: Estado de Actas
      Sección 3: Votos por Candidato (top 2)
      Sección 4: Votos Blancos y Nulos
      Sección 5: Total general de Votos
    """
    t = raw.get("totals", {}) or {}
    candidates = raw.get("candidates", []) or []

    def find(keywords: list[str]) -> dict | None:
        for c in candidates:
            name = (c.get("nombreAgrupacionPolitica", "") or "").upper()
            cand = (c.get("nombreCandidato", "") or "").upper()
            for kw in keywords:
                if kw.upper() in name or kw.upper() in cand:
                    return c
        return None

    keiko = find(["FUJIMORI", "FUERZA POPULAR"])
    roberto = find(["SANCHEZ", "SÁNCHEZ", "JUNTOS POR EL PERÚ"])
    blanco = find(["BLANCO"])
    nulo = find(["NULO"])

    def cv(c: dict | None, field: str, default=0):
        return c.get(field, default) if c else default

    return {
        "actas": {
            "total": t.get("totalActas"),
            "contabilizadas_num": t.get("contabilizadas"),
            "contabilizadas_pct": t.get("actasContabilizadas"),
            "envio_jee_num": t.get("enviadasJee"),
            "envio_jee_pct": t.get("actasEnviadasJee"),
            "pendientes_num": t.get("pendientesJee"),
            "pendientes_pct": t.get("actasPendientesJee"),
        },
        "candidatos": {
            "keiko": {
                "votos": cv(keiko, "totalVotosValidos"),
                "pct_validos": cv(keiko, "porcentajeVotosValidos"),
                "pct_emitidos": cv(keiko, "porcentajeVotosEmitidos"),
            },
            "roberto": {
                "votos": cv(roberto, "totalVotosValidos"),
                "pct_validos": cv(roberto, "porcentajeVotosValidos"),
                "pct_emitidos": cv(roberto, "porcentajeVotosEmitidos"),
            },
        },
        "blancos_nulos": {
            "blanco": {
                "votos": cv(blanco, "totalVotosValidos"),
                "pct_validos": cv(blanco, "porcentajeVotosValidos"),
                "pct_emitidos": cv(blanco, "porcentajeVotosEmitidos"),
            },
            "nulo": {
                "votos": cv(nulo, "totalVotosValidos"),
                "pct_validos": cv(nulo, "porcentajeVotosValidos"),
                "pct_emitidos": cv(nulo, "porcentajeVotosEmitidos"),
            },
        },
        "totales": {
            "votos_validos_num": t.get("totalVotosValidos"),
            "votos_validos_pct": t.get("porcentajeVotosValidos"),
            "votos_emitidos_num": t.get("totalVotosEmitidos"),
            "votos_emitidos_pct": t.get("porcentajeVotosEmitidos"),
            "participacion": t.get("participacionCiudadana"),
        },
    }


# ─── CLI ─────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="ONPE Electoral Results Scraper")
    ap.add_argument("--output", "-o", default="./onpe_output", help="Output directory")
    ap.add_argument("--repeat", "-r", type=int, default=0, help="Repeat every N seconds")
    ap.add_argument("--db", action="store_true", help="Save to SQLite database")
    args = ap.parse_args()

    def run_once(iteration: int = 0) -> dict:
        label = f" [iteration {iteration}]" if iteration else ""
        print(f"\n{'═' * 50}{label}")
        print("ONPE Scraper")
        print(f"{'═' * 50}{label}")

        raw = asyncio.run(scrape())
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)

        # Raw JSON
        safe = serialize(raw)
        wrapped = {"_meta": {"timestamp": datetime.now().isoformat()}, **safe}
        raw_path = out / f"onpe_raw_{ts}.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(wrapped, f, indent=2, ensure_ascii=False)
        print(f"  Raw → {raw_path}")

        # Formatted form data
        form = format_form_data(raw)
        form_path = out / f"onpe_form_{ts}.json"
        with open(form_path, "w", encoding="utf-8") as f:
            json.dump(form, f, indent=2, ensure_ascii=False)
        print(f"  Form → {form_path}")

        # Print summary
        candidates = raw.get("candidates", []) or []
        totals = raw.get("totals", {}) or {}
        mesas = raw.get("mesas", {}) or {}
        print(f"  Candidates: {len(candidates)}")
        if totals:
            print(f"  Actas: {totals.get('contabilizadas', '?')}/{totals.get('totalActas', '?')} ({totals.get('actasContabilizadas', '?')}%)")
            print(f"  Participación: {totals.get('participacionCiudadana', '?')}%")
            print(f"  Votos emitidos: {totals.get('totalVotosEmitidos', '?'):,}")
        if mesas:
            print(f"  Mesas instaladas: {mesas.get('mesasInstaladas', '?')}")
        if candidates:
            for c in candidates[:5]:
                name = c.get("nombreAgrupacionPolitica", "?")
                cand = c.get("nombreCandidato", "")
                votes = c.get("totalVotosValidos", 0)
                pct = c.get("porcentajeVotosValidos", 0)
                print(f"    {name:30s} {cand:30s} {votes:>8,} ({pct}%)")

        # Print form preview
        a = form.get("actas", {})
        print(f"  ─── Formulario ───")
        print(f"  Total actas: {a.get('total')} | Contabilizadas: {a.get('contabilizadas_num')} ({a.get('contabilizadas_pct')}%)")
        print(f"  Envío JEE: {a.get('envio_jee_num')} ({a.get('envio_jee_pct')}%) | Pendientes: {a.get('pendientes_num')} ({a.get('pendientes_pct')}%)")
        ck = form.get("candidatos", {}).get("keiko", {})
        cr = form.get("candidatos", {}).get("roberto", {})
        print(f"  KEIKO FUJIMORI: {ck.get('votos'):>8,} ({ck.get('pct_validos')}% vál / {ck.get('pct_emitidos')}% emit)")
        print(f"  ROBERTO SÁNCHEZ: {cr.get('votos'):>8,} ({cr.get('pct_validos')}% vál / {cr.get('pct_emitidos')}% emit)")
        b = form.get("blancos_nulos", {}).get("blanco", {})
        n = form.get("blancos_nulos", {}).get("nulo", {})
        print(f"  Blanco: {b.get('votos'):>8,} ({b.get('pct_validos')}% vál / {b.get('pct_emitidos')}% emit)")
        print(f"  Nulo:   {n.get('votos'):>8,} ({n.get('pct_validos')}% vál / {n.get('pct_emitidos')}% emit)")
        tg = form.get("totales", {})
        print(f"  Total válidos: {tg.get('votos_validos_num'):>8,} ({tg.get('votos_validos_pct')}%) | Emitidos: {tg.get('votos_emitidos_num'):>8,} ({tg.get('votos_emitidos_pct')}%)")

        if args.db:
            from database import save_run_onpe
            rid = save_run_onpe(wrapped)
            print(f"  DB → run_id={rid}")

        print(f"  Done!{label}")
        return wrapped

    run_once()

    if args.repeat > 0:
        iteration = 1
        print(f"\nMonitoring: every {args.repeat}s")
        try:
            while True:
                import time
                time.sleep(args.repeat)
                run_once(iteration)
                iteration += 1
        except KeyboardInterrupt:
            print("\n  Stopped.")


if __name__ == "__main__":
    main()
