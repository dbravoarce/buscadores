#!/usr/bin/env python3
"""
=============================================================
  BUSCADOR DE OFERTAS DE EMPLEO
  Portales: Infojobs · Indeed · SEPE · Tecnoempleo
=============================================================
  Uso:
      python buscar_empleo.py

  Para cambiar las palabras clave, edita la sección
  CONFIGURACIÓN más abajo.
=============================================================
"""

import re
import sys
import time
import json
import html as html_module
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote_plus

# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — edita aquí tus búsquedas
# ══════════════════════════════════════════════════════════════

PALABRAS_CLAVE = [
    "trabajo social",
    "monitor de ocio",
    "integración social",
    "educador social",
    "animador sociocultural",
    # Añade o quita términos aquí
    # "enfermero",
    # "administrativo",
    # "cocinero",
]

# Número máximo de resultados por portal y palabra clave
MAX_RESULTADOS = 10

# ══════════════════════════════════════════════════════════════
#  COLORES PARA TERMINAL
# ══════════════════════════════════════════════════════════════
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    RED    = "\033[91m"
    GREY   = "\033[90m"
    WHITE  = "\033[97m"
    BLUE   = "\033[94m"

def color(texto, *codes):
    return "".join(codes) + texto + C.RESET

def limpiar_html(texto):
    """Quita etiquetas HTML y decodifica entidades."""
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html_module.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()

# ══════════════════════════════════════════════════════════════
#  UTILIDADES HTTP
# ══════════════════════════════════════════════════════════════
HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

HEADERS_JSON = {
    **HEADERS_BROWSER,
    "Accept": "application/json, text/javascript, */*",
}

def fetch(url, headers=None, timeout=20, retries=3):
    """GET con reintentos y gestión de errores."""
    h = headers or HEADERS_BROWSER
    req = Request(url, headers=h)
    for intento in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            if e.code in (403, 429):
                # Bloqueado o rate limit — esperar más
                time.sleep(5 * intento)
            if intento == retries:
                return ""
            time.sleep(2 * intento)
        except URLError:
            if intento == retries:
                return ""
            time.sleep(2 * intento)
    return ""

# ══════════════════════════════════════════════════════════════
#  PORTAL 1: INFOJOBS
#  Usa el buscador público de Infojobs (scraping HTML)
# ══════════════════════════════════════════════════════════════
def buscar_infojobs(termino):
    """Busca ofertas en Infojobs para un término dado."""
    url = (
        f"https://www.infojobs.net/jobsearch/search-results/list.xhtml"
        f"?keyword={quote_plus(termino)}&provinceIds=0&sortBy=PUBLICATION_DATE"
    )
    html = fetch(url)
    if not html:
        return []

    resultados = []

    # Extraer bloques de oferta
    # Infojobs renderiza los datos en JSON dentro de un script
    patron_json = re.search(
        r'window\.__INITIAL_PROPS__\s*=\s*(\{.*?\});?\s*</script>',
        html, re.DOTALL
    )
    if patron_json:
        try:
            data = json.loads(patron_json.group(1))
            ofertas = (
                data.get("items") or
                data.get("offers") or
                data.get("searchResult", {}).get("items", [])
            )
            for o in ofertas[:MAX_RESULTADOS]:
                titulo   = limpiar_html(o.get("title") or o.get("titulo", ""))
                empresa  = limpiar_html(o.get("author", {}).get("name") or o.get("empresa", ""))
                ciudad   = limpiar_html(o.get("city") or o.get("ciudad", ""))
                url_of   = o.get("link") or o.get("url", "")
                if titulo:
                    resultados.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "ubicacion": ciudad,
                        "url": url_of if url_of.startswith("http") else "https://www.infojobs.net" + url_of,
                        "portal": "Infojobs",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: scraping de títulos en HTML
    patron_titulo = re.compile(
        r'<a[^>]+class="[^"]*js-offer-link[^"]*"[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
        re.DOTALL | re.IGNORECASE
    )
    patron_empresa = re.compile(
        r'class="[^"]*company[^"]*"[^>]*>\s*(.*?)\s*</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )
    patron_ciudad = re.compile(
        r'class="[^"]*location[^"]*"[^>]*>\s*(.*?)\s*</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )

    titulos  = patron_titulo.findall(html)
    empresas = [limpiar_html(e) for e in patron_empresa.findall(html)]
    ciudades = [limpiar_html(c) for c in patron_ciudad.findall(html)]

    for i, (href, tit) in enumerate(titulos[:MAX_RESULTADOS]):
        titulo = limpiar_html(tit)
        if not titulo:
            continue
        resultados.append({
            "titulo": titulo,
            "empresa": empresas[i] if i < len(empresas) else "",
            "ubicacion": ciudades[i] if i < len(ciudades) else "",
            "url": href if href.startswith("http") else "https://www.infojobs.net" + href,
            "portal": "Infojobs",
        })

    return resultados


# ══════════════════════════════════════════════════════════════
#  PORTAL 2: INDEED
#  Usa el buscador público de Indeed España
# ══════════════════════════════════════════════════════════════
def buscar_indeed(termino):
    """Busca ofertas en Indeed España."""
    url = (
        f"https://es.indeed.com/jobs"
        f"?q={quote_plus(termino)}&l=Espa%C3%B1a&sort=date"
    )
    headers = {
        **HEADERS_BROWSER,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    html = fetch(url, headers=headers)
    if not html:
        return []

    resultados = []

    # Indeed a veces inyecta JSON con los resultados
    patron_json = re.search(r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*window', html, re.DOTALL)
    if patron_json:
        try:
            data = json.loads(patron_json.group(1))
            jobs = data.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results", [])
            for j in jobs[:MAX_RESULTADOS]:
                titulo   = limpiar_html(j.get("title", ""))
                empresa  = limpiar_html(j.get("company", ""))
                ciudad   = limpiar_html(j.get("formattedLocation", ""))
                job_key  = j.get("jobkey", "")
                url_of   = f"https://es.indeed.com/viewjob?jk={job_key}" if job_key else ""
                if titulo:
                    resultados.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "ubicacion": ciudad,
                        "url": url_of,
                        "portal": "Indeed",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback HTML
    patron_card = re.compile(
        r'<h2[^>]*class="[^"]*jobTitle[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>\s*<span[^>]*>(.*?)</span>',
        re.DOTALL | re.IGNORECASE
    )
    patron_emp = re.compile(
        r'class="[^"]*companyName[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )
    patron_loc = re.compile(
        r'class="[^"]*companyLocation[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )

    cards   = patron_card.findall(html)
    empresas = [limpiar_html(e) for e in patron_emp.findall(html)]
    ciudades = [limpiar_html(c) for c in patron_loc.findall(html)]

    for i, (href, tit) in enumerate(cards[:MAX_RESULTADOS]):
        titulo = limpiar_html(tit)
        if not titulo:
            continue
        full_url = href if href.startswith("http") else "https://es.indeed.com" + href
        resultados.append({
            "titulo": titulo,
            "empresa": empresas[i] if i < len(empresas) else "",
            "ubicacion": ciudades[i] if i < len(ciudades) else "",
            "url": full_url,
            "portal": "Indeed",
        })

    return resultados


# ══════════════════════════════════════════════════════════════
#  PORTAL 3: SEPE — Servicio Público de Empleo Estatal
#  API abierta oficial: https://datos.gob.es
# ══════════════════════════════════════════════════════════════
def buscar_sepe(termino):
    """Busca ofertas en el portal de empleo del SEPE."""
    # El SEPE tiene un buscador en empleo.sepe.es
    url = (
        f"https://empleo.sepe.es/portalEmpleo/servlet/ofertaServlet"
        f"?accion=buscarOfertas&palabraClave={quote_plus(termino)}"
        f"&provinciaOferta=&tipoJornada=&nivelEstudios="
        f"&numResultados={MAX_RESULTADOS}&pagina=1"
    )
    html = fetch(url)

    resultados = []

    if html:
        # Intentar parsear JSON si el endpoint devuelve JSON
        try:
            data = json.loads(html)
            ofertas = data.get("listaOfertas") or data.get("ofertas") or []
            for o in ofertas[:MAX_RESULTADOS]:
                titulo  = limpiar_html(o.get("denominacionOferta") or o.get("titulo", ""))
                empresa = limpiar_html(o.get("nombreEmpresa") or o.get("empresa", ""))
                ciudad  = limpiar_html(o.get("localidad") or o.get("provincia", ""))
                cod     = o.get("codOferta") or o.get("id", "")
                url_of  = f"https://empleo.sepe.es/portalEmpleo/servlet/ofertaServlet?accion=verOferta&codOferta={cod}" if cod else ""
                if titulo:
                    resultados.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "ubicacion": ciudad,
                        "url": url_of,
                        "portal": "SEPE",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback HTML scraping
        patron_titulo = re.compile(
            r'class="[^"]*tituloOferta[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )
        patron_empresa = re.compile(
            r'class="[^"]*empresa[^"]*"[^>]*>(.*?)</[^>]+>',
            re.DOTALL | re.IGNORECASE
        )
        patron_ciudad = re.compile(
            r'class="[^"]*localidad[^"]*"[^>]*>(.*?)</[^>]+>',
            re.DOTALL | re.IGNORECASE
        )

        titulos  = patron_titulo.findall(html)
        empresas = [limpiar_html(e) for e in patron_empresa.findall(html)]
        ciudades = [limpiar_html(c) for c in patron_ciudad.findall(html)]

        for i, (href, tit) in enumerate(titulos[:MAX_RESULTADOS]):
            titulo = limpiar_html(tit)
            if not titulo:
                continue
            resultados.append({
                "titulo": titulo,
                "empresa": empresas[i] if i < len(empresas) else "",
                "ubicacion": ciudades[i] if i < len(ciudades) else "",
                "url": href if href.startswith("http") else "https://empleo.sepe.es" + href,
                "portal": "SEPE",
            })

    # Si nada funciona, enlace directo de búsqueda
    if not resultados:
        resultados.append({
            "titulo": f"🔗 Ver resultados de '{termino}' en SEPE",
            "empresa": "",
            "ubicacion": "España",
            "url": f"https://empleo.sepe.es/portalEmpleo/servlet/ofertaServlet?accion=buscarOfertas&palabraClave={quote_plus(termino)}",
            "portal": "SEPE",
        })

    return resultados


# ══════════════════════════════════════════════════════════════
#  PORTAL 4: TECNOEMPLEO
#  Especializado en perfiles técnicos y sector social/educativo
# ══════════════════════════════════════════════════════════════
def buscar_tecnoempleo(termino):
    """Busca ofertas en Tecnoempleo."""
    url = (
        f"https://www.tecnoempleo.com/busqueda-empleo.php"
        f"?te={quote_plus(termino)}&provincia=0&ordenar=2"
    )
    html = fetch(url)
    if not html:
        return []

    resultados = []

    # Tecnoempleo estructura sus ofertas en bloques con clase oferta
    patron_bloque = re.compile(
        r'<div[^>]*class="[^"]*(?:oferta|job-offer|vacancy)[^"]*"[^>]*>(.*?)</div>\s*</div>',
        re.DOTALL | re.IGNORECASE
    )
    patron_titulo = re.compile(
        r'<(?:h2|h3|a)[^>]*class="[^"]*(?:title|titulo)[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )
    patron_titulo_alt = re.compile(
        r'<a[^>]*href="(/oferta-trabajo/[^"]+)"[^>]*>\s*<(?:span|h[23])[^>]*>(.*?)</(?:span|h[23])>',
        re.DOTALL | re.IGNORECASE
    )
    patron_empresa = re.compile(
        r'class="[^"]*(?:empresa|company)[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )
    patron_ciudad = re.compile(
        r'class="[^"]*(?:ciudad|location|provincia)[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL | re.IGNORECASE
    )

    # Intentar patrón principal
    titulos = patron_titulo.findall(html)
    if not titulos:
        titulos = [(href, tit) for href, tit in patron_titulo_alt.findall(html)]

    empresas = [limpiar_html(e) for e in patron_empresa.findall(html)]
    ciudades = [limpiar_html(c) for c in patron_ciudad.findall(html)]

    for i, (href, tit) in enumerate(titulos[:MAX_RESULTADOS]):
        titulo = limpiar_html(tit)
        if not titulo:
            continue
        full_url = href if href.startswith("http") else "https://www.tecnoempleo.com" + href
        resultados.append({
            "titulo": titulo,
            "empresa": empresas[i] if i < len(empresas) else "",
            "ubicacion": ciudades[i] if i < len(ciudades) else "",
            "url": full_url,
            "portal": "Tecnoempleo",
        })

    # Si no extrajo nada, ofrece enlace directo
    if not resultados:
        resultados.append({
            "titulo": f"🔗 Ver resultados de '{termino}' en Tecnoempleo",
            "empresa": "",
            "ubicacion": "España",
            "url": url,
            "portal": "Tecnoempleo",
        })

    return resultados


# ══════════════════════════════════════════════════════════════
#  MOTOR PRINCIPAL DE BÚSQUEDA
# ══════════════════════════════════════════════════════════════
PORTALES = {
    "Infojobs":    buscar_infojobs,
    "Indeed":      buscar_indeed,
    "SEPE":        buscar_sepe,
    "Tecnoempleo": buscar_tecnoempleo,
}

COLORES_PORTAL = {
    "Infojobs":    C.BLUE,
    "Indeed":      C.CYAN,
    "SEPE":        C.GREEN,
    "Tecnoempleo": C.YELLOW,
}

def buscar_todo():
    todos_resultados = {}  # {termino: {portal: [ofertas]}}

    total_ofertas = 0

    for termino in PALABRAS_CLAVE:
        todos_resultados[termino] = {}
        print(color(f"\n🔍 Buscando: '{termino}'", C.BOLD, C.WHITE))
        print("─" * 60)

        for nombre_portal, funcion in PORTALES.items():
            col = COLORES_PORTAL.get(nombre_portal, C.WHITE)
            sys.stdout.write(f"  {color(nombre_portal, col, C.BOLD)}: buscando...")
            sys.stdout.flush()

            try:
                ofertas = funcion(termino)
            except Exception as e:
                ofertas = []

            todos_resultados[termino][nombre_portal] = ofertas
            total_ofertas += len(ofertas)

            if ofertas:
                print(f"\r  {color(nombre_portal, col, C.BOLD)}: {color(str(len(ofertas)) + ' ofertas', C.GREEN)}          ")
            else:
                print(f"\r  {color(nombre_portal, col, C.BOLD)}: {color('sin resultados', C.GREY)}          ")

            time.sleep(1.5)  # pausa entre portales

    return todos_resultados, total_ofertas


# ══════════════════════════════════════════════════════════════
#  PRESENTACIÓN DE RESULTADOS
# ══════════════════════════════════════════════════════════════
def mostrar_resultados(todos_resultados, total_ofertas):
    print("\n\n" + "═" * 70)
    print(color("  RESULTADOS", C.BOLD, C.WHITE))
    print("═" * 70)

    if total_ofertas == 0:
        print(color("\n  No se encontraron ofertas.", C.YELLOW))
        print("  Es posible que los portales hayan cambiado su estructura.")
        print("  En ese caso, usa los enlaces directos más abajo.\n")
    else:
        for termino, por_portal in todos_resultados.items():
            hay_algo = any(len(v) > 0 for v in por_portal.values())
            if not hay_algo:
                continue

            print(f"\n  {color('▶ ' + termino.upper(), C.BOLD, C.WHITE)}")

            for portal, ofertas in por_portal.items():
                if not ofertas:
                    continue
                col = COLORES_PORTAL.get(portal, C.WHITE)
                print(f"\n    {color('[' + portal + ']', col, C.BOLD)}")

                for o in ofertas:
                    titulo   = o.get("titulo", "")[:70]
                    empresa  = o.get("empresa", "")
                    ubicacion = o.get("ubicacion", "")
                    url_of   = o.get("url", "")

                    print(f"\n      {color('▸', C.GREY)} {color(titulo, C.WHITE)}")
                    if empresa:
                        print(f"        {color('Empresa:', C.GREY)} {empresa}")
                    if ubicacion:
                        print(f"        {color('Ubicación:', C.GREY)} {ubicacion}")
                    if url_of:
                        print(f"        {color('URL:', C.GREY)} {url_of}")

    print("\n" + "═" * 70)
    print(color(f"  Total ofertas encontradas: {total_ofertas}", C.GREEN, C.BOLD))
    print("═" * 70)

    # Enlaces directos siempre visibles
    print(color("\n  ENLACES DIRECTOS (búsqueda manual):", C.BOLD, C.WHITE))
    for termino in PALABRAS_CLAVE:
        t = quote_plus(termino)
        print(f"\n  {color(termino, C.YELLOW, C.BOLD)}")
        print(f"    Infojobs:    https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={t}")
        print(f"    Indeed:      https://es.indeed.com/jobs?q={t}&l=Espa%C3%B1a")
        print(f"    SEPE:        https://empleo.sepe.es/portalEmpleo/servlet/ofertaServlet?accion=buscarOfertas&palabraClave={t}")
        print(f"    Tecnoempleo: https://www.tecnoempleo.com/busqueda-empleo.php?te={t}")

    print()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print("\n" + "═" * 70)
    print(color("  BUSCADOR DE EMPLEO", C.BOLD, C.WHITE))
    print(color("  Infojobs · Indeed · SEPE · Tecnoempleo", C.GREY))
    print("═" * 70)
    print(f"\n  Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Palabras clave: {', '.join(PALABRAS_CLAVE)}")
    print(f"  Máx. resultados por portal: {MAX_RESULTADOS}")
    print(color(
        "\n  NOTA: Si un portal bloquea el acceso automático, verás 0 resultados\n"
        "  pero siempre tendrás los enlaces directos al final para buscar manualmente.",
        C.GREY
    ))

    todos_resultados, total_ofertas = buscar_todo()
    mostrar_resultados(todos_resultados, total_ofertas)


if __name__ == "__main__":
    main()
