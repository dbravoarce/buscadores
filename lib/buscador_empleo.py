"""
Lógica de búsqueda de empleo — Infojobs, Indeed, SEPE, Tecnoempleo.
Importable desde la app Streamlit.
"""

import re
import time
import json
import html as html_module
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus

MAX_RESULTADOS = 10

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def limpiar_html(texto):
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html_module.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def fetch(url, headers=None, timeout=20, retries=3):
    h = headers or HEADERS_BROWSER
    req = Request(url, headers=h)
    for intento in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            if e.code in (403, 429):
                time.sleep(5 * intento)
            if intento == retries:
                return ""
            time.sleep(2 * intento)
        except URLError:
            if intento == retries:
                return ""
            time.sleep(2 * intento)
    return ""


def buscar_infojobs(termino):
    url = (
        f"https://www.infojobs.net/jobsearch/search-results/list.xhtml"
        f"?keyword={quote_plus(termino)}&provinceIds=0&sortBy=PUBLICATION_DATE"
    )
    html = fetch(url)
    if not html:
        return []

    resultados = []
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
                titulo  = limpiar_html(o.get("title") or o.get("titulo", ""))
                empresa = limpiar_html(o.get("author", {}).get("name") or o.get("empresa", ""))
                ciudad  = limpiar_html(o.get("city") or o.get("ciudad", ""))
                url_of  = o.get("link") or o.get("url", "")
                if titulo:
                    resultados.append({
                        "titulo": titulo, "empresa": empresa, "ubicacion": ciudad,
                        "url": url_of if url_of.startswith("http") else "https://www.infojobs.net" + url_of,
                        "portal": "Infojobs",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, KeyError):
            pass

    patron_titulo = re.compile(
        r'<a[^>]+class="[^"]*js-offer-link[^"]*"[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
        re.DOTALL | re.IGNORECASE
    )
    patron_empresa = re.compile(r'class="[^"]*company[^"]*"[^>]*>\s*(.*?)\s*</[^>]+>', re.DOTALL | re.IGNORECASE)
    patron_ciudad  = re.compile(r'class="[^"]*location[^"]*"[^>]*>\s*(.*?)\s*</[^>]+>', re.DOTALL | re.IGNORECASE)

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


def buscar_indeed(termino):
    url = f"https://es.indeed.com/jobs?q={quote_plus(termino)}&l=Espa%C3%B1a&sort=date"
    headers = {**HEADERS_BROWSER, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}
    html = fetch(url, headers=headers)
    if not html:
        return []

    resultados = []
    patron_json = re.search(
        r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*window',
        html, re.DOTALL
    )
    if patron_json:
        try:
            data = json.loads(patron_json.group(1))
            jobs = data.get("metaData", {}).get("mosaicProviderJobCardsModel", {}).get("results", [])
            for j in jobs[:MAX_RESULTADOS]:
                titulo  = limpiar_html(j.get("title", ""))
                empresa = limpiar_html(j.get("company", ""))
                ciudad  = limpiar_html(j.get("formattedLocation", ""))
                job_key = j.get("jobkey", "")
                url_of  = f"https://es.indeed.com/viewjob?jk={job_key}" if job_key else ""
                if titulo:
                    resultados.append({
                        "titulo": titulo, "empresa": empresa, "ubicacion": ciudad,
                        "url": url_of, "portal": "Indeed",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, KeyError):
            pass

    patron_card = re.compile(
        r'<h2[^>]*class="[^"]*jobTitle[^"]*"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>\s*<span[^>]*>(.*?)</span>',
        re.DOTALL | re.IGNORECASE
    )
    patron_emp = re.compile(r'class="[^"]*companyName[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)
    patron_loc = re.compile(r'class="[^"]*companyLocation[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)

    cards   = patron_card.findall(html)
    empresas = [limpiar_html(e) for e in patron_emp.findall(html)]
    ciudades = [limpiar_html(c) for c in patron_loc.findall(html)]

    for i, (href, tit) in enumerate(cards[:MAX_RESULTADOS]):
        titulo = limpiar_html(tit)
        if not titulo:
            continue
        resultados.append({
            "titulo": titulo,
            "empresa": empresas[i] if i < len(empresas) else "",
            "ubicacion": ciudades[i] if i < len(ciudades) else "",
            "url": href if href.startswith("http") else "https://es.indeed.com" + href,
            "portal": "Indeed",
        })
    return resultados


def buscar_sepe(termino):
    url = (
        f"https://sede.sepe.gob.es/portalEmpleo/flows/buscarOfertas"
        f"?accion=buscarOfertas&palabraClave={quote_plus(termino)}"
        f"&provinciaOferta=&tipoJornada=&nivelEstudios="
        f"&numResultados={MAX_RESULTADOS}&pagina=1"
    )
    html = fetch(url)
    resultados = []

    if html:
        try:
            data = json.loads(html)
            ofertas = data.get("listaOfertas") or data.get("ofertas") or []
            for o in ofertas[:MAX_RESULTADOS]:
                titulo  = limpiar_html(o.get("denominacionOferta") or o.get("titulo", ""))
                empresa = limpiar_html(o.get("nombreEmpresa") or o.get("empresa", ""))
                ciudad  = limpiar_html(o.get("localidad") or o.get("provincia", ""))
                cod     = o.get("codOferta") or o.get("id", "")
                url_of  = f"https://sede.sepe.gob.es/portalEmpleo/flows/verOferta?accion=verOferta&codOferta={cod}" if cod else ""
                if titulo:
                    resultados.append({
                        "titulo": titulo, "empresa": empresa, "ubicacion": ciudad,
                        "url": url_of, "portal": "SEPE",
                    })
            if resultados:
                return resultados
        except (json.JSONDecodeError, ValueError):
            pass

        patron_titulo  = re.compile(r'class="[^"]*tituloOferta[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
        patron_empresa = re.compile(r'class="[^"]*empresa[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)
        patron_ciudad  = re.compile(r'class="[^"]*localidad[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)

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
                "url": href if href.startswith("http") else "https://sede.sepe.gob.es" + href,
                "portal": "SEPE",
            })

    if not resultados:
        resultados.append({
            "titulo": f"Ver resultados de '{termino}' en SEPE",
            "empresa": "", "ubicacion": "España",
            "url": f"https://sede.sepe.gob.es/portalEmpleo/flows/buscarOfertas?accion=buscarOfertas&palabraClave={quote_plus(termino)}",
            "portal": "SEPE",
        })
    return resultados


def buscar_tecnoempleo(termino):
    url = f"https://www.tecnoempleo.com/busqueda-empleo.php?te={quote_plus(termino)}&provincia=0&ordenar=2"
    html = fetch(url)
    if not html:
        return []

    resultados = []
    patron_titulo = re.compile(
        r'<(?:h2|h3|a)[^>]*class="[^"]*(?:title|titulo)[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )
    patron_titulo_alt = re.compile(
        r'<a[^>]*href="(/oferta-trabajo/[^"]+)"[^>]*>\s*<(?:span|h[23])[^>]*>(.*?)</(?:span|h[23])>',
        re.DOTALL | re.IGNORECASE
    )
    patron_empresa = re.compile(r'class="[^"]*(?:empresa|company)[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)
    patron_ciudad  = re.compile(r'class="[^"]*(?:ciudad|location|provincia)[^"]*"[^>]*>(.*?)</[^>]+>', re.DOTALL | re.IGNORECASE)

    titulos = patron_titulo.findall(html)
    if not titulos:
        titulos = [(href, tit) for href, tit in patron_titulo_alt.findall(html)]

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
            "url": href if href.startswith("http") else "https://www.tecnoempleo.com" + href,
            "portal": "Tecnoempleo",
        })

    if not resultados:
        resultados.append({
            "titulo": f"Ver resultados de '{termino}' en Tecnoempleo",
            "empresa": "", "ubicacion": "España",
            "url": url, "portal": "Tecnoempleo",
        })
    return resultados


PORTALES = {
    "Infojobs":    buscar_infojobs,
    "Indeed":      buscar_indeed,
    "SEPE":        buscar_sepe,
    "Tecnoempleo": buscar_tecnoempleo,
}


def buscar_todo(palabras_clave, callback=None):
    """
    Ejecuta la búsqueda en todos los portales.
    callback(termino, portal, n_ofertas) se llama tras cada portal para actualizar progreso.
    Devuelve dict {termino: {portal: [ofertas]}} y total.
    """
    todos = {}
    total = 0
    for termino in palabras_clave:
        todos[termino] = {}
        for nombre, funcion in PORTALES.items():
            try:
                ofertas = funcion(termino)
            except Exception:
                ofertas = []
            todos[termino][nombre] = ofertas
            total += len(ofertas)
            if callback:
                callback(termino, nombre, len(ofertas))
            time.sleep(1.0)
    return todos, total
