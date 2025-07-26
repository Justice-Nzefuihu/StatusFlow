from fastapi import (
    APIRouter, Request
    )
from fastapi.responses import JSONResponse
import hmac
import hashlib
import json
from ..config import setting

router = APIRouter(prefix="/webhook", tags=["Webhook"])

VERIFY_TOKEN = setting.verify_token
APP_SECRET = setting.app_secret

@router.get("/")
async def verify_webhook(request: Request):
    """
    Webhook verification for WhatsApp Business API.
    """
    query_params = request.query_params
    mode = query_params.get("hub.mode")
    token = query_params.get("hub.verify_token")
    challenge = query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return JSONResponse(content={"error": "Verification failed"}, status_code=403)


@router.post("/")
async def receive_webhook(request: Request):
    """
    Handles incoming messages from WhatsApp.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    secret = APP_SECRET

    expected_signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if signature != expected_signature:
        return JSONResponse(content={"error": "Invalid signature"}, status_code=403)
    
    data = await request.json()
    print("Webhook data:", json.dumps(data, indent=4))

    if "entry" in data:
        for entry in data["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if messages:
                    for msg in messages:
                        phone_number = msg.get("from")
                        text = msg.get("text", {}).get("body")
                        print(f"Received message from {phone_number}: {text}")

    return JSONResponse(content={"status": "received"}, status_code=200)
