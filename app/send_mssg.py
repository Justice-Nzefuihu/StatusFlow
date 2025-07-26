import requests
from config import setting

ACCESS_TOKEN = setting.access_token
PHONE_NUMBER_ID = setting.phone_number_id
RECIPIENT_PHONE = "2349043262304"

url = f"https://graph.facebook.com/v22.0/753045567890417/messages"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "messaging_product": "whatsapp",
    "to": RECIPIENT_PHONE,
    "type": "text",
    "text": {
        "body": "Hello! This is a test message from WhatsApp API."
    }
}

try:
    response = requests.post(url, headers=headers, json=data)
    response_data = response.json()
    print(response.status_code, response.json())
except Exception as e:
    print(f"Error occurred: {e}")

# { 
#     "messaging_product": "whatsapp", 
#     "to": "2349043262304", 
#     "type": "template", 
#     "template": { 
#         "name": "hello_world", 
#         "language": { "code": "en_US" } 
#     } 
# }

