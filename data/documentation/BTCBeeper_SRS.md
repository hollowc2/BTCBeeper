# 📄 Software Requirements Specification (SRS)  
## BTC Live Tape Audio Visualizer

---

## **1. Introduction**

### 1.1 Purpose
Develop a real-time web application that streams live BTC/USD trades (tape) from Coinbase, displays price and trade stats on a Svelte frontend, and uses browser-generated audio to reflect trading activity.

### 1.2 Scope
- Connect to Coinbase Advanced Trade WebSocket API to get real-time BTC-USD trade data.
- Python backend built with FastAPI:
  - Broadcast trade data to frontend via WebSocket.
- Svelte frontend:
  - Display current BTC price and trade stats.
  - Use Web Audio API to generate dynamic sound based on trade activity.
- Focus on BTC/USD.
- Real-time only; no historical storage.
- Deployable to a VPS.

### 1.3 Intended Audience
- Developer(s)
- Users interested in live BTC price + audio visualization.

### 1.4 Definitions
| Term        | Definition |
|------------|------------|
| Tape       | Stream of executed trades. |
| FastAPI    | Modern Python web framework for APIs & WebSockets. |
| Svelte     | Modern frontend framework to build reactive UIs. |
| Web Audio API | JavaScript API to generate audio in the browser. |

---

## **2. Overall Description**

### 2.1 Product Perspective
A web app built from:
- FastAPI backend (Python):
  - Connects to Coinbase, processes live trades, and pushes them to frontend.
- Svelte frontend:
  - Receives trade data via WebSocket.
  - Displays live BTC price and rolling stats.
  - Generates audio that adapts to trade activity.

### 2.2 Product Functions
- Subscribe to real-time BTC trades.
- Push trades to frontend.
- Frontend shows:
  - Current BTC price.
  - Trades per second, average trade size.
- Frontend plays audio that changes with market speed/volume.

### 2.3 User Characteristics
- Crypto traders / enthusiasts.
- Users with modern browsers supporting Web Audio API.

### 2.4 Constraints
- Real-time performance is important.
- Audio generation must happen in browser.
- Single pair (BTC/USD).
- Initially local, but should be easy to deploy to a VPS.

### 2.5 Assumptions & Dependencies
- Coinbase Advanced Trade API is stable.
- Users have modern browsers.
- VPS has Python and Node.js for deployment.

---

## **3. Functional Requirements**

### 3.1 Data Collection
- Python backend connects to Coinbase Advanced Trade WebSocket.
- Subscribe to `matches` channel for BTC-USD.
- Parse and validate each trade message.

### 3.2 Backend API
- FastAPI WebSocket
