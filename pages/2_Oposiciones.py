import streamlit as st
from streamlit_local_storage import LocalStorage
from datetime import date, timedelta
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib.buscador_oposiciones import (
    buscar_boe, buscar_portal_empleo, PALABRAS_CLAVE_DEFAULT
)

st.set_page_config(page_title="Buscador de Oposiciones", page_icon="📋", layout="centered")
st.title("📋 Buscador de Oposiciones")
st.caption("BOE (API oficial) · Portal de Empleo Público")

# ── Persistencia en localStorage ──────────────────────────────
ls = LocalStorage()
KEY = "opos_config"

guardado = ls.getItem(KEY)
if guardado and isinstance(guardado, str):
    try:
        config = json.loads(guardado)
    except Exception:
        config = {}
else:
    config = {}

# Valores por defecto
default_perfiles = config.get("perfiles", PALABRAS_CLAVE_DEFAULT)
default_dias     = config.get("dias", 14)

# ── Configuración de perfiles ──────────────────────────────────
st.subheader("Perfiles y palabras clave")
st.caption("Cada perfil agrupa palabras clave. Edítalas a tu gusto (una por línea).")

perfiles_actuales = {}
nombres_perfil = list(default_perfiles.keys())

tabs = st.tabs(nombres_perfil + ["➕ Nuevo perfil"])

for i, nombre in enumerate(nombres_perfil):
    with tabs[i]:
        palabras_default = "\n".join(default_perfiles[nombre])
        texto = st.text_area(
            f"Palabras clave — {nombre}",
            value=palabras_default,
            height=150,
            key=f"perfil_{i}",
            label_visibility="collapsed",
        )
        perfiles_actuales[nombre] = [p.strip() for p in texto.splitlines() if p.strip()]

with tabs[-1]:
    nuevo_nombre = st.text_input("Nombre del nuevo perfil", placeholder="Ej: Enfermería")
    nuevo_kw     = st.text_area("Palabras clave", height=120, placeholder="enfermero\nDUE\nenfermería")
    if st.button("Añadir perfil") and nuevo_nombre.strip():
        perfiles_actuales[nuevo_nombre.strip()] = [
            p.strip() for p in nuevo_kw.splitlines() if p.strip()
        ]
        st.success(f"Perfil '{nuevo_nombre.strip()}' añadido. Guarda para conservarlo.")

# ── Opciones de búsqueda ───────────────────────────────────────
st.divider()
st.subheader("Opciones")

col_a, col_b = st.columns(2)
with col_a:
    dias = st.number_input("Días hacia atrás (BOE)", min_value=1, max_value=90, value=default_dias)
with col_b:
    fuente = st.radio("Fuentes", ["BOE + Portal", "Solo BOE", "Solo Portal"], horizontal=True)

# ── Botones ────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])
with col1:
    guardar = st.button("💾 Guardar configuración", use_container_width=True)
with col2:
    buscar = st.button("🔍 Buscar ahora", type="primary", use_container_width=True)

if guardar:
    config_nueva = {"perfiles": perfiles_actuales, "dias": int(dias)}
    ls.setItem(KEY, json.dumps(config_nueva))
    st.success("Configuración guardada en este dispositivo.")

# ── Búsqueda ───────────────────────────────────────────────────
if buscar:
    perfiles_validos = {k: v for k, v in perfiles_actuales.items() if v}
    if not perfiles_validos:
        st.warning("Define al menos un perfil con palabras clave.")
        st.stop()

    # Guardar automáticamente al buscar
    ls.setItem(KEY, json.dumps({"perfiles": perfiles_actuales, "dias": int(dias)}))

    hoy   = date.today()
    desde = hoy - timedelta(days=int(dias))

    st.divider()
    st.info(f"Buscando del **{desde.strftime('%d/%m/%Y')}** al **{hoy.strftime('%d/%m/%Y')}**…")

    resultados_boe    = []
    resultados_portal = []

    if fuente in ("BOE + Portal", "Solo BOE"):
        barra_boe = st.progress(0)
        txt_boe   = st.empty()

        def cb_boe(i, total, fecha):
            barra_boe.progress(i / total)
            txt_boe.caption(f"BOE: consultando {fecha}…")

        resultados_boe = buscar_boe(desde, hoy, perfiles_validos, callback=cb_boe)
        barra_boe.empty()
        txt_boe.empty()

    if fuente in ("BOE + Portal", "Solo Portal"):
        barra_portal = st.progress(0)
        txt_portal   = st.empty()

        def cb_portal(i, total, termino):
            barra_portal.progress(i / total)
            txt_portal.caption(f"Portal: buscando '{termino}'…")

        resultados_portal = buscar_portal_empleo(perfiles_validos, callback=cb_portal)
        barra_portal.empty()
        txt_portal.empty()

    # ── Presentación ──────────────────────────────────────────
    todos = resultados_boe + resultados_portal
    st.subheader(f"Resultados — {len(todos)} convocatoria(s) encontrada(s)")

    if not todos:
        st.info("No se encontraron convocatorias. Prueba a ampliar el número de días o revisar las palabras clave.")
    else:
        por_perfil = {k: [] for k in perfiles_validos}
        por_perfil["Otros"] = []

        for r in todos:
            asignado = False
            for perfil in r.get("perfiles", []):
                if perfil in por_perfil:
                    if r not in por_perfil[perfil]:
                        por_perfil[perfil].append(r)
                    asignado = True
            if not asignado:
                por_perfil["Otros"].append(r)

        for perfil, lista in por_perfil.items():
            if not lista:
                continue
            with st.expander(f"**{perfil.upper()}** — {len(lista)} convocatoria(s)", expanded=True):
                for r in lista:
                    st.markdown(f"**{r['titulo']}**")
                    st.caption(f"{r['fuente']}  ·  {r['fecha']}")
                    if r.get("url"):
                        st.markdown(f"[Ver convocatoria]({r['url']})")
                    st.markdown("---")

    st.caption(
        "**Nota:** El Portal de Empleo Público cubre BOE + boletines autonómicos, "
        "pero NO incluye la mayoría de BOP provinciales. "
        "Para BOP consulta: https://www.diba.cat/es/web/obmap/bops"
    )
