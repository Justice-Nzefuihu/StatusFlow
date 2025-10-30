import os
from cryptography.fernet import Fernet, InvalidToken
from .config import setting
import json
from dotenv import load_dotenv
from base64 import b64decode, b64encode
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1, hashes
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64
import hashlib
# import hmac
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad



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
    """
    Decrypt WhatsApp encrypted flow payload using RSA + AES-GCM.
    Returns: (decrypted_data, aes_key, initial_vector)
    """
    try:
        # Step 1: Decode Base64 inputs
        encrypted_aes_key = b64decode(encrypted_data["encrypted_aes_key"])
        initial_vector = b64decode(encrypted_data["initial_vector"])
        encrypted_flow_data = b64decode(encrypted_data["encrypted_flow_data"])

        # Step 2: Load private key securely
        private_key = os.getenv("PRIVATE_KEY")
        key_password = os.getenv("KEY_PASSWORD")
        if not private_key or not key_password:
            logger.error("Private key or password environment variables not set.")
            raise ValueError("Missing encryption key credentials.")

        try:
            private_key = load_pem_private_key(
                private_key.encode("utf-8"),
                password=key_password.encode("utf-8")
            )
        except Exception as e:
            logger.exception("Failed to load private key.")
            raise ValueError("Private key loading failed.") from e

        # Step 3: Decrypt the AES encryption key
        try:
            aes_key = private_key.decrypt(
                encrypted_aes_key,
                OAEP(
                    mgf=MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        except Exception as e:
            logger.exception("RSA decryption failed for AES key.")
            raise ValueError("AES key decryption failed.") from e

        # Step 4: Decrypt the Flow data
        try:
            encrypted_flow_data_body = encrypted_flow_data[:-16]
            encrypted_flow_data_tag = encrypted_flow_data[-16:]
            decryptor = Cipher(
                algorithms.AES(aes_key),
                modes.GCM(initial_vector, encrypted_flow_data_tag)
            ).decryptor()

            decrypted_data_bytes = decryptor.update(
                encrypted_flow_data_body
            ) + decryptor.finalize()

            decrypted_data = json.loads(decrypted_data_bytes.decode("utf-8"))
            logger.info("Successfully decrypted WhatsApp flow data.")
            return decrypted_data, aes_key, initial_vector

        except Exception as e:
            logger.exception("Failed to decrypt or parse flow data.")
            raise ValueError("Flow data decryption or decoding failed.") from e

    except Exception as e:
        logger.exception("WhatsApp flow request decryption failed.")
        raise ValueError("Unable to process encrypted request.") from e


def encrypt_response(response, aes_key, iv):
    """
    Encrypt response using AES-GCM.
    Returns Base64 encoded ciphertext (includes GCM tag).
    """
    try:
        # Flip the initialization vector
        flipped_iv = bytearray()
        for byte in iv:
            flipped_iv.append(byte ^ 0xFF)

        # Encrypt the response data
        try:
            encryptor = Cipher(
                algorithms.AES(aes_key),
                modes.GCM(flipped_iv)
            ).encryptor()

            encrypted_payload = (
                encryptor.update(json.dumps(response).encode("utf-8")) +
                encryptor.finalize() +
                encryptor.tag
            )

            encrypted_base64 = b64encode(encrypted_payload).decode("utf-8")
            logger.info("Successfully encrypted WhatsApp flow response.")
            return encrypted_base64

        except Exception as e:
            logger.exception("AES encryption failed for response.")
            raise ValueError("Response encryption failed.") from e

    except Exception as e:
        logger.exception("WhatsApp flow response encryption failed.")
        raise ValueError("Unable to encrypt response data.") from e


def decrypt_whatsapp_media(media_data: dict) -> str:
    """
    Decrypt WhatsApp Flow or Business API media file and return its Base64 string.
    """

    try:
        metadata = media_data.get("encryption_metadata")
        if not metadata:
            logger.error("Missing encryption_metadata in media_data.")
            raise ValueError("Missing encryption_metadata in media_data")

        cdn_url = media_data.get("cdn_url")
        if not cdn_url:
            logger.error("Missing cdn_url in media_data.")
            raise ValueError("Missing cdn_url in media_data")

        # Step 1: Download encrypted media
        try:
            response = requests.get(cdn_url, stream=True, timeout=30)
            response.raise_for_status()
            ciphertext = response.content
        except Exception as e:
            logger.exception("Failed to download encrypted media from CDN.")
            raise ValueError("Failed to download encrypted media.") from e

        # Step 2: Verify encrypted file hash
        try:
            expected_enc_hash = base64.b64decode(metadata["encrypted_hash"])
            actual_enc_hash = hashlib.sha256(ciphertext).digest()
            if actual_enc_hash != expected_enc_hash:
                logger.warning("Encrypted file hash mismatch detected.")
                raise ValueError("Encrypted file hash mismatch. File corrupted or tampered.")
        except KeyError:
            logger.error("Missing encrypted_hash key in metadata.")
            raise ValueError("Invalid encryption metadata structure.")

        # Step 3: Prepare decryption keys
        try:
            iv = base64.b64decode(metadata["iv"])
            aes_key = base64.b64decode(metadata["encryption_key"])
            # hmac_key = base64.b64decode(metadata["hmac_key"])
            plaintext_hash = base64.b64decode(metadata["plaintext_hash"])
        except KeyError:
            logger.error("Missing one or more encryption metadata fields (iv, encryption_key, plaintext_hash).")
            raise ValueError("Incomplete encryption metadata provided.")

        # Step 4: Validate HMAC (optional but recommended)
        # computed_hmac = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
        # If WhatsApp includes a 10-byte HMAC in metadata, verify like this:
        # expected_hmac10 = base64.b64decode(metadata["hmac10"])
        # if computed_hmac[:10] != expected_hmac10:
        #     raise ValueError("HMAC validation failed.")

        # Step 5: Decrypt AES-256-CBC
        try:
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            decrypted_data = cipher.decrypt(ciphertext)
            decrypted_data = unpad(decrypted_data, AES.block_size)
        except Exception as e:
            logger.exception("AES decryption or unpadding failed.")
            raise ValueError("Decryption failed due to invalid padding or AES key mismatch.") from e

        # Step 6: Verify decrypted file integrity
        try:
            if hashlib.sha256(decrypted_data).digest() != plaintext_hash:
                logger.warning("Decrypted file integrity check failed.")
                raise ValueError("Decrypted file integrity check failed.")
        except Exception as e:
            logger.exception("File integrity verification failed.")
            raise ValueError("Integrity check failed.") from e

        # Step 7: Return as Base64 string
        try:
            media_base64 = base64.b64encode(decrypted_data).decode("utf-8")
            logger.info("Media file successfully decrypted and verified.")
            return media_base64
        except Exception as e:
            logger.exception("Failed to encode media file to Base64.")
            raise ValueError("Failed to encode decrypted media.") from e

    except Exception as e:
        logger.exception("Media decryption process failed.")
        raise ValueError("Unable to process media decryption request.") from e 