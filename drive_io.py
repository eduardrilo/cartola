import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# Ruta completa al JSON (fuera del repo)
SERVICE_ACCOUNT_JSON = r"C:\Users\DRIMO\Documents\service_account.json"

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_NAME = os.getenv("GOOGLE_DRIVE_FOLDER_NAME", "LOOKER")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

def _drive_client():
    if not os.path.exists(SERVICE_ACCOUNT_JSON):
        raise FileNotFoundError(
            f"No se encontró el archivo en: {SERVICE_ACCOUNT_JSON}"
        )

    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_JSON, DRIVE_SCOPES
    )
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
            "Crea/Comparte con el Service Account (Editor)."
        )
    return folders[0]["id"]

def upload_csv_to_drive(local_path: str, drive_title: str) -> str:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"No existe el archivo local: {local_path}")
    drive = _drive_client()
    folder_id = _ensure_folder_id(drive)
    existing = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false and title='{drive_title}'"}).GetList()
    if existing:
        gfile = existing[0]
        gfile.SetContentFile(local_path)
        gfile.Upload()
        return gfile["id"]
    gfile = drive.CreateFile({"title": drive_title, "parents": [{"id": folder_id}], "mimeType": "text/csv"})
    gfile.SetContentFile(local_path)
    gfile.Upload()
    return gfile["id"]
