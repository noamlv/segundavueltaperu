# Publicación: GitHub, Supabase y Vercel

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

## 3. Scrapers cada 15 minutos

Configurar `DATABASE_URL` como GitHub Actions Secret.

El workflow `.github/workflows/scrape.yml` ejecuta:

```bash
python scripts/scrape_once.py
```

## 4. Vercel

La app actual es Streamlit. Para Vercel, el camino recomendado es construir una capa web Next.js que lea Supabase. El repositorio queda preparado para datos y dashboard analítico, pero no fuerza un `vercel.json` engañoso para Streamlit.

Cuando se implemente la capa Next.js:

- Vercel recibirá `DATABASE_URL`.
- La UI pública leerá tablas agregadas desde Supabase.
- Los scrapers seguirán corriendo por GitHub Actions o un scheduler dedicado.
