#!/usr/bin/env python3
"""
=============================================================
  BUSCADOR DE OPOSICIONES - Trabajo Social / Monitor Ocio / TSEAS
  Fuentes: BOE (API oficial) + Portal Empleo Público (administracion.gob.es)
=============================================================
  Uso:
      python buscar_oposiciones.py
      python buscar_oposiciones.py --dias 30        # últimos 30 días
      python buscar_oposiciones.py --desde 2026-01-01 --hasta 2026-04-19
=============================================================
"""

import argparse
import sys
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta, datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote_plus
import json

# ──────────────────────────────────────────────
#  PALABRAS CLAVE por perfil
# ──────────────────────────────────────────────
PALABRAS_CLAVE = {
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
        "educación infantil",          # a veces convocan junto a TSEAS
    ],
}

TODAS_LAS_PALABRAS = [p for lista in PALABRAS_CLAVE.values() for p in lista]

# ──────────────────────────────────────────────
#  COLORES PARA TERMINAL
# ──────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    RED    = "\033[91m"
    GREY   = "\033[90m"
    WHITE  = "\033[97m"

def color(texto, *codes):
    return "".join(codes) + texto + C.RESET


# ──────────────────────────────────────────────
#  UTILIDADES HTTP
# ──────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BuscadorOposiciones/1.0; "
        "+https://github.com/usuario/buscador-oposiciones)"
    ),
    "Accept": "application/xml, text/html, */*",
}

def fetch(url, timeout=15, retries=3):
    """GET con reintentos."""
    req = Request(url, headers=HEADERS)
    for intento in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (HTTPError, URLError) as e:
            if intento == retries:
                raise
            time.sleep(2 * intento)


def normalizar(texto):
    """Minúsculas + quita tildes para comparar."""
    if not texto:
        return ""
    texto = texto.lower()
    for con, sin in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ü","u"),("ñ","n")]:
        texto = texto.replace(con, sin)
    return texto


def detectar_perfil(texto):
    """Devuelve lista de perfiles que coinciden en el texto."""
    texto_n = normalizar(texto)
    encontrados = []
    for perfil, palabras in PALABRAS_CLAVE.items():
        for p in palabras:
            if normalizar(p) in texto_n:
                encontrados.append(perfil)
                break
    return encontrados


# ──────────────────────────────────────────────
#  FUENTE 1: BOE – API de sumario diario
#  https://boe.es/datosabiertos/api/boe/sumario/AAAAMMDD
# ──────────────────────────────────────────────
BOE_API_BASE = "https://boe.es/datosabiertos/api/boe/sumario/{fecha}"
BOE_DOC_BASE = "https://www.boe.es/diario_boe/txt.php?id={id}"

def fechas_en_rango(desde, hasta):
    """Genera fechas laborables (lun-vie) entre dos fechas."""
    actual = desde
    while actual <= hasta:
        if actual.weekday() < 5:   # el BOE no sale sábado/domingo
            yield actual
        actual += timedelta(days=1)


def buscar_boe_dia(fecha):
    """Descarga el sumario del BOE de una fecha y filtra sección II-B."""
    url = BOE_API_BASE.format(fecha=fecha.strftime("%Y%m%d"))
    try:
        datos = fetch(url)
    except Exception:
        return []

    try:
        root = ET.fromstring(datos)
    except ET.ParseError:
        return []

    resultados = []

    # Buscar todos los ítems en la sección II.B (oposiciones y concursos)
    # El XML tiene: sumario > diario > secciones > seccion > departamentos > departamento > epigrafe > item
    for seccion in root.iter("seccion"):
        codigo = seccion.get("codigo", "")
        nombre = seccion.get("nombre", "")
        # Sección II tiene código "2" y subsección B
        # En la API, la sección II se identifica como codigo="2"
        if codigo not in ("2",):
            continue

        for item in seccion.iter("item"):
            titulo_el = item.find("titulo")
            titulo = titulo_el.text if titulo_el is not None else ""
            if not titulo:
                titulo = item.get("titulo", "")

            # Buscar URL_HTML y URL_PDF
            url_html_el = item.find("url_html")
            url_pdf_el  = item.find("url_pdf")
            url_doc = ""
            if url_html_el is not None and url_html_el.text:
                url_doc = "https://www.boe.es" + url_html_el.text
            elif url_pdf_el is not None and url_pdf_el.text:
                url_doc = "https://www.boe.es" + url_pdf_el.text

            # ID del documento
            doc_id = item.get("id", "")

            # Filtrar por palabras clave
            perfiles = detectar_perfil(titulo)
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


def buscar_boe(desde, hasta):
    print(color(f"\n[BOE] Consultando sumarios del {desde} al {hasta}...", C.CYAN, C.BOLD))
    resultados = []
    fechas = list(fechas_en_rango(desde, hasta))
    total = len(fechas)
    for i, fecha in enumerate(fechas, 1):
        sys.stdout.write(f"\r  Día {i}/{total}: {fecha}   ")
        sys.stdout.flush()
        resultados.extend(buscar_boe_dia(fecha))
        time.sleep(0.3)   # respetar el servidor
    print(f"\r  {total} días consultados. {color(str(len(resultados))+' resultados', C.GREEN)}   ")
    return resultados


# ──────────────────────────────────────────────
#  FUENTE 2: Portal Empleo Público
#  https://administracion.gob.es/pagFront/empleoBecas/empleo/buscadorEmpleoAvanzado.htm
#  Usa un endpoint interno que devuelve HTML con las convocatorias
# ──────────────────────────────────────────────
# El portal tiene un endpoint de búsqueda por texto libre
EMPLEO_SEARCH_URL = (
    "https://administracion.gob.es/pagFront/ofertasempleopublico/"
    "buscarEmpleo.htm"
)

def buscar_portal_empleo_termino(termino, pagina=1):
    """Consulta el buscador del portal de empleo público para un término."""
    params = {
        "tipoBusqueda": "CONVOCATORIAS",
        "denominacionCuerpo": termino,
        "plazo": "T",          # Todas (abiertas y cerradas)
        "viaAcceso": "L",      # Libre acceso
        "paginaActual": str(pagina),
    }
    url = EMPLEO_SEARCH_URL + "?" + urlencode(params)
    try:
        datos = fetch(url, timeout=20).decode("utf-8", errors="replace")
        return datos
    except Exception:
        return ""


def extraer_convocatorias_html(html, termino):
    """Extrae convocatorias del HTML del portal de empleo."""
    resultados = []

    # El portal devuelve un HTML con bloques de convocatorias
    # Buscamos patrones clave
    bloques = re.split(r'class="[^"]*resultado[^"]*"', html)

    # Patrón para extraer: Denominación, plazas, fin plazo, URL, titulación
    patron_conv = re.compile(
        r'idConvocatoria=(\d+)[^>]*>.*?'      # ID convocatoria
        r'<[^>]+class="[^"]*titulo[^"]*"[^>]*>(.*?)</.*?'  # título
        r'(?:Plazas.*?(\d+).*?)?'
        r'(?:Fin de plazo.*?([\d/]+).*?)?',
        re.DOTALL | re.IGNORECASE
    )

    # Estrategia alternativa: buscar los <tr> o divs con clase resultado
    patron_enlace = re.compile(
        r'detalleEmpleo\.htm\?idConvocatoria=(\d+)',
        re.IGNORECASE
    )
    patron_titulo = re.compile(
        r'detalleEmpleo\.htm\?idConvocatoria=\d+[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )
    patron_fin = re.compile(
        r'Fin de plazo[:\s]*</[^>]+>\s*<[^>]+>([\d/\-]+)',
        re.IGNORECASE | re.DOTALL
    )
    patron_plazas = re.compile(
        r'Plazas[:\s]*</[^>]+>\s*<[^>]+>(\d+)',
        re.IGNORECASE | re.DOTALL
    )

    ids = patron_enlace.findall(html)
    titulos_raw = patron_titulo.findall(html)

    for i, conv_id in enumerate(ids):
        titulo_raw = titulos_raw[i] if i < len(titulos_raw) else ""
        titulo = re.sub(r'<[^>]+>', '', titulo_raw).strip()
        if not titulo:
            continue

        perfiles = detectar_perfil(titulo)
        # Si no detecta por título, puede ser una categoría general
        if not perfiles:
            # Verificar que el término de búsqueda está en el título
            if normalizar(termino) not in normalizar(titulo):
                continue
            # Asignar perfil por el término buscado
            for perfil, palabras in PALABRAS_CLAVE.items():
                if any(normalizar(p) in normalizar(termino) for p in palabras):
                    perfiles = [perfil]
                    break

        url_detalle = (
            "https://administracion.gob.es/pagFront/ofertasempleopublico/"
            f"detalleEmpleo.htm?idConvocatoria={conv_id}&tipoBusqueda=CONVOCATORIAS"
        )

        resultados.append({
            "fuente": "Portal Empleo Público (PAGe)",
            "fecha": "—",
            "titulo": titulo,
            "perfiles": perfiles if perfiles else ["(término: " + termino + ")"],
            "url": url_detalle,
            "id": conv_id,
        })

    return resultados


def buscar_portal_empleo():
    """Busca en el portal de empleo público todos los términos relevantes."""
    print(color("\n[Portal Empleo Público] Consultando convocatorias...", C.CYAN, C.BOLD))

    terminos_busqueda = [
        "trabajo social",
        "trabajador social",
        "monitor ocio",
        "animador sociocultural",
        "tseas",
        "integración social",
        "técnico superior educacion",
    ]

    todos = []
    ids_vistos = set()

    for termino in terminos_busqueda:
        sys.stdout.write(f"  Buscando: '{termino}'... ")
        sys.stdout.flush()
        html = buscar_portal_empleo_termino(termino)
        encontrados = extraer_convocatorias_html(html, termino)
        nuevos = [r for r in encontrados if r["id"] not in ids_vistos]
        for r in nuevos:
            ids_vistos.add(r["id"])
        todos.extend(nuevos)
        print(color(f"{len(nuevos)} nuevas", C.GREEN))
        time.sleep(1)

    return todos


# ──────────────────────────────────────────────
#  PRESENTACIÓN DE RESULTADOS
# ──────────────────────────────────────────────
ETIQUETA_COLORES = {
    "Trabajo Social": C.GREEN,
    "Monitor Ocio y Tiempo Libre": C.YELLOW,
    "TSEAS / Integración Social": C.CYAN,
}

def etiqueta_perfil(perfil):
    col = ETIQUETA_COLORES.get(perfil, C.WHITE)
    return color(f"[{perfil}]", col, C.BOLD)


def mostrar_resultados(resultados_boe, resultados_portal):
    todos = resultados_boe + resultados_portal

    print("\n" + "═" * 70)
    print(color("  RESULTADOS", C.BOLD, C.WHITE))
    print("═" * 70)

    if not todos:
        print(color("\n  No se encontraron convocatorias con los criterios indicados.", C.YELLOW))
        print("  Prueba a ampliar el rango de fechas con --dias 60\n")
        return

    # Agrupar por perfil
    por_perfil = {k: [] for k in PALABRAS_CLAVE}
    por_perfil["Otros"] = []

    for r in todos:
        asignado = False
        for perfil in r["perfiles"]:
            if perfil in por_perfil:
                if r not in por_perfil[perfil]:
                    por_perfil[perfil].append(r)
                asignado = True
        if not asignado:
            por_perfil["Otros"].append(r)

    total_mostrado = 0
    for perfil, lista in por_perfil.items():
        if not lista:
            continue
        col = ETIQUETA_COLORES.get(perfil, C.WHITE)
        print(f"\n  {color(perfil.upper(), col, C.BOLD)}  ({len(lista)} convocatorias)")
        print("  " + "─" * 66)
        for r in lista:
            total_mostrado += 1
            print(f"\n  {color('▸', C.GREY)} {color(r['titulo'], C.WHITE)}")
            print(f"    {color('Fuente:', C.GREY)} {r['fuente']}  "
                  f"{color('Fecha:', C.GREY)} {r['fecha']}")
            print(f"    {color('URL:', C.GREY)} {r['url']}")

    print("\n" + "═" * 70)
    print(color(f"  Total: {total_mostrado} convocatoria(s) encontrada(s)", C.GREEN, C.BOLD))
    print(f"  {color('BOE:', C.GREY)} {len(resultados_boe)}   "
          f"{color('Portal Empleo Público:', C.GREY)} {len(resultados_portal)}")
    print("═" * 70 + "\n")

    # Aviso importante
    print(color("  NOTA:", C.YELLOW, C.BOLD) +
          " El Portal de Empleo Público cubre BOE + boletines autonómicos,")
    print("  pero NO incluye la mayoría de BOP provinciales.")
    print("  Para BOP: consulta directamente cada provincia en")
    print("  https://www.diba.cat/es/web/obmap/bops  (mapa de BOPs)\n")


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def parsear_argumentos():
    p = argparse.ArgumentParser(
        description="Buscador de oposiciones: Trabajo Social, Monitor Ocio, TSEAS"
    )
    p.add_argument(
        "--dias", type=int, default=14,
        help="Buscar en los últimos N días del BOE (por defecto: 14)"
    )
    p.add_argument(
        "--desde", type=str, default=None,
        help="Fecha inicio para BOE (formato YYYY-MM-DD)"
    )
    p.add_argument(
        "--hasta", type=str, default=None,
        help="Fecha fin para BOE (formato YYYY-MM-DD, por defecto hoy)"
    )
    p.add_argument(
        "--solo-boe", action="store_true",
        help="Consultar solo el BOE (más rápido)"
    )
    p.add_argument(
        "--solo-portal", action="store_true",
        help="Consultar solo el Portal de Empleo Público"
    )
    return p.parse_args()


def main():
    args = parsear_argumentos()

    print("\n" + "═" * 70)
    print(color("  BUSCADOR DE OPOSICIONES", C.BOLD, C.WHITE))
    print(color("  Trabajo Social · Monitor Ocio y Tiempo Libre · TSEAS", C.GREY))
    print("═" * 70)

    hoy = date.today()

    # Calcular rango de fechas para el BOE
    if args.desde:
        desde = datetime.strptime(args.desde, "%Y-%m-%d").date()
    else:
        desde = hoy - timedelta(days=args.dias)

    hasta = datetime.strptime(args.hasta, "%Y-%m-%d").date() if args.hasta else hoy

    print(f"\n  Fecha actual: {hoy.strftime('%d/%m/%Y')}")
    print(f"  Rango BOE:    {desde.strftime('%d/%m/%Y')} → {hasta.strftime('%d/%m/%Y')}")
    print(f"  Perfiles:     {', '.join(PALABRAS_CLAVE.keys())}")

    resultados_boe = []
    resultados_portal = []

    if not args.solo_portal:
        resultados_boe = buscar_boe(desde, hasta)

    if not args.solo_boe:
        resultados_portal = buscar_portal_empleo()

    mostrar_resultados(resultados_boe, resultados_portal)


if __name__ == "__main__":
    main()
