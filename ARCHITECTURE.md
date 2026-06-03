# Monitoreo Electoral — Architecture & Data Reference

## Stack
- **Scrapers**: Playwright (JNE), `httpx[http2]` (ONPE REST API)
- **Storage**: SQLite (`data/electoral.db`)
- **Dashboard**: Streamlit + Plotly

---

## How to Run

```bash
# JNE scraper (Power BI)
python pbi_scraper.py --url "https://web.jne.gob.pe/reporteactasobservadas/" --db --repeat 900

# ONPE scraper (direct API)
python onpe_scraper.py --db --repeat 900

# Dashboard
streamlit run dashboard.py
```

---

## JNE — Power BI Scraper (`pbi_scraper.py`)

**Source**: `https://web.jne.gob.pe/reporteactasobservadas/` (Power BI Publish to Web)

**Method**: Playwright intercepts `/public/reports/querydata` POSTs. Parses DSR v2 (Data Shape Representation) — DM0/DM1 entries, R-bitmask sparse rows, Ø control segments.

### Indicator KPIs (33 measures)

Stored in `kpi_measures` with `measure_name`, `value` (text). Used in dashboard via `kpi_val()` / `fmt_pct()`.

| measure_name | Meaning | Sample |
|---|---|---|
| `ActasObservadas.PorcentajeAvance` | % avance general | 0.9999 |
| `ActasObservadas.PorcentajePronunciamientos` | % pronunciamientos | 0.9999 |
| `ActasObservadas.ActasObservadas` | Total actas observadas | 98983 |
| `ActasObservadas.ActasProcesadas` | Actas procesadas | 68519 |
| `ActasObservadas.ExpedientesFaltantes` | Expedientes faltantes | 1 |
| `ActasObservadas.MedidaAudienciasRealizadas` | Audiencias realizadas (#) | 2474 |
| `ActasObservadas.%audienciasRealizadas` | % audiencias realizadas | 0.6459 |
| `ActasObservadas.%audienciasProgramadas` | % audiencias programadas | 0 |
| `ActasObservadas.%audienciasPendientes` | % audiencias pendientes | 0.0663 |
| `ActasObservadas.OtrosPronunciamientos` | Otros pronunciamientos (#) | 30465 |
| `ActasObservadas.PorcentajeActasSDM` | % Senado Distrito Múltiple | 0.2009 |
| `ActasObservadas.PorcentajeActasSDU` | % Senado Distrito Único | 0.2629 |
| `ActasObservadas.PorcentajeActasDiputados` | % Diputados | 0.2299 |
| `ActasObservadas.PorcentajeActasParlamento` | % Parlamento Andino | 0.2141 |
| `ActasObservadas.PorcentajeActasExtravSinies` | % Extraviadas/Siniestradas | 0.0047 |
| `ActasObservadas.ActasEnTramite` | Actas en trámite | 2 |
| `ActasObservadas.ActasRecuento` | Actas de recuento | 3830 |
| `ActasObservadas.CantidadActasAtendidas` | Actas atendidas | 68518 |
| `ActasObservadas.Expedientes_Ajustado` | Expedientes ajustado | 68520 |
| `ActasObservadas.TotalExpedientes` | Total expedientes SD | 14672 |
| `ActasObservadas.TotalExpedientes__1` | Total expedientes Pres | 5978 |
| `ActasObservadas.TotalExpedientes__2` | Total expedientes SDM | 13767 |
| `ActasObservadas.TotalExpedientes__3` | Total expedientes Dip | 15757 |
| `ActasObservadas.TotalExpedientes__4` | Total expedientes SDU | 18018 |
| `ActasObservadas.TotalExpedientes__5` | Total expedientes mixto | 328 |
| `ActasObservadas.%ActasSinDigitalizar` | % sin digitalizar | 1.45e-05 |
| `ActasObservadas.%ActasTramite` | % en trámite | 1.45e-05 |
| `ActasObservadas.%audienciasRealizadasSinReconteo` | % audiencias sin reconteo | 0.2877 |
| `ActasObservadas.MedidaAudienciasNoProgramadas` | Audiencias no programadas (#) | 254 |
| `ActasObservadas.MedidaAudienciasRealizadasSinReconteo` | Audiencias realizadas sin reconteo (#) | 1102 |
| `ActasObservadas.MedidaAudienciasProgramadas` | Audiencias programadas (#) | 0 |
| `ActasObservadas.MedidaAudienciasNoProgramadas` | Audiencias no programadas (#) | 254 |
| `ActasObservadas.FechaActualizacion` | Texto de última actualización | "Actualizado al 2026-06-02 12:07:38" |

### Tables (3)

**1. `actas_by_type`** — Actas completas por tipo de elección

| tipo_eleccion | actas_completas |
|---|---|
| PRESIDENCIA | 5978 |
| SENADORES DISTRITO MÚLTIPLE | 13767 |
| DIPUTADOS | 15757 |
| SENADORES DISTRITO ÚNICO | 18017 |
| PARLAMENTO ANDINO | 14672 |
| MAS DE UN TIPO DE ELECCIÓN | 328 |

**2. `jje_detail`** — Detalle por JEE (60 jurisdicciones)

| Column | Type | Description |
|---|---|---|
| `jee_name` | TEXT | Nombre del JEE (ej. ABANCAY, AREQUIPA 1) |
| `expedientes_completos` | INT | Expedientes completos |
| `expedientes_ajustado` | INT | Expedientes ajustado |
| `pct_pronunciamientos_sin_total` | REAL (≈%) | % pronunciamientos (0–1, puede ser None) |
| `cantidad_actas_atendidas` | INT | Actas atendidas |

**3. `jee_porcentaje`** — % de pronunciamientos por JEE (tabla separada del PBI)

| Column | Type |
|---|---|
| `jee_name` | TEXT |
| `porcentaje` | REAL (≈%) |

---

## ONPE — REST API Scraper (`onpe_scraper.py`)

**Base**: `https://resultadoelectoral.onpe.gob.pe/presentacion-backend`

**Headers required**: HTTP/2 (`httpx[http2]`), `Accept: */*`, `Content-Type: application/json`, `Referer: …/presidenciales`.

### Endpoints

| Endpoint | Returns |
|---|---|
| `GET /proceso/proceso-electoral-activo` | Process metadata, `idEleccionPrincipal` |
| `GET /proceso/{id}/elecciones` | Election list |
| `GET /resumen-general/totales?idEleccion={id}&tipoFiltro=eleccion` | Totals KPIs |
| `GET /eleccion-presidencial/participantes-ubicacion-geografica-nombre?idEleccion={id}&tipoFiltro=eleccion` | Candidates with votes (38 1ra vuelta, 2+BN 2da vuelta) |
| `GET /mesa/totales?tipoFiltro=eleccion` | Mesa installation stats |
| `GET /resumen-general/mapa-calor?idEleccion={id}&tipoFiltro=total` | National heatmap |

> ⚠️ `tipoFiltro=departamento` returns 204 — likely needs POST body or interaction context.

### Raw API Fields → DB mapping

**`onpe_totals`** — one row per run

| DB column | API field | Type | Description |
|---|---|---|---|
| `actas_contabilizadas` | `actasContabilizadas` | REAL (%) | % actas contabilizadas |
| `contabilizadas` | `contabilizadas` | INT (#) | Actas contabilizadas |
| `total_actas` | `totalActas` | INT (#) | Total de actas |
| `participacion` | `participacionCiudadana` | REAL (%) | Participación ciudadana |
| `votos_emitidos` | `totalVotosEmitidos` | INT (#) | Total votos emitidos |
| `votos_validos` | `totalVotosValidos` | INT (#) | Total votos válidos |
| `enviadas_jee` | `enviadasJee` | INT (#) | Actas enviadas al JEE |
| `actas_enviadas_jee` | `actasEnviadasJee` | REAL (%) | % enviadas al JEE |
| `pendientes_jee` | `pendientesJee` | INT (#) | Actas pendientes JEE |
| `actas_pendientes_jee` | `actasPendientesJee` | REAL (%) | % pendientes JEE |
| `porcentaje_votos_validos` | `porcentajeVotosValidos` | REAL (%) | % votos válidos |
| `porcentaje_votos_emitidos` | `porcentajeVotosEmitidos` | REAL (%) | % votos emitidos |
| `fec_actualizacion` | `fechaActualizacion` | TEXT (ms timestamp) | Actualizado (convertir: `dt.fromtimestamp(int/1000)`) |

**`onpe_mesas`** — one row per run

| DB column | API field | Description |
|---|---|---|
| `instaladas` | `mesasInstaladas` | Mesas instaladas |
| `no_instaladas` | `mesasNoInstaladas` | Mesas no instaladas |
| `pendientes` | `mesasPendientes` | Mesas pendientes (first round: 0) |

**`onpe_candidates`** — one row per candidate per run

| DB column | API field | Description |
|---|---|---|
| `nombre_partido` | `nombreAgrupacionPolitica` | "FUERZA POPULAR" |
| `codigo_partido` | `codigoAgrupacionPolitica` | "8" |
| `nombre_candidato` | `nombreCandidato` | "KEIKO SOFIA FUJIMORI HIGUCHI" |
| `dni_candidato` | `dniCandidato` | "10001088" |
| `votos_validos` | `totalVotosValidos` | # votos válidos |
| `pct_validos` | `porcentajeVotosValidos` | % sobre válidos (null para blanco/nulo) |
| `pct_emitidos` | `porcentajeVotosEmitidos` | % sobre emitidos |

### Form Output (`onpe_form_*.json`)

Reformats raw API into Google Form structure:

```json
{
  "actas": {
    "total": 92766,
    "contabilizadas_num": 92766,
    "contabilizadas_pct": 100.0,
    "envio_jee_num": 0,
    "envio_jee_pct": 0.0,
    "pendientes_num": 0,
    "pendientes_pct": 0.0
  },
  "candidatos": {
    "keiko": { "votos": 2877678, "pct_validos": 17.192, "pct_emitidos": 14.269 },
    "roberto": { "votos": 2015114, "pct_validos": 12.039, "pct_emitidos": 9.992 }
  },
  "blancos_nulos": {
    "blanco": { "votos": 2372895, "pct_validos": null, "pct_emitidos": 11.766 },
    "nulo": { "votos": 1056811, "pct_validos": null, "pct_emitidos": 5.24 }
  },
  "totales": {
    "votos_validos_num": 16738039,
    "votos_validos_pct": 100,
    "votos_emitidos_num": 20167745,
    "votos_emitidos_pct": 100,
    "participacion": 73.806
  }
}
```

> ⚠️ Note: `VOTOS EN BLANCO` has `porcentajeVotosValidos: null` (0% of valid votes by definition). `VOTOS NULOS` also has null pct_validos.

---

## Database Schema (`data/electoral.db`)

```
scrape_runs          → id, source, scraped_at, created_at
│
├── kpi_measures     → run_id, measure_name, value          (JNE)
├── jje_detail       → run_id, jee_name, expedientes*       (JNE)
├── actas_by_type    → run_id, tipo_eleccion, actas_completas (JNE)
├── jee_porcentaje   → run_id, jee_name, porcentaje         (JNE)
│
├── onpe_totals      → run_id, actas_contabilizadas, …      (ONPE)
├── onpe_mesas       → run_id, instaladas, …                (ONPE)
└── onpe_candidates  → run_id, nombre_partido, votos*, …     (ONPE)
```

All ONPE and JNE tables are linked via `scrape_runs.id = *_tables.run_id`.

---

## Dashboard Pages (`dashboard.py`)

| Sidebar option | Page | Key features |
|---|---|---|
| 🔵 ONPE — Actual | `ONPE — Actual` | Formulario Secciones 2–5 (Actas, Candidatos, Blancos/Nulos, Totales) |
| 🔵 ONPE — Histórico | `ONPE — Histórico` | Líneas: actas, participación, candidatos, tabla histórica |
| 🔴 JNE — Actual | `JNE — Actual` | KPIs en 3 filas de 5, barras por tipo de elección, treemap + tabla de 60 JEEs |
| 🔴 JNE — Histórico | `JNE — Histórico` | Selector de KPI → línea temporal, selector JEE → evolución |

Product/dashboard planning is captured in [`docs/DASHBOARD_BRIEF.md`](docs/DASHBOARD_BRIEF.md). That brief is the working contract for the future public site: ONPE first, then JNE; each source gets an "Actual" view that mirrors the official site and an "Evolución" view powered by 15-minute snapshots.

---

## Production Direction

Current local development uses SQLite (`data/electoral.db`). This is good for fast iteration and offline scraping.

Target production architecture:

- **GitHub**: source control, branches, pull requests, CI.
- **Supabase/PostgreSQL**: durable remote database for scraper snapshots.
- **Vercel**: public frontend/API hosting when the dashboard moves beyond local Streamlit.
- **Scheduled scraper worker**: runs ONPE and JNE scrapers every 15 minutes and writes immutable run rows.

Migration approach:

1. Keep SQLite as the local fallback.
2. Add `DATABASE_URL` support.
3. Move schema changes into explicit migrations.
4. Translate SQLite-specific SQL (`INSERT OR IGNORE`, autoincrement behavior, pragmas) to a Postgres-compatible adapter.
5. Preserve the current `scrape_runs` snapshot model so historical charts keep working.

---

## Critical Notes for Cursor/Codex

### PBI Scraper (`pbi_scraper.py`)
- Intercepts `/public/reports/querydata` responses
- DSR v2 parsing: DM0..DMN, R bitmask (1=null), Ø=control segment, S=schema, C=cell values
- KPI values may have `L`/`D` suffixes → strip with `_clean_pbi_number()`
- The Power BI report may change its internal measure names → update `dashboard.py` KPI lookup names
- `--pages` flag cycles through report pages via `postMessage({action: 'setPage', pageName: …})`

### ONPE Scraper (`onpe_scraper.py`)
- **Requires HTTP/2** — CloudFront blocks HTTP/1.1 API calls, returns Angular HTML
- Uses `httpx.AsyncClient(http2=True)` — requires `pip install httpx[http2]`
- First visits `…/main/presidenciales` to establish session cookies (optional but safer)
- Second round (post-Jun 7) should return only 2 candidates + blancos + nulos

### Dashboard (`dashboard.py`)
- `fmt_num()` handles `None` and string values (JNE KPIs returning "—")
- `fmt_pct()` assumes values <1 are fractions (0.85→85.00%), values ≥1 are already percent
- ONPE pages query DB with `get_onpe_latest()` which uses `source='onpe'`
- Historical pages need ≥2 runs to display charts

### Database (`database.py`)
- `save_run()` and `save_run_onpe()` auto-create tables via `init_db()`
- `init_db()` has migration logic with `ALTER TABLE ADD COLUMN` wrapped in try/except
- `get_run_timestamps()` must return `source` column (needed to filter by source)

---

## Design TODO (restore with images)

To match the original Google Form / electoral dashboard design, capture screenshots of:

1. **ONPE "Segunda Vuelta" candidate banner** — add header image with KEIKO vs ROBERTO photos side by side with party logos
2. **JNE layout** — capture the JNE PBI report layout and re-create column groupings and color scheme
3. **Progress gauges** — replace numeric KPIs with circular gauge charts (Plotly `indicator` with `gauge`) for percentage metrics
4. **Party colors** — Fuerza Popular = #FDC300 (orange/gold), Juntos por el Perú = #00843D (green)
5. **ONPE Actual section numbering** — mirror the exact order: 1–7 (Actas), 8–9 (Candidatos), 10–11 (Blancos/Nulos), 12 (Totales)
6. **Auto-scroll to KPIs** — add `st.empty()` anchors for direct section navigation
7. **Responsive layout** — collapse to fewer columns on mobile

Place reference images in `docs/` folder and reference them here.

---

## Roadmap

- [ ] Add sub-national breakdowns (departamento/provincia) — likely need POST params
- [ ] Deploy on server (Railway/Fly.io) with Streamlit + 15-min scraper cron
- [ ] Second round polish (Jun 7, 5pm → live data with 2 candidates)
- [ ] Add map (choropleth) for geographical results (ONPE heatmap endpoint exists)
- [ ] Alert system — push notification when new data differs significantly
