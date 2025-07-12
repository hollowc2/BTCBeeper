import asyncio
import json
import websockets
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
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

# Global manager instance
manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global manager
    manager = BTCConnectionManager()
    asyncio.create_task(manager.start_btc_connection())
    yield
    # Shutdown
    if manager and manager.is_connected:
        await manager.disconnect_all()

app = FastAPI(title="BTC Audio Visualizer", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BTCTradeData(BaseModel):
    price: float
    size: float
    side: str
    timestamp: str
    trade_id: str

class BTCTickerData(BaseModel):
    price: float
    best_bid: float
    best_ask: float
    volume_24h: float
    low_24h: float
    high_24h: float
    timestamp: str

class BTCOrderBookData(BaseModel):
    bids: List[List[str]]  # [price, size]
    asks: List[List[str]]  # [price, size]
    timestamp: str

class BTCOrderBookUpdate(BaseModel):
    side: str  # 'buy' or 'sell'
    price: float
    size: float
    timestamp: str

class BTCConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.coinbase_ws = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.subscribed_channels = set()
        self.btc_order_book = {"bids": {}, "asks": {}}
        self.btc_stats = {
            "total_trades": 0,
            "volume_today": 0.0,
            "last_price": 0.0,
            "price_change_24h": 0.0
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    async def start_btc_connection(self, channels: List[str] = None):
        """Start BTC-only connection to Coinbase"""
        if channels is None:
            channels = ["matches", "ticker", "heartbeat"]  # Removed level2 - requires auth
        
        if self.is_connected:
            return
        
        try:
            uri = "wss://ws-feed.exchange.coinbase.com"
            
            # Create subscription message for BTC-USD only
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],  # Only BTC
                "channels": channels
            }
            
            logger.info(f"Connecting to Coinbase for BTC-USD with channels: {channels}")
            
            async with websockets.connect(uri) as websocket:
                self.coinbase_ws = websocket
                self.is_connected = True
                self.reconnect_attempts = 0
                self.subscribed_channels.update(channels)
                
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to BTC-USD channels: {channels}")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.process_btc_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                    except Exception as e:
                        logger.error(f"Error processing BTC message: {e}")
                        
        except Exception as e:
            logger.error(f"BTC connection error: {e}")
            self.is_connected = False
            self.reconnect_attempts += 1
            if self.reconnect_attempts < self.max_reconnect_attempts:
                await asyncio.sleep(5)
                await self.start_btc_connection(channels)

    async def process_btc_message(self, data: Dict[str, Any]):
        """Process BTC-only messages"""
        msg_type = data.get("type", "unknown")
        
        # Only process BTC-USD messages
        if data.get("product_id") not in ["BTC-USD", None]:
            return
        
        try:
            if msg_type == "subscriptions":
                logger.info(f"BTC subscription confirmed: {data.get('channels', [])}")
                
            elif msg_type == "error":
                logger.error(f"BTC WebSocket error: {data}")
                
            elif msg_type == "heartbeat":
                # Heartbeat for connection health - reduced logging
                await self.broadcast(json.dumps({
                    "type": "btc_heartbeat",
                    "data": {
                        "timestamp": datetime.now().isoformat(),
                        "price": self.btc_stats["last_price"]
                    }
                }))
                
            elif msg_type in ["match", "last_match"]:
                # BTC Trade data
                logger.info(f"Processing BTC trade: {data.get('price', 'N/A')} @ {data.get('size', 'N/A')}")
                
                trade_data = BTCTradeData(
                    price=float(data["price"]),
                    size=float(data["size"]),
                    side=data["side"],
                    timestamp=data.get("time", datetime.now().isoformat()),
                    trade_id=str(data.get("trade_id", int(time.time())))
                )
                
                # Update BTC stats
                self.btc_stats["total_trades"] += 1
                self.btc_stats["volume_today"] += trade_data.size
                self.btc_stats["last_price"] = trade_data.price
                
                logger.info(f"BTC trade processed: ${trade_data.price:.2f}, Total trades: {self.btc_stats['total_trades']}")
                
                await self.broadcast(json.dumps({
                    "type": "btc_trade",
                    "data": trade_data.model_dump()
                }))
                
            elif msg_type == "ticker":
                # BTC Ticker data
                logger.info(f"Processing BTC ticker: {data.get('price', 'N/A')}")
                
                ticker_data = BTCTickerData(
                    price=float(data["price"]),
                    best_bid=float(data["best_bid"]),
                    best_ask=float(data["best_ask"]),
                    volume_24h=float(data["volume_24h"]),
                    low_24h=float(data["low_24h"]),
                    high_24h=float(data["high_24h"]),
                    timestamp=data.get("time", datetime.now().isoformat())
                )
                
                # Update price change
                if self.btc_stats["last_price"] > 0:
                    self.btc_stats["price_change_24h"] = ((ticker_data.price - ticker_data.low_24h) / ticker_data.low_24h) * 100
                
                logger.info(f"BTC ticker processed: ${ticker_data.price:.2f}")
                
                await self.broadcast(json.dumps({
                    "type": "btc_ticker",
                    "data": ticker_data.model_dump()
                }))
                
            elif msg_type == "snapshot":
                # BTC Order book snapshot
                self.btc_order_book = {
                    "bids": {float(bid[0]): float(bid[1]) for bid in data["bids"]},
                    "asks": {float(ask[0]): float(ask[1]) for ask in data["asks"]}
                }
                
                await self.broadcast(json.dumps({
                    "type": "btc_orderbook_snapshot",
                    "data": {
                        "bids": data["bids"][:10],  # Top 10 bids
                        "asks": data["asks"][:10],  # Top 10 asks
                        "timestamp": datetime.now().isoformat()
                    }
                }))
                
            elif msg_type == "l2update":
                # BTC Order book updates
                changes = data.get("changes", [])
                
                for change in changes:
                    side, price, size = change
                    price_float = float(price)
                    size_float = float(size)
                    
                    # Update internal BTC order book
                    if side == "buy":
                        if size_float == 0:
                            self.btc_order_book["bids"].pop(price_float, None)
                        else:
                            self.btc_order_book["bids"][price_float] = size_float
                    else:  # sell
                        if size_float == 0:
                            self.btc_order_book["asks"].pop(price_float, None)
                        else:
                            self.btc_order_book["asks"][price_float] = size_float
                    
                    # Send individual BTC update
                    update = BTCOrderBookUpdate(
                        side=side,
                        price=price_float,
                        size=size_float,
                        timestamp=data.get("time", datetime.now().isoformat())
                    )
                    
                    await self.broadcast(json.dumps({
                        "type": "btc_orderbook_update",
                        "data": update.model_dump()
                    }))
                    
            elif msg_type == "status":
                # BTC Trading status updates
                await self.broadcast(json.dumps({
                    "type": "btc_status",
                    "data": {
                        "status": "active",
                        "timestamp": datetime.now().isoformat()
                    }
                }))
                
        except Exception as e:
            logger.error(f"Error processing BTC {msg_type} message: {e}")

    async def disconnect_all(self):
        """Disconnect all connections"""
        if self.coinbase_ws:
            await self.coinbase_ws.close()
        self.is_connected = False
        self.active_connections.clear()
        """Get current BTC order book statistics"""
        bids = sorted(self.btc_order_book["bids"].items(), reverse=True)
        asks = sorted(self.btc_order_book["asks"].items())
        
        return {
            "spread": asks[0][0] - bids[0][0] if bids and asks else 0,
            "bid_depth": sum(size for _, size in bids[:10]),
            "ask_depth": sum(size for _, size in asks[:10]),
            "total_bids": len(bids),
            "total_asks": len(asks),
            "best_bid": bids[0][0] if bids else 0,
            "best_ask": asks[0][0] if asks else 0
        }

    def get_btc_order_book_stats(self):
        """Get current BTC order book statistics"""
        bids = sorted(self.btc_order_book["bids"].items(), reverse=True)
        asks = sorted(self.btc_order_book["asks"].items())

        return {
            "spread": asks[0][0] - bids[0][0] if bids and asks else 0,
            "bid_depth": sum(size for _, size in bids[:10]),
            "ask_depth": sum(size for _, size in asks[:10]),
            "total_bids": len(bids),
            "total_asks": len(asks),
            "best_bid": bids[0][0] if bids else 0,
            "best_ask": asks[0][0] if asks else 0
        }

    def get_btc_stats(self):
        """Get current BTC trading statistics"""
        return {
            **self.btc_stats,
            "order_book": self.get_btc_order_book_stats()
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channels: Optional[str] = Query(None)):
    """WebSocket endpoint for BTC data with optional channel filtering"""
    await manager.connect(websocket)
    
    # If client wants specific channels, send a filter message
    if channels:
        channel_list = channels.split(",")
        await websocket.send_text(json.dumps({
            "type": "filter_channels",
            "channels": channel_list
        }))
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def root():
    return {"message": "BTC Audio Visualizer API", "focus": "Bitcoin (BTC-USD) only"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "coinbase_connected": manager.is_connected,
        "active_connections": len(manager.active_connections),
        "subscribed_channels": list(manager.subscribed_channels),
        "btc_stats": manager.get_btc_stats()
    }

@app.get("/btc/stats")
async def get_btc_stats():
    """Get comprehensive BTC statistics"""
    return {
        "btc_stats": manager.get_btc_stats(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/btc/orderbook")
async def get_btc_orderbook():
    """Get current BTC order book snapshot"""
    bids = sorted(manager.btc_order_book["bids"].items(), reverse=True)[:10]
    asks = sorted(manager.btc_order_book["asks"].items())[:10]
    
    return {
        "bids": [[str(price), str(size)] for price, size in bids],
        "asks": [[str(price), str(size)] for price, size in asks],
        "stats": manager.get_btc_order_book_stats(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/btc/channels")
async def get_btc_channels():
    """Get list of available BTC channels"""
    return {
        "available_channels": [
            {
                "name": "matches",
                "description": "Real-time BTC trade executions",
                "data_type": "btc_trade"
            },
            {
                "name": "ticker",
                "description": "BTC 24hr rolling window price statistics",
                "data_type": "btc_ticker"
            },
            {
                "name": "heartbeat",
                "description": "BTC connection health pings",
                "data_type": "btc_heartbeat"
            }
        ]
    }

@app.post("/btc/subscribe")
async def subscribe_to_btc_channels(channels: List[str]):
    """Dynamically subscribe to new BTC channels"""
    if manager.is_connected:
        # This would require reconnection with new channels
        return {"message": "Reconnection required for new BTC channels", "requested_channels": channels}
    else:
        asyncio.create_task(manager.start_btc_connection(channels))
        return {"message": "Subscribing to BTC channels", "channels": channels}

@app.get("/btc/price")
async def get_current_btc_price():
    """Get current BTC price"""
    return {
        "price": manager.btc_stats["last_price"],
        "change_24h": manager.btc_stats["price_change_24h"],
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)