# Segunda vuelta presidencial Peru 2026 - arquitectura y handoff para Codex

Este archivo es la memoria principal del proyecto. Codex debe leerlo antes de
modificar el dashboard, los scrapers, la base de datos o el despliegue.

## Estado actual

- Repositorio: `https://github.com/noamlv/segundavueltaperu`
- Rama principal: `main`
- Dashboard publico: Streamlit Community Cloud
- Base productiva: Supabase/Postgres
- Scheduler actual: GitHub Actions como respaldo, no como scheduler confiable
- Scheduler pendiente: Azure Container Apps Jobs
- Usuario colaborador operativo: `addmoeuperu`

El dashboard esta funcionando y lee datos desde Supabase. Lo que falta para la
operacion electoral robusta es mover los agentes ONPE/JNE desde GitHub Actions a
Azure Jobs para ejecutar `python scripts/scrape_once.py` cada 15 minutos.

## Arquitectura objetivo

```text
Codex / desarrollo local
        |
        v
GitHub: noamlv/segundavueltaperu
        |                         \
        |                          \
        v                           v
Streamlit Community Cloud        Azure Container Apps Job
dashboard.py                     scripts/scrape_once.py cada 15 min
        |                           |
        |                           v
        +----------------------> Supabase/Postgres
                                  snapshot historico ONPE/JNE
```

GitHub se mantiene como repositorio y fuente de verdad. Streamlit publica la
web. Supabase guarda los datos. Azure reemplaza solamente a GitHub Actions como
ejecutor programado de los agentes.

## Componentes

| Componente | Archivo/recurso | Rol |
|---|---|---|
| Dashboard | `dashboard.py` | UI Streamlit con Resumen, ONPE, JNE, Monitoreo y Actualizacion |
| Base de datos | `database.py` | Adaptador SQLite local / Postgres Supabase productivo |
| Scraper ONPE | `onpe_scraper.py` | Consulta API publica ONPE con `httpx[http2]` |
| Scraper JNE | `pbi_scraper.py` | Extrae datos desde Power BI publico con Playwright |
| Ejecucion una vez | `scripts/scrape_once.py` | Corre ONPE y JNE, guarda ambos en base |
| Preflight DB | `scripts/check_database.py` | Valida conexion a Supabase sin exponer secretos |
| Workflow respaldo | `.github/workflows/scrape.yml` | Corre scrapers, pero GitHub no garantiza cadencia exacta |
| Guia Azure | `docs/AZURE_AGENTS.md` | Pasos para crear jobs programados en Azure |

## Estado productivo actual

### GitHub

GitHub guarda el codigo y permite que Codex suba cambios. Tambien contiene un
workflow de respaldo en `.github/workflows/scrape.yml`.

Ese workflow tiene `schedule`, pero GitHub Actions no es adecuado como SLA de
15 minutos. La documentacion oficial indica que los schedules pueden retrasarse
o descartarse bajo carga. En las pruebas del proyecto, los runs programados
saltaron por horas. Se conserva como respaldo y ejecucion manual.

### Streamlit

Streamlit Community Cloud publica el dashboard desde:

- Repository: `noamlv/segundavueltaperu`
- Branch: `main`
- Main file path: `dashboard.py`

Streamlit necesita el secreto:

```toml
DATABASE_URL = "postgresql://..."
```

Streamlit no debe ejecutar scrapers de forma programada. Solo lee Supabase y
muestra visualizaciones.

### Supabase

Supabase/Postgres es la base productiva. El connection string usa el transaction
pooler compatible con IPv4:

```text
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-1-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
```

No guardar la contrasena en GitHub ni en archivos del repo. Usarla solo como
secret en Streamlit, GitHub Actions y Azure.

### Azure pendiente

La proxima tarea importante es crear un Azure Container Apps Job que ejecute:

```bash
python scripts/scrape_once.py
```

cada 15 minutos, con estos secretos:

- `DATABASE_URL`
- `JNE_POWERBI_URL`
- `JNE_WAIT_SECONDS`

Ver guia detallada en `docs/AZURE_AGENTS.md`.

## Desarrollo local en macOS

```bash
cd "/Users/noam/Documents/GitHub/Electoral scrapping"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
streamlit run dashboard.py
```

Si `DATABASE_URL` no esta configurado, se usa SQLite local en
`data/electoral.db`.

## Desarrollo local en Windows

En PowerShell, con la cuenta `addmoeuperu` autenticada en GitHub:

```powershell
cd $HOME\Documents
git clone https://github.com/noamlv/segundavueltaperu.git
cd segundavueltaperu

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium

streamlit run dashboard.py
```

Para leer Supabase desde Windows durante una sesion local:

```powershell
$env:DATABASE_URL="postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-1-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require"
streamlit run dashboard.py
```

No escribir `DATABASE_URL` real en archivos versionados.

## Variables y secretos

| Nombre | Donde se usa | Requerido | Descripcion |
|---|---|---|---|
| `DATABASE_URL` | Streamlit, Azure, GitHub Actions, local opcional | Si en produccion | URL Postgres/Supabase con `sslmode=require` |
| `JNE_POWERBI_URL` | Azure/GitHub Actions | Opcional | URL del reporte JNE; default en codigo |
| `JNE_WAIT_SECONDS` | Azure/GitHub Actions | Opcional | Tiempo de espera para que Power BI cargue; default `25` |

## Modelo de datos

Todas las capturas se ordenan por `scrape_runs.id`.

```text
scrape_runs
  id, source, scraped_at, created_at
  source = 'onpe' o 'jne'

JNE
  kpi_measures     -> run_id, measure_name, value
  jje_detail       -> run_id, jee_name, expedientes_completos, ...
  actas_by_type    -> run_id, tipo_eleccion, actas_completas
  jee_porcentaje   -> run_id, jee_name, porcentaje

ONPE
  onpe_totals      -> run_id, actas, participacion, votos, fecha
  onpe_mesas       -> run_id, instaladas, no_instaladas, pendientes
  onpe_candidates  -> run_id, partido, candidato, votos, porcentajes
```

El dashboard usa historicos para mostrar evolucion temporal. Una captura vacia
no debe borrar datos validos anteriores.

## Hallazgo operativo importante sobre ONPE

El 4 de junio de 2026 se verifico:

- ONPE responde bien desde la maquina local: totales y 38 candidaturas.
- ONPE responde vacio desde GitHub Actions: `totales=no, candidaturas=0`.
- JNE responde bien desde GitHub Actions.

Por eso `get_onpe_latest()` en `database.py` busca la ultima captura ONPE valida
que tenga totales o candidaturas. Las consultas ONPE vacias siguen quedando
registradas en `scrape_runs` para monitoreo operativo, pero no reemplazan el
ultimo dato valido del dashboard.

Azure debe probarse especificamente contra ONPE. Si Azure tambien recibe ONPE
vacio, considerar:

- ajustar headers/sesion del scraper ONPE;
- correr ONPE desde otra region;
- separar ONPE y JNE en jobs distintos;
- usar un worker en una red que ONPE no degrade.

## ONPE - REST API scraper

Base:

```text
https://resultadoelectoral.onpe.gob.pe/presentacion-backend
```

Endpoints usados:

| Endpoint | Uso |
|---|---|
| `/proceso/proceso-electoral-activo` | Detectar proceso e `idEleccionPrincipal` |
| `/resumen-general/totales?idEleccion={id}&tipoFiltro=eleccion` | KPIs generales |
| `/mesa/totales?tipoFiltro=eleccion` | Mesas |
| `/eleccion-presidencial/participantes-ubicacion-geografica-nombre?idEleccion={id}&tipoFiltro=eleccion` | Candidaturas y votos |
| `/resumen-general/mapa-calor?idEleccion={id}&tipoFiltro=total` | Mapa/calor |

Notas:

- Requiere HTTP/2 (`httpx[http2]`).
- El scraper visita primero la pagina presidencial para establecer contexto.
- En segunda vuelta deberian aparecer dos candidaturas principales mas blancos
  y nulos.

## JNE - Power BI scraper

Fuente:

```text
https://web.jne.gob.pe/reporteactasobservadas/
```

Metodo:

- Playwright carga el reporte publico.
- Intercepta respuestas `/public/reports/querydata`.
- Parseo DSR v2: `DM0..DMN`, `R` bitmask, segmentos `S` y `C`.
- Guarda medidas en `kpi_measures` y tablas en `jje_detail`, `actas_by_type` y
  `jee_porcentaje`.

KPIs principales usados por el dashboard:

| Measure | Lectura |
|---|---|
| `ActasObservadas.PorcentajeAvance` | Avance general |
| `ActasObservadas.ActasObservadas` | Actas observadas |
| `ActasObservadas.ActasProcesadas` | Actas observadas con expedientes creados |
| `ActasObservadas.ActasEnTramite` | Expedientes en tramite |
| `ActasObservadas.ActasRecuento` | Actas enviadas a recuento |
| `ActasObservadas.MedidaAudienciasRealizadas` | Audiencias realizadas |
| `ActasObservadas.ExpedientesFaltantes` | Expedientes faltantes |
| `ActasObservadas.FechaActualizacion` | Fecha oficial del reporte |

Si el Power BI cambia nombres internos, revisar `KPI_LABELS` y usos de
`kpi_value()` en `dashboard.py`.

## Dashboard

Titulo:

```text
Segunda vuelta de la Eleccion Presidencial Peru 2026
```

Caption:

```text
Seguimiento de los datos electorales publicados por la ONPE y el JNE, con capturas periodicas para analizar avance y evolucion temporal.
```

Pestanas:

- `Resumen`
- `ONPE`
  - `Actual`
  - `Evolucion`
- `JNE`
  - `Actual`
  - `Evolucion`
- `Monitoreo`
- `Actualizacion`

Lenguaje de usuario:

- Usar "consultas", no "corridas".
- Evitar jerga de scraping en textos visibles.
- Los cards deben explicar indicadores en lenguaje electoral.

## Flujo de cambios con Codex

Para cualquier Codex en cualquier computadora:

1. Leer este archivo.
2. Revisar `git status --short`.
3. Hacer cambios pequenos y verificables.
4. Ejecutar al menos:

```bash
python -m py_compile dashboard.py database.py scripts/scrape_once.py
```

5. Si se toca dashboard, probar localmente:

```bash
streamlit run dashboard.py
```

6. Commit y push a `main` si el usuario lo pide o si el cambio debe desplegar.

Streamlit redeploya el dashboard desde GitHub. Azure debera redeployar o
reconstruir la imagen de agentes cuando cambie codigo de scrapers o base.

## Tareas pendientes prioritarias

1. Crear `Dockerfile` para los agentes.
2. Crear Azure Container Apps Environment.
3. Crear Azure Container Registry o usar GitHub Container Registry.
4. Crear Azure Container Apps Job programado cada 15 minutos.
5. Configurar secretos en Azure.
6. Ejecutar job manual y revisar logs:
   - ONPE debe traer `totales=si` y candidaturas.
   - JNE debe traer tablas y medidas.
7. Si ONPE sale vacio desde Azure, separar diagnostico de ONPE y JNE.
8. Dejar GitHub Actions como respaldo/manual, no como scheduler principal.

## Reglas de seguridad

- Nunca commitear contrasenas, `DATABASE_URL` real, tokens ni claves Azure.
- Usar secrets en Streamlit, GitHub Actions y Azure.
- No borrar datos de Supabase sin confirmacion explicita.
- No revertir cambios de otros colaboradores sin revisar.

## Referencias utiles

- Guia Azure del proyecto: `docs/AZURE_AGENTS.md`
- Publicacion: `docs/DEPLOYMENT.md`
- Brief del dashboard: `docs/DASHBOARD_BRIEF.md`
- Imagenes de referencia: `docs/reference_images/README.md`
