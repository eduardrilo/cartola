# utils/sheets_io.py
import streamlit as st
import gspread
from gspread_dataframe import set_with_dataframe
from typing import Optional
import pandas as pd

# Lee el Spreadsheet ID desde Secrets si lo tienes
SHEET_SPREADSHEET_ID = st.secrets.get("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()

def _get_client() -> gspread.Client:
    """
    Autentica contra Google con la Service Account desde st.secrets[gcp_service_account].
    (Habilita Google Sheets API y Google Drive API en tu proyecto.)
    """
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "Falta [gcp_service_account] en Secrets. Agrega tu Service Account en TOML."
        )
    sa_dict = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(sa_dict)

def _open_spreadsheet(client: gspread.Client, spreadsheet_id: Optional[str]) -> gspread.Spreadsheet:
    """
    Abre el Spreadsheet por ID. No crea archivos nuevos.
    """
    target_id = spreadsheet_id or SHEET_SPREADSHEET_ID
    if not target_id:
        raise RuntimeError(
            "No se proporcionó Spreadsheet ID. Define GOOGLE_SHEETS_SPREADSHEET_ID en Secrets "
            "o pásalo como argumento."
        )
    try:
        return client.open_by_key(target_id)
    except Exception as e:
        raise RuntimeError(
            "No pude abrir el Spreadsheet. Verifica:\n"
            "1) El ID es correcto.\n"
            "2) Compartiste el Sheet con el Service Account (Editor).\n"
            f"Detalle: {e}"
        )

def _get_or_create_worksheet(sh: gspread.Spreadsheet, worksheet_title: str) -> gspread.Worksheet:
    """
    Devuelve la worksheet (pestaña). Si no existe, la crea.
    (Crear hojas dentro de un Spreadsheet SÍ está permitido con SA.)
    """
    try:
        return sh.worksheet(worksheet_title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=worksheet_title, rows=100, cols=26)

def update_sheet_with_dataframe(
    df: pd.DataFrame,
    spreadsheet_id: Optional[str] = None,
    worksheet_title: str = "cartola",
    include_index: bool = False,
) -> str:
    """
    Escribe el DataFrame en una worksheet del Spreadsheet:
    - Borra contenido previo de la hoja objetivo y escribe df con encabezados.
    - Retorna la URL del Spreadsheet.
    """
    if df is None or df.empty:
        raise ValueError("El DataFrame está vacío; nada que subir a Google Sheets.")

    client = _get_client()
    sh = _open_spreadsheet(client, spreadsheet_id)
    ws = _get_or_create_worksheet(sh, worksheet_title)

    # Limpiar y escribir
    ws.clear()
    set_with_dataframe(ws, df, include_index=include_index, include_column_header=True)

    return sh.url
