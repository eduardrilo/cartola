# utils/drive_io.py
import os
from typing import Optional

import streamlit as st
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# --- Config ---
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_NAME = st.secrets.get("GOOGLE_DRIVE_FOLDER_NAME", "LOOKER")
DRIVE_FOLDER_ID = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()   # opcional
DRIVE_FILE_ID  = st.secrets.get("GOOGLE_DRIVE_FILE_ID", "").strip()      # **opcional**: si lo pones, actualizamos por ID
# Si no defines GOOGLE_DRIVE_FILE_ID, buscaremos por nombre (drive_title) dentro de la carpeta.

# --- Auth ---
def _load_credentials():
    if "gcp_service_account" not in st.secrets:
        raise FileNotFoundError(
            "Falta [gcp_service_account] en Secrets. Agrega el JSON de la Service Account en formato TOML."
        )
    sa_info = dict(st.secrets["gcp_service_account"])
    return ServiceAccountCredentials.from_json_keyfile_dict(sa_info, DRIVE_SCOPES)

def _drive_client() -> GoogleDrive:
    gauth = GoogleAuth()
    gauth.credentials = _load_credentials()
    return GoogleDrive(gauth)

def _get_service_account_email() -> Optional[str]:
    try:
        return st.secrets["gcp_service_account"].get("client_email")
    except Exception:
        return None

# --- Folder lookup ---
def _ensure_folder_id(drive: GoogleDrive) -> str:
    if DRIVE_FOLDER_ID:
        return DRIVE_FOLDER_ID

    query = (
        "mimeType='application/vnd.google-apps.folder' and trashed=false "
        f"and title='{DRIVE_FOLDER_NAME}'"
    )
    folders = drive.ListFile({'q': query}).GetList()
    if not folders:
        sa_email = _get_service_account_email()
        hint = f" y compártela con {sa_email} (Editor)" if sa_email else ""
        raise RuntimeError(
            f"No encontré la carpeta '{DRIVE_FOLDER_NAME}'. Créala{hint}."
        )
    return folders[0]["id"]

# --- File lookup ---
def _get_file_in_folder_by_title(drive: GoogleDrive, folder_id: str, drive_title: str):
    query = f"'{folder_id}' in parents and trashed=false and title='{drive_title}'"
    files = drive.ListFile({'q': query}).GetList()
    return files[0] if files else None

def _get_file_by_id(drive: GoogleDrive, file_id: str):
    try:
        f = drive.CreateFile({'id': file_id})
        f.FetchMetadata()  # valida existencia/permisos
        return f
    except Exception:
        return None

# --- Public API ---
def upload_csv_to_drive(local_path: str, drive_title: str) -> str:
    """
    Actualiza un CSV existente en Drive. NO crea archivos nuevos (los SA no tienen cuota en 'Mi unidad').
    - local_path: ruta local al CSV existente
    - drive_title: nombre del archivo ya creado en la carpeta (si no usas GOOGLE_DRIVE_FILE_ID)
    Return: file_id actualizado
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"No existe el archivo local: {local_path}")

    drive = _drive_client()

    # 1) Si nos dan el FILE_ID por Secrets, actualizamos directo por ID.
    if DRIVE_FILE_ID:
        gfile = _get_file_by_id(drive, DRIVE_FILE_ID)
        if not gfile:
            raise RuntimeError(
                "GOOGLE_DRIVE_FILE_ID no es válido o no hay permisos sobre ese archivo. "
                "Verifica el ID y que la Service Account tenga rol Editor."
            )
        gfile.SetContentFile(local_path)
        gfile.Upload()
        return gfile["id"]

    # 2) Si no hay FILE_ID, buscamos por nombre dentro de la carpeta
    folder_id = _ensure_folder_id(drive)
    gfile = _get_file_in_folder_by_title(drive, folder_id, drive_title)
    if not gfile:
        sa_email = _get_service_account_email()
        raise RuntimeError(
            f"No encontré el archivo '{drive_title}' dentro de la carpeta '{DRIVE_FOLDER_NAME}'. "
            f"Como las Service Accounts no tienen cuota, debes PRE-CREAR el archivo en esa carpeta y "
            f"compartirlo con {sa_email} (Editor), o bien define GOOGLE_DRIVE_FILE_ID en Secrets."
        )

    # Actualizar contenido
    gfile.SetContentFile(local_path)
    gfile.Upload()
    return gfile["id"]
