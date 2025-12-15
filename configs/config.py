# /configs/config.py
import os
from dotenv import load_dotenv

use_env_working_dir = False
working_dir = "/root/miniapp_backend/game"
ENV_WORKING_DIR_KEY = "WORKING_DIR"

# Decide working dir
BASE_DIR = (
    os.getenv(ENV_WORKING_DIR_KEY)
    if use_env_working_dir and os.getenv(ENV_WORKING_DIR_KEY)
    else working_dir
)

# Load .env from game directory
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

# Read secret
SECRET = os.getenv("SECRET")


def get_base_dir() -> str:
    """
    Returns the working directory:
    - from ENV if enabled
    - otherwise from config fallback
    """
    if use_env_working_dir:
        env_value = os.getenv(ENV_WORKING_DIR_KEY)
        if env_value:
            return env_value
        else:
            raise RuntimeError(
                f"use_env_working_dir=True but ENV variable '{ENV_WORKING_DIR_KEY}' not set"
            )

    return working_dir


def get_klines_dir() -> str:
    """Returns the full path to the klines directory."""
    return os.path.join(get_base_dir(), "klines")


WS_ALLOWED_ORIGINS = {
    "https://dev.simmerliq.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
        "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://demoapp.prime-academy.online",
   'https://tradcastdev.prime-academy.online',
   'https://tradcast.simmerliq.com'
    }


# ✅ Allowed origins for HTTP
CORS_ALLOWED_ORIGINS = [
    'https://tradcastdev.prime-academy.online',
        "https://dev.simmerliq.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "demoapp.prime-academy.online",
    'tradcastdev.prime-academy.online',
    'tradcast.simmerliq.com'
    ]

