import os
import re
import pdfplumber
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Cartola Santander", layout="wide")
st.title("🧾 Clasificador de Gastos Cartola Santander")
with st.expander("🧹 Eliminar cartolas anteriores"):
    archivos_existentes = [f for f in os.listdir("historico") if f.endswith(".csv")]
    if archivos_existentes:
        cartolas_a_borrar = st.multiselect("Selecciona las cartolas que quieres borrar:", archivos_existentes)
        if st.button("🗑️ Borrar seleccionadas"):
            for archivo in cartolas_a_borrar:
                os.remove(os.path.join("historico", archivo))
            st.success(f"✅ {len(cartolas_a_borrar)} cartola(s) eliminada(s). Recarga la página para ver los cambios.")
    else:
        st.info("No hay cartolas guardadas aún.")


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
    elif any(x in descripcion for x in ["GUESS", "PARIS", "FALABELLA", "HM", "H&M", "EASTON", "CK"]):
        return "👖 Ropa"
    elif any(x in descripcion for x in ["SABA", "ESTACIONAMIENTO", "PARKING"]):
        return "🚩 Estacionamiento"
    elif any(x in descripcion for x in ["VESPUCIONORTE", "COSTANERA", "AUTOPASE", "VESPUCIOSUR", "CONCESIO", "AUTOPISTA"]):
        return "🚧 Peaje / Autopista"
    elif any(x in descripcion for x in ["KRYTERION"]):
        return "🎓 Educacion"
    elif any(x in descripcion for x in ["UBER", "DIDI", "BIPQR"]):
        return "🚗 Transporte"
    elif any(x in descripcion for x in ["BRANDO", "CASAIDEAS"]):
        return "🏠 Hogar"
    elif any(x in descripcion for x in ["FARMACIA", "CRUZ VERDE", "SALCO", "PROCEDIMIENTOS", "CONTINGENCIA CPA", "CLINICA"]):
        return "💊 Salud"
    elif any(x in descripcion for x in ["TUU","BDK", "GASTRONOMICA", "RESTAURANTE", "CAFE", "MCDONALD", "STARBUCKS", "MELT", "ICE"]):
        return "🍽️ Comida"
    elif "VETERINARIA" in descripcion or "PET" in descripcion:
        return "🐾 Veterinaria"
    elif "SEGURO" in descripcion or "SANTANDER COMPRAS P.A.T" in descripcion:
        return "🛡️ Seguro Auto"
    elif "CHATGPT" in descripcion:
        return "🤖 Chat GPT"
    elif "METROGAS" in descripcion:
        return "💨 GAS"
    elif "MOVISTARHOGAR" in descripcion:
        return "📺 Internet + TV"
    elif any(x in descripcion for x in ["STA ISABEL","PIWEN", "LIDER", "JUMBO", "TOTTUS"]):
        return "🛒 Supermercado"
    else:
        return "📦 Otro gasto"

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

        # Extraer descripción
        partes = linea.split(fecha)
        if len(partes) > 1:
            desc_bruta = partes[1].split("$")[0].strip()
        else:
            desc_bruta = "Revisar"

        # Fallback si queda vacía
        if not desc_bruta or desc_bruta.upper() in ["", "NONE"]:
            desc_bruta = "Revisar"

        categoria = clasificar_categoria(desc_bruta)

        movimientos.append({
            "Fecha": fecha,
            "Descripción": desc_bruta,
            "Monto": monto,
            "Categoría": categoria
        })

    return pd.DataFrame(movimientos)


def obtener_periodo_facturacion_custom(fecha):
    fecha = pd.to_datetime(fecha)
    periodo = pd.Timestamp(year=fecha.year, month=fecha.month, day=25)
    return periodo.strftime("%Y-%m-%d")

uploaded_file = st.file_uploader("Sube tu cartola en PDF", type="pdf")
password = st.text_input("Ingresa la clave del PDF", type="password")

if uploaded_file and password:
    with pdfplumber.open(uploaded_file, password=password) as pdf:
        texto = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    df = extraer_movimientos(texto)
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
    df = df[~df["Descripción"].str.contains("(?i)banco|monto cancelado", na=False)]

        # Asegúrate de que la columna Fecha esté en formato datetime
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors='coerce')

    # Extraer la fecha del nombre del PDF y guardar CSV
if uploaded_file is not None and password:
    nombre_pdf = uploaded_file.name  # ✅ Definimos nombre del PDF

    try:
        match = re.search(r"_(\d{8})\.pdf$", nombre_pdf)
        if match:
            fecha_pdf = datetime.strptime(match.group(1), "%Y%m%d")
            periodo_referencia = obtener_periodo_facturacion_custom(fecha_pdf)
        else:
            st.error("❌ No se pudo extraer la fecha del nombre del archivo PDF.")
            st.stop()

        df["Periodo"] = periodo_referencia

        os.makedirs("historico", exist_ok=True)
        nombre_archivo = f"historico/cartola_{periodo_referencia}.csv"
        if not os.path.exists(nombre_archivo):
            df.to_csv(nombre_archivo, index=False)
            st.success(f"✅ Cartola guardada como {nombre_archivo}")
        else:
            st.info(f"ℹ️ Cartola ya existe para el periodo {periodo_referencia}. No se guardó nuevamente.")

    except Exception as e:
        st.error(f"❌ Error procesando la cartola: {e}")



archivos = [f for f in os.listdir("historico") if f.endswith(".csv")]
if not archivos:
    st.warning("⚠️ No hay cartolas cargadas.")
else:
    dfs = [pd.read_csv(f"historico/{f}") for f in archivos]
    df_historico = pd.concat(dfs, ignore_index=True)
    df_historico["Fecha"] = pd.to_datetime(df_historico["Fecha"])
    df_historico["Monto_formateado"] = df_historico["Monto"].apply(lambda x: f"$ {x:,.0f}".replace(",", "."))
    df_historico["Periodo"] = df_historico["Fecha"].apply(obtener_periodo_facturacion_custom)

    periodos = sorted(df_historico["Periodo"].unique(), reverse=True)
    categorias = sorted(df_historico["Categoría"].unique())

    col1, col2 = st.columns(2)
    default_periodo = periodos[0] if periodos else "Todos"
    filtro_periodo = col1.selectbox("🗓️ Filtrar por cartola (25 a 25):", ["Todos"] + periodos, index=1 if "Todos" in periodos else 0)
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
            tooltip=[
                alt.Tooltip("Categoría", title="Categoría"),
                alt.Tooltip("Monto", title="Monto", format=",.0f")
            ]
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
        tooltip=[
            alt.Tooltip("Periodo", title="Periodo"),
            alt.Tooltip("Gasto Neto", format=",.0f")
        ]
    ).properties(width=800, height=400)
    st.altair_chart(grafico, use_container_width=True)
