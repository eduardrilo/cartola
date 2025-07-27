import os
import re
import glob
import pdfplumber
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Cartola Santander", layout="wide")
st.title("🧾 Clasificador de Gastos Cartola Santander")

# Clasificador de gastos
def clasificar_categoria(descripcion):
    descripcion = str(descripcion).upper()
    if "ENEL" in descripcion:
        return "💡 Luz"
    if "NOTA DE CREDITO" in descripcion:
        return "🍱 Devoluciones"
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
        return "🚩 Estacionamiento"
    elif any(x in descripcion for x in ["VESPUCIONORTE", "COSTANERA", "AUTOPASE", "VESPUCIOSUR", "CONCESIO"]):
        return "🚧 Peaje / Autopista"
    elif any(x in descripcion for x in ["KRYTERION"]):
        return "🎓 Educacion"
    elif any(x in descripcion for x in ["UBER", "DIDI", "BIPQR"]):
        return "🚗 Transporte"
    elif any(x in descripcion for x in ["BRANDO", "CASAIDEAS"]):
        return "🏠 Hogar"
    elif any(x in descripcion for x in ["FARMACIA", "CRUZ VERDE", "SALCO", "PROCEDIMIENTOS", "CONTINGENCIA CPA"]):
        return "💊 Salud"
    elif any(x in descripcion for x in ["TUU", "BDK", "GASTRONOMICA", "RESTAURANTE", "CAFE", "MCDONALD", "STARBUCKS"]):
        return "🍽️ Comida"
    elif "VETERINARIA" in descripcion or "PET" in descripcion:
        return "🐾 Veterinaria"
    elif "SEGURO" in descripcion or "SANTANDER COMPRAS P.A.T" in descripcion:
        return "🛡️ Seguro Auto"
    elif "CHATGPT" in descripcion:
        return "🤖 Chat GPT"
    elif "MOVISTARHOGAR" in descripcion:
        return "📺 Internet + TV"
    elif "STA ISABEL" in descripcion or "SANTA ISABEL" in descripcion:
        return "🛒 Supermercado"
    else:
        return "📦 Otro gasto"

# Lógica de periodos (25 a 25)
def obtener_periodo_facturacion_custom(fecha):
    fecha = pd.to_datetime(fecha)
    if fecha.day >= 25:
        inicio = pd.Timestamp(fecha.year, fecha.month, 25)
    else:
        mes_anterior = fecha - pd.DateOffset(months=1)
        inicio = pd.Timestamp(mes_anterior.year, mes_anterior.month, 25)
    return inicio.strftime("%Y-%m")

# Extraer movimientos desde texto
def extraer_movimientos(texto):
    movimientos = []
    lineas = texto.splitlines()[8:]
    for linea in lineas:
        if "$" not in linea:
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

# Asegurar carpeta
try:
    os.makedirs("historico", exist_ok=True)
except Exception as e:
    st.error(f"Error creando carpeta historico: {e}")

# Procesar PDFs del proyecto
archivos_locales = glob.glob("80_*.pdf")
for pdf_path in archivos_locales:
    try:
        with pdfplumber.open(pdf_path, password=os.getenv("PDF_PASSWORD")) as pdf:
            texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        df = extraer_movimientos(texto)
        df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
        df["Periodo"] = df["Fecha"].apply(obtener_periodo_facturacion_custom)
        periodo = df["Periodo"].iloc[0]
        archivo_csv = f"historico/cartola_{periodo}.csv"
        if os.path.exists(archivo_csv):
            existente = pd.read_csv(archivo_csv, parse_dates=["Fecha"])
            df = pd.concat([existente, df]).drop_duplicates(subset=["Fecha", "Descripción", "Monto"])
        df.to_csv(archivo_csv, index=False)
    except Exception as e:
        st.warning(f"No se pudo procesar {pdf_path}: {e}")

# Subida manual del usuario
uploaded_file = st.file_uploader("📎 Sube tu cartola en PDF (manual)", type="pdf")
password = st.text_input("🔐 Clave del PDF", type="password")
if uploaded_file and password:
    with pdfplumber.open(uploaded_file, password=password) as pdf:
        texto = "\n".join([pagina.extract_text() for pagina in pdf.pages if pagina.extract_text()])
    df = extraer_movimientos(texto)
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
    df = df[~df["Descripción"].str.contains("(?i)banco|monto cancelado", na=False)]
    df["Periodo"] = df["Fecha"].apply(obtener_periodo_facturacion_custom)
    periodo = df["Periodo"].iloc[0]
    archivo_csv = f"historico/cartola_{periodo}.csv"
    if os.path.exists(archivo_csv):
        existente = pd.read_csv(archivo_csv, parse_dates=["Fecha"])
        df = pd.concat([existente, df]).drop_duplicates(subset=["Fecha", "Descripción", "Monto"])
        st.info("ℹ️ Cartola existente actualizada sin duplicados.")
    else:
        st.success("✅ Nueva cartola guardada.")
    df.to_csv(archivo_csv, index=False)

# Cargar datos históricos
os.makedirs("historico", exist_ok=True)
archivos = [f for f in os.listdir("historico") if f.endswith(".csv")]
if not archivos:
    st.warning("⚠️ No hay cartolas disponibles.")
else:
    dfs = [pd.read_csv(f"historico/{f}") for f in archivos]
    df_historico = pd.concat(dfs, ignore_index=True)
    df_historico["Fecha"] = pd.to_datetime(df_historico["Fecha"])
    df_historico["Monto_formateado"] = df_historico["Monto"].apply(lambda x: f"$ {x:,.0f}".replace(",", "."))
    df_historico["Periodo"] = df_historico["Fecha"].apply(obtener_periodo_facturacion_custom)

    periodos = sorted(df_historico["Periodo"].unique(), reverse=True)
    categorias = sorted(df_historico["Categoría"].unique())

    col1, col2 = st.columns(2)
    filtro_periodo = col1.selectbox("🗓️ Filtrar por cartola (25 a 25):", ["Todos"] + periodos)
    filtro_cat = col2.multiselect("🔍 Categorías:", categorias, default=categorias)

    df_vista = df_historico.copy()
    if filtro_periodo != "Todos":
        df_vista = df_vista[df_vista["Periodo"] == filtro_periodo]
    df_vista = df_vista[df_vista["Categoría"].isin(filtro_cat)]
    df_vista = df_vista.sort_values("Fecha", ascending=False)

    st.dataframe(df_vista[["Fecha", "Descripción", "Monto_formateado", "Categoría"]], use_container_width=True)

    gastos = df_vista[df_vista["Monto"] > 0]["Monto"].sum()
    abonos = df_vista[df_vista["Monto"] < 0]["Monto"].sum()
    gasto_neto = gastos + abonos

    st.metric("💸 Gastos", f"$ {gastos:,.0f}")
    st.metric("💰 Abonos", f"$ {abonos:,.0f}")
    st.metric("📊 Gasto neto (real)", f"$ {gasto_neto:,.0f}")
    st.metric("📄 Total de movimientos", len(df_vista))

    df_agrupado = df_vista[df_vista["Monto"] > 0].groupby("Categoría", as_index=False)["Monto"].sum()

    st.subheader("📊 Distribución de gasto por categoría")
    if not df_agrupado.empty:
        chart = alt.Chart(df_agrupado).mark_bar().encode(
            x=alt.X("Categoría:N", sort='-y'),
            y=alt.Y("Monto:Q", scale=alt.Scale(domain=[0, df_agrupado["Monto"].max() * 1.1])),
            color="Categoría:N",
            tooltip=["Categoría", alt.Tooltip("Monto", format=",.0f")]
        ).properties(width=600, height=400)
        st.altair_chart(chart, use_container_width=True)

    st.subheader("🥧 Gasto por categoría (torta 3D)")
    fig_pie = px.pie(
        df_agrupado,
        names="Categoría",
        values="Monto",
        title="🧻 Distribución por categoría",
        hole=0.4
    )
    fig_pie.update_traces(
        textinfo='percent+label',
        pull=[0.05]*len(df_agrupado),
        hovertemplate="%{label}<br>$ %{value:,.0f}<extra></extra>"
    )
    fig_pie.update_layout(showlegend=True, height=500)
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("📉 Seguimiento de Gasto Neto por Cartola (25 a 25)")
    df_gasto_neto = df_historico.groupby("Periodo").agg(
        Gastos=("Monto", lambda x: x[x > 0].sum()),
        Abonos=("Monto", lambda x: x[x < 0].sum())
    ).reset_index()
    df_gasto_neto["Gasto Neto"] = df_gasto_neto["Gastos"] + df_gasto_neto["Abonos"]

    grafico = alt.Chart(df_gasto_neto).mark_bar().encode(
        x=alt.X("Periodo:N", sort=None),
        y=alt.Y("Gasto Neto:Q", title="Gasto Neto"),
        tooltip=["Periodo", alt.Tooltip("Gasto Neto", format=",.0f")]
    ).properties(width=800, height=400)
    st.altair_chart(grafico, use_container_width=True)
