from fastapi import FastAPI, WebSocketDisconnect
from game.price_flow import *
from game.wallet import *
import json, random
from utils.auth_utils import decrypt
import uvicorn
from configs.config import WS_ALLOWED_ORIGINS, CORS_ALLOWED_ORIGINS
from storage.firestore_client import FirestoreManager
import time
import uuid
from collections import deque
from configs.config import SECRET
from fastapi.middleware.cors import CORSMiddleware
import requests, threading

SECRET_KEY = SECRET

game_app = FastAPI()

game_app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


debug_ = False 

firestore_manager = FirestoreManager()


def increase_tracker_thread(fid, timeout=10):
    """Synchronous version - simpler for threading"""
    try:
        requests.get(
            f'http://localhost:5009/increase_tracker',
            params={'fid': fid},
            timeout=timeout
        )
    except requests.Timeout:
        print(f"Tracker increase for FID {fid} timed out")
    except Exception as e:
        print(f"Error increasing tracker: {e}")


@game_app.get('/')
async def game_router_status():
    return {'status': 'running'}



@game_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    print(origin)
    if origin not in WS_ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    # Session tracking variables
    trade_actions = []
    trade_env_id = str(uuid.uuid4())
    fid = None
    auth_time = None
    session_timeout = 250
    
    rate_limit_window = deque(maxlen=15)
    rate_limit_duration = 1.0

    def is_rate_limited() -> bool:
        now = time.time()
        while rate_limit_window and rate_limit_window[0] < now - rate_limit_duration:
            rate_limit_window.popleft()
        
        if len(rate_limit_window) >= 15:
            return True
        
        rate_limit_window.append(now)
        return False

    def is_session_expired() -> bool:
        if auth_time is None:
            return False
        return time.time() - auth_time >= session_timeout

    # Authentication phase with proper error handling
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        print(auth_message)
        auth_data = json.loads(auth_message)
        print(auth_data)

        encrypted_token = auth_data.get('encrypted_token')
        if not encrypted_token:
            try:
                await websocket.send_json({"error": "No encrypted_token provided"})
            except Exception:
                pass  # Client already disconnected
            await websocket.close(code=1008)
            return

        # Decrypt and validate the token
        try:
            decrypted_json = decrypt(encrypted_token, SECRET_KEY)
            payload = json.loads(decrypted_json)
            print(payload)

            fid = payload.get('fid')
            print(fid)
            if not fid:
                try:
                    await websocket.send_json({"error": "No fid in token"})
                except Exception:
                    pass
                await websocket.close(code=1008)
                return

            print(f"✅ WebSocket authenticated for FID: {fid}")
            
            resp = await firestore_manager.reduce_energy(str(fid))
            if resp:
                auth_time = time.time()
                #current_gameplay = gameplay_tracker.increment_gameplay(str(fid), amount=2)
                #asyncio.create_task(requests.get('http://localhost:5009/increase_tracker'))
                #asyncio.create_task(increase_tracker(fid))
                thread = threading.Thread(target=increase_tracker_thread, args=(fid,))
                thread.daemon = True
                thread.start()

                try:
                    await websocket.send_json({"authenticated": True, "fid": fid})
                except Exception as e:
                    print(f"Failed to send auth success (client disconnected): {e}")
                    return
            else:
                try:
                    await websocket.send_json({"error": "no energy"})
                except Exception:
                    pass
                await websocket.close(code=1008)
                return

        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            try:
                await websocket.send_json({"error": "Authentication failed"})
            except Exception:
                pass  # Client already disconnected
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
    except WebSocketDisconnect:
        print("❌ Client disconnected during authentication")
        return

    # WebSocket logic
    sending_task = None
    handle_wallet_task = None
    timeout_task = None

    keys = list(spike_df_map.keys())
    random_token = random.choice(keys)
    print(random_token)

    price_flow = PriceFlow(token_selection=random_token)
    futures_wallet = FuturesWallet(leverage=20, token_selection=random_token)

    async def auto_close_after_timeout():
        try:
            await asyncio.sleep(session_timeout)
            print(f"⏰ Session timeout reached for FID: {fid}")
            try:
                await websocket.send_json({
                    "type": "session_timeout",
                    "message": "Session expired after 6 minutes"
                })
                await websocket.close(code=1000, reason="Session timeout")
            except Exception as e:
                print(f"Error closing timed out session: {e}")
        except asyncio.CancelledError:
            print("Timeout task cancelled")

    async def handle_wallet():
        try:
            a = 0
            while True:
                if is_session_expired():
                    print(f"⏰ Session expired for FID: {fid}")
                    break
                    
                if debug_:
                    print(a)
                    print("[x] consume queue")
                await futures_wallet.consume_queue()
                if debug_:
                    print("[x] calculate final balance")
                await futures_wallet.calculate_final_balance(price_flow.current_index)
                if debug_:
                    print("[x] send wallet to websocket")
                
                try:
                    await websocket.send_json({
                        "type": "wallet",
                        "wallet": await futures_wallet.get_wallet_state()
                    })
                except Exception as e:
                    print(f"Failed to send wallet state: {e}")
                    break
                    
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
        timeout_task = asyncio.create_task(auto_close_after_timeout())
        
        while True:
            if is_session_expired():
                print(f"⏰ Session expired during message processing for FID: {fid}")
                break
                
            message = await websocket.receive_text()

            if message == "start":
                if sending_task is None or sending_task.done():
                    futures_wallet = FuturesWallet(leverage=20, token_selection=random_token)
                    sending_task = asyncio.create_task(stream_rows())
                    handle_wallet_task = asyncio.create_task(handle_wallet())

                    await asyncio.sleep(0.01)
                    try:
                        await websocket.send_text("Streaming started.")
                    except Exception:
                        break
                else:
                    try:
                        await websocket.send_text("Already streaming.")
                    except Exception:
                        break

            elif message == "stop":
                if sending_task:
                    sending_task.cancel()
                    handle_wallet_task.cancel()
                    await asyncio.sleep(0.01)
                    try:
                        await websocket.send_text("Streaming stopped.")
                    except Exception:
                        break
                else:
                    try:
                        await websocket.send_text("Nothing is streaming.")
                    except Exception:
                        break

            elif message in ["long", "short", "close"]:
                if is_rate_limited():
                    try:
                        await websocket.send_json({
                            "error": "Rate limit exceeded",
                            "message": "Maximum 15 actions per second"
                        })
                    except Exception:
                        break
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
                try:
                    await websocket.send_text(f"Message received: {message}")
                except Exception:
                    break

    except WebSocketDisconnect:
        print(f"Client disconnected (FID: {fid})")
    except Exception as e:
        print(f"Error in WebSocket loop: {e}")
    finally:
        # Cancel all tasks
        if sending_task:
            sending_task.cancel()
        if handle_wallet_task:
            handle_wallet_task.cancel()
        if timeout_task:
            timeout_task.cancel()
        
        # Save session data to Firestore
        if fid and trade_actions:
            try:
                wallet_state = await futures_wallet.get_wallet_state()
                final_profit = wallet_state.get('balance_total', 0.0)
                if final_profit != 0.0:
                    final_profit = final_profit - 1000
                final_pnl = final_profit/10 
                
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


@game_app.get('/increase_tracker')
def increase_tracker(fid: int):
    resp = requests.get(
        'http://localhost:5009/increase_tracker',
        params={'fid': fid}
    )

    if resp.status_code == 200:
        return {'status': 'success'}
    return {'status': 'failed'}


@game_app.get('/get_tracker')
def get_tracker():
    resp = requests.get('http://localhost:5009/get_tracker')
    return resp.json()


from fastapi.responses import HTMLResponse

from fastapi.responses import HTMLResponse

@game_app.get('/transactions', response_class=HTMLResponse)
async def get_transactions_page():
    """Serve the transactions visualization page"""
    
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transaction Data</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 30px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 18px;
            color: #667eea;
        }
        
        .error {
            background: #fee;
            border: 1px solid #fcc;
            color: #c33;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }
        
        .view-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .chart-section {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .chart-title {
            font-size: 20px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .chart-container {
            position: relative;
            height: 400px;
        }
        
        .selected-date-info {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            text-align: center;
            font-weight: 600;
            display: none;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-size: 28px;
            font-weight: bold;
        }

        @media (max-width: 768px) {
            .view-container {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Transaction Data Dashboard</h1>
        <p class="subtitle">View gameplay transactions per date and FID distribution</p>
        
        <button class="refresh-btn" onclick="fetchData()">🔄 Refresh Data</button>
        
        <div id="content">
            <div class="loading">Loading data...</div>
        </div>
    </div>

    <script>
        let dateChart, fidChart;
        let allData = {};
        let dataByDate = {};
        
        async function fetchData() {
            const content = document.getElementById('content');
            content.innerHTML = '<div class="loading">Loading data...</div>';
            
            try {
                // Fetch from the same domain's get_tracker endpoint
                const response = await fetch('/get_tracker');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                allData = await response.json();
                
                if (!allData || Object.keys(allData).length === 0) {
                    content.innerHTML = `
                        <div class="error">
                            <p>No transaction data available yet.</p>
                            <p style="margin-top: 10px; font-size: 14px;">Data will appear here after gameplay sessions.</p>
                        </div>
                    `;
                    return;
                }
                
                content.innerHTML = `
                    <div class="view-container">
                        <div class="chart-section">
                            <div class="chart-title">📅 Total Transactions per Date</div>
                            <div style="text-align: center; margin-bottom: 15px;">
                                <label for="dateSelector" style="font-weight: 600; color: #333; margin-right: 10px;">Select Date:</label>
                                <select id="dateSelector" onchange="onDateSelected()" style="padding: 8px 15px; border: 2px solid #667eea; border-radius: 6px; font-size: 14px; cursor: pointer; background: white;">
                                    <option value="">Choose a date...</option>
                                </select>
                            </div>
                            <div class="chart-container">
                                <canvas id="dateChart"></canvas>
                            </div>
                        </div>
                        
                        <div class="chart-section">
                            <div class="selected-date-info" id="selectedDateInfo">
                                Selected Date: <span id="selectedDateText"></span>
                            </div>
                            <div class="chart-title">🔢 FID Distribution</div>
                            <div class="chart-container">
                                <canvas id="fidChart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <div class="stats-grid" id="statsGrid"></div>
                `;
                
                loadData();
                
            } catch (error) {
                console.error('Error fetching data:', error);
                content.innerHTML = `
                    <div class="error">
                        <p>❌ Failed to load data from API</p>
                        <p style="margin-top: 10px; font-size: 14px;">Error: ${error.message}</p>
                        <p style="margin-top: 10px; font-size: 14px;">Please try refreshing the page.</p>
                    </div>
                `;
            }
        }
        
        function loadData() {
            // Group data by date
            dataByDate = {};
            Object.keys(allData).forEach(fid => {
                const date = allData[fid].date;
                const count = allData[fid].count;
                
                if (!dataByDate[date]) {
                    dataByDate[date] = {
                        total: 0,
                        fids: {}
                    };
                }
                
                dataByDate[date].total += count;
                dataByDate[date].fids[fid] = count;
            });
            
            visualizeDateChart();
            updateStats();
        }
        
        function visualizeDateChart() {
            const dates = Object.keys(dataByDate).sort();
            const totals = dates.map(date => dataByDate[date].total);
            
            // Populate date selector
            const dateSelector = document.getElementById('dateSelector');
            dateSelector.innerHTML = '<option value="">Choose a date...</option>';
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                dateSelector.appendChild(option);
            });
            
            if (dateChart) dateChart.destroy();
            
            const ctx = document.getElementById('dateChart').getContext('2d');
            dateChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: dates,
                    datasets: [{
                        label: 'Total Transactions',
                        data: totals,
                        backgroundColor: 'rgba(102, 126, 234, 0.8)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2,
                        borderRadius: 8,
                        hoverBackgroundColor: 'rgba(118, 75, 162, 0.9)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const selectedDate = dates[index];
                            const dateSelector = document.getElementById('dateSelector');
                            dateSelector.value = selectedDate;
                            visualizeFidChart(selectedDate);
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Total: ' + context.parsed.y + ' transactions';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        },
                        x: {
                            ticks: {
                                font: {
                                    weight: 'bold'
                                }
                            }
                        }
                    }
                }
            });
            
            // Show first date by default
            if (dates.length > 0) {
                const dateSelector = document.getElementById('dateSelector');
                dateSelector.value = dates[0];
                visualizeFidChart(dates[0]);
            }
        }
        
        function onDateSelected() {
            const dateSelector = document.getElementById('dateSelector');
            const selectedDate = dateSelector.value;
            if (selectedDate) {
                visualizeFidChart(selectedDate);
            }
        }
        
        function visualizeFidChart(selectedDate) {
            const fids = Object.keys(dataByDate[selectedDate].fids);
            const counts = fids.map(fid => dataByDate[selectedDate].fids[fid]);
            
            document.getElementById('selectedDateInfo').style.display = 'block';
            document.getElementById('selectedDateText').textContent = selectedDate;
            
            if (fidChart) fidChart.destroy();
            
            const ctx = document.getElementById('fidChart').getContext('2d');
            const colors = generateColors(fids.length);
            
            fidChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: fids.map(fid => `FID ${fid}`),
                    datasets: [{
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 15,
                                padding: 10,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
        
        function updateStats() {
            const totalFids = Object.keys(allData).length;
            const totalDates = Object.keys(dataByDate).length;
            const totalTransactions = Object.values(allData).reduce((sum, item) => sum + item.count, 0);
            const avgPerDate = totalDates > 0 ? (totalTransactions / totalDates).toFixed(2) : 0;
            
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Total FIDs</div>
                    <div class="stat-value">${totalFids}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Dates</div>
                    <div class="stat-value">${totalDates}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Transactions</div>
                    <div class="stat-value">${totalTransactions}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Avg per Date</div>
                    <div class="stat-value">${avgPerDate}</div>
                </div>
            `;
        }
        
        function generateColors(count) {
            const colors = [];
            for (let i = 0; i < count; i++) {
                const hue = (i * 360 / count) % 360;
                colors.push(`hsla(${hue}, 70%, 60%, 0.8)`);
            }
            return colors;
        }
        
        // Initial load
        fetchData();
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run(
        "game_main:game_app",
        port=5010,
        reload=False
    )
