"""
Scraper diario de subastas.boe.es
- Bloque 1: Viviendas en Madrid que terminan en las próximas 24h
- Bloque 2: Vehículos en toda España que terminan en las próximas 24h
Envía un mensaje de Telegram por cada bloque.
"""

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

MADRID_TZ = ZoneInfo("Europe/Madrid")
URL = "https://subastas.boe.es/subastas_ava.php"
BASE_URL = "https://subastas.boe.es/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScraperPersonalSubastas/1.0; +uso personal no comercial)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": URL,
}

# --------------------------------------------------------------------------
# Emojis por tipo de bien
# --------------------------------------------------------------------------

def emoji_vehiculo(descripcion: str) -> str:
    desc = descripcion.upper()
    if "MOTOCICLETA" in desc or "MOTO " in desc:
        return "🏍️"
    if "CICLOMOTOR" in desc:
        return "🛵"
    if "TODO TERRENO" in desc or "SUV" in desc:
        return "🚙"
    if "FURGONETA" in desc or "FURGON" in desc:
        return "🚐"
    if "CAMION" in desc or "CAMIÓN" in desc:
        return "🚛"
    if "AUTOBUS" in desc or "AUTOBÚS" in desc or "AUTOCAR" in desc:
        return "🚌"
    if "REMOLQUE" in desc:
        return "🚚"
    if "TURISMO" in desc:
        return "🚗"
    return "🚗"  # por defecto, cualquier otro vehículo a motor


EMOJI_VIVIENDA = "🏠"


# --------------------------------------------------------------------------
# Construcción del payload de búsqueda
# --------------------------------------------------------------------------

def construir_payload(bien_tipo, subtipo="", localidad="", cod_provincia="", dias_rango=2):
    """
    bien_tipo: 'I' (inmuebles) o 'V' (vehículos)
    subtipo:   solo aplica a inmuebles (ej. '501' = vivienda). Dejar vacío para vehículos.
    """
    hoy = datetime.now(MADRID_TZ).date()
    fin_rango = hoy + timedelta(days=dias_rango)

    return {
        "campo[0]": "SUBASTA.ORIGEN", "dato[0]": "",
        "campo[1]": "SUBASTA.AUTORIDAD", "dato[1]": "",
        "campo[2]": "SUBASTA.ESTADO.CODIGO", "dato[2]": "",
        "campo[3]": "BIEN.TIPO", "dato[3]": bien_tipo, "dato[4]": subtipo,
        "campo[5]": "BIEN.DIRECCION", "dato[5]": "",
        "campo[6]": "BIEN.CODPOSTAL", "dato[6]": "",
        "campo[7]": "BIEN.LOCALIDAD", "dato[7]": localidad,
        "campo[8]": "BIEN.COD_PROVINCIA", "dato[8]": cod_provincia,
        "campo[9]": "SUBASTA.POSTURA_MINIMA_MINIMA_LOTES", "dato[9]": "",
        "campo[10]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_1", "dato[10]": "",
        "campo[11]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_2", "dato[11]": "",
        "campo[12]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_3", "dato[12]": "",
        "campo[13]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_4", "dato[13]": "",
        "campo[14]": "SUBASTA.NUM_CUENTA_EXPEDIENTE_5", "dato[14]": "",
        "campo[15]": "SUBASTA.ID_SUBASTA_BUSCAR", "dato[15]": "",
        "campo[16]": "SUBASTA.ACREEDORES", "dato[16]": "",
        "campo[17]": "SUBASTA.FECHA_FIN",
        "dato[17][0]": hoy.strftime("%Y-%m-%d"),
        "dato[17][1]": fin_rango.strftime("%Y-%m-%d"),
        "campo[18]": "SUBASTA.FECHA_INICIO", "dato[18][0]": "", "dato[18][1]": "",
        "page_hits": "50",
        "sort_field[0]": "SUBASTA.FECHA_FIN",
        "sort_order[0]": "asc",
        "accion": "Buscar",
    }


def buscar(payload):
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(URL)  # sesión inicial
    resp = session.post(URL, data=payload)
    resp.raise_for_status()

    if "No se han encontrado documentos" in resp.text:
        return None

    return resp.text


# --------------------------------------------------------------------------
# Parseo del listado de resultados
# --------------------------------------------------------------------------

def parsear_resultados(html):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.resultado-busqueda")
    subastas = []

    for item in items:
        id_sub = item.find("h3").get_text(strip=True).replace("SUBASTA ", "")
        autoridad = item.find("h4").get_text(strip=True)

        parrafos = item.find_all("p")
        # El nº de <p> varía (a veces hay "Expediente:" antes del estado),
        # así que localizamos el que empieza por "Estado:" y usamos
        # siempre el último <p> como descripción del bien.
        estado_p = next(
            (p for p in parrafos if p.get_text(strip=True).startswith("Estado:")),
            None,
        )
        estado_texto = estado_p.get_text(strip=True) if estado_p else ""
        descripcion = parrafos[-1].get_text(strip=True) if parrafos else ""

        # Fecha de fin: puede venir como "Conclusión prevista" o
        # "Fecha de conclusión"
        match = re.search(
            r"[Cc]onclusi[oó]n(?: prevista)?:\s*(\d{2}/\d{2}/\d{4})\s*a las\s*(\d{2}:\d{2}:\d{2})",
            estado_texto,
        )
        fecha_fin = None
        if match:
            fecha_str, hora_str = match.groups()
            fecha_fin = datetime.strptime(
                f"{fecha_str} {hora_str}", "%d/%m/%Y %H:%M:%S"
            ).replace(tzinfo=MADRID_TZ)

        link_tag = item.find("a", class_="resultado-busqueda-link-defecto")
        href = link_tag["href"].lstrip("./") if link_tag else None
        url_detalle = BASE_URL + href if href else None

        subastas.append({
            "id": id_sub,
            "autoridad": autoridad,
            "estado": estado_texto,
            "descripcion": descripcion,
            "fecha_fin": fecha_fin,
            "url": url_detalle,
        })

    return subastas


def filtrar_proximas_24h(subastas):
    ahora = datetime.now(MADRID_TZ)
    limite = ahora + timedelta(hours=24)
    return [
        s for s in subastas
        if s["fecha_fin"] and ahora <= s["fecha_fin"] <= limite
    ]


# --------------------------------------------------------------------------
# Formateo de mensajes
# --------------------------------------------------------------------------

def formatear_mensaje(subastas, titulo, emoji_default, emoji_fn=None):
    if not subastas:
        return f"{emoji_default} *{titulo}*\n\nNo hay resultados que terminen en las próximas 24h."

    lineas = [f"{emoji_default} *{titulo}* ({len(subastas)})\n"]
    for s in subastas:
        emoji = emoji_fn(s["descripcion"]) if emoji_fn else emoji_default
        fecha_fmt = s["fecha_fin"].strftime("%d/%m %H:%M")
        lineas.append(
            f"{emoji} *{fecha_fmt}*\n"
            f"{s['descripcion']}\n"
            f"{s['autoridad']}\n"
            f"[Ver detalle]({s['url']})\n"
        )
    return "\n".join(lineas)


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------

def enviar_telegram(mensaje):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    resp.raise_for_status()


# --------------------------------------------------------------------------
# Bloques de búsqueda
# --------------------------------------------------------------------------

def procesar_viviendas_madrid():
    payload = construir_payload(
        bien_tipo="I", subtipo="501",
        localidad="Madrid", cod_provincia="28",
        dias_rango=2,
    )
    html = buscar(payload)
    subastas = parsear_resultados(html) if html else []
    proximas = filtrar_proximas_24h(subastas)
    mensaje = formatear_mensaje(
        proximas,
        titulo="Viviendas Madrid — terminan en 24h",
        emoji_default=EMOJI_VIVIENDA,
    )
    enviar_telegram(mensaje)


def procesar_vehiculos_espana():
    payload = construir_payload(
        bien_tipo="V", subtipo="",
        localidad="", cod_provincia="",
        dias_rango=2,
    )
    html = buscar(payload)
    subastas = parsear_resultados(html) if html else []
    proximas = filtrar_proximas_24h(subastas)
    mensaje = formatear_mensaje(
        proximas,
        titulo="Vehículos España — terminan en 24h",
        emoji_default="🚗",
        emoji_fn=emoji_vehiculo,
    )
    enviar_telegram(mensaje)


# --------------------------------------------------------------------------
# Modo test: últimos N resultados, sin filtrar por fecha de fin
# --------------------------------------------------------------------------

def obtener_ultimos(bien_tipo, subtipo="", localidad="", cod_provincia="", n=10):
    """
    Igual que un procesar_*, pero con un rango de fechas amplio
    (1 año atrás -> 1 año adelante) y SIN el filtro de 24h, para
    poder ver cómo salen los datos independientemente de cuándo terminen.
    Ordena por fecha de fin descendente y se queda con los N más recientes.
    """
    hoy = datetime.now(MADRID_TZ).date()
    payload = construir_payload(
        bien_tipo=bien_tipo, subtipo=subtipo,
        localidad=localidad, cod_provincia=cod_provincia,
        dias_rango=365,
    )
    # ampliamos también hacia atrás, reescribiendo la fecha de inicio del rango
    payload["dato[17][0]"] = (hoy - timedelta(days=365)).strftime("%Y-%m-%d")
    payload["sort_order[0]"] = "desc"

    html = buscar(payload)
    if not html:
        return []

    subastas = parsear_resultados(html)
    # nos quedamos solo con las que tienen fecha_fin parseada, para poder ordenar bien
    subastas = [s for s in subastas if s["fecha_fin"]]
    subastas.sort(key=lambda s: s["fecha_fin"], reverse=True)
    return subastas[:n]


def test_viviendas_madrid(n=10, enviar_telegram_flag=False):
    subastas = obtener_ultimos(
        bien_tipo="I", subtipo="501",
        localidad="Madrid", cod_provincia="28",
        n=n,
    )
    mensaje = formatear_mensaje(
        subastas,
        titulo=f"TEST · Últimas {n} viviendas Madrid",
        emoji_default=EMOJI_VIVIENDA,
    )
    print(mensaje)
    if enviar_telegram_flag:
        enviar_telegram(mensaje)


def test_vehiculos_espana(n=10, enviar_telegram_flag=False):
    subastas = obtener_ultimos(
        bien_tipo="V", subtipo="",
        localidad="", cod_provincia="",
        n=n,
    )
    mensaje = formatear_mensaje(
        subastas,
        titulo=f"TEST · Últimos {n} vehículos España",
        emoji_default="🚗",
        emoji_fn=emoji_vehiculo,
    )
    print(mensaje)
    if enviar_telegram_flag:
        enviar_telegram(mensaje)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    procesar_viviendas_madrid()
    procesar_vehiculos_espana()


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        # Modo test: imprime por consola los últimos 10 de cada tipo,
        # sin importar la fecha de fin. Añade --telegram para mandarlos también.
        enviar = "--telegram" in sys.argv
        test_viviendas_madrid(n=10, enviar_telegram_flag=enviar)
        print("\n" + "=" * 60 + "\n")
        test_vehiculos_espana(n=10, enviar_telegram_flag=enviar)
    else:
        main()