from fastapi.middleware.cors import CORSMiddleware
from routes.users import user_router
from routes.sessions import session_router  
from configs.config import *
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request
from htmls import *
from fastapi.responses import HTMLResponse

from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

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

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/health")
async def health():
    return {"status": "ok"}



