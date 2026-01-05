from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime


app = FastAPI()
fid_mem = []


from fastapi import Request
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

# CRITICAL: Move this to environment variable in production!
SECRET_KEY = "74bd7aa5fe7cebe852e09b2e5a6496ddd22d47640110fda654b1cf4ff53a4e1c05ef3e1866f6db6d9c23188143af1214"  # Must match the Node.js SECRET_KEY

def decrypt(encrypted_data: str, secret: str) -> str:
    """Decrypt AES-256-GCM encrypted data"""
    try:
        # Split the encrypted data: iv:authTag:encrypted
        parts = encrypted_data.split(':')
        if len(parts) != 3:
            raise ValueError("Invalid encrypted data format")

        iv_hex, auth_tag_hex, encrypted_hex = parts

        # Convert from hex
        iv = bytes.fromhex(iv_hex)
        auth_tag = bytes.fromhex(auth_tag_hex)
        encrypted = bytes.fromhex(encrypted_hex)

        # Derive key using Scrypt (matching Node.js scryptSync)
        kdf = Scrypt(
            salt=b'salt',  # Must match Node.js salt
            length=32,
            n=2**14,
            r=8,
            p=1,
            backend=default_backend()
        )
        key = kdf.derive(secret.encode())

        # Decrypt using AES-256-GCM
        aesgcm = AESGCM(key)
        # Combine encrypted data with auth tag for decryption
        ciphertext = encrypted + auth_tag
        decrypted = aesgcm.decrypt(iv, ciphertext, None)

        return decrypted.decode('utf8')
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


@app.post("/start_session")
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


@app.get("/home")
async def get_home(fid: int):
    print('home', fid)
    return {'energy': 6}


@app.get("/profile")
async def get_profile(fid: int):
    """
    GET /profile?fid=123
    """
    try:
        # Replace this with your DB lookup
        user = fake_db_get_user(fid)
        print('profile get', fid)
        if fid not in fid_mem:
            print('fid not found')
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))




@app.post("/profile")
async def create_or_update_profile(request: Request):
    """
    POST /profile
    Body: { ...fields, fid }
    """
    print('profile request')
    try:
        body = await request.json()
        fid = body.get("fid")
        print(fid)
        print(body)
        if fid not in fid_mem:
            fid_mem.append(fid)
        
        if fid is None:
            raise HTTPException(status_code=400, detail="Missing fid")

        # Example: Save to DB
        user = fake_db_upsert_user(body)

        return user

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))



# -----------------------------
# Example stub DB functions
# Replace with Mongo / SQL logic
# -----------------------------
def fake_db_get_user(fid: int):
    trade_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    return {
        "fid": fid,
        "test": 1,
        "name": "Dummy 1User",
        "stats": {
            "total_games": 0,
            "liquidation_times": 0
        },
        "achivements": {
            "highest pnl": 0
        },
        "history": [
            {"trade_time": trade_time,
            "initial_balance": 1000,
            "final_balance": 2404,
            "pnl": 140}, # at most total of 6, least 0  
            ]
    }


def fake_db_upsert_user(data: dict):
    # Example
    return {"status": "ok", "user": data}

if __name__ == "__main__":
    uvicorn.run(
        "fake_listener:app",       # filename:app
        port=8031,
    )
