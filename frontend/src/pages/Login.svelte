<script>
  import { createEventDispatcher } from 'svelte';
  import { api } from '../lib/api';
  
  const dispatch = createEventDispatcher();
  
  let username = '';
  let password = '';
  let error = '';
  let loading = false;
  
  async function handleLogin(e) {
    e.preventDefault();
    error = '';
    loading = true;
    
    try {
      await api.login(username, password);
      dispatch('login');
    } catch (err) {
      error = 'Invalid username or password';
    } finally {
      loading = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600">
  <div class="max-w-md w-full bg-white rounded-lg shadow-2xl p-8">
    <div class="text-center mb-8">
      <h1 class="text-4xl font-bold text-gray-800 mb-2">SmartStoreDB</h1>
      <p class="text-gray-600">Intelligent Key-Value Store with ML</p>
    </div>
    
    <form on:submit={handleLogin} class="space-y-6">
      {#if error}
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      {/if}
      
      <div>
        <label for="username" class="block text-sm font-medium text-gray-700 mb-2">
          Username
        </label>
        <input
          id="username"
          type="text"
          bind:value={username}
          placeholder="admin"
          required
          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      
      <div>
        <label for="password" class="block text-sm font-medium text-gray-700 mb-2">
          Password
        </label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="••••••••"
          required
          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
      
      <button
        type="submit"
        disabled={loading}
        class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
    
    <div class="mt-6 text-center text-sm text-gray-600">
      <p>Default credentials:</p>
      <p class="font-mono mt-1">admin / admin123</p>
    </div>
  </div>
</div>
