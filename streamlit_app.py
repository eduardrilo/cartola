import os
import re
import pdfplumber
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px

st.set_page_config(page_title="Cartola Santander", layout="wide")
st.title("📊 Clasificador de Gastos Cartola Santander")

# Subida del archivo
uploaded_file = st.file_uploader("Sube tu cartola en PDF", type="pdf")

# Ingreso de clave
password = st.text_input("Ingresa la clave del PDF", type="password")

# Clasificación mejorada
def clasificar_categoria(descripcion):
    descripcion = str(descripcion).upper()

    if "ENEL" in descripcion:
        return "💡 Luz"
    if "NOTA DE CREDITO" in descripcion:
        return "🎁 Devoluciones"
    elif "BARBER" in descripcion:
        return "✂️ Barbería"
    elif "ENTELPCS" in descripcion or "ENTEL PCS" in descripcion:
        return "📱 Plan Celular"
    elif "AGUASCORDILLERA" in descripcion or "AGUAS CORDILLERA" in descripcion:
        return "🚿 Agua"
    elif any(x in descripcion for x in ["ARAMCO", "COPEC", "PETROBRAS", "SHELL"]):
        return "⛽ Gasolina"
    elif any(x in descripcion for x in ["GUESS", "PARIS", "FALABELLA", "HYM", "EASTON"]):
        return "👖 Ropa"
    elif any(x in descripcion for x in ["SABA", "ESTACIONAMIENTO"]):
        return "🅿️ Estacionamiento"
    elif any(x in descripcion for x in ["VESPUCIONORTE", "COSTANERA", "AUTOPASE", "VESPUCIOSUR", "CONCESIO"]):
        return "🛣️ Peaje / Autopista"
    elif "KRYTERION" in descripcion:
        return "🎓 Educación"
    elif any(x in descripcion for x in ["UBER", "DIDI", "BIPQR"]):
        return "🚗 Transporte"
    elif any(x in descripcion for x in ["BRANDO", "CASAIDEAS"]):
        return "🏠 Hogar"
    elif any(x in descripcion for x in ["FARMACIA", "CRUZ VERDE", "SALCO", "PROCEDIMIENTOS", "CONTINGENCIA CPA"]):
        return "💊 Salud"
    elif any(x in descripcion for x in ["TUU","BDK", "GASTRONOMICA", "RESTAURANTE", "CAFE", "MCDONALD", "STARBUCKS"]):
        return "🍽️ Comida"
    elif "VETERINARIA" in descripcion or "PET" in descripcion:
        return "🐾 Veterinaria"
    elif "SEGURO" in descripcion or "SANTANDER COMPRAS P.A.T" in descripcion:
        return "🛡️ Seguro Auto"
    elif "CHATGPT" in descripcion:
        return "🤖 Chat GPT"
    elif "MOVISTARHOGAR" in descripcion:
        return "📺 Internet + Televisión"
    elif "STA ISABEL" in descripcion or "SANTA ISABEL" in descripcion:
        return "🛒 Supermercado"
    else:
        return "📦 Otro gasto"

# Extraer movimientos desde texto del PDF
def extraer_movimientos(texto):
    
    movimientos = []
    lineas = texto.splitlines()[8:]

    for linea in lineas:
        if not "$" in linea:
            continue
        match = re.search(r"(\d{2}/\d{2}/\d{4}).*?\$[\s-]*([\d.]+)", linea)
        if not match:
            continue
        fecha = match.group(1)
        monto = float(match.group(2).replace(".", ""))
        if "NOTA DE CREDITO" in linea.upper():
            monto *= -1
        desc = re.sub(r".*?\d{4} ", "", linea).split("$")[0].strip()
        categoria = clasificar_categoria(desc)
        movimientos.append({
            "Fecha": fecha,
            "Descripción": desc,
            "Monto": monto,
            "Categoría": categoria
        })
    return pd.DataFrame(movimientos)

if uploaded_file and password:
    with pdfplumber.open(uploaded_file, password=password) as pdf:
        texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

    df = extraer_movimientos(texto)
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
    df = df[~df["Descripción"].str.contains("(?i)banco|monto cancelado", na=False)]
    
    # Tomamos la fecha del primer movimiento como referencia
    fecha_referencia = df["Fecha"].min()
    anio_mes = fecha_referencia.strftime("%Y-%m")  # Ej: 2024-03
    nombre_archivo = f"historico/cartola_{anio_mes}.csv"
    
    # Creamos carpeta si no existe
    os.makedirs("historico", exist_ok=True)
    
    # Guardamos si no existe ya ese archivo
    if not os.path.exists(nombre_archivo):
        df.to_csv(nombre_archivo, index=False)
        st.success(f"✅ Cartola guardada como {nombre_archivo}")
    else:
        st.info(f"ℹ️ Ya existe un archivo para el mes {anio_mes}, no se volvió a guardar.")


    if df.empty:
        st.warning("No se encontraron movimientos.")
    else:
        df["Monto_formateado"] = df["Monto"].apply(lambda x: f"$ {x:,.0f}".replace(",", "."))

        categorias = df["Categoría"].unique().tolist()
        seleccion = st.multiselect("🔎 Filtrar por categoría:", categorias, default=categorias)
        df_filtrado = df[df["Categoría"].isin(seleccion)].sort_values("Fecha", ascending=False)

        st.dataframe(df_filtrado[["Fecha", "Descripción", "Monto_formateado", "Categoría"]], use_container_width=True)

        gasto_total = df_filtrado[df_filtrado["Monto"] > 0]["Monto"].sum()
        abonos = df_filtrado[df_filtrado["Monto"] < 0]["Monto"].sum()
        st.metric("💸 Gasto total", f"$ {gasto_total:,.0f}")
        st.metric("💰 Abonos", f"$ {abonos:,.0f}")
        st.metric("📄 Total de movimientos", len(df_filtrado))

        st.subheader("📊 Distribución de gasto por categoría")

        df_filtrado["Monto"] = pd.to_numeric(df_filtrado["Monto"], errors="coerce")
        df_agrupado = df_filtrado[df_filtrado["Monto"] > 0].groupby("Categoría", as_index=False)["Monto"].sum()

        if not df_agrupado.empty:
            chart = alt.Chart(df_agrupado).mark_bar().encode(
                x=alt.X("Categoría:N", sort='-y'),
                y=alt.Y("Monto:Q", scale=alt.Scale(domain=[0, df_agrupado["Monto"].max() * 1.1])),
                color="Categoría:N",
                tooltip=[
                    alt.Tooltip("Categoría", title="Categoría"),
                    alt.Tooltip("Monto", title="Monto", format=",.0f")
                ]
            ).properties(width=600, height=400)
            st.altair_chart(chart, use_container_width=True)

            st.subheader("🥧 Gasto por categoría (estilo torta 3D)")
            fig_pie = px.pie(
                df_agrupado,
                names="Categoría",
                values="Monto",
                title="🧁 Distribución por categoría",
                hole=0.4
            )
            fig_pie.update_traces(
                textinfo='percent+label',
                pull=[0.05]*len(df_agrupado),
                hovertemplate="%{label}<br>$ %{value:,.0f}<extra></extra>"
            )
            fig_pie.update_layout(showlegend=True, height=500)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos para mostrar en el gráfico.")
