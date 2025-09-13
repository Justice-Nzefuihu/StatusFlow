from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from config import setting
from crypto import encrypt_file, decrypt_file
import os
import shutil

SCOPES = [setting.google_scopes]
SERVICE_ACCOUNT_FILE = setting.service_account_file


def get_drive_service():
    cred = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    return build("drive", "v3", credentials=cred)


def upload_file(file_path, folder_id = None):
    service = get_drive_service()

    file_path = encrypt_file(file_path)

    file_metadata = {'name': os.path.basename(file_path)}

    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, parents'
    ).execute()

    os.remove(file_path)

    return file


def upload_folder(folder_path, parent_folder_id = None):
    service = get_drive_service()
    file_metadata = {
        'name': os.path.basename(folder_path), 
        'mimeType': 'application/vnd.google-apps.folder'
        }
    
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    folder = service.files().create(
        body=file_metadata,
        fields='id, name, parents'
    ).execute()

    folder_id =  folder.get('id')

    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            upload_file(item_path, folder_id)
        elif os.path.basename(item_path).lower() == "profiles":
            upload_zip_file(item_path, parent_folder_id=folder_id)
        elif os.path.isdir(item_path):
            upload_folder(item_path, folder_id)

    
    shutil.rmtree(folder_path)

    return folder


def download_file(file_id, save_file_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)

    with open(save_file_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    save_file_path =  decrypt_file(save_file_path)

    if save_file_path.endwith(".zip"):
        return unzip_file(save_file_path)
        
    return save_file_path


def list_files_in_folder(folder_id):
    service = get_drive_service()
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query, fields="files(id, name, mimeType)"
        ).execute()
    return results.get('files', [])

def download_folder(folder_id, save_folder_path):
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


def zip_local_folder(folder_path, output_zip_path):
    os.makedirs(os.path.dirname(output_zip_path), exist_ok=True)
    zip_file = shutil.make_archive(output_zip_path, "zip", folder_path)
    return zip_file

def upload_zip_file(local_folder, output_zip_base = None, parent_folder_id=None):
    if not output_zip_base:
        folder_name = os.path.basename(os.path.normpath(local_folder))
        output_zip_base = os.path.join("archives", folder_name + "_backup")
    
    zip_file = zip_local_folder(local_folder, output_zip_base)

    uploaded_file = upload_file(zip_file, parent_folder_id)

    if os.path.exists(zip_file):
        os.remove(zip_file)

    return uploaded_file


def unzip_file(zip_file):
    extract_dir = os.path.splitext(zip_file)[0]
    os.makedirs(extract_dir, exist_ok=True)
    shutil.unpack_archive(zip_file, extract_dir, 'zip')

    os.remove(zip_file)
    return extract_dir

def delete_by_name(name: str, parent_id: str = None):
    service = get_drive_service()

    query = f"name = '{name}' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get("files", [])

    if not files:
        print(f"No file/folder named '{name}' found.")
        return False

    for f in files:
        service.files().delete(fileId=f["id"]).execute()
        print(f"Deleted: {f['name']} (id: {f['id']})")

    return True
