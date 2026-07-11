# 🔨 Subastas BOE → Telegram

Bot que revisa cada día el [Portal de Subastas del BOE](https://subastas.boe.es) y envía por Telegram las subastas que **terminan en las próximas 24 horas**:

- 🏠 Viviendas en Madrid
- 🚗 Vehículos en toda España

Se ejecuta automáticamente todos los días mediante GitHub Actions — no necesitas ningún servidor.

## 📋 Requisitos

- Python 3.10+
- Un bot de Telegram (token) y el `chat_id` donde quieres recibir los avisos

### Crear el bot de Telegram

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram → `/newbot` → sigue los pasos → guarda el **token**
2. Escríbele algo a tu bot recién creado (cualquier mensaje, para "activar" el chat)
3. Averigua tu `chat_id` visitando (con tu token):
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   y buscando el campo `"chat":{"id": ...}` en la respuesta

## 🛠️ Instalación local

```bash
git clone <url-del-repo>
cd <nombre-del-repo>
pip install -r requirements.txt
```

`requirements.txt`:
```
requests
beautifulsoup4
```

### Variables de entorno

Crea un archivo `.env` (o expórtalas directamente en tu terminal):

```bash
export TELEGRAM_TOKEN="123456789:AAExampleTokenAquiNoEsReal"
export TELEGRAM_CHAT_ID="987654321"
```

## 🚀 Uso

### Ejecución normal (lo que corre cada día en producción)

```bash
python script.py
```

Busca viviendas en Madrid y vehículos en toda España que terminen en las próximas 24h, y envía **dos mensajes** de Telegram (uno por bloque).

### Modo test

Para comprobar que el scraping y el formateo funcionan bien, sin depender de que haya subastas terminando justo ahora:

```bash
# Imprime por consola los 10 resultados más recientes de cada bloque,
# sin filtrar por fecha de fin
python script.py --test

# Igual, pero además los envía a Telegram para ver cómo queda el formato ahí
python script.py --test --telegram
```

## ⚙️ Despliegue automático (GitHub Actions)

El repo incluye un workflow (`.github/workflows/subastas.yml`) que ejecuta `script.py` todos los días automáticamente, gratis, sin necesidad de servidor.

### 1. Configurar los secrets

En tu repositorio de GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Nombre               | Valor                          |
|-----------------------|--------------------------------|
| `TELEGRAM_TOKEN`      | El token de tu bot             |
| `TELEGRAM_CHAT_ID`    | Tu chat_id                     |

### 2. El workflow

```yaml
name: BOE Subastas Diario
on:
  schedule:
    - cron: '0 7 * * *'   # 07:00 UTC ≈ 09:00 hora España (ajustar en verano/invierno)
  workflow_dispatch:        # permite lanzarlo manualmente desde la pestaña Actions

jobs:
  scrape-and-notify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python script.py
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

### 3. Probar manualmente

Ve a la pestaña **Actions** del repo → selecciona el workflow **BOE Subastas Diario** → **Run workflow**. Así puedes lanzarlo a mano sin esperar al cron, y ver los logs si algo falla.

> ⚠️ El cron de GitHub Actions va en UTC. España usa CET (UTC+1) en invierno y CEST (UTC+2) en verano, así que la hora real de llegada del mensaje puede variar ±1h según la época del año. Si te importa que sea siempre exactamente a las 9:00 hora española, hay que ajustar el cron dos veces al año o comprobar la hora dentro del propio script.

## 📁 Estructura del proyecto

```
.
├── script.py              # Script principal
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── subastas.yml    # Workflow de GitHub Actions (cron diario)
```

## 🧩 Cómo funciona

1. `construir_payload()` genera los parámetros de búsqueda que espera el formulario de `subastas_ava.php` (tipo de bien, localidad, rango de fechas de fin, etc.)
2. `buscar()` hace la petición POST con sesión (cookies) y devuelve el HTML de resultados
3. `parsear_resultados()` extrae cada subasta (`<li class="resultado-busqueda">`) con BeautifulSoup: id, autoridad, descripción, fecha de fin y enlace al detalle
4. `filtrar_proximas_24h()` se queda solo con las que terminan en las próximas 24h
5. `formatear_mensaje()` genera el texto en Markdown para Telegram, con emoji según el tipo de bien (🏠 vivienda, 🏍️/🚗/🚙/🚐/🚛/🚌 según tipo de vehículo)
6. `enviar_telegram()` manda el mensaje vía la API de Telegram Bot

## ⚠️ Notas y limitaciones

- El `robots.txt` de `subastas.boe.es` desaconseja el acceso automatizado a esta ruta. Este script está pensado para **uso personal, no comercial, con una única ejecución diaria** — evita aumentar la frecuencia de las peticiones.
- `page_hits=50`: si algún día hay más de 50 resultados en el rango de búsqueda usado internamente, podrían quedarse fuera algunos. Para el volumen habitual (24h de vivienda en Madrid o vehículos en España) no debería ser un problema.
- Los datos son informativos. Verifica siempre los detalles de cada subasta en el portal oficial antes de tomar cualquier decisión.

## 📄 Licencia

Uso personal. Los datos pertenecen a la Agencia Estatal Boletín Oficial del Estado.
