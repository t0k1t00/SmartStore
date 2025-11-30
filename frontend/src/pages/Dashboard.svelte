<script>
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../lib/api';
  import StatCard from '../components/StatCard.svelte';

  let stats = {
    total_keys: 0,
    cache_hit_rate: 0,
    avg_response_time_ms: 0,
    requests_per_second: 0,
    total_size_bytes: 0,
    uptime_seconds: 0,
    memory_usage_mb: 0
  };

  let loading = true;
  let error = null;
  let eventSource = null;

  async function loadStats() {
    try {
      const raw = await api.getStats();
      const s = raw.stats;

      stats = {
        total_keys: s.total_keys || 0,
        cache_hit_rate: s.hit_rate || 0,
        avg_response_time_ms: 0,
        requests_per_second: (s.hits + s.misses) || 0,
        total_size_bytes: s.cache_size || 0,
        uptime_seconds: s.uptime_seconds || 0,
        memory_usage_mb: s.memory_usage_mb || 0
      };

      loading = false;
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  function connectSSE() {
    try {
      eventSource = api.createEventSource('/streaming/metrics');

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        stats = { ...stats, ...data };
      };

      eventSource.onerror = () => {
        console.error('SSE connection error');
        eventSource.close();
      };
    } catch (err) {
      console.error('Failed to connect SSE:', err);
    }
  }

  onMount(() => {
    loadStats();
    connectSSE();
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });
</script>


<div class="space-y-6">
  <div class="flex justify-between items-center">
    <h1 class="text-3xl font-bold text-gray-800">Dashboard</h1>
    <button
      on:click={loadStats}
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
    >
      Refresh
    </button>
  </div>
  
  {#if loading}
    <div class="text-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
      <p class="mt-4 text-gray-600">Loading dashboard...</p>
    </div>
  {:else if error}
    <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
      {error}
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        title="Total Keys"
        value={stats.total_keys?.toLocaleString() || '0'}
        icon="📦"
        color="blue"
      />
      <StatCard
        title="Cache Hit Rate"
        value="{(stats.cache_hit_rate * 100).toFixed(1)}%"
        icon="🎯"
        color="green"
      />
      <StatCard
        title="Avg Response Time"
        value="{stats.avg_response_time_ms?.toFixed(2) || '0'} ms"
        icon="⚡"
        color="yellow"
      />
      <StatCard
        title="Requests/sec"
        value={stats.requests_per_second?.toLocaleString() || '0'}
        icon="📊"
        color="purple"
      />
    </div>
    
    <div class="bg-white rounded-lg shadow-lg p-6">
      <h2 class="text-xl font-bold text-gray-800 mb-4">System Overview</h2>
      <div class="space-y-3">
        <div class="flex justify-between items-center py-2 border-b">
          <span class="text-gray-600">Status</span>
          <span class="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
            Operational
          </span>
        </div>
        <div class="flex justify-between items-center py-2 border-b">
          <span class="text-gray-600">Total Size</span>
          <span class="font-semibold">{(stats.total_size_bytes / 1024 / 1024).toFixed(2)} MB</span>
        </div>
        <div class="flex justify-between items-center py-2 border-b">
          <span class="text-gray-600">Uptime</span>
          <span class="font-semibold">{Math.floor((stats.uptime_seconds || 0) / 3600)}h {Math.floor(((stats.uptime_seconds || 0) % 3600) / 60)}m</span>
        </div>
        <div class="flex justify-between items-center py-2">
          <span class="text-gray-600">Memory Usage</span>
          <span class="font-semibold">{stats.memory_usage_mb || 0} MB</span>
        </div>
      </div>
    </div>
    
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-bold text-gray-800 mb-4">Quick Actions</h2>
        <div class="space-y-3">
          <a href="/keys" class="block px-4 py-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition">
            <div class="flex items-center justify-between">
              <span class="font-medium text-blue-900">Manage Keys</span>
              <span class="text-blue-600">→</span>
            </div>
          </a>
          <a href="/ml" class="block px-4 py-3 bg-purple-50 hover:bg-purple-100 rounded-lg transition">
            <div class="flex items-center justify-between">
              <span class="font-medium text-purple-900">Train ML Models</span>
              <span class="text-purple-600">→</span>
            </div>
          </a>
          <a href="/monitoring" class="block px-4 py-3 bg-green-50 hover:bg-green-100 rounded-lg transition">
            <div class="flex items-center justify-between">
              <span class="font-medium text-green-900">Real-time Monitoring</span>
              <span class="text-green-600">→</span>
            </div>
          </a>
        </div>
      </div>
      
      <div class="bg-white rounded-lg shadow-lg p-6">
        <h2 class="text-xl font-bold text-gray-800 mb-4">Recent Activity</h2>
        <div class="space-y-3 text-sm text-gray-600">
          <div class="flex items-start space-x-3">
            <span class="text-green-500">✓</span>
            <div>
              <p class="font-medium text-gray-800">Cache optimized</p>
              <p class="text-xs text-gray-500">2 minutes ago</p>
            </div>
          </div>
          <div class="flex items-start space-x-3">
            <span class="text-blue-500">ℹ</span>
            <div>
              <p class="font-medium text-gray-800">LSTM model retrained</p>
              <p class="text-xs text-gray-500">1 hour ago</p>
            </div>
          </div>
          <div class="flex items-start space-x-3">
            <span class="text-yellow-500">⚠</span>
            <div>
              <p class="font-medium text-gray-800">Anomaly detected</p>
              <p class="text-xs text-gray-500">3 hours ago</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
