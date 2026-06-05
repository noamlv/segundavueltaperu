# Segunda vuelta presidencial Peru 2026 - arquitectura y handoff para Codex

Este archivo es la memoria principal del proyecto. Codex debe leerlo antes de
modificar el dashboard, los scrapers, la base de datos o el despliegue.

## Estado actual

- Repositorio: `https://github.com/noamlv/segundavueltaperu`
- Rama principal: `main`
- Dashboard publico: Streamlit Community Cloud
- Base productiva: Supabase/Postgres
- Scheduler actual: GitHub Actions como respaldo, no como scheduler confiable
- Scheduler probado: Azure Container Apps Jobs funciona para JNE/Supabase, pero
  no quedo apto para ONPE por degradacion de la API desde varias IPs Azure
- Usuario colaborador operativo: `addmoeueperu`

Nota de cuenta: en GitHub el colaborador aparece como `addmoeueperu`. Si en la
conversacion aparece como `addmoeperu` o `addmoeuperu`, tratarlo como una
variante escrita y verificar la ortografia antes de conectar Azure. La tarea de
Azure debe hacerse desde la otra computadora Windows usando la cuenta
GitHub/Azure de `addmoeueperu`.

El dashboard esta funcionando y lee datos desde Supabase. Se probo mover los
agentes ONPE/JNE desde GitHub Actions a Azure Jobs para ejecutar
`python scripts/scrape_once.py` cada 15 minutos. Azure ejecuto y guardo en
Supabase correctamente, pero ONPE devolvio respuestas degradadas desde IPs de
Azure; por eso Azure no debe considerarse solucion cerrada para ONPE.

## Arquitectura objetivo

```text
Codex / desarrollo local
        |
        v
GitHub: noamlv/segundavueltaperu
        |                         \
        |                          \
        v                           v
Streamlit Community Cloud        Scheduler de agentes
dashboard.py                     scripts/scrape_once.py cada 15 min
        |                           |
        |                           v
        +----------------------> Supabase/Postgres
                                  snapshot historico ONPE/JNE
```

GitHub se mantiene como repositorio y fuente de verdad. Streamlit publica la
web. Supabase guarda los datos. El scheduler debe ejecutar los agentes sin
degradar ONPE; Azure quedo validado solo parcialmente.

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

### Azure probado

El 5 de junio de 2026 se creo y valido infraestructura Azure desde Windows con
la cuenta institucional asociada a `addmoeueperu`:

- Resource group: `rg-segunda-vuelta-peru`
- ACR: `acralelectoraldce54871`
- Environment productivo inicial: `env-electoral-agents` en `West US 2`
- Job inicial: `job-electoral-scrapers`
- Imagen: `acralelectoraldce54871.azurecr.io/segundavueltaperu-agents:latest`
- Cron: `*/15 * * * *`

El job ejecuta:

```bash
python scripts/scrape_once.py
```

con estos secretos:

- `DATABASE_URL`
- `JNE_POWERBI_URL`
- `JNE_WAIT_SECONDS`

Resultados comprobados en logs:

- Supabase/Postgres: guardado correcto.
- JNE: correcto desde Azure; ejemplo validado `tablas=3, medidas=33`.
- ONPE en `West US 2`: incorrecto; devuelve `totales=no, candidaturas=0`.
- Diagnostico ONPE en `Brazil South`: incorrecto; los endpoints API devuelven
  HTML de la app (`len=35808`) y no JSON.
- Diagnostico ONPE en `East US`: parcialmente bueno; algunas IPs Azure
  devuelven JSON y otras devuelven HTML. Sin IP fija, Container Apps puede
  alternar entre salida buena y mala.

Conclusion: Azure Container Apps Jobs sirve para ejecutar y guardar JNE, pero
no es confiable para ONPE mientras la salida de red no este controlada. Ver guia
detallada y bitacora en `docs/AZURE_AGENTS.md`.

Prompt recomendado para Codex en la otra PC:

```text
Lee ARCHITECTURE.md y docs/AZURE_AGENTS.md. Estoy en Windows con el usuario
GitHub addmoeueperu y una cuenta institucional de Azure. Necesito crear rapido
los Azure Container Apps Jobs para este proyecto, correr scripts/scrape_once.py
cada 15 minutos, guardar en Supabase y validar en logs que ONPE traiga totales
y candidaturas y que JNE traiga tablas y medidas. Hazlo de principio a fin y no
commitees secretos.
```

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

En PowerShell, con la cuenta `addmoeueperu` autenticada en GitHub:

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

Actualizacion del 5 de junio de 2026:

- ONPE desde esta PC Windows local respondio correctamente: totales y 38
  candidaturas.
- ONPE desde Azure `West US 2` devolvio vacio en el scraper productivo.
- Diagnostico endpoint por endpoint mostro que Azure `West US 2` recibia HTML
  (`JSONDecodeError`) donde local recibia JSON.
- `Brazil South` fallo igual que `West US 2`.
- `East US` fue intermitente: 4 de 5 diagnosticos devolvieron JSON con 38
  candidaturas, 1 de 5 devolvio HTML. Esto apunta a degradacion por IP de
  salida, no a datos estabilizados.
- DNS local resolvio `resultadoelectoral.onpe.gob.pe` a IPs `54.230.124.*`;
  con `httpx` y DNS forzado local esas IPs devolvieron JSON. Falta validar si
  forzar IP o usar NAT Gateway/IP fija desde Azure estabiliza ONPE.

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

Tareas pendientes despues de la prueba Azure:

1. Decidir scheduler definitivo para ONPE:
   - maquina local/no-Azure con salida ya validada;
   - self-hosted runner;
   - otro proveedor;
   - o Azure con egress controlado por NAT Gateway/IP fija si el diagnostico lo
     confirma.
2. Mantener JNE en Azure o migrarlo junto con ONPE para simplificar operacion.
3. Si se insiste con Azure para ONPE, probar:
   - Container Apps en `East US` con NAT Gateway e IP publica fija;
   - `ONPE_FORCE_IP`/resolucion forzada hacia un edge ONPE que devuelva JSON;
   - separar ONPE y JNE en jobs distintos para evitar que fallas ONPE afecten
     JNE.
4. No borrar capturas ONPE vacias: sirven como evidencia de degradacion de red.
5. Dejar GitHub Actions como respaldo/manual, no como scheduler principal.

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
