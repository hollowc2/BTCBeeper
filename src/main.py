import asyncio
import json
import websockets
import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import hmac
import hashlib
import time
import base64

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BTC Live Tape Audio Visualizer")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TradeData(BaseModel):
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    timestamp: str
    trade_id: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.coinbase_ws = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    def create_signature(self, timestamp: str, method: str, path: str, body: str = ""):
        """Create signature for Coinbase Advanced Trade API"""
        api_secret = os.getenv("COINBASE_API_SECRET")
        if not api_secret:
            raise ValueError("COINBASE_API_SECRET not found in environment variables")
        
        message = timestamp + method + path + body
        signature = hmac.new(
            base64.b64decode(api_secret),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    async def start_coinbase_connection(self):
        """Start connection to Coinbase Advanced Trade WebSocket"""
        if self.is_connected:
            return
        
        try:
            # Check if API credentials are available
            api_key = os.getenv("COINBASE_API_KEY")
            api_secret = os.getenv("COINBASE_API_SECRET")
            
            if not api_key or not api_secret:
                logger.error("Missing Coinbase API credentials in environment variables")
                return
            
            # Try public feed first (no authentication required)
            await self.connect_public_feed()
            
        except Exception as e:
            logger.error(f"Failed to start Coinbase connection: {e}")
            self.reconnect_attempts += 1
            if self.reconnect_attempts < self.max_reconnect_attempts:
                logger.info(f"Retrying connection in 5 seconds... (Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
                await asyncio.sleep(5)
                await self.start_coinbase_connection()
            else:
                logger.error("Max reconnection attempts reached. Stopping reconnection attempts.")

    async def connect_public_feed(self):
        """Connect to Coinbase public WebSocket feed (no authentication required)"""
        try:
            # Use the public WebSocket feed which doesn't require authentication
            uri = "wss://ws-feed.exchange.coinbase.com"
            
            # Subscribe to ticker channel for BTC-USD
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channels": ["matches"]
            }
            
            logger.info("Connecting to Coinbase public WebSocket feed...")
            
            async with websockets.connect(uri) as websocket:
                self.coinbase_ws = websocket
                self.is_connected = True
                self.reconnect_attempts = 0
                
                # Send subscription message
                await websocket.send(json.dumps(subscribe_message))
                logger.info("Subscribed to BTC-USD matches channel (public feed)")
                
                # Listen for messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.process_coinbase_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message: {message}, Error: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Public feed connection error: {e}")
            self.is_connected = False
            raise

    async def connect_authenticated_feed(self):
        """Connect to Coinbase Advanced Trade WebSocket with authentication"""
        try:
            # Advanced Trade WebSocket URL
            uri = "wss://advanced-trade-ws.coinbase.com"
            
            # Load API credentials
            api_key = os.getenv("COINBASE_API_KEY")
            api_secret = os.getenv("COINBASE_API_SECRET")
            
            if not api_key or not api_secret:
                raise ValueError("Missing API credentials")
            
            # Generate timestamp
            timestamp = str(int(time.time()))
            
            # Create signature for WebSocket authentication
            method = "GET"
            path = "/users/self/verify"
            signature = self.create_signature(timestamp, method, path)
            
            # Create subscription message with authentication
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channels": ["matches"],
                "signature": signature,
                "key": api_key,
                "timestamp": timestamp,
                "passphrase": os.getenv("COINBASE_API_PASSPHRASE", "")
            }
            
            logger.info("Connecting to Coinbase Advanced Trade WebSocket...")
            
            async with websockets.connect(uri) as websocket:
                self.coinbase_ws = websocket
                self.is_connected = True
                self.reconnect_attempts = 0
                
                # Send subscription message
                await websocket.send(json.dumps(subscribe_message))
                logger.info("Subscribed to BTC-USD matches channel (authenticated)")
                
                # Listen for messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.process_coinbase_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message: {message}, Error: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        
        except Exception as e:
            logger.error(f"Authenticated connection error: {e}")
            self.is_connected = False
            raise

    async def process_coinbase_message(self, data: Dict):
        """Process incoming messages from Coinbase WebSocket"""
        # Log all message types for debugging
        msg_type = data.get("type", "unknown")
        logger.info(f"Received message type: {msg_type}")
        
        try:
            # Handle different message types
            if msg_type == "subscriptions":
                logger.info("Subscription confirmed")
                return
            elif msg_type == "error":
                logger.error(f"Coinbase WebSocket error: {data}")
                return
            elif msg_type in ["match", "last_match"]:
                # Process trade data
                trade_data = TradeData(
                    price=float(data["price"]),
                    size=float(data["size"]),
                    side=data["side"],
                    timestamp=data.get("time", datetime.now().isoformat()),
                    trade_id=str(data.get("trade_id", int(time.time())))
                )
                
                # Broadcast to all connected clients
                message = {
                    "type": "trade",
                    "data": trade_data.dict()
                }
                
                await self.broadcast(json.dumps(message))
                logger.info(f"Trade: {trade_data.side} {trade_data.size} BTC at ${trade_data.price}")
            else:
                logger.debug(f"Unhandled message type: {msg_type}, data: {data}")
                
        except KeyError as e:
            logger.error(f"Missing required field in trade data: {e}, data: {data}")
        except ValueError as e:
            logger.error(f"Invalid data format: {e}, data: {data}")
        except Exception as e:
            logger.error(f"Error processing trade data: {e}, data: {data}")

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """Start Coinbase connection on startup"""
    asyncio.create_task(manager.start_coinbase_connection())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "BTC Live Tape Audio Visualizer API"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "coinbase_connected": manager.is_connected,
        "active_connections": len(manager.active_connections),
        "reconnect_attempts": manager.reconnect_attempts
    }

@app.get("/debug")
async def debug_info():
    """Debug endpoint to check API credentials and connection status"""
    return {
        "api_key_configured": bool(os.getenv("COINBASE_API_KEY")),
        "api_secret_configured": bool(os.getenv("COINBASE_API_SECRET")),
        "connection_status": manager.is_connected,
        "reconnect_attempts": manager.reconnect_attempts
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)