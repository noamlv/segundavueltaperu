# Dashboard Brief: ONPE + JNE Electoral Monitor

This brief captures the product and data contract inferred from the ONPE and JNE reference screenshots shared on 2026-06-03.

## Product Goal

Build a public electoral monitoring site that shows the current state and historical evolution of:

- ONPE presidential results and citizen participation.
- JNE processing of observed electoral records.

The key value is historical tracking. The official sites show the current snapshot, but they do not make it easy to see what changed every 15 minutes across the day, previous days, or the full reporting period.

## Target Architecture

Current development path:

- Scrapers run every 15 minutes.
- SQLite stores local snapshots in `data/electoral.db`.
- Streamlit renders the first dashboard iteration.

Production path:

- GitHub stores the codebase.
- Supabase/PostgreSQL stores durable snapshots.
- Vercel hosts the public web experience or API/frontend layer.
- A scheduled worker runs ONPE/JNE scrapers every 15 minutes and writes one immutable run per source.

SQLite is acceptable for local development. Supabase is the preferred production database because it gives remote persistence, backups, public/private access control, and a cleaner split between scrapers and the public dashboard.

## Dashboard Information Architecture

Default ordering:

1. ONPE - Actual
2. ONPE - Evolucion
3. JNE - Actual
4. JNE - Evolucion

Each institution has the same dashboard logic:

- `Actual`: mirror the official site's current state in a cleaner combined view.
- `Evolucion`: show historical changes across the 15-minute snapshots.

## ONPE: Actual View

Source: ONPE public API.

The second round is presidential only, so the view should focus on the presidential contest and citizen participation.

### Header And Status

Show:

- Election name: Eleccion de Formula Presidencial.
- Last update timestamp from ONPE.
- Actas contabilizadas percent.
- Total actas.
- Actas contabilizadas count.
- Actas para envio al JEE count and percent.
- Actas pendientes count and percent.

Visual treatment:

- Horizontal progress bar similar to ONPE.
- Compact legend for contabilizadas, envio JEE, pendientes.
- Freshness label near the top.

### Presidential Results

Show the two second-round candidates as the primary result block:

- Candidate full name.
- Party name.
- Party logo/color where available.
- Candidate photo where available.
- Valid votes percent.
- Emitted votes percent.
- Vote count.
- Horizontal vote bar.

Expected second-round candidates:

- Keiko Sofia Fujimori Higuchi / Fuerza Popular.
- Roberto Helbert Sanchez Palomino / Juntos por el Peru.

Candidate colors:

- Fuerza Popular: `#F58220` or official orange/gold variant.
- Juntos por el Peru: `#00843D`.
- ONPE navy for neutral bars: `#003F7D`.

### Blank, Null, And Totals

Show:

- Votos en blanco: votes, emitted votes percent, valid votes percent as null/blank.
- Votos nulos: votes, emitted votes percent, valid votes percent as null/blank.
- Total votos validos.
- Total votos emitidos.

Important definition:

- Valid votes are votes obtained by political organizations.
- Emitted votes are political organization votes plus blank votes plus null votes.

### Citizen Participation

Show:

- Electores habiles.
- Total asistentes.
- Total ausentes.
- Participacion ciudadana percent.
- Ausentismo percent.
- Pendientes/classification gap if ONPE exposes it.

Breakdowns to add when endpoints are solved:

- Peru vs extranjero.
- Department/province/district.
- Map view using ONPE heatmap/geographic endpoints.

## ONPE: Evolution View

Use one point per scraper run.

Primary charts:

- Actas contabilizadas percent over time.
- Total actas contabilizadas count over time.
- Candidate votes over time.
- Candidate valid vote percent over time.
- Candidate emitted vote percent over time.
- Blank and null vote counts over time.
- Participation percent over time.
- Total emitted and valid votes over time.

Useful diagnostics:

- Delta since previous run.
- Delta since start of day.
- Latest run freshness.
- Runs missing or failed by source.

## JNE: Actual View

Source: JNE Power BI public report intercepted through `/public/reports/querydata`.

The current report appears likely to repeat the same structure for the second round unless JNE changes the Power BI model.

### Header And Filters

Show:

- Processing title: Procesamiento de Actas Observadas.
- Election label: Elecciones Generales 2026.
- Last update timestamp from JNE.
- Filters if supported: Jurado Electoral Especial, tipo de eleccion, tipo de acta electoral.

For the public dashboard, filters can be implemented as Streamlit/select controls or web dropdowns backed by DB dimensions.

### Actas Observadas Summary

Show:

- Total actas observadas received by JEE.
- Expedientes creados de actas observadas.
- Expedientes en proceso de creacion.
- Percent created.
- Percent pending creation.

### Estado De Expedientes

Show:

- Expedientes atendidos.
- Expedientes en tramite.
- Percent atendidos.
- Percent en tramite.

### Pronunciamientos

Show:

- Total pronunciamientos.
- Pronunciamientos que atienden el expediente.
- Otros pronunciamientos relacionados al expediente.

### Recuento De Votos

Show:

- Actas enviadas a recuento de votos.
- Audiencias publicas realizadas.
- Resuelto sin recuento de votos.
- Audiencias publicas programadas.
- Audiencias publicas pendientes.

Each metric should show count and percent when the Power BI model provides both.

### Por Tipo De Eleccion

Show:

- Donut chart of expedientes/actas by election type.
- Side cards for each election type:
  - Presidenciales.
  - Senadores Distrito Electoral Unico.
  - Senadores Distrito Electoral Multiple.
  - Diputados.
  - Parlamento Andino.
  - Mas de una eleccion.

### Detalle Por JEE

Show:

- Table by Jurado Electoral Especial.
- Horizontal bar chart for percent avance by JEE.

Expected columns:

- JEE name.
- Actas recibidas.
- Expedientes creados.
- Expedientes atendidos.
- Expedientes atendidos percent.

## JNE: Evolution View

Use one point per scraper run.

Primary charts:

- Total actas observadas over time.
- Expedientes creados/atendidos/en tramite over time.
- Pronunciamientos over time.
- Actas enviadas a recuento over time.
- Audiencias realizadas/programadas/pendientes over time.
- Election type distribution over time.
- JEE completion percent over time.

Useful diagnostics:

- JEE ranking by latest pending workload.
- JEE ranking by largest change since previous run.
- JEE with percent below 100 when most are complete.
- Difference between `expedientes_completos`, `expedientes_ajustado`, and `cantidad_actas_atendidas`.

## Data Model Requirements

Every scrape should write one immutable `scrape_runs` row:

- `source`: `onpe` or `jne`.
- `scraped_at`: timestamp from local scrape time or source update time when reliable.
- `created_at`: DB insert timestamp.

For production, add:

- `source_updated_at`: official ONPE/JNE timestamp when available.
- `scrape_status`: success, partial, failed.
- `error_message`: nullable.
- `raw_payload_path` or `raw_payload_hash`.
- `schema_version`.

ONPE needs tables for:

- Totals.
- Mesas/actas status.
- Candidates.
- Blank/null votes.
- Participation.
- Geographic breakdowns once solved.

JNE needs tables for:

- KPI measures.
- Actas by type.
- JEE detail.
- JEE percent avance.
- Optional raw Power BI model metadata.

## Implementation Priorities

1. Keep SQLite working locally and add a repository-safe `.gitignore`.
2. Normalize the dashboard page order to ONPE first, then JNE.
3. Improve ONPE Actual to match the official structure from the screenshots.
4. Improve JNE Actual to match the official structure from the screenshots.
5. Add historical deltas and freshness diagnostics.
6. Add a database abstraction so `DATABASE_URL` can switch from SQLite to Supabase/PostgreSQL.
7. Add migrations instead of inline `ALTER TABLE` growth.
8. Add scheduled scraper entrypoints for 15-minute production runs.
9. Deploy the UI and scraper workflow.

## Reference Images

Expected local reference image slots:

- `docs/reference_images/onpe_01_presidential_candidates.png`
- `docs/reference_images/onpe_02_presidential_dashboard.png`
- `docs/reference_images/onpe_03_blancos_nulos_totales.png`
- `docs/reference_images/onpe_04_participacion_ciudadana.png`
- `docs/reference_images/jne_01_actas_observadas_overview.png`
- `docs/reference_images/jne_02_tipo_eleccion.png`
- `docs/reference_images/jne_03_detalle_jee.png`

The screenshots were shared in chat on 2026-06-03, but the referenced Desktop file paths were not present in the local filesystem during this update. Copy them into the paths above once they are available locally.
