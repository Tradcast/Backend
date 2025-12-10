from fastapi import FastAPI, WebSocketDisconnect
from game.price_flow import *
from game.wallet import *
import json, random
from utils.auth_utils import decrypt, SECRET_KEY
import uvicorn
from configs.config import WS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGINS
from storage.firestore_client import FirestoreManager
import time
import uuid
from collections import deque

game_app = FastAPI()
debug_ = False 

firestore_manager = FirestoreManager()

@game_app.get('/')
async def game_router_status():
    return {'status': 'running'}


@game_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")

    if origin not in WS_ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    # Session tracking variables
    trade_actions = []  # Store all trade actions
    trade_env_id = str(uuid.uuid4())  # Unique session ID
    fid = None
    
    # Rate limiting: 15 messages per second
    rate_limit_window = deque(maxlen=15)
    rate_limit_duration = 1.0  # 1 second

    def is_rate_limited() -> bool:
        """Check if rate limit is exceeded"""
        now = time.time()
        # Remove timestamps older than 1 second
        while rate_limit_window and rate_limit_window[0] < now - rate_limit_duration:
            rate_limit_window.popleft()
        
        if len(rate_limit_window) >= 15:
            return True
        
        rate_limit_window.append(now)
        return False

    # Wait for authentication message first
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_data = json.loads(auth_message)
        print(auth_data)

        encrypted_token = auth_data.get('encrypted_token')
        if not encrypted_token:
            await websocket.send_json({"error": "No encrypted_token provided"})
            await websocket.close(code=1008)
            return

        # Decrypt and validate the token
        try:
            decrypted_json = decrypt(encrypted_token, SECRET_KEY)
            payload = json.loads(decrypted_json)
            print(payload)

            # Extract FID for later use
            fid = payload.get('fid')
            print(fid)
            if not fid:
                await websocket.send_json({"error": "No fid in token"})
                await websocket.close(code=1008)
                return

            print(f"✅ WebSocket authenticated for FID: {fid}")
            
            resp = await firestore_manager.reduce_energy(str(fid))
            if resp:
                await websocket.send_json({"authenticated": True, "fid": fid})
            else:
                await websocket.send_json({"error": "no energy"})
                await websocket.close(code=1008)
                return

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
            print("stream was cancelled handle_wallet")

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
            print("Stream was cancelled stream_rows")
            raise
        except Exception as e:
            print(f"Error in stream_rows: {e}")
            raise

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

            # Wallet commands with rate limiting
            elif message in ["long", "short", "close"]:
                if is_rate_limited():
                    await websocket.send_json({
                        "error": "Rate limit exceeded",
                        "message": "Maximum 15 actions per second"
                    })
                    continue

                index = price_flow.current_index
                current_time = time.time()
                
                if message == "long":
                    if debug_:
                        print("long")
                    await futures_wallet.push_order_long(index)
                    trade_actions.append({
                        "action": "long",
                        "time": current_time,
                        "index": index
                    })

                elif message == "short":
                    if debug_:
                        print("short")
                    await futures_wallet.push_order_short(index)
                    trade_actions.append({
                        "action": "short",
                        "time": current_time,
                        "index": index
                    })

                elif message == "close":
                    if debug_:
                        print("close")
                    await futures_wallet.push_close(index)
                    trade_actions.append({
                        "action": "close",
                        "time": current_time,
                        "index": index
                    })

            else:
                await websocket.send_text(f"Message received: {message}")

    except WebSocketDisconnect:
        print(f"Client disconnected (FID: {fid})")
        if sending_task:
            sending_task.cancel()
        if handle_wallet_task:
            handle_wallet_task.cancel()
        
        # Save session data to Firestore
        if fid and trade_actions:
            try:
                # Get final wallet state
                wallet_state = await futures_wallet.get_wallet_state()
                #final_pnl = wallet_state.get('total_pnl', 0.0)
                final_profit = wallet_state.get('balance_total', 0.0)
                if final_profit != 0.0:
                    final_profit = final_profit - 1000
                final_pnl = final_profit/10 
                # Save everything to Firestore
                print(f"💾 Saving session {trade_env_id} with {len(trade_actions)} actions")
                success = await firestore_manager.save_game_session_result(
                    fid=str(fid),
                    trade_env_id=trade_env_id,
                    actions=trade_actions,
                    final_pnl=final_pnl,
                    final_profit=final_profit
                )
                
                if success:
                    print(f"✅ Session saved successfully for FID: {fid}")
                else:
                    print(f"❌ Failed to save session for FID: {fid}")
                    
            except Exception as e:
                print(f"❌ Error saving session on disconnect: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "game_main:game_app",
        port=5010,
    )


