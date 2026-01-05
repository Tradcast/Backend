import random

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import pandas as pd
import asyncio
from collections import deque
from datetime import datetime
from watchfiles import awatch
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from htmls import *
import os
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

# CRITICAL: Move this to environment variable in production!
SECRET_KEY = "74bd7aa5fe7cebe852e09b2e5a6496ddd22d47640110fda654b1cf4ff53a4e1c05ef3e1866f6db6d9c23188143af1214"  # Must match the Node.js SECRET_KEY

# os get current directory then list and loop all parquet data here
...
spike_df_somi = pd.read_parquet('klines/SOMI_upbit_listing_spot_10_01.parquet')
spike_df_hyper = pd.read_parquet('klines/HYPER_upbit_listing_spot_07_10.parquet')


# start from index 35
spike_df_somi = spike_df_somi.iloc[35:].reset_index(drop=True)

debug_ = False  # make true if face a problem
spike_df_map = {'somi': spike_df_somi, 'hyper': spike_df_hyper}


app = FastAPI()

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
    'tradcastdev.prime-academy.online'
    ]

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
   'https://tradcastdev.prime-academy.online' 
    }



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




# ✅ Custom Middleware (Only affects HTTP, not WebSocket)
class BlockUnknownRoutesMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_paths: list[str]):
        super().__init__(app)
        self.allowed_paths = set(allowed_paths)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.allowed_paths or path.startswith("/static/") or path == "/favicon.ico":
            return await call_next(request)

        return HTMLResponse(
            content=not_found_html,
            status_code=403
        )

# ✅ CORS setup (for HTTP only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Restrict unknown paths (HTTP only)
allowed_paths = [
    "/ws",
    "/favicon.ico"
]

app.add_middleware(BlockUnknownRoutesMiddleware, allowed_paths=allowed_paths)

# it is not hedge. Every position is 100 dollar worth.
# if long started continue long
# if going short continue short
# to switch close long and open short or close short and open long.
# version is isolated not cross for now.
import asyncio
from typing import Optional


class FuturesWallet:
    def __init__(self, token_selection='somi', leverage: int = 20, capital: float = 1000.0):
        self.leverage = leverage
        self.position_size = 100.0
        self.token_selection = token_selection

        self.capital = float(capital)  # starting capital (constant baseline)

        # balances:
        self.balance_free = float(capital)  # cash not reserved as margin
        self.balance_in_position = 0.0  # margin currently locked in positions
        self.balance_total = float(capital)  # equity (free + in_position + unrealized PnL)

        # position tracking
        self.long_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.short_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.direction = None  # "long" or "short" or None when no position

        # async lock for concurrent access from websocket tasks
        self._lock = asyncio.Lock()

        self.long_queue = []
        self.short_queue = []
        self.close_pos_queue = []

        def get_order_packet_send_time():
            ...

        self.binance_packet_sending_time = get_order_packet_send_time()

    # small helper to clear positions without touching balances
    async def _clear_positions(self):
        self.balance_in_position = 0.0
        self.long_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.short_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.direction = None

    async def get_wallet_state(self):
        async with self._lock:
            total_profit = (self.balance_total - self.capital) / self.capital
            return {
                "balance_total": self.balance_total,
                "total_profit": total_profit,
                "balance_free": self.balance_free,
                "in_position": self.balance_in_position,
                "long_average": self.long_positions['average_price'],
                "short_average": self.short_positions['average_price'],
                "direction": self.direction
            }

    # open a long (returns True if opened)
    async def add_long(self, index) -> bool:
        async with self._lock:
            if self.short_positions['num_pos'] > 0:
                return False
            if self.balance_free < self.position_size:
                return False
            price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            self.long_positions['total_price'] += price
            self.long_positions['num_pos'] += 1
            self.long_positions['average_price'] = (self.long_positions['total_price'] /
                                                    self.long_positions['num_pos'])

            self.direction = "long"
            self.balance_in_position += self.position_size
            self.balance_free -= self.position_size
            # update total equity after opening (no unrealized PnL yet)
            self.balance_total = self.balance_free + self.balance_in_position
            return True

    async def add_short(self, index) -> bool:
        async with self._lock:
            if self.long_positions['num_pos'] > 0:
                return False
            if self.balance_free < self.position_size:
                return False
            price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            self.short_positions['total_price'] += price
            self.short_positions['num_pos'] += 1
            self.short_positions['average_price'] = (self.short_positions['total_price'] /
                                                     self.short_positions['num_pos'])

            self.direction = "short"
            self.balance_in_position += self.position_size
            self.balance_free -= self.position_size
            self.balance_total = self.balance_free + self.balance_in_position
            return True

    # close fully: release margin and apply realized PnL
    async def close_position_full(self, index) -> bool:
        async with self._lock:
            # choose which position we're closing
            if self.direction == "long":
                positions = self.long_positions
            elif self.direction == "short":
                positions = self.short_positions
            else:
                return False  # nothing to close

            if positions['num_pos'] == 0 or positions['average_price'] is None:
                return False

            cur_price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            change = (cur_price - positions['average_price']) / positions['average_price']  # decimal
            profit = self.balance_in_position * change * self.leverage
            # for short, profit sign is reversed
            if self.direction == "short":
                profit = -profit

            # release margin + realized PnL back to free balance
            self.balance_free += self.balance_in_position + profit

            # clear positions (without overwriting new balance_free)
            await self._clear_positions()

            # set total equity to free balance (no open positions)
            self.balance_total = self.balance_free
            return True

    # handle liquidation: margin is lost (already removed from balance_free at open),
    # so we just clear positions and set balance_total = balance_free
    async def liq_position(self):
        # losing margin (it was already subtracted from balance_free on open)
        await self._clear_positions()
        self.balance_total = self.balance_free

    # called periodically (every 0.4s). computes unrealized pnl and updates balance_total,
    # checks liquidation using decimal thresholds (<= -1 or >= 1)
    async def calculate_final_balance(self, current_index):
        async with self._lock:
            # if no open positions, equity is simply free cash
            if self.direction is None:
                self.balance_total = self.balance_free
                return

            if self.direction == "long":
                positions = self.long_positions
            else:
                positions = self.short_positions

            if positions['num_pos'] == 0 or positions['average_price'] is None:
                self.balance_total = self.balance_free
                return

            cur_price = float(spike_df_map[self.token_selection]['close'].iloc[current_index])
            cur_low = float(spike_df_map[self.token_selection]['low'].iloc[current_index])
            cur_high = float(spike_df_map[self.token_selection]['high'].iloc[current_index])

            entry = positions['average_price']
            change_close = (cur_price - entry) / entry
            change_low = (cur_low - entry) / entry
            change_close_lev = change_close * self.leverage
            change_low_lev = change_low * self.leverage

            if self.direction == "long":
                # liquidation if worst intrabar price -> loss >= margin
                if change_low_lev <= -1.0:
                    await self.liq_position()
                    return
                unrealized = self.balance_in_position * change_close_lev
                self.balance_total = self.balance_free + self.balance_in_position + unrealized
            else:
                change_high = (cur_high - entry) / entry
                change_high_lev = change_high * self.leverage
                if change_high_lev >= 1.0:
                    await self.liq_position()
                    return
                # short unrealized PnL (profit when price goes down -> negative change)
                unrealized = - self.balance_in_position * change_close_lev
                self.balance_total = self.balance_free + self.balance_in_position + unrealized

    async def push_order_long(self, index):
        self.long_queue.append(index)

    async def push_order_short(self, index):
        self.short_queue.append(index)

    async def push_close(self, index):
        self.close_pos_queue.append(index)

    # runs as a task
    async def consume_queue(self):
        # while True:
        for index in self.long_queue:
            await self.add_long(index)

        for index in self.short_queue:
            await self.add_short(index)

        for index in self.close_pos_queue:
            await self.close_position_full(index)

        self.long_queue = []
        self.short_queue = []
        self.close_pos_queue = []
        # await asyncio.sleep(0.1)  # some ms like 10ms maybe


class PriceFlow:
    def __init__(self, window_size=60, token_selection='somi'):
        self.window_size = window_size
        self.token_selection = token_selection
        self.total_rows = len(spike_df_map[self.token_selection])
        self.window = []
        self.current_index = 0

    @staticmethod
    def serialize_row(row):
        """Convert a DataFrame row to a JSON-serializable dict"""
        row_dict = row.to_dict()
        return {k: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
                for k, v in row_dict.items()}

    async def initialize_dict(self):
        # restart window
        self.window = []
        for i in range(self.window_size):
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))

        return self.window

    async def handle_websocket_flow(self, websocket: WebSocket):  # , futures_wallet: FuturesWallet):
        # Start sliding
        for i in range(self.window_size, self.total_rows):
            self.current_index = i
            self.window.pop(0)
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))
            await websocket.send_json({
                "type": "prices",
                "count": i + 1,
                "window": self.window,
                # "wallet": await futures_wallet.get_wallet_state()
            })
            await asyncio.sleep(1)

        for i in range(self.window_size, self.total_rows):
            self.current_index = i
            self.window.pop(0)
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))
            await websocket.send_json({
                "type": "prices",
                "count": i + 1,
                "window": self.window,
                # "wallet": await futures_wallet.get_wallet_state()
            })

            await asyncio.sleep(1)



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    origin = websocket.headers.get("origin")

    if origin not in WS_ALLOWED_ORIGINS:
        await websocket.close(code=1008)  # Policy violation
        return

    await websocket.accept()

    # Wait for authentication message first
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_data = json.loads(auth_message)

        encrypted_token = auth_data.get('encrypted_token')
        if not encrypted_token:
            await websocket.send_json({"error": "No encrypted_token provided"})
            await websocket.close(code=1008)
            return

        # Decrypt and validate the token
        try:
            decrypted_json = decrypt(encrypted_token, SECRET_KEY)
            payload = json.loads(decrypted_json)

            # Extract FID for later use
            fid = payload.get('fid')
            if not fid:
                await websocket.send_json({"error": "No fid in token"})
                await websocket.close(code=1008)
                return

            print(f"✅ WebSocket authenticated for FID: {fid}")
            await websocket.send_json({"authenticated": True, "fid": fid})

        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            await websocket.send_json({"error": "Authentication failed"})
            await websocket.close(code=1008)
            return

    except asyncio.TimeoutError:
        print("❌ Authentication timeout")
        await websocket.close(code=1008)
        return
    except json.JSONDecodeError:
        print("❌ Invalid JSON in auth message")
        await websocket.close(code=1008)
        return

    # Now proceed with normal WebSocket logic
    sending_task = None
    handle_wallet_task = None

    keys = list(spike_df_map.keys())
    random_token = random.choice(keys)

    price_flow = PriceFlow(token_selection=random_token)
    futures_wallet = FuturesWallet(leverage=20, token_selection=random_token)

    async def handle_wallet():
        try:
            a = 0
            while True:
                if debug_:
                    print(a)
                    print("[x] consume queue")
                await futures_wallet.consume_queue()
                if debug_:
                    print("[x] calculate final balance")
                await futures_wallet.calculate_final_balance(price_flow.current_index)
                if debug_:
                    print("[x] send wallet to websocket")
                await websocket.send_json({
                    "type": "wallet",
                    "wallet": await futures_wallet.get_wallet_state()
                })
                if debug_:
                    print("[x] sleep")
                await asyncio.sleep(0.1)
                a += 1

        except asyncio.CancelledError:
            print("stream was cancelled")

        except Exception as e:
            print(f"error in stream: {e}")

    async def stream_rows():
        try:
            window = await price_flow.initialize_dict()
            window_size = price_flow.window_size

            await websocket.send_json({"count": window_size, "window": window})

            print(f"Sent initial window of {window_size} rows")
            await asyncio.sleep(1)
            await price_flow.handle_websocket_flow(websocket)

        except asyncio.CancelledError:
            print("Stream was cancelled")
            raise
        except Exception as e:
            print(f"Error in stream_rows: {e}")
            raise

    async def print_price_flow_index():
        while price_flow.current_index < 120:
            print(price_flow.current_index)
            await asyncio.sleep(1)

    try:
        while True:
            message = await websocket.receive_text()

            if message == "start":
                if sending_task is None or sending_task.done():
                    futures_wallet = FuturesWallet(leverage=20, token_selection=random_token)
                    sending_task = asyncio.create_task(stream_rows())
                    handle_wallet_task = asyncio.create_task(handle_wallet())

                    await asyncio.sleep(0.01)
                    await websocket.send_text("Streaming started.")
                else:
                    await websocket.send_text("Already streaming.")

            elif message == "stop":
                if sending_task:
                    sending_task.cancel()
                    handle_wallet_task.cancel()
                    await asyncio.sleep(0.01)
                    await websocket.send_text("Streaming stopped.")
                else:
                    await websocket.send_text("Nothing is streaming.")

            # Wallet commands
            elif message == "long":
                index = price_flow.current_index
                if debug_:
                    print("long")
                await futures_wallet.push_order_long(index)

            elif message == "short":
                index = price_flow.current_index
                if debug_:
                    print("short")
                await futures_wallet.push_order_short(index)

            elif message == "close":
                index = price_flow.current_index
                if debug_:
                    print("close")
                await futures_wallet.push_close(index)

            else:
                await websocket.send_text(f"Message received: {message}")

    except WebSocketDisconnect:
        print(f"Client disconnected (FID: {fid})")
        if sending_task:
            sending_task.cancel()
        if handle_wallet_task:
            handle_wallet_task.cancel()

