<script>
  import { Router, Route } from 'svelte-routing';
  import { onMount } from 'svelte';
  import { authStore } from './lib/api';
  
  // Pages
  import Login from './pages/Login.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import Keys from './pages/Keys.svelte';
  import MLModels from './pages/MLModels.svelte';
  import Monitoring from './pages/Monitoring.svelte';
  
  // Components
  import Navbar from './components/Navbar.svelte';
  
  let isAuthenticated = false;
  
  onMount(() => {
    isAuthenticated = authStore.isAuthenticated();
  });
  
  function handleLogin() {
    isAuthenticated = true;
  }
  
  function handleLogout() {
    authStore.clearToken();
    isAuthenticated = false;
    window.location.href = '/';
  }
</script>

<Router>
  {#if !isAuthenticated}
    <Route path="*">
      <Login on:login={handleLogin} />
    </Route>
  {:else}
    <div class="min-h-screen bg-gray-50">
      <Navbar on:logout={handleLogout} />
      <main class="container mx-auto px-4 py-8">
        <Route path="/" component={Dashboard} />
        <Route path="/keys" component={Keys} />
        <Route path="/ml" component={MLModels} />
        <Route path="/monitoring" component={Monitoring} />
      </main>
    </div>
  {/if}
</Router>
