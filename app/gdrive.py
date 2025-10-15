import os
import mimetypes
import shutil
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .config import setting
from .crypto import encrypt_file, decrypt_file

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- Config ----------------
SCOPES = [setting.google_scopes]
CREDENTIALS_FILE = setting.credentials_file
TOKEN_FILE = setting.token_file

# Threshold for simple vs resumable upload (5MB)
UPLOAD_THRESHOLD = 5 * 1024 * 1024


# ---------------- Auth ----------------
def get_drive_service():
    """Authenticate and return Google Drive API service."""
    creds = None
    try:
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("Refreshed expired credentials")
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("New login via OAuth flow")

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
                logger.info("Saved refreshed credentials")

        return build("drive", "v3", credentials=creds, cache_discovery=False)

    except Exception as e:
        logger.error(f"Failed to authenticate with Google Drive: {e}")
        raise


# ---------------- Upload ----------------
def upload_file(file_path: str, folder_id=None):
    """Upload a file (encrypted first) to Google Drive."""
    service = get_drive_service()

    # Encrypt before upload (skip if already encrypted)
    if not file_path.endswith(".enc"):
        file_path = encrypt_file(file_path)

    file_metadata = {"name": os.path.basename(file_path)}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    file_size = os.path.getsize(file_path)

    try:
        if file_size < UPLOAD_THRESHOLD:
            # -------- Simple Upload --------
            logger.info(f"⬆ Simple upload: {file_path} ({file_size} bytes)")
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=False)
            uploaded = service.files().create(
                body=file_metadata, media_body=media, fields="id, name"
            ).execute()

        else:
            # -------- Resumable Upload --------
            logger.info(f"Resumable upload: {file_path} ({file_size} bytes)")
            media = MediaFileUpload(
                file_path, mimetype=mime_type, resumable=True, chunksize=5 * 1024 * 1024
            )
            request = service.files().create(
                body=file_metadata, media_body=media, fields="id, name"
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Progress: {int(status.progress() * 100)}%")
            uploaded = response

        logger.info(f"File uploaded: {uploaded['name']} (id={uploaded['id']})")

        # Remove local encrypted file only after success
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted local file: {file_path}")

        return uploaded

    except HttpError as e:
        logger.error(f"Upload failed: {e}")
        raise


def upload_zip_file(local_folder, output_zip_base=None, parent_folder_id=None):
    """Zip, encrypt, upload a folder, then clean up local files."""
    if not output_zip_base:
        folder_name = os.path.basename(os.path.normpath(local_folder))
        parent_dir = os.path.dirname(os.path.normpath(local_folder))
        output_zip_base = os.path.join(parent_dir, folder_name + "_backup")

    zip_file = zip_local_folder(local_folder, output_zip_base)

    try:
        uploaded_file = upload_file(zip_file, parent_folder_id)
        logger.info(f"Uploaded zipped folder: {local_folder}")

        # Cleanup only after success
        if os.path.exists(local_folder):
            shutil.rmtree(local_folder)
            logger.info(f"Deleted original folder: {local_folder}")

        return uploaded_file

    except Exception as e:
        logger.error(f"Failed to upload zipped folder {local_folder}: {e}")
        raise


def upload_folder(folder_path, parent_folder_id=None):
    """Recursively upload a folder to Google Drive."""
    service = get_drive_service()
    try:
        folder_metadata = {
            "name": os.path.basename(folder_path),
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_folder_id:
            folder_metadata["parents"] = [parent_folder_id]

        folder = service.files().create(
            body=folder_metadata, fields="id, name, parents"
        ).execute()

        folder_id = folder["id"]

        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                upload_file(item_path, folder_id)
            elif os.path.basename(item_path).lower() == "profiles":
                upload_zip_file(item_path, parent_folder_id=folder_id)
            elif os.path.isdir(item_path):
                upload_folder(item_path, folder_id)

        # Remove only after successful full upload
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Deleted uploaded folder: {folder_path}")

        return folder

    except Exception as e:
        logger.error(f"Failed to upload folder {folder_path}: {e}")
        raise


# ---------------- Download ----------------
def download_file(file_id, save_file_path):
    """Download and decrypt a file from Google Drive."""
    service = get_drive_service()
    try:
        request = service.files().get_media(fileId=file_id)
        with open(save_file_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        save_file_path = decrypt_file(save_file_path)

        if save_file_path.endswith(".zip"):
            return unzip_file(save_file_path)

        return save_file_path

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise


def list_files_in_folder(folder_id):
    """List files inside a Drive folder."""
    service = get_drive_service()
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query, fields="files(id, name, mimeType)"
        ).execute()
        return results.get("files", [])
    except Exception as e:
        logger.error(f"Failed to list folder {folder_id}: {e}")
        raise


def download_folder(folder_id, save_folder_path):
    """Download a folder (recursive)."""
    os.makedirs(save_folder_path, exist_ok=True)
    items = list_files_in_folder(folder_id)

    for item in items:
        item_id = item["id"]
        item_name = item["name"]
        item_type = item["mimeType"]

        if item_type == "application/vnd.google-apps.folder":
            new_local = os.path.join(save_folder_path, item_name)
            download_folder(item_id, new_local)
        else:
            save_path = os.path.join(save_folder_path, item_name)
            download_file(item_id, save_path)

    return save_folder_path


# ---------------- Helpers ----------------
def zip_local_folder(folder_path, output_zip_path):
    """Zip a folder into a .zip file."""
    os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
    zip_file = shutil.make_archive(output_zip_path, "zip", folder_path)
    return zip_file


def unzip_file(zip_file):
    """Unzip a file and remove the archive."""
    extract_dir = os.path.splitext(zip_file)[0]
    os.makedirs(extract_dir, exist_ok=True)
    shutil.unpack_archive(zip_file, extract_dir, "zip")

    os.remove(zip_file)
    return extract_dir


def delete_by_name(name: str, parent_id: str = None):
    """Delete a file/folder by name from Drive."""
    service = get_drive_service()
    try:
        query = f"name = '{name}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = service.files().list(
            q=query, fields="files(id, name, mimeType)"
        ).execute()
        files = results.get("files", [])

        if not files:
            logger.warning(f"No file/folder named '{name}' found.")
            return False

        for f in files:
            service.files().delete(fileId=f["id"]).execute()
            logger.info(f"Deleted: {f['name']} (id: {f['id']})")

        return True

    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise
