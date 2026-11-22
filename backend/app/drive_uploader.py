import os
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_DRIVE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_DRIVE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_DRIVE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("drive", "v3", credentials=creds)


def create_folder(service, name: str, parent_id=None):
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    folder = service.files().create(body=body, fields="id").execute()
    return folder["id"]


def upload_file(service, file_path: str, folder_id: str, mime_type: str):
    file_name = os.path.basename(file_path)
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.FileIO(file_path, "rb"), mimetype=mime_type)
    file = service.files().create(
        body=file_metadata, media_body=media, fields="id, webViewLink"
    ).execute()
    return file.get("webViewLink"), file.get("id")