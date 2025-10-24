import os
import mimetypes
import shutil
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import humanize
import socket

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
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
UPLOAD_THRESHOLD = 10 * 1024 * 1024
MAX_WORKERS = 5

# Extend global socket timeout (important for large files)
socket.setdefaulttimeout(300)  # 5 minute


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
    """Upload a file (encrypted first) to Google Drive safely and cleanly."""
    service = get_drive_service()

    # Encrypt file if needed
    if not file_path.endswith(".enc"):
        file_path = encrypt_file(file_path)

    file_metadata = {"name": os.path.basename(file_path)}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"

    file_size = os.path.getsize(file_path)
    human_size = humanize.naturalsize(file_size)
    logger.info(f"Uploading '{os.path.basename(file_path)}' ({human_size})")

    try:
        with open(file_path, "rb") as f:  # ensures file is closed properly
            if file_size < UPLOAD_THRESHOLD:
                media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=False)
                uploaded = service.files().create(
                    body=file_metadata, media_body=media, fields="id, name"
                ).execute()
            else:
                media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True, chunksize=20 * 1024 * 1024)
                request = service.files().create(
                    body=file_metadata, media_body=media, fields="id, name"
                )
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        logger.info(f"Progress: {int(status.progress() * 100)}%")
                uploaded = response

        logger.info(f" Uploaded file: {uploaded['name']} (id={uploaded['id']})")
        return uploaded

    except HttpError as e:
        logger.error(f" Upload failed for {file_path}: {e}")
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

        return uploaded_file

    except Exception as e:
        logger.error(f"Failed to upload zipped folder {local_folder}: {e}")
        raise

def upload_folder(folder_path, parent_folder_id=None):
    """Recursively upload a folder to Google Drive.
    Deletes the folder ONLY if every upload is successful."""
    service = get_drive_service()

    folder_name = os.path.basename(folder_path)
    prev_folder_name = folder_name
    if folder_name.endswith("_uploading"):
        folder_name = folder_name[:-10]

    uploaded_successfully = True  # track success state

    try:
        # --- Create Drive folder ---
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_folder_id:
            folder_metadata["parents"] = [parent_folder_id]

        folder = service.files().create(body=folder_metadata, fields="id, name").execute()
        folder_id = folder["id"]
        logger.info(f"Created Drive folder: {folder_name} (id={folder_id})")

        # --- Collect items ---
        items = os.listdir(folder_path)
        file_tasks, subfolders = [], []

        for item in items:
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                file_tasks.append(item_path)
            elif os.path.basename(item_path).lower() == "profiles":
                file_tasks.append(item_path)
            elif os.path.isdir(item_path):
                subfolders.append(item_path)

        total_items = len(file_tasks) + len(subfolders)
        completed = 0
        futures = []

        # --- Upload files concurrently ---
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for file_path in file_tasks:
                if os.path.basename(file_path).lower() == "profiles":
                    futures.append(executor.submit(upload_zip_file, file_path, parent_folder_id=folder_id))
                else:
                    futures.append(executor.submit(upload_file, file_path, folder_id))

            for future in as_completed(futures):
                try:
                    future.result()
                    completed += 1
                    percent = (completed / total_items) * 100
                    logger.info(f"Uploaded file ({completed}/{total_items}) - {percent:.1f}% complete")
                except Exception as e:
                    uploaded_successfully = False
                    logger.error(f" File upload error: {e}")

        # --- Upload subfolders recursively ---
        for subfolder in subfolders:
            try:
                upload_folder(subfolder, folder_id)
                completed += 1
                percent = (completed / total_items) * 100
                logger.info(f"Uploaded folder ({completed}/{total_items}) - {percent:.1f}% complete")
            except Exception as e:
                uploaded_successfully = False
                logger.error(f" Subfolder upload error: {e}")

        # --- Delete only if EVERYTHING succeeded ---
        if uploaded_successfully:
            try:
                logger.info(f" All uploads successful. Deleting {folder_path}")
                time.sleep(1)
                shutil.rmtree(prev_folder_name)
                logger.info(f" Deleted local folder: {prev_folder_name}")
            except Exception as cleanup_error:
                logger.warning(f" Could not delete folder {prev_folder_name}: {cleanup_error}")
        else:
            logger.warning(f" Upload incomplete. Keeping folder {folder_path} for retry.")

        return folder

    except Exception as e:
        logger.error(f" Failed to upload folder {prev_folder_name}: {e}", exc_info=True)
        raise


# ---------------- Download ----------------

def download_file(file_id, save_file_path, max_retries=5):
    """Download (with progress + retry) and decrypt a file from Google Drive."""
    service = get_drive_service()

    try:
        # --- metadata ---
        file_meta = service.files().get(fileId=file_id, fields="name,size").execute()
        file_name = file_meta.get("name", "unknown")
        file_size = int(file_meta.get("size", 0))
        readable_size = humanize.naturalsize(file_size)
        logger.info(f"Downloading '{file_name}' ({readable_size}) to {save_file_path}")

        request = service.files().get_media(fileId=file_id)
        start_time = time.time()
        done = False
        last_percent = 0

        with open(save_file_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=10 * 1024 * 1024)

            retries = 0
            while not done:
                try:
                    status, done = downloader.next_chunk()
                    if status:
                        percent = int(status.progress() * 100)
                        if percent - last_percent >= 5 or percent == 100:
                            elapsed = time.time() - start_time
                            downloaded = status.resumable_progress
                            speed = downloaded / elapsed if elapsed else 0
                            logger.info(
                                f"{percent}% ({humanize.naturalsize(downloaded)} / {readable_size}) "
                                f"at {humanize.naturalsize(speed)}/s"
                            )
                            last_percent = percent

                except TimeoutError as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Download failed after {max_retries} retries: {e}")
                        raise
                    logger.warning(f"Timeout occurred (attempt {retries}/{max_retries}), retrying after 5s...")
                    time.sleep(5)
                    # Recreate downloader to resume
                    downloader = MediaIoBaseDownload(fh, request, chunksize=10 * 1024 * 1024)

        logger.info(f" Download complete: {save_file_path}")

        # --- post-download ---
        if save_file_path.endswith(".enc"):
            logger.info("Decrypting downloaded file...")
            save_file_path = decrypt_file(save_file_path)
        if save_file_path.endswith(".zip"):
            logger.info("Unzipping archive...")
            return unzip_file(save_file_path)

        return save_file_path

    except HttpError as he:
        logger.error(f"Google API error: {he}")
        raise
    except socket.timeout:
        logger.error("Download failed due to persistent timeout.")
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
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
    """Download a folder (recursive) with concurrent file downloads."""
    os.makedirs(save_folder_path, exist_ok=True)
    items = list_files_in_folder(folder_id)

    if not items:
        logger.warning(f"No files found in folder: {folder_id}")
        return save_folder_path

    folders = []
    files = []

    # Separate folders and files
    for item in items:
        item_id = item["id"]
        item_name = item["name"]
        item_type = item["mimeType"]

        if item_type == "application/vnd.google-apps.folder":
            folders.append((item_id, item_name))
        else:
            files.append((item_id, item_name))

    # Parallel file downloads
    def _safe_download_file(item_id, item_name):
        """Wrapper for safe concurrent downloads."""
        save_path = os.path.join(save_folder_path, item_name)
        try:
            logger.info(f"Downloading: {item_name}")
            download_file(item_id, save_path)
            logger.info(f"Completed: {item_name}")
        except HttpError as he:
            logger.error(f"Google API error while downloading {item_name}: {he}")
        except Exception as e:
            logger.error(f"Failed: {item_name} | Error: {e}")

    if files:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            executor.map(lambda f: _safe_download_file(*f), files)

    # Recurse into subfolders sequentially
    for sub_id, sub_name in folders:
        sub_folder_path = os.path.join(save_folder_path, sub_name)
        download_folder(sub_id, sub_folder_path)

    return save_folder_path


# ---------------- Helpers ----------------
def zip_local_folder(folder_path, output_zip_path):
    """Zip a folder into a .zip file."""
    os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
    def ignore_patterns(path, names):
        return {'lockfile'} if 'lockfile' in names else set()

    zip_file = shutil.make_archive(
        output_zip_path,
        'zip',
        root_dir=folder_path,
        logger=logger.info,
        ignore=ignore_patterns
    )
    return zip_file


def unzip_file(zip_file):
    """Unzip a file and remove the archive."""
    extract_dir = str(os.path.splitext(zip_file)[0])
    if extract_dir.endswith("_backup"):
        extract_dir = extract_dir[:-7]
    os.makedirs(extract_dir, exist_ok=True)
    shutil.unpack_archive(zip_file, extract_dir, "zip")

    os.remove(zip_file)
    return extract_dir

def delete_by_name(name: str, parent_id: str = None):
    """
    Delete a file or folder by name (recursively if folder).
    """
    service = get_drive_service()
    try:
        # More lenient match (case-insensitive partial)
        query = f"name contains '{name}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, parents)"
        ).execute()
        files = results.get("files", [])

        if not files:
            logger.warning(f"No file/folder found for '{name}'.")
            return False

        for f in files:
            file_id = f["id"]
            mime_type = f["mimeType"]
            logger.info(f"Found {f['name']} ({mime_type}) -> {file_id}")

            # If it's a folder, delete contents first
            if mime_type == "application/vnd.google-apps.folder":
                child_results = service.files().list(
                    q=f"'{file_id}' in parents and trashed = false",
                    fields="files(id, name, mimeType)"
                ).execute()

                for child in child_results.get("files", []):
                    delete_by_name(child["name"], file_id)

            # Delete file/folder itself
            try:
                service.files().delete(fileId=file_id).execute()
                logger.info(f"Deleted: {f['name']} (id: {file_id})")
            except Exception as e:
                logger.error(f"Failed to delete {f['name']} ({file_id}): {e}")

        return True

    except Exception as e:
        logger.exception(f"Delete failed for '{name}': {e}")
        return False