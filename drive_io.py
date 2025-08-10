# utils/drive_io.py
import os, json
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_NAME = os.getenv("GOOGLE_DRIVE_FOLDER_NAME", "LOOKER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

def _load_credentials():
    # 1) Streamlit Cloud: secrets TOML -> [gcp_service_account]
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            sa_dict = dict(st.secrets["gcp_service_account"])
            return ServiceAccountCredentials.from_json_keyfile_dict(sa_dict, DRIVE_SCOPES)
    except Exception:
        pass

    # 2) (Opcional) variable de entorno con el JSON completo
    raw = os.getenv("GCP_SA_JSON", "")
    if raw:
        return ServiceAccountCredentials.from_json_keyfile_dict(json.loads(raw), DRIVE_SCOPES)

    raise FileNotFoundError(
        "No encontré credenciales:\n"
        "- Define [gcp_service_account] en Secrets (recomendado), o\n"
        "- Exporta GCP_SA_JSON con el JSON completo de la service account."
    )

def _drive_client():
    gauth = GoogleAuth()
    gauth.credentials = _load_credentials()
    return GoogleDrive(gauth)

def _ensure_folder_id(drive: GoogleDrive) -> str:
    if DRIVE_FOLDER_ID:
        return DRIVE_FOLDER_ID
    q = ("mimeType='application/vnd.google-apps.folder' and trashed=false "
         f"and title='{DRIVE_FOLDER_NAME}'")
    folders = drive.ListFile({'q': q}).GetList()
    if not folders:
        raise RuntimeError(
            f"No encontré la carpeta '{DRIVE_FOLDER_NAME}' en tu Drive. "
            "Créala y compártela con el Service Account (Editor)."
        )
    return folders[0]["id"]

def upload_csv_to_drive(local_path: str, drive_title: str) -> str:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"No existe el archivo local: {local_path}")
    drive = _drive_client()
    folder_id = _ensure_folder_id(drive)

    # Si ya existe un archivo con ese nombre en la carpeta, lo actualiza
    existing = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false and title='{drive_title}'"}).GetList()
    if existing:
        gfile = existing[0]
        gfile.SetContentFile(local_path)
        gfile.Upload()
        return gfile["id"]

    # Si no existe, crea uno nuevo
    gfile = drive.CreateFile({
        "title": drive_title,
        "parents": [{"id": folder_id}],
        "mimeType": "text/csv"
    })
    gfile.SetContentFile(local_path)
    gfile.Upload()
    return gfile["id"]
