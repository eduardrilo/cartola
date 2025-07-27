# ----------------------------------
# FUNCIONES INTERNAS
# ----------------------------------

def clasificar_gasto(descripcion):
    descripcion = descripcion.lower()
    if any(palabra in descripcion for palabra in ["uber", "cabify", "taxi"]):
        return "Transporte"
    elif any(palabra in descripcion for palabra in ["jumbo", "lider", "unimarc", "super", "mercado"]):
        return "Supermercado"
    elif any(palabra in descripcion for palabra in ["netflix", "spotify", "youtube", "hbo"]):
        return "Suscripciones"
    elif any(palabra in descripcion for palabra in ["farmacia", "cruz verde", "ahumada"]):
        return "Salud"
    elif any(palabra in descripcion for palabra in ["rest", "café", "bar", "burg", "kfc", "pizza", "mcdon", "domino"]):
        return "Comida"
    elif any(palabra in descripcion for palabra in ["abono", "transferencia", "pago recib"]):
        return "Abono"
    else:
        return "Otros"

def obtener_periodo_facturacion_custom(fecha):
    fecha = pd.to_datetime(fecha)
    if fecha.day >= 25:
        inicio = pd.Timestamp(fecha.year, fecha.month, 25)
    else:
        mes_anterior = fecha - pd.DateOffset(months=1)
        inicio = pd.Timestamp(mes_anterior.year, mes_anterior.month, 25)
    return inicio.strftime("%Y-%m")

# ----------------------------------
# CARGA AUTOMÁTICA DESDE PDF EN REPO
# ----------------------------------

os.makedirs("historico", exist_ok=True)
clave_pdf = st.sidebar.text_input("🔐 Clave para desbloquear PDFs del repo", type="password")

pdfs_en_repo = [f for f in os.listdir() if f.endswith(".pdf")]
csvs_procesados = set(f.replace(".csv", "") for f in os.listdir("historico"))

for nombre_pdf in pdfs_en_repo:
    nombre_base = nombre_pdf.replace(".pdf", "")
    if nombre_base in csvs_procesados:
        continue
    try:
        with pdfplumber.open(nombre_pdf, password=clave_pdf) as pdf:
            data = []
            for pagina in pdf.pages:
                tabla = pagina.extract_table()
                if tabla:
                    for fila in tabla[1:]:
                        if len(fila) >= 4:
                            fecha, descripcion, canal, monto = fila[:4]
                            data.append([fecha.strip(), descripcion.strip(), canal.strip(), monto.strip()])
        df = pd.DataFrame(data, columns=["Fecha", "Descripción", "Canal", "Monto"])
        df["Monto"] = df["Monto"].str.replace(".", "", regex=False).str.replace(",", "", regex=False).astype(int)
        df["Categoría"] = df["Descripción"].apply(clasificar_gasto)
        df.to_csv(f"historico/{nombre_base}.csv", index=False)
        st.success(f"✅ Procesado y guardado: {nombre_base}.csv")
    except Exception as e:
        st.warning(f"⚠️ No se pudo procesar {nombre_pdf}: {e}")

# ----------------------------------
# CARGA MANUAL PDF
# ----------------------------------

st.markdown("📂 **Sube tu cartola en PDF (opcional)**")
archivo_subido = st.file_uploader("Arrastra aquí tu cartola", type=["pdf"])
clave_manual = st.text_input("🔐 Clave para PDF subido", type="password", key="clave_manual")

if archivo_subido and clave_manual:
    nombre_archivo = archivo_subido.name.replace(".pdf", "")
    if f"{nombre_archivo}.csv" not in os.listdir("historico"):
        try:
            with pdfplumber.open(archivo_subido, password=clave_manual) as pdf:
                data = []
                for pagina in pdf.pages:
                    tabla = pagina.extract_table()
                    if tabla:
                        for fila in tabla[1:]:
                            if len(fila) >= 4:
                                fecha, descripcion, canal, monto = fila[:4]
                                data.append([fecha.strip(), descripcion.strip(), canal.strip(), monto.strip()])
            df = pd.DataFrame(data, columns=["Fecha", "Descripción", "Canal", "Monto"])
            df["Monto"] = df["Monto"].str.replace(".", "", regex=False).str.replace(",", "", regex=False).astype(int)
            df["Categoría"] = df["Descripción"].apply(clasificar_gasto)
            df.to_csv(f"historico/{nombre_archivo}.csv", index=False)
            st.success(f"✅ Cartola subida: {nombre_archivo}.csv")
        except Exception as e:
            st.error(f"❌ Error al procesar el PDF: {e}")
    else:
        st.info("ℹ️ Este archivo ya fue procesado anteriormente.")

# ----------------------------------
# CARGAR DATOS HISTÓRICOS Y VISUALIZACIÓN
# ----------------------------------

archivos = [f for f in os.listdir("historico") if f.endswith(".csv")]
if not archivos:
    st.warning("⚠️ No hay cartolas disponibles.")
else:
    dfs = [pd.read_csv(f"historico/{f}") for f in archivos]
    df_historico = pd.concat(dfs, ignore_index=True)
    df_historico = df_historico.drop_duplicates(subset=["Fecha", "Descripción", "Monto"])
    df_historico["Fecha"] = pd.to_datetime(df_historico["Fecha"])
    df_historico["Periodo"] = df_historico["Fecha"].apply(obtener_periodo_facturacion_custom)
    df_historico["Monto_formateado"] = df_historico["Monto"].apply(lambda x: f"$ {x:,.0f}".replace(",", "."))

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

    # Métricas principales
    gastos = df_vista[~df_vista["Categoría"].isin(["Abono"])]["Monto"].sum()
    abonos = df_vista[df_vista["Categoría"] == "Abono"]["Monto"].sum()
    neto = gastos - abonos

    st.markdown("### 💵 Resumen financiero")
    col3, col4, col5 = st.columns(3)
    col3.metric("Gastos", f"$ {gastos:,.0f}".replace(",", "."))
    col4.metric("Abonos", f"$ {abonos:,.0f}".replace(",", "."))
    col5.metric("Gasto Total Neto", f"$ {neto:,.0f}".replace(",", "."))

    # Gráfico: evolución neta por cartola
    st.markdown("### 📊 Evolución de Gasto Total Neto por Cartola")
    resumen = df_historico.groupby("Periodo").apply(
        lambda x: x[~x["Categoría"].isin(["Abono"])]["Monto"].sum()
                  - x[x["Categoría"] == "Abono"]["Monto"].sum()
    ).reset_index(name="Gasto Total Neto")
    st.bar_chart(resumen.set_index("Periodo"))
