<script>
  import { Link } from 'svelte-routing';
  import { createEventDispatcher } from 'svelte';
  
  const dispatch = createEventDispatcher();
  
  function handleLogout() {
    dispatch('logout');
  }
</script>

<nav class="bg-white shadow-lg">
  <div class="container mx-auto px-4">
    <div class="flex justify-between items-center h-16">
      <div class="flex items-center space-x-8">
        <Link to="/" class="text-2xl font-bold text-blue-600">
          SmartStoreDB
        </Link>
        
        <div class="hidden md:flex space-x-4">
          <Link 
            to="/" 
            class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-100"
          >
            Dashboard
          </Link>
          <Link 
            to="/keys" 
            class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-100"
          >
            Keys
          </Link>
          <Link 
            to="/ml" 
            class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-100"
          >
            ML Models
          </Link>
          <Link 
            to="/monitoring" 
            class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-100"
          >
            Monitoring
          </Link>
        </div>
      </div>
      
      <button
        on:click={handleLogout}
        class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
      >
        Logout
      </button>
    </div>
  </div>
</nav>
