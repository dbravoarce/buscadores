"""
Lógica de búsqueda de oposiciones — BOE + Portal Empleo Público.
Importable desde la app Streamlit.
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta, datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote_plus

PALABRAS_CLAVE_DEFAULT = {
    "Trabajo Social": [
        "trabajo social",
        "trabajador social",
        "trabajadora social",
        "diplomado en trabajo social",
        "grado en trabajo social",
    ],
    "Monitor Ocio y Tiempo Libre": [
        "monitor de ocio",
        "monitor ocio y tiempo libre",
        "animador sociocultural",
        "monitor tiempo libre",
        "director de tiempo libre",
        "ocio y tiempo libre",
    ],
    "TSEAS / Integración Social": [
        "tseas",
        "técnico superior en educación",
        "integración social",
        "técnico de integración",
        "fp integración social",
        "educación infantil",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BuscadorOposiciones/1.0)"
    ),
    "Accept": "application/xml, text/html, */*",
}

BOE_API_BASE  = "https://boe.es/datosabiertos/api/boe/sumario/{fecha}"
BOE_DOC_BASE  = "https://www.boe.es/diario_boe/txt.php?id={id}"
EMPLEO_URL    = "https://administracion.gob.es/pagFront/ofertasempleopublico/buscarEmpleo.htm"


def fetch(url, timeout=15, retries=3):
    req = Request(url, headers=HEADERS)
    for intento in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (HTTPError, URLError):
            if intento == retries:
                return b""
            time.sleep(2 * intento)
    return b""


def normalizar(texto):
    if not texto:
        return ""
    texto = texto.lower()
    for con, sin in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ü","u"),("ñ","n")]:
        texto = texto.replace(con, sin)
    return texto


def detectar_perfil(texto, palabras_clave):
    texto_n = normalizar(texto)
    encontrados = []
    for perfil, palabras in palabras_clave.items():
        for p in palabras:
            if normalizar(p) in texto_n:
                encontrados.append(perfil)
                break
    return encontrados


def fechas_en_rango(desde, hasta):
    actual = desde
    while actual <= hasta:
        if actual.weekday() < 5:
            yield actual
        actual += timedelta(days=1)


def buscar_boe_dia(fecha, palabras_clave):
    url = BOE_API_BASE.format(fecha=fecha.strftime("%Y%m%d"))
    datos = fetch(url)
    if not datos:
        return []

    try:
        root = ET.fromstring(datos)
    except ET.ParseError:
        return []

    resultados = []
    for seccion in root.iter("seccion"):
        if seccion.get("codigo", "") not in ("2",):
            continue
        for item in seccion.iter("item"):
            titulo_el = item.find("titulo")
            titulo = (titulo_el.text if titulo_el is not None else "") or item.get("titulo", "")

            url_html_el = item.find("url_html")
            url_pdf_el  = item.find("url_pdf")
            url_doc = ""
            if url_html_el is not None and url_html_el.text:
                url_doc = "https://www.boe.es" + url_html_el.text
            elif url_pdf_el is not None and url_pdf_el.text:
                url_doc = "https://www.boe.es" + url_pdf_el.text

            doc_id  = item.get("id", "")
            perfiles = detectar_perfil(titulo, palabras_clave)
            if perfiles:
                resultados.append({
                    "fuente": "BOE",
                    "fecha": fecha.strftime("%d/%m/%Y"),
                    "titulo": titulo.strip(),
                    "perfiles": perfiles,
                    "url": url_doc or BOE_DOC_BASE.format(id=doc_id),
                    "id": doc_id,
                })
    return resultados


def buscar_boe(desde, hasta, palabras_clave, callback=None):
    resultados = []
    fechas = list(fechas_en_rango(desde, hasta))
    total  = len(fechas)
    for i, fecha in enumerate(fechas, 1):
        if callback:
            callback(i, total, fecha)
        resultados.extend(buscar_boe_dia(fecha, palabras_clave))
        time.sleep(0.3)
    return resultados


def buscar_portal_empleo(palabras_clave, callback=None):
    terminos = list({
        p.lower()
        for lista in palabras_clave.values()
        for p in lista
        if len(p) > 5
    })[:12]  # máx 12 peticiones para no sobrecargar

    todos = []
    ids_vistos = set()
    total = len(terminos)

    for i, termino in enumerate(terminos, 1):
        if callback:
            callback(i, total, termino)
        params = {
            "tipoBusqueda": "CONVOCATORIAS",
            "denominacionCuerpo": termino,
            "plazo": "T",
            "viaAcceso": "L",
            "paginaActual": "1",
        }
        url = EMPLEO_URL + "?" + urlencode(params)
        datos = fetch(url, timeout=20)
        html  = datos.decode("utf-8", errors="replace") if datos else ""

        encontrados = _extraer_convocatorias(html, termino, palabras_clave)
        nuevos = [r for r in encontrados if r["id"] not in ids_vistos]
        for r in nuevos:
            ids_vistos.add(r["id"])
        todos.extend(nuevos)
        time.sleep(1)

    return todos


def _extraer_convocatorias(html, termino, palabras_clave):
    resultados = []
    patron_enlace = re.compile(r'detalleEmpleo\.htm\?idConvocatoria=(\d+)', re.IGNORECASE)
    patron_titulo = re.compile(
        r'detalleEmpleo\.htm\?idConvocatoria=\d+[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )

    ids     = patron_enlace.findall(html)
    titulos = patron_titulo.findall(html)

    for i, conv_id in enumerate(ids):
        titulo_raw = titulos[i] if i < len(titulos) else ""
        titulo = re.sub(r'<[^>]+>', '', titulo_raw).strip()
        if not titulo:
            continue

        perfiles = detectar_perfil(titulo, palabras_clave)
        if not perfiles:
            if normalizar(termino) not in normalizar(titulo):
                continue
            for perfil, palabras in palabras_clave.items():
                if any(normalizar(p) in normalizar(termino) for p in palabras):
                    perfiles = [perfil]
                    break

        url_detalle = (
            "https://administracion.gob.es/pagFront/ofertasempleopublico/"
            f"detalleEmpleo.htm?idConvocatoria={conv_id}&tipoBusqueda=CONVOCATORIAS"
        )
        resultados.append({
            "fuente": "Portal Empleo Público",
            "fecha": "—",
            "titulo": titulo,
            "perfiles": perfiles or [termino],
            "url": url_detalle,
            "id": conv_id,
        })
    return resultados
