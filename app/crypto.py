import logging
import os
from cryptography.fernet import Fernet, InvalidToken
from .config import setting

logger = logging.getLogger(__name__)

try:
    KEY = setting.fernet_key
    CIPHER = Fernet(KEY)
    logger.info("Fernet cipher initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Fernet cipher: {e}", exc_info=True)
    raise


def encrypt_file(file_path: str, remove_original: bool = True) -> str:
    """Encrypt a file and save as file.enc"""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        logger.debug(f"Read {len(data)} bytes from {file_path}")

        encrypted_data = CIPHER.encrypt(data)
        encrypted_path = file_path + ".enc"

        with open(encrypted_path, "wb") as f:
            f.write(encrypted_data)
        logger.info(f"File encrypted successfully -> {encrypted_path}")

        if remove_original:
            try:
                os.remove(file_path)
                logger.info(f"Original file removed: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove original file {file_path}: {e}")

        return encrypted_path
    except FileNotFoundError as e:
        logger.error(f"File not found for encryption: {file_path} | Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error encrypting {file_path}: {e}", exc_info=True)
        raise


def decrypt_file(encrypted_path: str, output_path: str = None, remove_original: bool = True) -> str:
    """Decrypt a file, output defaults to removing .enc extension"""
    try:
        with open(encrypted_path, "rb") as f:
            encrypted_data = f.read()
        logger.debug(f"Read {len(encrypted_data)} bytes from {encrypted_path}")

        data = CIPHER.decrypt(encrypted_data)

        if not output_path:
            if encrypted_path.endswith(".enc"):
                output_path = encrypted_path[:-4]
            else:
                output_path = encrypted_path + ".dec"

        with open(output_path, "wb") as f:
            f.write(data)
        logger.info(f"File decrypted successfully -> {output_path}")

        if remove_original:
            try:
                os.remove(encrypted_path)
                logger.info(f"Encrypted file removed: {encrypted_path}")
            except Exception as e:
                logger.warning(f"Failed to remove encrypted file {encrypted_path}: {e}")

        return output_path
    except FileNotFoundError as e:
        logger.error(f"Encrypted file not found: {encrypted_path} | Error: {e}")
        raise
    except InvalidToken as e:
        logger.error(f"Decryption failed for {encrypted_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error decrypting {encrypted_path}: {e}", exc_info=True)
        raise
