# utils/sheets_io.py
import streamlit as st
import gspread
from gspread_dataframe import set_with_dataframe
import pandas as pd
from typing import Optional, Literal

# Lee (opcionalmente) el Spreadsheet ID desde Secrets.
# Puedes sobreescribirlo pasando 'spreadsheet_id' como argumento en las funciones.
SHEET_SPREADSHEET_ID = st.secrets.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()


def _get_client() -> gspread.Client:
    """
    Autentica usando la Service Account guardada en st.secrets[gcp_service_account].
    Asegúrate de habilitar Google Sheets API y Google Drive API en el proyecto de la SA,
    y de compartir el Spreadsheet con el client_email de la SA (Editor).
    """
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "Falta [gcp_service_account] en Secrets. Agrega tu Service Account en formato TOML."
        )
    sa_dict = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(sa_dict)


def _open_spreadsheet(client: gspread.Client, spreadsheet_id: Optional[str]) -> gspread.Spreadsheet:
    """
    Abre el Spreadsheet por ID (no crea archivos nuevos).
    - spreadsheet_id: si None, usa SHEET_SPREADSHEET_ID (Secrets).
    """
    target_id = spreadsheet_id or SHEET_SPREADSHEET_ID
    if not target_id:
        raise RuntimeError(
            "No se proporcionó Spreadsheet ID. Define GOOGLE_SHEETS_SPREADSHEET_ID en Secrets "
            "o pásalo como argumento a la función."
        )
    try:
        return client.open_by_key(target_id)
    except Exception as e:
        raise RuntimeError(
            "No pude abrir el Spreadsheet. Verifica:\n"
            "1) El ID es correcto.\n"
            "2) Compartiste el Sheet con la Service Account (Editor).\n"
            f"Detalle: {e}"
        )


def _get_or_create_worksheet(
    sh: gspread.Spreadsheet,
    worksheet_title: str,
) -> gspread.Worksheet:
    """
    Devuelve la worksheet (pestaña). Si no existe, la CREAMOS dentro del mismo Spreadsheet.
    Ojo: Crear hojas (pestañas) sí está permitido con Service Accounts.
    """
    try:
        return sh.worksheet(worksheet_title)
    except gspread.WorksheetNotFound:
        # Dimensiones iniciales; se ajustan automáticamente al escribir DataFrame.
        return sh.add_worksheet(title=worksheet_title, rows=100, cols=26)


def update_sheet_with_dataframe(
    df: pd.DataFrame,
    spreadsheet_id: Optional[str] = None,
    worksheet_title: str = "cartola",
    include_index: bool = False,
) -> str:
    """
    Sobrescribe una worksheet con el contenido del DataFrame (incluye encabezados).
    - Crea la worksheet si no existe.
    - Limpia y escribe todo el DF.
    Retorna: URL del Spreadsheet.
    """
    if df is None or df.empty:
        raise ValueError("El DataFrame está vacío; nada que escribir en Google Sheets.")

    client = _get_client()
    sh = _open_spreadsheet(client, spreadsheet_id)
    ws = _get_or_create_worksheet(sh, worksheet_title)

    # Limpia hoja y escribe DataFrame
    ws.clear()
    set_with_dataframe(ws, df, include_index=include_index, include_column_header=True)

    return sh.url


def write_dataframe(
    df: pd.DataFrame,
    mode: Literal["overwrite", "append"] = "overwrite",
    spreadsheet_id: Optional[str] = None,
    worksheet_title: str = "cartola",
    include_index: bool = False,
) -> str:
    """
    API de alto nivel:
    - mode="overwrite": limpia la worksheet y escribe el DataFrame completo.
    - mode="append": agrega filas al final (sin borrar lo existente).
      NOTA: en append, se asume que la worksheet ya tiene encabezados compatibles
            o que el DF incluye las mismas columnas que lo existente.

    Retorna: URL del Spreadsheet.
    """
    if df is None or df.empty:
        raise ValueError("El DataFrame está vacío; nada que escribir en Google Sheets.")

    client = _get_client()
    sh = _open_spreadsheet(client, spreadsheet_id)
    ws = _get_or_create_worksheet(sh, worksheet_title)

    if mode == "overwrite":
        ws.clear()
        set_with_dataframe(ws, df, include_index=include_index, include_column_header=True)
        return sh.url

    # Append: calculamos la siguiente fila libre y pegamos valores sin encabezados
    # Para consistencia, nos aseguramos de que df sea DataFrame "puro"
    df_to_write = df.copy()
    if include_index:
        df_to_write.reset_index(inplace=True)

    # Encuentra la siguiente fila vacía (Google Sheets es 1-indexed)
    last_row = len(ws.get_all_values())
    start_row = last_row + 1 if last_row > 0 else 1

    # Si la hoja está vacía, primero escribimos encabezados
    if last_row == 0:
        set_with_dataframe(ws, df_to_write, include_index=False, include_column_header=True)
    else:
        # Solo valores (sin header)
        values = [list(map(lambda x: "" if pd.isna(x) else x, row)) for _, row in df_to_write.iterrows()]
        if values:
            ws.update(f"A{start_row}", values)

    return sh.url
