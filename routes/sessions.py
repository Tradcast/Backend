from fastapi import APIRouter
from fastapi import Request
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from configs.config import SECRET_KEY

session_router = APIRouter()

# get token, session_end, fid for ws
@session_router.post("/start_session")
async def start_session(request: Request):
    body = await request.json()
    print("📦 Received body:", body)

    try:
        encrypted_token = body.get('encrypted_token')
        if not encrypted_token:
            return {"error": "No encrypted_token provided"}

        # Decrypt the token
        decrypted_json = decrypt(encrypted_token, SECRET_KEY)
        print("🔓 Decrypted message:", decrypted_json)

        # Parse the JSON payload
        payload = json.loads(decrypted_json)
        print("✅ Parsed payload:", payload)
        print(f"   - FID: {payload.get('fid')}")
        print(f"   - Token: {payload.get('token')}")
        print(f"   - Session End: {payload.get('session_end')}")

        return {"success": True, "payload": payload}

    except Exception as e:
        print(f"❌ Decryption error: {str(e)}")
        return {"error": str(e)}

