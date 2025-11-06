from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import hmac
import hashlib
from ..config import setting
from app.middlewares import get_rate_limit
from ..send_mssg import first_message, wow_flow_mssg, registration_flow_mssg

# Configure logger
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

VERIFY_TOKEN = setting.verify_token
APP_SECRET = setting.app_secret


@router.get("", dependencies=[Depends(get_rate_limit(50, 60))])
async def verify_webhook(request: Request):
    """
    Webhook verification for WhatsApp Business API.
    """
    try:
        query_params = request.query_params
        mode = query_params.get("hub.mode")
        token = query_params.get("hub.verify_token")
        challenge = query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully.")
            return int(challenge)

        logger.warning("Webhook verification failed. Invalid token or mode.")
        return JSONResponse(content={"error": "Verification failed"}, status_code=403)

    except Exception as e:
        logger.error(f"Error verifying webhook: {e}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)


@router.post("", dependencies=[Depends(get_rate_limit(50, 60))])
async def receive_webhook(request: Request):
    """
    Handles incoming messages from WhatsApp.
    """
    try:
        signature = request.headers.get("X-Hub-Signature-256")
        body = await request.body()

        expected_signature = "sha256=" + hmac.new(
            APP_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()

        if signature != expected_signature:
            logger.warning("Invalid signature detected in webhook.")
            return JSONResponse(content={"error": "Invalid signature"}, status_code=403)

        data = await request.json()
        logger.info("Webhook event received successfully.")

        if "entry" in data:
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    contacts = value.get("contacts", [])
                    messages = value.get("messages", [])
                    if len(contacts) == len(messages) and contacts:
                        for index in len(contacts):
                            contact = contacts[index]
                            username = contact["profile"]["name"]

                            msg = messages[index]
                            phone_number = msg.get("from")
                            logger.info(f"Message received from {username} ({phone_number}).")

                            text = msg.get("text", {})
                            body = text.get("body", "")

                            if body == "STATUSFLOW":
                                first_message(phone_number, username)
                            elif body == "register":
                                registration_flow_mssg(phone_number)
                            elif body == "Done":
                                wow_flow_mssg(phone_number)


        return JSONResponse(content={"status": "received"}, status_code=200)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)
