# Segunda vuelta de la Elección Presidencial Perú 2026

Dashboard y scrapers para monitorear resultados ONPE y actas observadas del JNE con capturas históricas cada 15 minutos.

## Qué incluye

- Dashboard Streamlit con Resumen, ONPE, JNE, Monitoreo y Actualización.
- Scraper ONPE desde API pública.
- Scraper JNE desde dashboard Power BI público.
- Persistencia local en SQLite.
- Persistencia productiva en Supabase/Postgres usando `DATABASE_URL`.
- Workflow de GitHub Actions para ejecutar ambos scrapers cada 15 minutos.

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python onpe_scraper.py --db
python pbi_scraper.py --url "https://web.jne.gob.pe/reporteactasobservadas/" --db
python -m streamlit run dashboard.py
```

Si `DATABASE_URL` no está configurado, el proyecto usa `data/electoral.db`.

## Supabase

1. Crear un proyecto en Supabase.
2. Copiar el connection string Postgres.
3. Guardarlo como `DATABASE_URL` en GitHub Actions y en el entorno de despliegue.
4. Ejecutar `python scripts/scrape_once.py` una vez para crear tablas y cargar datos.

## GitHub Actions

El workflow `.github/workflows/scrape.yml` corre cada 15 minutos y también puede ejecutarse manualmente.

Secrets requeridos:

- `DATABASE_URL`: conexión Postgres/Supabase.

Variables opcionales:

- `JNE_POWERBI_URL`
- `JNE_WAIT_SECONDS`

## Vercel

El dashboard actual está hecho en Streamlit. Vercel es excelente para una app web Next.js, pero Streamlit necesita un proceso web persistente y no es el encaje natural de Vercel Serverless.

Opciones:

- Mantener Streamlit para análisis interno/local y desplegar una versión Next.js en Vercel leyendo Supabase.
- Desplegar Streamlit en un servicio compatible con procesos persistentes.
- Usar Vercel para una futura capa pública y GitHub Actions/Supabase para datos.

## Datos no versionados

Los archivos crudos, CSV, screenshots y SQLite local están excluidos por `.gitignore`.
