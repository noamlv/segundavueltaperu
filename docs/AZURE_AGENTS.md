# Azure Agents - guia para correr scrapers cada 15 minutos

Objetivo: usar Azure solo como ejecutor programado de agentes. GitHub sigue
siendo el repositorio, Supabase la base de datos y Streamlit la web publica.

## Estado de la prueba Azure del 5 de junio de 2026

Azure Container Apps Jobs se pudo crear y ejecutar, pero no quedo como solucion
confiable para ONPE.

Recursos creados y probados:

- Resource group: `rg-segunda-vuelta-peru`
- ACR: `acralelectoraldce54871`
- Imagen: `acralelectoraldce54871.azurecr.io/segundavueltaperu-agents:latest`
- Environment inicial: `env-electoral-agents` en `West US 2`
- Job inicial: `job-electoral-scrapers`
- Cron: `*/15 * * * *`
- Secretos cargados en Azure: `database-url`, `jne-powerbi-url`

Resultados:

- Azure ejecuto el contenedor y guardo en Supabase.
- JNE funciono desde Azure; logs validados con `JNE payload: tablas=3,
  medidas=33`.
- ONPE no funciono de forma confiable desde Azure; el scraper guardo capturas
  vacias con `ONPE payload: totales=no, candidaturas=0`.
- ONPE desde la PC Windows local, en el mismo periodo, si devolvio totales y 38
  candidaturas.

Diagnostico tecnico:

- Local: endpoints ONPE devuelven JSON valido:
  - `totals`: `status=200`, `len=489`, `success=True`, `data=dict`
  - `candidates`: `status=200`, `len=9537`, `success=True`, `data=list:38`
- Azure `West US 2`: endpoints ONPE devuelven HTML de la app:
  - `status=200`, `len=35808`, `json_error=JSONDecodeError`
- Azure `Brazil South`: mismo fallo que `West US 2`.
- Azure `East US`: intermitente. En una muestra de 5 ejecuciones:
  - 4 IPs de salida devolvieron JSON correcto con `candidates=list:38`.
  - 1 IP de salida devolvio HTML `len=35808`.

Conclusion: no es que ONPE no tenga actualizaciones. La API sigue devolviendo
datos desde la red local. El problema es la salida de red/IP de Azure: algunos
origenes reciben HTML donde deberian recibir JSON. Azure solo seria viable para
ONPE si se controla el egress con una IP que se haya validado, por ejemplo con
NAT Gateway en `East US`, o si se fuerza una resolucion/IP ONPE que devuelva
JSON desde Azure.

Recomendacion actual:

- No usar el job Azure de `West US 2` como fuente principal ONPE.
- Mantener Azure solo para JNE, o migrar ambos agentes a una salida no-Azure.
- Si se quiere insistir con Azure, crear una prueba aislada en `East US` con
  VNet + NAT Gateway + IP fija, ejecutar `scripts/onpe_diagnostic.py` varias
  veces y solo promover a produccion si ONPE devuelve JSON estable.

Esta guia esta pensada para ejecutarse desde la otra computadora Windows con el
usuario GitHub/Azure `addmoeueperu`. Si aparece escrito como `addmoeperu` o
`addmoeuperu` en una conversacion, confirmar la ortografia: en el repositorio el
colaborador visible es `addmoeueperu`.

## Tarea para Codex en Windows

Cuando se abra Codex en la otra computadora, pedirle:

```text
Lee ARCHITECTURE.md y docs/AZURE_AGENTS.md. Estoy en Windows con el usuario
GitHub addmoeueperu y una cuenta institucional de Azure. Necesito crear rapido
los Azure Container Apps Jobs para este proyecto, correr scripts/scrape_once.py
cada 15 minutos, guardar en Supabase y validar en logs que ONPE traiga totales
y candidaturas y que JNE traiga tablas y medidas. Hazlo de principio a fin y no
commitees secretos.
```

La tarea concreta de esa sesion es:

1. Clonar o actualizar `https://github.com/noamlv/segundavueltaperu`.
2. Probar `DATABASE_URL` y `scripts/scrape_once.py` localmente.
3. Crear el `Dockerfile` si todavia no existe.
4. Crear Azure Container Registry o elegir GitHub Container Registry.
5. Crear Azure Container Apps Environment.
6. Crear Azure Container Apps Job con cron `*/15 * * * *`.
7. Cargar secretos en Azure.
8. Ejecutar el job manualmente y revisar logs.
9. Confirmar que el dashboard ve nuevas capturas en Supabase.

## Resultado esperado

Un Azure Container Apps Job ejecuta:

```bash
python scripts/scrape_once.py
```

cada 15 minutos y guarda una captura ONPE y una captura JNE en Supabase.

Nota posterior a la prueba: este resultado esperado no se cumplio para ONPE en
Azure sin egress controlado. Si se usa Azure, validar ONPE con
`scripts/onpe_diagnostic.py` antes de confiar en el job programado.

## Por que no GitHub Actions como scheduler principal

GitHub Actions queda como respaldo/manual. En pruebas reales del proyecto no
disparo cada 15 minutos de forma confiable, y ONPE devolvio payload vacio desde
los runners de GitHub aunque respondia bien desde una maquina local.

Azure debe validarse con una ejecucion real. El criterio minimo es:

```text
ONPE payload: totales=si, candidaturas>0
JNE payload: tablas>=1, medidas>=1
```

## Requisitos

En la computadora Windows con la cuenta `addmoeueperu`:

- Git instalado.
- Python 3.11 instalado.
- Azure CLI instalado.
- GitHub CLI opcional.
- Acceso al repo `noamlv/segundavueltaperu`.
- Cuenta Azure institucional con permisos para crear recursos.

Instalacion rapida en PowerShell:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.11 -e
winget install --id Microsoft.AzureCLI -e
winget install --id GitHub.cli -e
```

Cerrar y reabrir PowerShell despues de instalar.

## Clonar el repo en Windows

```powershell
gh auth login

cd $HOME\Documents
git clone https://github.com/noamlv/segundavueltaperu.git
cd segundavueltaperu

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Prueba local:

```powershell
streamlit run dashboard.py
```

## Secretos necesarios

No escribir estos valores en archivos del repo.

```text
DATABASE_URL
JNE_POWERBI_URL
JNE_WAIT_SECONDS
```

Plantilla de `DATABASE_URL`:

```text
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-1-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
```

Valores sugeridos:

```text
JNE_POWERBI_URL=https://web.jne.gob.pe/reporteactasobservadas/
JNE_WAIT_SECONDS=25
```

## Paso 1: probar acceso a Supabase desde Windows

En PowerShell, solo para esta sesion:

```powershell
$env:DATABASE_URL="postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-1-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require"
python scripts/check_database.py
```

Debe salir algo como:

```text
Conexión Postgres OK: user=postgres, database=postgres
```

## Paso 2: probar scrapers desde Windows

```powershell
$env:JNE_POWERBI_URL="https://web.jne.gob.pe/reporteactasobservadas/"
$env:JNE_WAIT_SECONDS="25"
python scripts/scrape_once.py
```

Validar logs:

```text
ONPE payload: totales=si, candidaturas=...
ONPE saved as run_id=...
JNE payload: tablas=..., medidas=...
JNE saved as run_id=...
```

Si ONPE falla localmente en Windows pero funciona en Mac, revisar red,
certificados, HTTP/2 o bloqueo temporal de la fuente.

## Paso 3: crear Dockerfile para agentes

Si aun no existe `Dockerfile`, crear uno en la raiz del repo. Plantilla:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . .

CMD ["python", "scripts/scrape_once.py"]
```

Notas:

- Este contenedor corre una vez y termina.
- No debe levantar Streamlit.
- Si la imagen queda muy pesada, optimizar despues; primero validar operacion.

## Paso 4: login en Azure

```powershell
az login
az account show
```

Si hay varias suscripciones:

```powershell
az account list --output table
az account set --subscription "<SUBSCRIPTION_ID_O_NOMBRE>"
```

## Paso 5: variables de trabajo

Usar nombres unicos. `ACR_NAME` debe ser globalmente unico y solo letras/numeros.

```powershell
$LOCATION="westus2"
$RESOURCE_GROUP="rg-segunda-vuelta-peru"
$ACR_NAME="acralelectoralperu"
$ENV_NAME="env-electoral-agents"
$JOB_NAME="job-electoral-scrapers"
$IMAGE_NAME="segundavueltaperu-agents:latest"
```

## Paso 6: crear Resource Group

```powershell
az group create `
  --name $RESOURCE_GROUP `
  --location $LOCATION
```

## Paso 7: crear Azure Container Registry

```powershell
az acr create `
  --resource-group $RESOURCE_GROUP `
  --name $ACR_NAME `
  --sku Basic `
  --admin-enabled true
```

Construir y subir imagen desde el repo:

```powershell
az acr build `
  --registry $ACR_NAME `
  --image $IMAGE_NAME `
  .
```

Obtener credenciales del registry:

```powershell
$ACR_SERVER = az acr show --name $ACR_NAME --query "loginServer" -o tsv
$ACR_USER = az acr credential show --name $ACR_NAME --query "username" -o tsv
$ACR_PASS = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
```

## Paso 8: crear Container Apps Environment

```powershell
az containerapp env create `
  --name $ENV_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION
```

## Paso 9: crear Job programado

Cron cada 15 minutos:

```text
*/15 * * * *
```

Azure Container Apps Jobs usa expresiones cron de cinco campos y las evalua en
UTC. Para una frecuencia cada 15 minutos, UTC/Lima no cambia el intervalo. Si
luego se restringe a una ventana horaria electoral, convertir primero la hora de
Lima a UTC.

Crear el job:

```powershell
az containerapp job create `
  --name $JOB_NAME `
  --resource-group $RESOURCE_GROUP `
  --environment $ENV_NAME `
  --trigger-type Schedule `
  --cron-expression "*/15 * * * *" `
  --replica-timeout 720 `
  --replica-retry-limit 1 `
  --replica-completion-count 1 `
  --parallelism 1 `
  --image "$ACR_SERVER/$IMAGE_NAME" `
  --registry-server $ACR_SERVER `
  --registry-username $ACR_USER `
  --registry-password $ACR_PASS `
  --secrets `
      database-url="postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-1-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require" `
      jne-powerbi-url="https://web.jne.gob.pe/reporteactasobservadas/" `
  --env-vars `
      DATABASE_URL=secretref:database-url `
      JNE_POWERBI_URL=secretref:jne-powerbi-url `
      JNE_WAIT_SECONDS=25
```

Si Azure CLI rechaza algun parametro por version, actualizar:

```powershell
az upgrade
az extension add --name containerapp --upgrade
```

## Paso 10: ejecutar una prueba manual

```powershell
az containerapp job start `
  --name $JOB_NAME `
  --resource-group $RESOURCE_GROUP
```

Luego revisar ejecuciones:

```powershell
az containerapp job execution list `
  --name $JOB_NAME `
  --resource-group $RESOURCE_GROUP `
  --output table
```

Tambien revisar en Azure Portal:

```text
Container Apps Job -> Executions -> ultima ejecucion -> Logs
```

Buscar:

```text
ONPE payload: totales=si, candidaturas=...
JNE payload: tablas=..., medidas=...
```

## Paso 11: validar en Supabase y dashboard

En Supabase:

```sql
select source, count(*), max(scraped_at)
from scrape_runs
group by source
order by source;
```

Para ver las ultimas capturas:

```sql
select id, source, scraped_at, created_at
from scrape_runs
order by id desc
limit 20;
```

En Streamlit:

- Ver pestana `Monitoreo`.
- Confirmar que ONPE y JNE tengan capturas recientes.
- Confirmar que las graficas de evolucion tengan puntos nuevos.

## Si ONPE viene vacio desde Azure

El dashboard mantiene la ultima ONPE valida, pero operativamente hay que
investigar.

Checklist:

1. Ejecutar `python onpe_scraper.py` localmente en Windows con la misma red.
2. Comparar logs Azure vs local.
3. Probar otra region de Azure (`eastus`, `westus2`, etc.).
4. Separar ONPE y JNE en dos jobs para aislar tiempos y fallas.
5. Revisar headers en `onpe_scraper.py`.
6. Confirmar si ONPE bloquea o degrada IPs de nube.

### Evidencia ya recolectada

Se agrego `scripts/onpe_diagnostic.py` para comparar la respuesta ONPE por
endpoint sin guardar datos ni exponer secretos. La salida esperada cuando ONPE
funciona es:

```text
DIAG totals status=200 ... success=True data=dict:...
DIAG candidates status=200 ... success=True data=list:38
```

La salida observada cuando Azure falla es:

```text
DIAG totals status=200 ... len=35808 ... json_error=JSONDecodeError
DIAG candidates status=200 ... len=35808 ... json_error=JSONDecodeError
```

Ese `len=35808` coincide con la pagina HTML principal de ONPE, no con JSON de
la API.

### Regiones probadas

| Region Azure | Resultado ONPE | Nota |
|---|---|---|
| `westus2` | Falla | API devuelve HTML, scraper guarda ONPE vacio |
| `brazilsouth` | Falla | Igual que `westus2` |
| `eastus` | Intermitente | 4/5 diagnosticos OK, 1/5 devolvio HTML |

### Proxima prueba Azure si se insiste

1. Crear un Container Apps Environment nuevo en `East US` dentro de VNet.
2. Asociar NAT Gateway con IP publica fija.
3. Ejecutar `scripts/onpe_diagnostic.py` varias veces.
4. Promover esa configuracion solo si:

```text
ONPE totals: success=True data=dict
ONPE candidates: success=True data=list:38
```

Si la IP fija falla, pasar ONPE a una maquina/red no-Azure.

## Operacion recomendada

- Mantener GitHub Actions activado solo como respaldo.
- Azure puede usarse para JNE, pero no debe ser el scheduler principal de ONPE
  sin resolver la degradacion de red.
- No borrar datos vacios sin diagnostico; sirven para monitoreo de fallos.
- Si durante la jornada electoral ONPE/JNE cambian estructura, priorizar:
  1. que el scraper no caiga;
  2. que guarde logs claros;
  3. que el dashboard mantenga ultimo dato valido;
  4. luego ajustar visualizaciones.

## Referencias oficiales

- Azure Container Apps Jobs:
  `https://learn.microsoft.com/azure/container-apps/jobs`
- Azure Container Registry:
  `https://learn.microsoft.com/azure/container-registry/`
- Azure CLI Container Apps:
  `https://learn.microsoft.com/cli/azure/containerapp`
