import streamlit as st
from streamlit_local_storage import LocalStorage
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.buscador_empleo import buscar_todo, PORTALES

st.set_page_config(page_title="Buscador de Empleo", page_icon="💼", layout="centered")
st.title("💼 Buscador de Empleo")
st.caption("Infojobs · Indeed · SEPE · Tecnoempleo")

# ── Persistencia en localStorage ──────────────────────────────
ls = LocalStorage()
KEY = "empleo_keywords"

guardadas = ls.getItem(KEY)
if guardadas and isinstance(guardadas, str):
    default_kw = guardadas
else:
    default_kw = "trabajo social\nmonitor de ocio\nintegración social\neducador social\nanimador sociocultural"

# ── Formulario de palabras clave ───────────────────────────────
st.subheader("Palabras clave")
st.caption("Una por línea. Puedes añadir, quitar o cambiar las que quieras.")

keywords_text = st.text_area(
    label="Palabras clave",
    value=default_kw,
    height=160,
    label_visibility="collapsed",
    placeholder="trabajo social\nmonitor de ocio\n...",
)

col1, col2 = st.columns([1, 1])
with col1:
    guardar = st.button("💾 Guardar palabras clave", use_container_width=True)
with col2:
    buscar = st.button("🔍 Buscar ahora", type="primary", use_container_width=True)

if guardar:
    ls.setItem(KEY, keywords_text)
    st.success("Palabras clave guardadas en este dispositivo.")

# ── Búsqueda ───────────────────────────────────────────────────
if buscar:
    palabras = [p.strip() for p in keywords_text.splitlines() if p.strip()]
    if not palabras:
        st.warning("Escribe al menos una palabra clave.")
        st.stop()

    # Guardar automáticamente al buscar
    ls.setItem(KEY, keywords_text)

    st.divider()
    progreso = st.empty()
    barra    = st.progress(0)
    total_pasos = len(palabras) * len(PORTALES)
    estado = {"paso": 0}

    def on_progreso(termino, portal, n):
        estado["paso"] += 1
        barra.progress(estado["paso"] / total_pasos)
        progreso.caption(f"Buscando **{termino}** en {portal}…")

    todos, _ = buscar_todo(palabras, callback=on_progreso)

    barra.empty()
    progreso.empty()

    # Contar real
    total_ofertas = sum(
        len(ofertas)
        for por_portal in todos.values()
        for ofertas in por_portal.values()
    )

    st.subheader(f"Resultados — {total_ofertas} oferta(s) encontrada(s)")

    if total_ofertas == 0:
        st.info("No se encontraron ofertas. Los portales pueden bloquear el acceso automático. Usa los enlaces directos.")
    else:
        for termino, por_portal in todos.items():
            hay = any(len(v) > 0 for v in por_portal.values())
            if not hay:
                continue
            with st.expander(f"▶ {termino.upper()}", expanded=True):
                for portal, ofertas in por_portal.items():
                    if not ofertas:
                        continue
                    st.markdown(f"**{portal}**")
                    for o in ofertas:
                        titulo   = o.get("titulo", "")[:80]
                        empresa  = o.get("empresa", "")
                        ubicacion = o.get("ubicacion", "")
                        url_of   = o.get("url", "")
                        linea = f"**{titulo}**"
                        detalles = " · ".join(filter(None, [empresa, ubicacion]))
                        if detalles:
                            linea += f"  \n{detalles}"
                        if url_of:
                            linea += f"  \n[Ver oferta]({url_of})"
                        st.markdown(linea)
                        st.markdown("---")

    # ── Enlaces directos ──────────────────────────────────────
    st.divider()
    st.subheader("Enlaces directos (búsqueda manual)")
    from urllib.parse import quote_plus
    for termino in palabras:
        t = quote_plus(termino)
        with st.expander(termino):
            st.markdown(
                f"- [Infojobs](https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={t})\n"
                f"- [Indeed](https://es.indeed.com/jobs?q={t}&l=Espa%C3%B1a)\n"
                f"- [SEPE](https://empleo.sepe.es/portalEmpleo/servlet/ofertaServlet?accion=buscarOfertas&palabraClave={t})\n"
                f"- [Tecnoempleo](https://www.tecnoempleo.com/busqueda-empleo.php?te={t})"
            )
