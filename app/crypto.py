from cryptography.fernet import Fernet
from config import setting

KEY = setting.fernet_key
CIPHER = Fernet(KEY)

def encrypt_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()

    encrypted_data = CIPHER.encrypt(data)
    encrypted_path = file_path + '.enc'

    with open(encrypted_path, 'wb') as f:
        f.write(encrypted_data)
    return encrypted_path

def decrypt_file(encrypted_path, output_path = None):
    with open(encrypted_path, 'rb') as f:
        encrypted_data = f.read()

    data = CIPHER.decrypt(encrypted_data)
    if not output_path:
        if encrypted_path.endswith(".enc"):
            output_path = encrypted_path[:-4]
        else:
            output_path = encrypted_path + ".dec"

    with open(output_path, 'wb') as f:
        f.write(data)
    
    return output_path