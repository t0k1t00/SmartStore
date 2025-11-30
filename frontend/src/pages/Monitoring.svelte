<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api';
  
  let eventSource = null;
  let connected = false;
  let metrics = [];
  let stats = {
    total_keys: 0,
    cache_hit_rate: 0,
    avg_response_time_ms: 0,
    requests_per_second: 0
  };
  
  function connectSSE() {
    try {
      eventSource = api.createEventSource('/streaming/metrics');
      
      eventSource.onopen = () => {
        connected = true;
        addMetric('✓ Connected to real-time stream', 'success');
      };
      
      eventSource.addEventListener('initial_stats', (event) => {
        const data = JSON.parse(event.data);
        stats = { ...stats, ...data };
        addMetric('Initial stats received', 'info');
      });
      
      eventSource.addEventListener('message', (event) => {
        const data = JSON.parse(event.data);
        
        if (data.metric) {
          addMetric(`${data.metric}: ${data.value}`, 'info');
        }
        
        if (data.cache_hit_rate !== undefined) {
          stats = { ...stats, ...data };
        }
      });
      
      eventSource.addEventListener('heartbeat', (event) => {
        // Heartbeat received, connection is alive
      });
      
      eventSource.onerror = () => {
        connected = false;
        addMetric('✗ Connection lost, reconnecting...', 'error');
        eventSource.close();
        
        // Reconnect after 3 seconds
        setTimeout(() => {
          connectSSE();
        }, 3000);
      };
    } catch (err) {
      addMetric('Failed to connect: ' + err.message, 'error');
    }
  }
  
  function addMetric(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    metrics = [
      { timestamp, message, type },
      ...metrics.slice(0, 99) // Keep last 100 metrics
    ];
  }
  
  function disconnect() {
    if (eventSource) {
      eventSource.close();
      connected = false;
      addMetric('Disconnected from stream', 'warning');
    }
  }
  
  onMount(() => {
    connectSSE();
  });
  
  onDestroy(() => {
    disconnect();
  });
</script>

<div class="space-y-6">
  <div class="flex justify-between items-center">
    <h1 class="text-3xl font-bold text-gray-800">Real-Time Monitoring</h1>
    <div class="flex items-center gap-4">
      <div class="flex items-center">
        <div class="w-3 h-3 rounded-full {connected ? 'bg-green-500' : 'bg-red-500'} mr-2 animate-pulse"></div>
        <span class="text-sm font-medium text-gray-700">
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
      {#if connected}
        <button
          on:click={disconnect}
          class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
        >
          Disconnect
        </button>
      {:else}
        <button
          on:click={connectSSE}
          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
        >
          Connect
        </button>
      {/if}
    </div>
  </div>
  
  <!-- Live Metrics -->
  <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
    <div class="bg-white rounded-lg shadow-lg p-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-gray-600 mb-1">Total Keys</p>
          <p class="text-3xl font-bold text-gray-900">{stats.total_keys?.toLocaleString() || 0}</p>
        </div>
        <div class="text-4xl">📦</div>
      </div>
    </div>
    
    <div class="bg-white rounded-lg shadow-lg p-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-gray-600 mb-1">Cache Hit Rate</p>
          <p class="text-3xl font-bold text-green-600">
            {((stats.cache_hit_rate || 0) * 100).toFixed(1)}%
          </p>
        </div>
        <div class="text-4xl">🎯</div>
      </div>
    </div>
    
    <div class="bg-white rounded-lg shadow-lg p-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-gray-600 mb-1">Response Time</p>
          <p class="text-3xl font-bold text-yellow-600">
            {(stats.avg_response_time_ms || 0).toFixed(2)}ms
          </p>
        </div>
        <div class="text-4xl">⚡</div>
      </div>
    </div>
    
    <div class="bg-white rounded-lg shadow-lg p-6">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-gray-600 mb-1">Requests/sec</p>
          <p class="text-3xl font-bold text-purple-600">
            {(stats.requests_per_second || 0).toLocaleString()}
          </p>
        </div>
        <div class="text-4xl">📊</div>
      </div>
    </div>
  </div>
  
  <!-- Event Stream -->
  <div class="bg-white rounded-lg shadow-lg">
    <div class="p-6 border-b border-gray-200">
      <h2 class="text-xl font-bold text-gray-800">Event Stream</h2>
      <p class="text-sm text-gray-600 mt-1">Live updates from the server</p>
    </div>
    
    <div class="p-6">
      {#if metrics.length === 0}
        <div class="text-center py-12 text-gray-500">
          {#if connected}
            <p>Waiting for events...</p>
          {:else}
            <p>Not connected. Click "Connect" to start receiving events.</p>
          {/if}
        </div>
      {:else}
        <div class="space-y-2 max-h-96 overflow-y-auto">
          {#each metrics as metric}
            <div class="flex items-start gap-3 p-3 rounded-lg {
              metric.type === 'success' ? 'bg-green-50' :
              metric.type === 'error' ? 'bg-red-50' :
              metric.type === 'warning' ? 'bg-yellow-50' :
              'bg-gray-50'
            }">
              <span class="text-xs font-mono text-gray-500 min-w-[80px]">
                {metric.timestamp}
              </span>
              <span class="text-sm {
                metric.type === 'success' ? 'text-green-800' :
                metric.type === 'error' ? 'text-red-800' :
                metric.type === 'warning' ? 'text-yellow-800' :
                'text-gray-800'
              }">
                {metric.message}
              </span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
  
  <!-- Connection Info -->
  <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
    <div class="flex items-start">
      <div class="text-2xl mr-3">ℹ️</div>
      <div>
        <p class="text-sm font-semibold text-blue-900 mb-1">Server-Sent Events (SSE)</p>
        <p class="text-sm text-blue-800">
          This page uses SSE to receive real-time updates from the server. 
          Events include cache hits, key operations, and performance metrics.
        </p>
      </div>
    </div>
  </div>
</div>
