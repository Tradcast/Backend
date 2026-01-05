print(12)
from fastapi.middleware.cors import CORSMiddleware
print(44)
from routes.users import user_router
from routes.sessions import session_router  
print(43)
from configs.config import *
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request
print(4)
from htmls import *
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

print(3)
app = FastAPI()

#app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Custom Middleware (Only affects HTTP, not WebSocket)
class BlockUnknownRoutesMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_paths_prefixes: list[str]):
        super().__init__(app)
        self.allowed_paths_prefixes = allowed_paths_prefixes

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow exact matches
        if path == "/favicon.ico":
            return await call_next(request)

        # Allow static
        if path.startswith("/static/"):
            return await call_next(request)

        # Allow all allowed prefixes
        if any(path.startswith(prefix) for prefix in self.allowed_paths_prefixes):
            return await call_next(request)

        # Block everything else
        return HTMLResponse(
            content=not_found_html,
            status_code=403
        )


# ====================== CORS ======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================== Allowed Paths ======================
allowed_paths = [
    "/",                  # root
    "/docs",
    "/openapi.json",
    "/health",
    "/ws",                # websocket
    "/api/v1/session",    # whole session router
    "/api/v1/user",       # whole user router
]

app.add_middleware(BlockUnknownRoutesMiddleware, allowed_paths_prefixes=allowed_paths)


# ====================== Include Routers ======================
app.include_router(session_router, prefix="/api/v1/session", tags=["session"])
app.include_router(user_router, prefix="/api/v1/user", tags=["user"])


@app.get("/")
async def root():
    return {"message": "Miniapp backend is running 🚀"}

#@app.get("/favicon.ico")
#async def favicon():
#    return FileResponse("static/favicon.ico")


@app.get("/health")
async def health():
    return {"status": "ok"}




import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional
from pathlib import Path

class DailyGameplayTracker:
    """Tracks daily gameplay counts per FID with UTC midnight resets and persistent storage"""

    def __init__(self, storage_file: str = "gameplay_data.json"):
        self.storage_file = storage_file
        self.gameplay_data: Dict[str, Dict] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """Load gameplay data from disk"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    self.gameplay_data = json.load(f)
                print(f"✅ Loaded gameplay data from {self.storage_file}")
            except Exception as e:
                print(f"⚠️ Error loading gameplay data: {e}")
                self.gameplay_data = {}
        else:
            print(f"📝 No existing gameplay data found, starting fresh")
            self.gameplay_data = {}

    def _save_to_disk(self):
        """Save gameplay data to disk"""
        try:
            # Create directory if it doesn't exist
            Path(self.storage_file).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_file, 'w') as f:
                json.dump(self.gameplay_data, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving gameplay data: {e}")

    def get_current_utc_date(self) -> str:
        """Get current date in UTC as string"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def increment_gameplay(self, fid: str, amount: int = 2) -> int:
        """
        Increment gameplay count for a FID by the specified amount.
        Resets count if it's a new day.

        Args:
            fid: The user's FID
            amount: Amount to increment (default: 2)

        Returns:
            The new gameplay count for today
        """
        current_date = self.get_current_utc_date()

        if fid not in self.gameplay_data:
            # New FID
            self.gameplay_data[fid] = {
                "count": amount,
                "date": current_date
            }
        else:
            # Check if it's a new day
            if self.gameplay_data[fid]["date"] != current_date:
                # Reset for new day
                self.gameplay_data[fid] = {
                    "count": amount,
                    "date": current_date
                }
            else:
                # Increment for same day
                self.gameplay_data[fid]["count"] += amount

        # Save to disk after every change
        self._save_to_disk()
        
        return self.gameplay_data[fid]["count"]

    def get_gameplay_count(self, fid: str) -> int:
        """
        Get current gameplay count for a FID.
        Returns 0 if FID not found or date is old.
        """
        current_date = self.get_current_utc_date()

        if fid not in self.gameplay_data:
            return 0

        if self.gameplay_data[fid]["date"] != current_date:
            return 0

        return self.gameplay_data[fid]["count"]

    def reset_all(self):
        """Reset all gameplay data"""
        self.gameplay_data.clear()
        self._save_to_disk()

    def cleanup_old_data(self, days_to_keep: int = 7):
        """Remove data older than specified days"""
        current_date = datetime.now(timezone.utc)
        fids_to_remove = []
        
        for fid, data in self.gameplay_data.items():
            data_date = datetime.strptime(data["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_old = (current_date - data_date).days
            
            if days_old > days_to_keep:
                fids_to_remove.append(fid)
        
        for fid in fids_to_remove:
            del self.gameplay_data[fid]
        
        if fids_to_remove:
            self._save_to_disk()
            print(f"🧹 Cleaned up {len(fids_to_remove)} old entries")



# Usage in your game_main.py:
# Initialize at module level
gameplay_tracker = DailyGameplayTracker()


@app.get("/increase_tracker")
async def increase_tracker(fid):
    current_gameplay = gameplay_tracker.increment_gameplay(str(fid), amount=2)
    return {"status": "ok"}


@app.get("/get_tracker")
async def increase_tracker():
    return gameplay_tracker.gameplay_data


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        #host="127.0.0.1",
        port=5009,
        #reload=True
    )

