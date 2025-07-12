<script>
  import { onMount, onDestroy } from 'svelte';
  
  // WebSocket connection
  let ws;
  let isConnected = false;
  
  // Audio context and nodes
  let audioContext;
  let oscillator;
  let gainNode;
  let analyser;
  let dataArray;
  let isAudioInitialized = false;
  
  // Trade data
  let currentPrice = 0;
  let lastPrice = 0;
  let trades = [];
  let tradeCount = 0;
  let totalVolume = 0;
  let avgTradeSize = 0;
  let tradesPerSecond = 0;
  let largestTrade = null;
  
  // UI state
  let priceDirection = 'neutral'; // 'up', 'down', 'neutral'
  let volumeIntensity = 0;
  let audioEnabled = false;
  
  // Rolling window for TPS calculation
  let tradeTimestamps = [];
  const TPS_WINDOW = 10; // seconds
  
  let clickSound = null;

  onMount(() => {
    connectWebSocket();
    // Preload the click sound
    clickSound = new Audio('/geiger_click.wav');
    clickSound.load();
    initializeAudio();
  });
  
  onDestroy(() => {
    if (ws) {
      ws.close();
    }
    if (audioContext) {
      audioContext.close();
    }
  });
  
  function connectWebSocket() {
    try {
      ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        isConnected = true;
        console.log('Connected to WebSocket');
      };
      
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'trade') {
          processTrade(message.data);
        }
      };
      
      ws.onclose = () => {
        isConnected = false;
        console.log('WebSocket connection closed');
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
    }
  }
  
  function initializeAudio() {
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Create oscillator
      oscillator = audioContext.createOscillator();
      gainNode = audioContext.createGain();
      analyser = audioContext.createAnalyser();
      
      // Configure nodes
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(220, audioContext.currentTime);
      gainNode.gain.setValueAtTime(0, audioContext.currentTime);
      
      analyser.fftSize = 256;
      dataArray = new Uint8Array(analyser.frequencyBinCount);
      
      // Connect nodes
      oscillator.connect(gainNode);
      gainNode.connect(analyser);
      analyser.connect(audioContext.destination);
      
      // Start oscillator
      oscillator.start();
      
      isAudioInitialized = true;
      console.log('Audio initialized');
    } catch (error) {
      console.error('Failed to initialize audio:', error);
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
    trades = [trade, ...trades.slice(0, 99)]; // Svelte reactivity fix
    
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
    
    // Update audio
    if (audioEnabled && isAudioInitialized) {
      updateAudio(trade);
    }
    // Play the click sound if audio is enabled
    if (audioEnabled && clickSound) {
      clickSound.currentTime = 0;
      clickSound.play();
    }
    // Track largest trade
    if (!largestTrade || trade.size > largestTrade.size) {
      largestTrade = { ...trade };
      largestTrade = { ...largestTrade }; // Svelte reactivity fix
    }
  }
  
  function updateAudio(trade) {
    if (!audioContext || !oscillator || !gainNode) return;
    
    const now = audioContext.currentTime;
    
    // Map trade size to frequency (larger trades = lower frequency)
    const frequency = Math.max(100, 500 - (trade.size * 20));
    
    // Map volume intensity to gain (0-0.3 to avoid ear damage)
    const gain = volumeIntensity * 0.3;
    
    // Different tones for buy/sell
    const baseFreq = trade.side === 'buy' ? frequency : frequency * 0.8;
    
    // Set frequency and gain
    oscillator.frequency.setValueAtTime(baseFreq, now);
    gainNode.gain.setValueAtTime(gain, now);
    
    // Create a brief tone (attack and decay)
    gainNode.gain.exponentialRampToValueAtTime(gain, now + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
  }
  
  function toggleAudio() {
    audioEnabled = !audioEnabled;
    if (!audioEnabled && gainNode) {
      gainNode.gain.setValueAtTime(0, audioContext.currentTime);
    }
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
  
  function formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString();
  }
</script>

<main>
  <div class="container">
    <header>
      <h1>🎵 BTC Live Tape Audio Visualizer</h1>
      <div class="connection-status">
        <span class="status-indicator {isConnected ? 'connected' : 'disconnected'}"></span>
        {isConnected ? 'Connected' : 'Disconnected'}
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
    max-width: 1200px;
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
  }
  
  .status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #ff4444;
    transition: background 0.3s;
  }
  
  .status-indicator.connected {
    background: #44ff44;
    box-shadow: 0 0 10px rgba(68, 255, 68, 0.5);
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
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
  }
  
  .stat-card {
    background: rgba(255, 255, 255, 0.1);
    padding: 20px;
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
    font-size: 1.5em;
    font-weight: bold;
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
    width: 100%;
    height: 20px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 20px;
  }
  
  .volume-fill {
    height: 100%;
    background: linear-gradient(90deg, #44ff44, #ffff44, #ff4444);
    transition: width 0.3s;
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
  
  @media (max-width: 768px) {
    .price-value {
      font-size: 2em;
    }
    
    .trade-item {
      grid-template-columns: 50px 100px 100px 80px;
      font-size: 0.8em;
    }
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
</style>