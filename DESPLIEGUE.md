# Cómo subir y desplegar la app

## Estructura de archivos necesaria en GitHub

```
tu-repositorio/
├── app.py
├── requirements.txt
├── pages/
│   ├── 1_Empleo.py
│   └── 2_Oposiciones.py
└── lib/
    ├── __init__.py
    ├── buscador_empleo.py
    └── buscador_oposiciones.py
```

---

## Paso 1 — Crear repositorio en GitHub

1. Ve a https://github.com/new
2. Nombre: `buscadores` (o el que quieras)
3. Visibilidad: **Public** (necesario para el plan gratuito de Streamlit)
4. Pulsa **Create repository**

---

## Paso 2 — Subir los archivos

### Opción A: desde el navegador (sin instalar nada)

1. En tu repositorio vacío, pulsa **Add file → Upload files**
2. Arrastra todos los archivos y carpetas
3. Pulsa **Commit changes**

### Opción B: con Git desde el PC

```bash
cd C:/DESARROLLO/PROYECTOSPERSONALES/BUSCADORES
git init
git add .
git commit -m "primera versión"
git remote add origin https://github.com/TU_USUARIO/buscadores.git
git push -u origin main
```

---

## Paso 3 — Desplegar en Streamlit Community Cloud

1. Ve a https://share.streamlit.io
2. Inicia sesión con tu cuenta de GitHub
3. Pulsa **New app**
4. Selecciona:
   - **Repository**: `TU_USUARIO/buscadores`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Pulsa **Deploy**

En 1-2 minutos tendrás una URL pública tipo:
`https://TU_USUARIO-buscadores-app-XXXXX.streamlit.app`

---

## Paso 4 — Compartir con la familia

Comparte esa URL. Cada persona:
- La abre desde el navegador de su móvil
- Puede guardarla como acceso directo en la pantalla de inicio
- Sus palabras clave se guardan en su propio dispositivo

---

## Actualizar la app en el futuro

Cualquier cambio que subas a GitHub se despliega automáticamente en 1-2 minutos.
