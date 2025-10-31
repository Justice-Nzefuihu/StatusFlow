from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import PlainTextResponse
import httpx
import os
import base64
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta, time
from ..model import ScheduleEnum
from app.crypto import decrypt_request, encrypt_response, decrypt_whatsapp_media
from app.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/flow", tags=["WhatsApp Flow"])

# ─────────────────────────────
# Utility Functions
# ─────────────────────────────

def encode_image_base64(path: str | None) -> str | None:
    """Read image from file path and return as base64 string."""
    try:
        if not path or not Path(path).exists():
            return ""
        with open(path, "rb") as img:
            return base64.b64encode(img.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encode image at {path}: {e}")
        return ""


def is_due_by_schedule(schedule: ScheduleEnum, days_diff: int) -> bool:
    """Check if status is due to upload based on schedule."""
    schedule_map = {
        ScheduleEnum.EVERYDAY.value: 1,
        ScheduleEnum.EVERY_2_DAYS.value: 2,
        ScheduleEnum.EVERY_3_DAYS.value: 3,
        ScheduleEnum.EVERY_4_DAYS.value: 4,
        ScheduleEnum.EVERY_5_DAYS.value: 5,
        ScheduleEnum.EVERY_6_DAYS.value: 6,
        ScheduleEnum.EVERY_WEEK.value: 7,
        ScheduleEnum.EVERY_10_DAYS.value: 10,
        ScheduleEnum.EVERY_2_WEEKS.value: 14,
    }
    interval = schedule_map.get(schedule, 1)
    return days_diff % interval == 0


schedule_map = {
        ScheduleEnum.EVERYDAY.value: "Every Day",
        ScheduleEnum.EVERY_2_DAYS.value: "Every 2D",
        ScheduleEnum.EVERY_3_DAYS.value: "Every 3D",
        ScheduleEnum.EVERY_4_DAYS.value: "Every 4D",
        ScheduleEnum.EVERY_5_DAYS.value: "Every 5D",
        ScheduleEnum.EVERY_6_DAYS.value: "Every 6D",
        ScheduleEnum.EVERY_WEEK.value: "Weekly",
        ScheduleEnum.EVERY_10_DAYS.value: "Every 10D",
        ScheduleEnum.EVERY_2_WEEKS.value: "Biweekly",
    }


def get_error_screen(detail: str, flow_token, version):
    """Return standardized error response."""
    return {
        "screen": "ERROR",
        "data": {"error_mssg": detail},
        "flow_token": flow_token,
        "version": version,
    }


def get_next_screen(screen, response_data, flow_token, version):
    """Return next screen data with consistent format."""
    return {
        "screen": screen,
        "data": response_data,
        "flow_token": flow_token,
        "version": version,
    }

# ─────────────────────────────
# Helper Functions for Screens
# ─────────────────────────────

async def handle_signup_screen(data, phone_number, flow_token, version):
    """Handle sign-up logic."""
    try:
        if not data.get("terms_agreement"):
            return get_error_screen("You must agree to the terms and conditions.", flow_token, version)

        if phone_number != data.get("phone"):
            return get_error_screen("The phone number must match this WhatsApp number.", flow_token, version)

        USER_ENDPOINT = os.getenv("USER_ENDPOINT", "http://localhost:8000/user")
        async with httpx.AsyncClient() as client:
            forward_response = await client.post(USER_ENDPOINT, json=data)

        if forward_response.status_code >= 400:
            logger.warning(f"Signup failed: {forward_response.text}")
            return get_error_screen(forward_response.json().get("detail", "Signup failed."), flow_token, version)

        return {
            "screen": "SUCCESS",
            "data": {"extension_message_response": {"params": {"flow_token": flow_token}}},
        }
    except Exception as e:
        logger.exception(f"Error in handle_signup_screen: {e}")
        return get_error_screen("Unexpected error during sign-up.", flow_token, version)


async def handle_get_status_screen(data, phone_number, flow_token, version):
    """Handle GET STATUS logic (View or Delete)."""
    try:
        STATUS_ENDPOINT = os.getenv("STATUS_ENDPOINT", "http://localhost:8000/status")
        async with httpx.AsyncClient() as client:
            forward_response = await client.get(f"{STATUS_ENDPOINT}/{phone_number}")

        if forward_response.status_code >= 400:
            logger.warning(f"Failed to retrieve statuses: {forward_response.text}")
            return get_error_screen("Failed to retrieve statuses.", flow_token, version)

        statuses = forward_response.json()
        if not statuses:
            return get_next_screen("NO_DATA", {}, flow_token, version)

        status_list = []
        is_view = data.get("selected", "").lower() == "view"

        for status in statuses:
            image = encode_image_base64(status.get("images_path"))
            write_up = status.get("write_up") or "Image Status (No Write Up)"
            if len(write_up) >= 25:
                write_up = f"{write_up[:20]}..."

            schedule_time = time.fromisoformat(status['schedule_time']).strftime("%I:%M %p")
            schedule = schedule_map.get(status.get("schedule"), status.get("schedule"))

            # Format created_at
            created_at = status.get("created_at", "")
            if "T" in created_at:
                created_at = created_at.replace("T", " ")

            created_at = created_at.split(".")[0]

            now = datetime.now()
            start_time = (now - timedelta(minutes=5)).time()
            end_time = (now + timedelta(minutes=35)).time()
            days_diff = (now.date() - datetime.fromisoformat(str(status["created_at"])).date()).days
            is_within_window = start_time <= time.fromisoformat(str(status["schedule_time"])) <= end_time

            is_enabled = ((is_due_by_schedule(status["schedule"], days_diff) or days_diff == 1)
                              and is_within_window and not status["is_upload"])

            if is_view:
                status_dict = {
                    "id": status["id"],
                    "main-content": {
                        "title": write_up,
                        "description": f"{schedule} @{schedule_time}",
                        "metadata": f"{created_at}"
                    },
                    "start": {"image": image},
                    "on-click-action": {
                        "name": "navigate",
                        "next": {"name": "STATUS_DETAILS", "type": "screen"},
                        "payload": {
                            "id": status["id"],
                            "write_up": status["write_up"],
                            "is_text": status["is_text"],
                            "type": "Type: Text Status" if status["is_text"] else "Type: Image Status",
                            "image": image,
                            "scheduled": f"Schedule: {status['schedule']} ({status['schedule_time']})",
                            "schedule": f"{status['schedule']}",
                            "schedule_time": f"{status['schedule_time']}",
                            "is_upload": "Uploaded: Yes" if status["is_upload"] else "Uploaded: No",
                            "created_at": f"created_at: {created_at}",
                            "upload_window_active": is_enabled
                        }
                    }
                }
            else:
                status_dict = {
                    "id": status["id"],
                    "title": write_up,
                    "description": f"{schedule} @{schedule_time}",
                    "metadata": f"{created_at}",
                    "enabled": is_enabled,
                    "image": image
                }

            status_list.append(status_dict)

        next_screen = "VIEW_STATUS" if is_view else "DELETE_SCREEN"
        return get_next_screen(next_screen, {"statuses": status_list}, flow_token, version)

    except Exception as e:
        logger.exception(f"Error in handle_get_status_screen: {e}")
        return get_error_screen("Unexpected error while retrieving statuses.", flow_token, version)


async def handle_add_status_screen(data, phone_number, flow_token, version):
    """Handle adding new status logic."""
    try:
        STATUS_ENDPOINT = os.getenv("STATUS_ENDPOINT", "http://localhost:8000/status")
        ADD_STATUS_ENDPOINT = f"{STATUS_ENDPOINT}/{phone_number}"

        image_list = data.get("image")
        is_text = bool(data.get("is_text"))

        if not is_text:
            if image_list and len(image_list) > 0:
                photo_picker = image_list[0]
                data["image_path"] = photo_picker.get("file_name")
                data["image"] = decrypt_whatsapp_media(photo_picker)
        else:
            if not image_list:
                data.pop("image", None)
            else:
                logger.warning("Failed to add status: did  not cancel image or unselect only_text.")
                return get_error_screen("Please cancel image or unselect only_text.", flow_token, version)

        async with httpx.AsyncClient() as client:
            forward_response = await client.post(ADD_STATUS_ENDPOINT, json=data)

        if forward_response.status_code >= 400:
            logger.warning(f"Failed to add status: {forward_response.text}")
            return get_error_screen("Failed to add status.", flow_token, version)

        return get_next_screen("COMPLETE", {"mssg": "Status added successfully."}, flow_token, version)
    except Exception as e:
        logger.exception(f"Error in handle_add_status_screen: {e}")
        return get_error_screen("Unexpected error adding status.", flow_token, version)


async def handle_delete_status_screen(data, phone_number, flow_token, version):
    """Handle deleting an existing status."""
    try:
        STATUS_ENDPOINT = os.getenv("STATUS_ENDPOINT", "http://localhost:8000/status")
        DELETE_ENDPOINT = f"{STATUS_ENDPOINT}/{phone_number}/{data.get('id')}"
        async with httpx.AsyncClient() as client:
            forward_response = await client.delete(DELETE_ENDPOINT)
            if forward_response.status_code >= 400:
                    logger.warning(f"Failed to delete status: {forward_response.text}")
                    return get_error_screen("Failed to delete status." ,flow_token, version)

        return get_next_screen("DELETE_COMPLETE", {"mssg": "Status deleted successfully."}, flow_token, version)
    except Exception as e:
        logger.exception(f"Error in handle_delete_status_screen: {e}")
        return get_error_screen("Unexpected error deleteing status.", flow_token, version)
    
async def handle_status_details_screen(data, phone_number, flow_token, version):
    """Handle status details an existing status."""
    try:
       if data.get("Choose_an_action_for_detail").lower() == "delete":
            data["id"] = data.pop("status_id")
            return await handle_add_status_screen(data, phone_number, flow_token, version)
       else: 
            data.pop("Choose_an_action_for_detail", None)
            return get_next_screen("UPDATE_STATUS", data, flow_token, version)
       
    except Exception as e:
        logger.exception(f"Error in handle_status_details_screen: {e}")
        return get_error_screen("Unexpected error in status details.", flow_token, version)


async def handle_update_status_screen(data, phone_number, flow_token, version):
    """Handle updating a status (write-up, schedule, etc)."""
    try:
        STATUS_ENDPOINT = os.getenv("STATUS_ENDPOINT", "http://localhost:8000/status")
        status_id = data.pop("status_id", None) 
        STATUS_ENDPOINT = os.getenv("STATUS_ENDPOINT", "http://localhost:8000/status") 
        UPDATE_STATUS_ENDPOINT = f"{STATUS_ENDPOINT}/{phone_number}/{status_id}"
        async with httpx.AsyncClient() as client:
            forward_response = await client.put(UPDATE_STATUS_ENDPOINT, json=data)
            if forward_response.status_code >= 400:
                    logger.warning(f"Failed to update status: {forward_response.text}")
                    return get_error_screen("Failed to update status." ,flow_token, version)

        return get_next_screen("DELETE_COMPLETE", {"mssg": "Status updated successfully."}, flow_token, version)
    except Exception as e:
        logger.exception(f"Error in handle_delete_status_screen: {e}")
        return get_error_screen("Unexpected error deleteing status.", flow_token, version)


# ─────────────────────────────
# Main Endpoint
# ─────────────────────────────

@router.post("/receive")
async def receive_whatsapp_flow(request: Request):
    """
    Receive encrypted WhatsApp Flow request,
    decrypt, process based on action, and return encrypted response.
    """
    try:
        encrypted_body = await request.json()
        payload, aes_key, iv = decrypt_request(encrypted_body)
        logger.info("Received WhatsApp flow.")

        action = payload.get("action")
        screen = payload.get("screen")
        flow_token = payload.get("flow_token")
        version = payload.get("version", "3.0")
        data = payload.get("data", {})
        phone_number = f"+{flow_token}"

        plaintext_response = None

        if action == "ping":
            plaintext_response = {"data": {"status": "active"}}

        elif action == "data_exchange":
            if screen == "SIGN_UP":
                plaintext_response = await handle_signup_screen(data, phone_number, flow_token, version)
            elif screen == "INDEX":
                plaintext_response = await handle_get_status_screen(data, phone_number, flow_token, version)
            elif screen == "STATUS_DETAILS":
                plaintext_response = await handle_status_details_screen(data, phone_number, flow_token, version)
            elif screen == "DELETE_STATUS":
                plaintext_response = await handle_delete_status_screen(data, phone_number, flow_token, version)
            elif screen == "UPDATE_STATUS":
                plaintext_response = await handle_update_status_screen(data, phone_number, flow_token, version)
            elif screen == "ADD_STATUS":
                plaintext_response = await handle_add_status_screen(data, phone_number, flow_token, version)
            else:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unsupported screen: {screen}")
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action: {action}")

        encrypted_response = encrypt_response(plaintext_response, aes_key, iv)
        logger.info("Encrypted response successfully prepared.")
        return PlainTextResponse(content=encrypted_response)

    except Exception as e:
        logger.exception(f"Error processing WhatsApp flow: {e}")
        raise HTTPException(status_code=400, detail=f"Flow processing failed: {e}")
