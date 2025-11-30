<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  
  const models = [
    {
      id: 'lstm',
      name: 'LSTM Cache Predictor',
      description: 'Predicts next 5 keys with 92%+ accuracy',
      icon: '🧠',
      color: 'blue'
    },
    {
      id: 'iforest',
      name: 'Isolation Forest',
      description: 'Real-time anomaly detection',
      icon: '🔍',
      color: 'red'
    },
    {
      id: 'prophet',
      name: 'Prophet Forecaster',
      description: '30-day capacity predictions',
      icon: '📈',
      color: 'green'
    },
    {
      id: 'dbscan',
      name: 'DBSCAN Clustering',
      description: 'User behavior segmentation',
      icon: '🎯',
      color: 'purple'
    }
  ];
  
  let trainingTasks = {};
  let predictions = null;
  let forecast = null;
  let clusters = null;
  
  async function trainModel(modelId) {
    try {
      const response = await api.trainModel(modelId);
      trainingTasks[modelId] = {
        taskId: response.task_id,
        status: 'PENDING',
        progress: 0
      };
      
      // Poll status
      pollTrainingStatus(modelId, response.task_id);
    } catch (err) {
      alert('Failed to start training: ' + err.message);
    }
  }
  
  async function pollTrainingStatus(modelId, taskId) {
    const interval = setInterval(async () => {
      try {
        const status = await api.getTrainingStatus(taskId);

        trainingTasks[modelId].status = status.status;
        trainingTasks[modelId].progress = status.progress;

        if (status.status === "SUCCESS") {
          clearInterval(interval);
          trainingTasks[modelId].progress = 100;
        }

      } catch (err) {
        clearInterval(interval);
        console.error("Polling stopped:", err);
      }
    }, 1000);
  }


  async function loadPredictions() {
    try {
      const recentKeys = ['user:1', 'user:2', 'user:3'];
      predictions = await api.getCachePredictions(recentKeys, 5);
    } catch (err) {
      console.error('Failed to load predictions:', err);
    }
  }
  
  async function loadForecast() {
    try {
      forecast = await api.getForecast(30);
    } catch (err) {
      console.error('Failed to load forecast:', err);
    }
  }
  
  async function loadClusters() {
    try {
      clusters = await api.getClusters();
    } catch (err) {
      console.error('Failed to load clusters:', err);
    }
  }
  
  onMount(() => {
    loadPredictions();
    loadForecast();
    loadClusters();
  });
</script>

<div class="space-y-6">
  <h1 class="text-3xl font-bold text-gray-800">Machine Learning Models</h1>
  
  <!-- Model Training Cards -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    {#each models as model}
      <div class="bg-white rounded-lg shadow-lg p-6">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center">
            <div class="text-4xl mr-4">{model.icon}</div>
            <div>
              <h3 class="text-xl font-bold text-gray-800">{model.name}</h3>
              <p class="text-sm text-gray-600">{model.description}</p>
            </div>
          </div>
        </div>
        
        {#if trainingTasks[model.id]}
          <div class="mt-4">
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm font-medium text-gray-700">
                {trainingTasks[model.id].status}
              </span>
              <span class="text-sm text-gray-600">
                {trainingTasks[model.id].progress}%
              </span>
            </div>

            <div class="w-full bg-gray-200 rounded-full h-2">
              <div 
                class={`h-2 rounded-full bg-${model.color}-600 transition-all duration-300`}
                style="width: {trainingTasks[model.id].progress}%"
              ></div>
            </div>
          </div>
        {:else}
          <button
            on:click={() => trainModel(model.id)}
            class={`w-full mt-4 px-4 py-2 bg-${model.color}-600 text-white rounded-lg hover:bg-${model.color}-700`}
          >
            Train Model
          </button>
        {/if}
      </div>
    {/each}
  </div>
  
  <!-- Predictions Display -->
  {#if predictions}
    <div class="bg-white rounded-lg shadow-lg p-6">
      <h2 class="text-xl font-bold text-gray-800 mb-4">🧠 Cache Predictions (LSTM)</h2>
      <div class="space-y-2">
        {#each predictions.prediction || [] as pred}
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <code class="font-mono text-sm">{pred.key}</code>
            <div class="flex items-center">
              <div class="w-32 bg-gray-200 rounded-full h-2 mr-3">
                <div 
                  class="bg-blue-600 h-2 rounded-full"
                  style="width: {pred.probability * 100}%"
                ></div>
              </div>
              <span class="text-sm font-semibold text-gray-700">
                {(pred.probability * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}
  
  <!-- Forecast Display -->
  {#if forecast}
    <div class="bg-white rounded-lg shadow-lg p-6">
      <h2 class="text-xl font-bold text-gray-800 mb-4">📈 Storage Forecast (Prophet)</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="p-4 bg-blue-50 rounded-lg">
          <p class="text-sm text-gray-600 mb-1">Current Estimate</p>
          <p class="text-2xl font-bold text-blue-900">
            {forecast.summary?.current_estimate?.toLocaleString() || 0}
          </p>
        </div>
        <div class="p-4 bg-green-50 rounded-lg">
          <p class="text-sm text-gray-600 mb-1">30-Day Forecast</p>
          <p class="text-2xl font-bold text-green-900">
            {forecast.summary?.final_estimate?.toLocaleString() || 0}
          </p>
        </div>
        <div class="p-4 bg-purple-50 rounded-lg">
          <p class="text-sm text-gray-600 mb-1">Growth Rate</p>
          <p class="text-2xl font-bold text-purple-900">
            {forecast.summary?.growth_rate_percent?.toFixed(1) || 0}%
          </p>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- Clusters Display -->
  {#if clusters}
    <div class="bg-white rounded-lg shadow-lg p-6">
      <h2 class="text-xl font-bold text-gray-800 mb-4">🎯 User Clusters (DBSCAN)</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="p-4 bg-purple-50 rounded-lg">
          <p class="text-sm text-gray-600 mb-1">Total Clusters</p>
          <p class="text-2xl font-bold text-purple-900">{clusters.n_clusters || 0}</p>
        </div>
        <div class="p-4 bg-red-50 rounded-lg">
          <p class="text-sm text-gray-600 mb-1">Outliers Detected</p>
          <p class="text-2xl font-bold text-red-900">{clusters.n_outliers || 0}</p>
        </div>
      </div>
      
      {#if clusters.cluster_sizes}
        <div class="mt-4">
          <p class="text-sm font-medium text-gray-700 mb-2">Cluster Distribution</p>
          <div class="space-y-2">
            {#each Object.entries(clusters.cluster_sizes) as [id, size]}
              <div class="flex items-center">
                <span class="text-sm font-mono text-gray-600 w-20">Cluster {id}</span>
                <div class="flex-1 bg-gray-200 rounded-full h-6 mx-3">
                  <div 
                    class="bg-purple-600 h-6 rounded-full flex items-center justify-end pr-2"
                    style="width: {(size / Math.max(...Object.values(clusters.cluster_sizes))) * 100}%"
                  >
                    <span class="text-xs text-white font-semibold">{size}</span>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
