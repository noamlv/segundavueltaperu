# Publicación: GitHub, Supabase, Streamlit y Azure Agents

## 1. GitHub

Crear un repositorio vacío y conectar el remoto:

```bash
git init
git branch -M main
git remote add origin https://github.com/noamlv/<repo>.git
git add .
git commit -m "Initial electoral monitoring dashboard"
git push -u origin main
```

## 2. Supabase

Usar Supabase como Postgres productivo:

```bash
export DATABASE_URL="postgresql://..."
python scripts/scrape_once.py
```

El código crea las tablas automáticamente si no existen.

## 3. Streamlit Community Cloud

Publicar el dashboard desde `https://share.streamlit.io`:

- Repository: `noamlv/<repo>`
- Branch: `main`
- Main file path: `dashboard.py`
- App URL: elegir un subdominio propio si está disponible

En **Advanced settings > Secrets**, agregar:

```toml
DATABASE_URL = "postgresql://..."
```

Streamlit Community Cloud ejecuta el dashboard. Los scrapers no deben depender del proceso de Streamlit.

## 4. Scrapers

Configurar `DATABASE_URL` como GitHub Actions Secret.

El workflow `.github/workflows/scrape.yml` ejecuta:

```bash
python scripts/scrape_once.py
```

Para empezar una nueva ventana historica desde cero:

```bash
python scripts/reset_snapshots.py --yes-reset-election-data
python scripts/scrape_once.py
```

El primer comando borra todas las capturas ONPE/JNE de la base configurada. El
segundo comando carga la primera captura nueva.

GitHub Actions queda como respaldo/manual. En pruebas del proyecto no entrego
cadencia confiable cada 15 minutos y ONPE devolvio payload vacio desde runners
de GitHub. La arquitectura objetivo es mover el scheduler principal a Azure
Container Apps Jobs.

## 5. Azure Container Apps Jobs

Azure ejecutara los agentes programados. Debe correr:

```bash
python scripts/scrape_once.py
```

cada 15 minutos y escribir en Supabase con los secretos:

- `DATABASE_URL`
- `JNE_POWERBI_URL`
- `JNE_WAIT_SECONDS`

Ver guia completa en:

```text
docs/AZURE_AGENTS.md
```
