from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
import os
import json
from dotenv import load_dotenv

from app.crypto import decrypt_request, encrypt_response

load_dotenv()

router = APIRouter(prefix="/flow", tags=["WhatsApp Flow"])

@router.post("/receive")
async def receive_whatsapp_flow(request: Request):
    """
    Receives encrypted WhatsApp Flow request,
    decrypts it, processes based on action, and returns encrypted response.
    """
    try:
        encrypted_body = await request.json()
        payload, aes_key, iv = decrypt_request(encrypted_body)

        print("Decrypted WhatsApp flow data:", json.dumps(payload, indent=2))

        action = payload.get("action")
        screen = payload.get("screen")
        flow_token = payload.get("flow_token")
        version = payload.get("version", "3.0")
        data = payload.get("data", {})

        # Default response structure
        response_data = {}
        next_screen = screen  # default to same screen

        # Handle INIT: just acknowledge — no logic
        if action == "INIT":
            print("Flow initialized, no action required.")
            response_data = {"message": "Flow started successfully."}

        elif action == "ping":
            print("Health Checking")
            response_data = {"status": "pong"}

        # Handle BACK: navigate to previous screen
        elif action == "BACK":
            print("User pressed BACK from:", screen)
            # Example: send them to SIGN_UP screen again
            if screen == "TERMS_AND_CONDITIONS":
                next_screen = "SIGN_UP"
            response_data = {"message": f"Returned to {next_screen}."}

        # Handle DATA_EXCHANGE (form submission)
        elif action == "data_exchange":
            print("Data exchange detected for screen:", screen)

            if screen == "SIGN_UP":
                # Validate terms
                if not data.get("terms_agreement"):
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail="You must agree to the terms and conditions."
                    )

                # Forward data to your internal signup endpoint
                async with httpx.AsyncClient() as client:
                    USER_ENDPOINT = os.getenv("USER_ENDPOINT", "http://localhost:8000/user")
                    forward_response = await client.post(USER_ENDPOINT, json=data)
                    if forward_response.status_code >= 400:
                        raise HTTPException(
                            status.HTTP_400_BAD_REQUEST,
                            detail=f"Internal forward failed: {forward_response.text}"
                        )
                    response_data = forward_response.json()

        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action: {action}")

        # Prepare plaintext response for encryption
        plaintext_response = {
            "screen": next_screen,
            "data": response_data,
            "flow_token": flow_token,
            "version": version
        }

        # Encrypt before returning
        encrypted_response = encrypt_response(plaintext_response, aes_key, iv)

        print(" Encrypted response ready for WhatsApp.")

        return JSONResponse(content=encrypted_response)

    except Exception as e:
        print(" Error processing flow:", e)
        raise HTTPException(status_code=400, detail=f"Flow processing failed: {e}")
