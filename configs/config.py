import os
import load_dotenv

load_dotenv()
SECRET_KEY = os.environ.get('SECRET_KEY')

# Whether to use environment variable for working directory
use_env_working_dir = False

# ENV variable name for dynamic working dir
ENV_WORKING_DIR_KEY = "WORKING_DIR"

# Fallback working directory (used if above is False)
working_dir = "/home/..." # your working dir, where main.py is...

firestore_project_name = "your-project-name"

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
    # https://domain
    }


# ✅ Allowed origins for HTTP
CORS_ALLOWED_ORIGINS = [
    # domain
    ]

