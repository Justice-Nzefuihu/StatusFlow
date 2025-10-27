import os
import requests
from dotenv import load_dotenv

load_dotenv()

# === Configuration ===
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")  # Your WhatsApp Business API Access Token
print(ACCESS_TOKEN)
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # Replace with your own WhatsApp Business Account ID
print(PHONE_NUMBER_ID)

# the key as a string
PUBLIC_KEY = os.getenv("PUBLIC_KEY")


# === Prepare Request ===
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/x-www-form-urlencoded"
}

data = {
    "business_public_key": PUBLIC_KEY
}

GRAPH_URL = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/whatsapp_business_encryption"

# === Send Request ===
print(" Sending public key to WhatsApp Business API...")
print(f"headers : {headers}")
response = requests.post(GRAPH_URL, headers=headers, data=data)

# === Handle Response ===
if response.status_code == 200:
    print(" Public key uploaded successfully!")
    print("Response:", response.json())
else:
    print(f" Failed to upload key. Status: {response.status_code}")
    try:
        print("Error:", response.json())
    except Exception:
        print("Response Text:", response.text)
