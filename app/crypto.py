import os
from cryptography.fernet import Fernet, InvalidToken
from .config import setting
import json
from dotenv import load_dotenv
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key


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

def decrypt_request(encrypted_data: dict):
    encrypted_aes_key = b64decode(encrypted_data["encrypted_aes_key"])
    initial_vector = b64decode(encrypted_data["initial_vector"])
    encrypted_flow_data = b64decode(encrypted_data["encrypted_flow_data"])

    # Decrypt the AES encryption key
    private_key = os.getenv("PRIVATE_KEY")
    key_password = os.getenv("KEY_PASSWORD")
    private_key = load_pem_private_key(
        private_key.encode('utf-8'), password=key_password.encode('utf-8'))
    aes_key = private_key.decrypt(encrypted_aes_key, OAEP(
        mgf=MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

    # Decrypt the Flow data
    encrypted_flow_data_body = encrypted_flow_data[:-16]
    encrypted_flow_data_tag = encrypted_flow_data[-16:]
    decryptor = Cipher(algorithms.AES(aes_key),
                       modes.GCM(initial_vector, encrypted_flow_data_tag)).decryptor()
    decrypted_data_bytes = decryptor.update(
        encrypted_flow_data_body) + decryptor.finalize()
    decrypted_data = json.loads(decrypted_data_bytes.decode("utf-8"))
    return decrypted_data, aes_key, initial_vector

def encrypt_response(response, aes_key, iv):
    # Flip the initialization vector
    flipped_iv = bytearray()
    for byte in iv:
        flipped_iv.append(byte ^ 0xFF)

    # Encrypt the response data
    encryptor = Cipher(algorithms.AES(aes_key),
                       modes.GCM(flipped_iv)).encryptor()
    return b64encode(
        encryptor.update(json.dumps(response).encode("utf-8")) +
        encryptor.finalize() +
        encryptor.tag
    ).decode("utf-8")