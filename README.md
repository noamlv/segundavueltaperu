# Segunda vuelta de la Elección Presidencial Perú 2026

Dashboard y scrapers para monitorear resultados ONPE y actas observadas del JNE con capturas históricas.

## Qué incluye

- Dashboard Streamlit con Resumen, ONPE, JNE, Monitoreo y Actualización.
- Scraper ONPE desde API pública.
- Scraper JNE desde dashboard Power BI público.
- Persistencia local en SQLite como fallback.
- Persistencia productiva en Supabase/Postgres usando `DATABASE_URL`.
- Workflow de GitHub Actions como respaldo/manual.
- Arquitectura objetivo con Azure Container Apps Jobs para ejecutar agentes cada 15 minutos.

## Desarrollo local

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -m streamlit run dashboard.py
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
streamlit run dashboard.py
```

Si `DATABASE_URL` no está configurado, el proyecto usa `data/electoral.db`.

## Supabase

1. Crear un proyecto en Supabase.
2. Copiar el connection string Postgres.
3. Guardarlo como `DATABASE_URL` en GitHub Actions y en el entorno de despliegue.
4. Ejecutar `python scripts/scrape_once.py` una vez para crear tablas y cargar datos.

## Scrapers

Ejecutar una captura ONPE + JNE:

```bash
python scripts/scrape_once.py
```

Ejecutar solo ONPE mientras la segunda vuelta se actualiza rapido:

```bash
python scripts/scrape_once.py --source onpe
```

Reiniciar el historico para una nueva etapa electoral, por ejemplo segunda
vuelta:

```bash
python scripts/reset_snapshots.py --yes-reset-election-data
python scripts/scrape_once.py
```

Reiniciar solo JNE cuando el JNE todavia no publica segunda vuelta o sigue
mostrando datos anteriores:

```bash
python scripts/reset_snapshots.py --source jne --yes-reset-election-data
```

Este reinicio borra las capturas ONPE/JNE guardadas en la base configurada por
`DATABASE_URL`. No ejecutar sin confirmar que se quiere empezar el historico en
cero.

El workflow `.github/workflows/scrape.yml` puede ejecutarse manualmente y queda como respaldo. GitHub Actions no debe considerarse scheduler estricto de 15 minutos.

Secrets requeridos:

- `DATABASE_URL`: conexión Postgres/Supabase.

Variables opcionales:

- `JNE_POWERBI_URL`
- `JNE_WAIT_SECONDS`

## Azure

La tarea pendiente principal es mover los agentes a Azure Container Apps Jobs para que corran cada 15 minutos con mayor estabilidad que GitHub Actions.

Guia detallada:

```text
docs/AZURE_AGENTS.md
```

## Documentación para Codex

Antes de continuar el proyecto desde otra computadora o usuario, leer:

```text
ARCHITECTURE.md
docs/AZURE_AGENTS.md
docs/DEPLOYMENT.md
docs/DASHBOARD_BRIEF.md
```

## Datos no versionados

Los archivos crudos, CSV, screenshots y SQLite local están excluidos por `.gitignore`.
