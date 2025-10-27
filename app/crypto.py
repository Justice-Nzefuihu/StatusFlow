import os
from cryptography.fernet import Fernet, InvalidToken
from .config import setting
import base64
import json
from dotenv import load_dotenv
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad


from app.logging_config import get_logger

logger = get_logger(__name__)


load_dotenv()

try:
    KEY = setting.fernet_key
    CIPHER = Fernet(KEY)
    logger.info("Fernet cipher initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Fernet cipher: {e}", exc_info=True)
    raise

def encrypt_file(file_path: str, remove_original: bool = True) -> str:
    """Stream-encrypt large files in chunks to avoid memory bottlenecks."""
    encrypted_path = file_path + ".enc"
    try:
        with open(file_path, "rb") as infile, open(encrypted_path, "wb") as outfile:
            while chunk := infile.read(10 * 1024 * 1024):  # 10 MB chunks
                outfile.write(CIPHER.encrypt(chunk))

        logger.info(f"File encrypted successfully -> {encrypted_path}")
        if remove_original:
            os.remove(file_path)
            logger.info(f"Original file removed: {file_path}")

        return encrypted_path
    except Exception as e:
        logger.error(f"Error encrypting {file_path}: {e}", exc_info=True)
        raise

def decrypt_file(encrypted_path: str, output_path: str = None, remove_original: bool = True) -> str:
    """
    Stream decrypt a file efficiently (large-file friendly).
    Default output removes .enc extension.
    """
    try:
        if not os.path.exists(encrypted_path):
            raise FileNotFoundError(f"Encrypted file not found: {encrypted_path}")

        if not output_path:
            output_path = (
                encrypted_path[:-4] if encrypted_path.endswith(".enc") 
                else encrypted_path + ".dec"
            )

        logger.info(f"Starting decryption -> {encrypted_path}")

        with open(encrypted_path, "rb") as infile:
            encrypted_data = infile.read()

        decrypted_data = CIPHER.decrypt(encrypted_data)

        with open(output_path, "wb") as outfile:
            outfile.write(decrypted_data)
            
        logger.info(f"File decrypted successfully -> {output_path}")

        if remove_original:
            try:
                os.remove(encrypted_path)
                logger.debug(f"Removed encrypted file: {encrypted_path}")
            except Exception as e:
                logger.warning(f"Could not remove encrypted file {encrypted_path}: {e}")

        return output_path

    except InvalidToken as e:
        logger.error(f"Invalid decryption token for {encrypted_path}: {e}")
        raise
    except FileNotFoundError as e:
        logger.error(f"File not found: {encrypted_path} | {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected decryption error: {e}", exc_info=True)
        raise

def get_private_key():
    private_key_str = os.getenv("PRIVATE_KEY")
    if not private_key_str:
        raise ValueError("PRIVATE_KEY not found in environment variables.")
    
    return RSA.import_key(private_key_str)

def get_public_key():
    public_key_str = os.getenv("PUBLIC_KEY")
    if not public_key_str:
        raise ValueError("PUBLIC_KEY not found in environment variables.")
    
    return RSA.import_key(public_key_str)

def decrypt_flow_payload(encrypted_data: dict) -> dict:
    private_key = get_private_key()
    
    encrypted_aes_key = base64.b64decode(encrypted_data["encrypted_aes_key"])
    initial_vector = base64.b64decode(encrypted_data["initial_vector"])
    encrypted_flow_data = base64.b64decode(encrypted_data["encrypted_flow_data"])

    # RSA decrypt AES key
    rsa_cipher = PKCS1_OAEP.new(private_key)
    aes_key = rsa_cipher.decrypt(encrypted_aes_key)

    # AES decrypt flow data
    aes_cipher = AES.new(aes_key, AES.MODE_CBC, iv=initial_vector)
    decrypted_data = aes_cipher.decrypt(encrypted_flow_data)

    # Strip null padding and parse JSON
    decrypted_json = decrypted_data.rstrip(b"\0").decode("utf-8").strip()
    return json.loads(decrypted_json)

def encrypt_flow_response(response_data: dict):
    """
    Encrypts the response that will be sent back to WhatsApp.
    """
    public_key = get_public_key()
    aes_key = get_random_bytes(32)
    iv = get_random_bytes(16)

    # Encrypt response data with AES
    cipher_aes = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted_data = cipher_aes.encrypt(pad(json.dumps(response_data).encode(), AES.block_size))

    # Encrypt AES key with public RSA key
    cipher_rsa = PKCS1_OAEP.new(public_key)
    encrypted_aes_key = cipher_rsa.encrypt(aes_key)

    return {
        "encrypted_flow_data": base64.b64encode(encrypted_data).decode(),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode(),
        "initial_vector": base64.b64encode(iv).decode()
    }
