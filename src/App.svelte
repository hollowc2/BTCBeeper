<script>
  import { onMount, onDestroy } from 'svelte';
  
  // WebSocket connection
  let ws;
  let isConnected = false;
  
  // Trade data
  let currentPrice = 0;
  let lastPrice = 0;
  let trades = [];
  let tradeCount = 0;
  let totalVolume = 0;
  let avgTradeSize = 0;
  let tradesPerSecond = 0;
  let largestTrade = null;
  
  // New ticker data
  let tickerData = {
    bestBid: 0,
    bestAsk: 0,
    volume24h: 0,
    low24h: 0,
    high24h: 0,
    spread: 0
  };
  
  // Order book data
  let orderBook = {
    bids: [],
    asks: [],
    spread: 0,
    bidDepth: 0,
    askDepth: 0
  };
  
  // Connection health
  let lastHeartbeat = null;
  let connectionHealth = 'unknown';
  
  // UI state
  let priceDirection = 'neutral'; // 'up', 'down', 'neutral'
  let volumeIntensity = 0;
  let audioEnabled = false;
  let activeChannels = ['matches', 'ticker', 'level2', 'heartbeat'];
  
  // Rolling window for TPS calculation
  let tradeTimestamps = [];
  const TPS_WINDOW = 10; // seconds
  
  let clickSound = null;

  onMount(() => {
    connectWebSocket();
    // Preload the click sound
    clickSound = new Audio('/geiger_click.wav');
    clickSound.load();
  });
  
  onDestroy(() => {
    if (ws) {
      ws.close();
    }
  });
  
  function connectWebSocket() {
    try {
      // Connect with channel filtering for multi-channel support
      const channelParam = activeChannels.join(',');
      ws = new WebSocket(`ws://localhost:8000/ws?channels=${channelParam}`);
      
      ws.onopen = () => {
        isConnected = true;
        connectionHealth = 'healthy';
        console.log('Connected to WebSocket with channels:', activeChannels);
      };
      
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        // Only process BTC data
        if (message.product_id && message.product_id !== 'BTC-USD') {
          return;
        }
        
        switch (message.type) {
          case 'btc_trade':
            processTrade(message.data);
            break;
          case 'btc_ticker':
            processTicker(message.data);
            break;
          case 'btc_orderbook_snapshot':
            processOrderBookSnapshot(message.data);
            break;
          case 'btc_orderbook_update':
            processOrderBookUpdate(message.data);
            break;
          case 'btc_heartbeat':
            processHeartbeat(message.data);
            break;
          case 'btc_status':
            processStatus(message.data);
            break;
          case 'filter_channels':
            console.log('Channel filter applied:', message.channels);
            break;
        }
      };
      
      ws.onclose = () => {
        isConnected = false;
        connectionHealth = 'disconnected';
        console.log('WebSocket connection closed');
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        connectionHealth = 'error';
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      connectionHealth = 'error';
    }
  }
  
  function processTrade(trade) {
    const now = Date.now();
    
    // Update price data
    lastPrice = currentPrice;
    currentPrice = trade.price;
    
    // Determine price direction
    if (currentPrice > lastPrice) {
      priceDirection = 'up';
    } else if (currentPrice < lastPrice) {
      priceDirection = 'down';
    } else {
      priceDirection = 'neutral';
    }
    
    // Add to trades array (keep last 100 trades)
    trades = [trade, ...trades.slice(0, 99)];
    
    // Update statistics
    tradeCount++;
    totalVolume += trade.size;
    avgTradeSize = totalVolume / tradeCount;
    
    // Calculate trades per second
    tradeTimestamps.unshift(now);
    tradeTimestamps = tradeTimestamps.filter(ts => now - ts <= TPS_WINDOW * 1000);
    tradesPerSecond = tradeTimestamps.length / TPS_WINDOW;
    
    // Update volume intensity (0-1 scale)
    volumeIntensity = Math.min(trade.size / 10, 1); // Normalize to 10 BTC max
    
    // Play the click sound if audio is enabled
    if (audioEnabled && clickSound) {
      clickSound.currentTime = 0;
      clickSound.play();
    }
    
    // Track largest trade
    if (!largestTrade || trade.size > largestTrade.size) {
      largestTrade = { ...trade };
    }
  }
  
  function processTicker(ticker) {
    tickerData = {
      bestBid: ticker.best_bid,
      bestAsk: ticker.best_ask,
      volume24h: ticker.volume_24h,
      low24h: ticker.low_24h,
      high24h: ticker.high_24h,
      spread: ticker.best_ask - ticker.best_bid
    };
    
    // Update current price from ticker if no recent trades
    if (!currentPrice || Math.abs(currentPrice - ticker.price) > 0.01) {
      currentPrice = ticker.price;
    }
  }
  
  function processOrderBookSnapshot(snapshot) {
    orderBook.bids = snapshot.bids.slice(0, 10);
    orderBook.asks = snapshot.asks.slice(0, 10);
    updateOrderBookStats();
  }
  
  function processOrderBookUpdate(update) {
    // This is a simplified update - in production you'd want to maintain the full order book
    // For now, we'll just track the stats from the backend
    updateOrderBookStats();
  }
  
  function updateOrderBookStats() {
    if (orderBook.bids.length > 0 && orderBook.asks.length > 0) {
      const topBid = parseFloat(orderBook.bids[0][0]);
      const topAsk = parseFloat(orderBook.asks[0][0]);
      orderBook.spread = topAsk - topBid;
      
      // Calculate depth (total volume in top 10 levels)
      orderBook.bidDepth = orderBook.bids.reduce((sum, [price, size]) => sum + parseFloat(size), 0);
      orderBook.askDepth = orderBook.asks.reduce((sum, [price, size]) => sum + parseFloat(size), 0);
    }
  }
  
  function processHeartbeat(heartbeat) {
    lastHeartbeat = new Date(heartbeat.timestamp);
    connectionHealth = 'healthy';
  }
  
  function processStatus(status) {
    console.log('Status update:', status);
  }
  
  function toggleAudio() {
    audioEnabled = !audioEnabled;
  }
  
  function formatPrice(price) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(price);
  }
  
  function formatSize(size) {
    return size.toFixed(6);
  }
  
  function formatVolume(volume) {
    if (volume >= 1000000) {
      return (volume / 1000000).toFixed(2) + 'M';
    } else if (volume >= 1000) {
      return (volume / 1000).toFixed(2) + 'K';
    }
    return volume.toFixed(2);
  }
  
  function formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString();
  }
  
  function getConnectionStatus() {
    if (!isConnected) return 'disconnected';
    if (lastHeartbeat && (Date.now() - lastHeartbeat.getTime()) > 30000) {
      return 'stale';
    }
    return connectionHealth;
  }
</script>

<main>
  <div class="container">
    <header>
      <h1>🎵 BTC Live Multi-Channel Audio Visualizer</h1>
      <div class="connection-status">
        <span class="status-indicator {getConnectionStatus()}"></span>
        <span class="status-text">
          {#if isConnected}
            Connected ({getConnectionStatus()})
          {:else}
            Disconnected
          {/if}
        </span>
        {#if lastHeartbeat}
          <span class="heartbeat-time">
            Last heartbeat: {formatTime(lastHeartbeat)}
          </span>
        {/if}
      </div>
    </header>
    
    <div class="controls">
      <button class="audio-toggle {audioEnabled ? 'enabled' : 'disabled'}" on:click={toggleAudio}>
        {audioEnabled ? '🔊 Audio On' : '🔇 Audio Off'}
      </button>
    </div>

    <div class="price-section">
      <div class="current-price {priceDirection}">
        <div class="price-label">BTC/USD</div>
        <div class="price-value">{formatPrice(currentPrice)}</div>
        <div class="price-change">
          {#if priceDirection === 'up'}
            ↗️ UP
          {:else if priceDirection === 'down'}
            ↘️ DOWN
          {:else}
            ➡️ FLAT
          {/if}
        </div>
      </div>
    </div>

    <!-- Enhanced Stats Grid -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Trades/Second</div>
        <div class="stat-value">{tradesPerSecond.toFixed(2)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Trades</div>
        <div class="stat-value">{tradeCount}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Trade Size</div>
        <div class="stat-value">{formatSize(avgTradeSize)} BTC</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">24h Volume</div>
        <div class="stat-value">{formatVolume(tickerData.volume24h)} BTC</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">24h High</div>
        <div class="stat-value">{formatPrice(tickerData.high24h)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">24h Low</div>
        <div class="stat-value">{formatPrice(tickerData.low24h)}</div>
      </div>
      {#if largestTrade}
      <div class="stat-card largest-trade-card {largestTrade.side}">
        <div class="stat-label">Largest Trade</div>
        <div class="stat-value">{formatSize(largestTrade.size)} BTC</div>
        <div class="stat-details">
          <span class="trade-side">{largestTrade.side.toUpperCase()}</span>
          <span class="trade-price">{formatPrice(largestTrade.price)}</span>
          <span class="trade-time">{formatTime(largestTrade.timestamp)}</span>
        </div>
      </div>
      {/if}
    </div>

    <!-- Order Book Section -->
    <div class="orderbook-section">
      <h2>Order Book</h2>
      <div class="orderbook-stats">
        <div class="stat-card">
          <div class="stat-label">Spread</div>
          <div class="stat-value">{formatPrice(tickerData.spread)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Best Bid</div>
          <div class="stat-value">{formatPrice(tickerData.bestBid)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Best Ask</div>
          <div class="stat-value">{formatPrice(tickerData.bestAsk)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Bid Depth</div>
          <div class="stat-value">{formatSize(orderBook.bidDepth)} BTC</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Ask Depth</div>
          <div class="stat-value">{formatSize(orderBook.askDepth)} BTC</div>
        </div>
      </div>
      
      <div class="orderbook-display">
        <div class="orderbook-side">
          <h3>Bids</h3>
          <div class="orderbook-orders">
            {#each orderBook.bids as [price, size]}
              <div class="order-row bid">
                <span class="order-price">{formatPrice(parseFloat(price))}</span>
                <span class="order-size">{formatSize(parseFloat(size))}</span>
              </div>
            {/each}
          </div>
        </div>
        
        <div class="orderbook-side">
          <h3>Asks</h3>
          <div class="orderbook-orders">
            {#each orderBook.asks as [price, size]}
              <div class="order-row ask">
                <span class="order-price">{formatPrice(parseFloat(price))}</span>
                <span class="order-size">{formatSize(parseFloat(size))}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    </div>
    
    <div class="trades-section">
      <h2>Recent Trades</h2>
      <div class="trades-list">
        {#each trades.slice(0, 10) as trade}
          <div class="trade-item {trade.side}">
            <span class="trade-side">{trade.side.toUpperCase()}</span>
            <span class="trade-size">{formatSize(trade.size)} BTC</span>
            <span class="trade-price">{formatPrice(trade.price)}</span>
            <span class="trade-time">{formatTime(trade.timestamp)}</span>
          </div>
        {/each}
      </div>
    </div>
    
    <div class="visualizer">
      <div class="volume-bar">
        <div class="volume-fill" style="width: {volumeIntensity * 100}%"></div>
        <div class="volume-label">Volume Intensity</div>
      </div>
      <div class="pulse-indicator {audioEnabled ? 'active' : ''}"></div>
    </div>
  </div>
</main>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: white;
    min-height: 100vh;
  }
  
  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
  }
  
  header {
    text-align: center;
    margin-bottom: 30px;
  }
  
  h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
  }
  
  .connection-status {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 1.1em;
    flex-wrap: wrap;
  }
  
  .status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #ff4444;
    transition: background 0.3s;
  }
  
  .status-indicator.healthy {
    background: #44ff44;
    box-shadow: 0 0 10px rgba(68, 255, 68, 0.5);
  }
  
  .status-indicator.stale {
    background: #ffaa44;
    box-shadow: 0 0 10px rgba(255, 170, 68, 0.5);
  }
  
  .status-indicator.disconnected,
  .status-indicator.error {
    background: #ff4444;
    box-shadow: 0 0 10px rgba(255, 68, 68, 0.5);
  }
  
  .heartbeat-time {
    font-size: 0.9em;
    opacity: 0.7;
  }
  
  .controls {
    text-align: center;
    margin-bottom: 30px;
  }
  
  .audio-toggle {
    padding: 15px 30px;
    font-size: 1.2em;
    border: none;
    border-radius: 25px;
    cursor: pointer;
    transition: all 0.3s;
    font-weight: bold;
  }
  
  .audio-toggle.enabled {
    background: #44ff44;
    color: #000;
    box-shadow: 0 4px 15px rgba(68, 255, 68, 0.3);
  }
  
  .audio-toggle.disabled {
    background: #666;
    color: #fff;
  }
  
  .price-section {
    text-align: center;
    margin-bottom: 30px;
  }
  
  .current-price {
    display: inline-block;
    padding: 30px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 15px;
    backdrop-filter: blur(10px);
    transition: all 0.3s;
  }
  
  .current-price.up {
    border-left: 5px solid #44ff44;
    box-shadow: 0 0 20px rgba(68, 255, 68, 0.3);
  }
  
  .current-price.down {
    border-left: 5px solid #ff4444;
    box-shadow: 0 0 20px rgba(255, 68, 68, 0.3);
  }
  
  .price-label {
    font-size: 1.2em;
    opacity: 0.8;
    margin-bottom: 10px;
  }
  
  .price-value {
    font-size: 3em;
    font-weight: bold;
    margin-bottom: 10px;
  }
  
  .price-change {
    font-size: 1.1em;
    font-weight: bold;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    margin-bottom: 30px;
  }
  
  .stat-card {
    background: rgba(255, 255, 255, 0.1);
    padding: 15px;
    border-radius: 10px;
    text-align: center;
    backdrop-filter: blur(5px);
  }
  
  .stat-label {
    font-size: 0.9em;
    opacity: 0.8;
    margin-bottom: 5px;
  }
  
  .stat-value {
    font-size: 1.3em;
    font-weight: bold;
  }
  
  .orderbook-section {
    margin-bottom: 30px;
  }
  
  .orderbook-section h2 {
    text-align: center;
    margin-bottom: 20px;
  }
  
  .orderbook-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
    margin-bottom: 20px;
  }
  
  .orderbook-display {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
    padding: 20px;
  }
  
  .orderbook-side h3 {
    margin-bottom: 10px;
    text-align: center;
  }
  
  .orderbook-orders {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  
  .order-row {
    display: flex;
    justify-content: space-between;
    padding: 5px 10px;
    border-radius: 3px;
    font-size: 0.9em;
  }
  
  .order-row.bid {
    background: rgba(68, 255, 68, 0.1);
  }
  
  .order-row.ask {
    background: rgba(255, 68, 68, 0.1);
  }
  
  .trades-section {
    margin-bottom: 30px;
  }
  
  .trades-section h2 {
    margin-bottom: 15px;
    text-align: center;
  }
  
  .trades-list {
    max-height: 300px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 10px;
    padding: 10px;
  }
  
  .trade-item {
    display: grid;
    grid-template-columns: 60px 120px 120px 100px;
    gap: 10px;
    padding: 10px;
    margin-bottom: 5px;
    border-radius: 5px;
    font-size: 0.9em;
    align-items: center;
  }
  
  .trade-item.buy {
    background: rgba(68, 255, 68, 0.1);
    border-left: 3px solid #44ff44;
  }
  
  .trade-item.sell {
    background: rgba(255, 68, 68, 0.1);
    border-left: 3px solid #ff4444;
  }
  
  .trade-side {
    font-weight: bold;
  }
  
  .visualizer {
    text-align: center;
    margin-top: 30px;
  }
  
  .volume-bar {
    position: relative;
    width: 100%;
    height: 25px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 20px;
  }
  
  .volume-fill {
    height: 100%;
    background: linear-gradient(90deg, #44ff44, #ffff44, #ff4444);
    transition: width 0.3s;
  }
  
  .volume-label {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 0.9em;
    font-weight: bold;
    color: white;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
  }
  
  .pulse-indicator {
    width: 50px;
    height: 50px;
    background: #666;
    border-radius: 50%;
    margin: 0 auto;
    transition: all 0.3s;
  }
  
  .pulse-indicator.active {
    background: #44ff44;
    box-shadow: 0 0 20px rgba(68, 255, 68, 0.5);
    animation: pulse 2s infinite;
  }
  
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
  }
  
  .largest-trade-card {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    padding: 12px 16px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    min-width: 180px;
    max-width: 220px;
    margin: 0 auto;
  }
  
  .largest-trade-card.buy {
    border-left: 4px solid #44ff44;
  }
  
  .largest-trade-card.sell {
    border-left: 4px solid #ff4444;
  }
  
  .largest-trade-card .stat-details {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.95em;
    margin-top: 6px;
  }
  
  .largest-trade-card .trade-side {
    font-weight: bold;
  }
  
  @media (max-width: 768px) {
    .price-value {
      font-size: 2em;
    }
    
    .trade-item {
      grid-template-columns: 50px 100px 100px 80px;
      font-size: 0.8em;
    }
    
    .orderbook-display {
      grid-template-columns: 1fr;
    }
    
    .stats-grid {
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }
  }
</style>