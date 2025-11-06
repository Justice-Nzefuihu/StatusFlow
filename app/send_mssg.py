import os
import requests
from dotenv import load_dotenv

# -----------------------------------
# Logging Setup
# -----------------------------------
from app.logging_config import get_logger

logger = get_logger(__name__)

# -----------------------------------
# Env Variables
# -----------------------------------
load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
    logger.error("Missing ACCESS_TOKEN or PHONE_NUMBER_ID in environment variables!")


# -----------------------------------
# Core Send Function
# -----------------------------------
def send_mssg(data: dict):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        logger.info(f" Sending message to WhatsApp API: {data.j}")

        response = requests.post(url, headers=headers, json=data, timeout=15)

        logger.info(f" WhatsApp Response Code: {response.status_code}")

        # Attempt to parse JSON safely
        try:
            json_data = response.json()
        except Exception:
            logger.error("Failed to parse JSON response")
            return {"error": "Invalid JSON response", "status_code": response.status_code}

        if response.status_code >= 400:
            logger.error(f"WhatsApp API Error: {json_data}")

        return json_data

    except requests.exceptions.Timeout:
        logger.error("WhatsApp API request timed out!")
        return {"error": "timeout"}

    except requests.exceptions.RequestException as e:
        logger.error(f"WhatsApp API Request Error: {e}")
        return {"error": str(e)}

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return {"error": "unexpected_error"}


# -----------------------------------
# Template: First Message
# -----------------------------------
def first_message(phone_number: str, username: str) -> dict:
    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": "first_message",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": username}],
                }
            ],
        },
    }

    return send_mssg(data)


# -----------------------------------
# Template: Verification Message
# -----------------------------------
def verification_msg(phone_number: str, code: str) -> dict:
    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": "verification",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": code}],
                },
                {
                    "type": "button",
                    "sub_type": "COPY_CODE",
                    "index": "0",
                    "parameters": [{"type": "coupon_code", "coupon_code": code}],
                },
            ],
        },
    }

    return send_mssg(data)


# -----------------------------------
# Turn off Disappearing Messages
# -----------------------------------
def turn_off_disappearing_messages(phone_number: str) -> dict:
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "configuration",
        "configuration": {"ephemeral": {"duration": 0}},
    }

    return send_mssg(data)


# -----------------------------------
# Registration Flow
# -----------------------------------
def registration_flow_mssg(phone_number: str) -> dict:
    data = {
        "recipient_type": "individual",
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "body": {"text": "StatusFlow Registration"},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3.0",
                    "flow_token": phone_number,
                    "flow_id": "1128781119455126",
                    "flow_cta": "preview",
                    "mode": "draft",
                    "flow_action": "navigate",
                    "flow_action_payload": {"screen": "SIGN_UP"},
                },
            },
        },
    }

    return send_mssg(data)


# -----------------------------------
# WOW Flow
# -----------------------------------
def wow_flow_mssg(phone_number: str) -> dict:
    data = {
        "recipient_type": "individual",
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "body": {"text": "StatusFlow Registration"},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3.0",
                    "flow_token": phone_number,
                    "flow_id": "1978397743012942",
                    "flow_cta": "preview",
                    "mode": "draft",
                    "flow_action": "navigate",
                    "flow_action_payload": {"screen": "WELCOME"},
                },
            },
        },
    }

    return send_mssg(data)


# Example test
# print(first_message("", "Justice"))
# print(verification_msg("", "43SD54DF"))
# print(turn_off_disappearing_messages(""))
# print(registration_flow_mssg(""))
# print(wow_flow_mssg(""))
