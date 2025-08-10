# utils/drive_io.py
import os
from typing import Optional

import streamlit as st
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# Scopes y configuración (puedes sobreescribir por Secrets opcionalmente)
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_NAME = st.secrets.get("GOOGLE_DRIVE_FOLDER_NAME", "LOOKER")
DRIVE_FOLDER_ID = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()  # opcional


def _load_credentials():
    """Carga credenciales desde Streamlit Secrets."""
    if "gcp_service_account" not in st.secrets:
        raise FileNotFoundError(
            "No encontré [gcp_service_account] en Secrets. "
            "Agrega tu Service Account en Settings → Secrets (formato TOML)."
        )
    sa_info = dict(st.secrets["gcp_service_account"])
    return ServiceAccountCredentials.from_json_keyfile_dict(sa_info, DRIVE_SCOPES)


def _drive_client() -> GoogleDrive:
    """Inicializa el cliente de Google Drive usando PyDrive2."""
    gauth = GoogleAuth()
    gauth.credentials = _load_credentials()
    return GoogleDrive(gauth)


def _get_service_account_email() -> Optional[str]:
    """Devuelve el client_email del SA (útil para mensajes de permisos)."""
    try:
        return st.secrets["gcp_service_account"].get("client_email")
    except Exception:
        return None


def _ensure_folder_id(drive: GoogleDrive) -> str:
    """
    Obtiene el folder_id a usar:
    - Si se define GOOGLE_DRIVE_FOLDER_ID en Secrets, usa ese.
    - Si no, busca por nombre (DRIVE_FOLDER_NAME) y toma la primera coincidencia.
    """
    if DRIVE_FOLDER_ID:
        return DRIVE_FOLDER_ID

    query = (
        "mimeType='application/vnd.google-apps.folder' and trashed=false "
        f"and title='{DRIVE_FOLDER_NAME}'"
    )
    folders = drive.ListFile({'q': query}).GetList()
    if not folders:
        sa_email = _get_service_account_email()
        msg_extra = f" y compártela con {sa_email} (Editor)" if sa_email else ""
        raise RuntimeError(
            f"No encontré la carpeta '{DRIVE_FOLDER_NAME}' en tu Drive. "
            f"Crea la carpeta{msg_extra}."
        )
    return folders[0]["id"]


def upload_csv_to_drive(local_path: str, drive_title: str) -> str:
    """
    Sube (o actualiza) un CSV a Google Drive dentro de la carpeta configurada.
    - local_path: ruta local al CSV (ya existente)
    - drive_title: nombre del archivo en Drive (p.ej. 'cartola_latest.csv')
    Retorna: file_id del archivo en Drive.
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"No existe el archivo local: {local_path}")

    drive = _drive_client()

    # 1️⃣ Si hay ID fijo en Secrets, actualizamos por ID
    drive_file_id = st.secrets.get("GOOGLE_DRIVE_FILE_ID", "").strip()
    if drive_file_id:
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.SetContentFile(local_path)
        gfile.Upload()
        return gfile["id"]

    # 2️⃣ Si no hay ID, buscamos la carpeta
    folder_id = _ensure_folder_id(drive)

    # ¿Existe ya un archivo con ese nombre dentro de la carpeta?
    query = f"'{folder_id}' in parents and trashed=false and title='{drive_title}'"
    existing = drive.ListFile({'q': query}).GetList()

    if existing:
        gfile = existing[0]
        gfile.SetContentFile(local_path)
        gfile.Upload()
        return gfile["id"]

    # 3️⃣ Crear nuevo archivo (solo funcionará si es Shared Drive o tu cuenta permite creación)
    gfile = drive.CreateFile({
        "title": drive_title,
        "parents": [{"id": folder_id}],
        "mimeType": "text/csv",
    })
    gfile.SetContentFile(local_path)
    gfile.Upload()
    return gfile["id"]
