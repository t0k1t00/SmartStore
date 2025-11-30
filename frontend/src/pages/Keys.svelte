<script>
  import { onMount } from "svelte";
  import { api } from "../lib/api";

  let keys = [];
  let loading = true;
  let error = null;

  // Modal handler
  let showCreateModal = false;
  let editMode = false;

  // Form fields
  let formKey = "";
  let formValue = "";
  let formTTL = ""; // empty = no expiry

  // ================================
  // Helpers
  // ================================
  function parseTTL(ttl) {
    if (ttl === "" || ttl === null || ttl === undefined) return null;
    return Number(ttl);
  }

  function resetForm() {
    formKey = "";
    formValue = "";
    formTTL = "";
    editMode = false;
  }

  // ================================
  // Load all keys
  // ================================
  async function loadKeys() {
    loading = true;
    error = null;

    try {
      const response = await api.getKeys();
      keys = response.keys || [];
      console.log("Actual keys from backend:", keys);
    } catch (e) {
      error = e.message || "Failed to load keys";
    } finally {
      loading = false;
    }
  }

  // ================================
  // Create new key
  // ================================
  async function handleCreate() {
    if (!formKey.trim()) return alert("Key is required");

    try {
      const ttl = parseTTL(formTTL);
      await api.createKey(formKey, formValue, ttl);

      showCreateModal = false;
      resetForm();
      await loadKeys();
    } catch (e) {
      alert("Failed to create key: " + e.message);
    }
  }

  // ================================
  // Update existing key
  // ================================
  async function handleUpdate() {
    if (!formKey.trim()) return alert("Key is required");

    try {
      const ttl = parseTTL(formTTL);
      await api.updateKey(formKey, formValue, ttl);

      showCreateModal = false;
      resetForm();
      await loadKeys();
    } catch (e) {
      alert("Failed to update key: " + e.message);
    }
  }

  // ================================
  // Delete key
  // ================================
  async function handleDelete(key) {
    if (!confirm(`Delete key "${key}"?`)) return;

    try {
      await api.deleteKey(key);
      await loadKeys();
    } catch (e) {
      alert("Failed to delete key: " + e.message);
    }
  }

  // ================================
  // Open modal for editing
  // ================================
  async function openEditModal(key) {
    try {
      const data = await api.getKey(key);

      editMode = true;
      showCreateModal = true;

      formKey = key;
      formValue = data.value || "";
      formTTL = data.ttl ?? ""; // "" = no TTL
    } catch (e) {
      alert(e.message || "Could not load key");
    }
  }

  // ================================
  // Open modal for creating
  // ================================
  function openCreateModal() {
    resetForm();
    editMode = false;
    showCreateModal = true;
  }

  onMount(loadKeys);
</script>

<style>
  .modal-bg {
    background: rgba(0, 0, 0, 0.5);
  }
</style>

<div class="space-y-6">
  <div class="flex justify-between items-center">
    <h1 class="text-3xl font-bold text-gray-800">Key Management</h1>

    <button
      class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      on:click={openCreateModal}
    >
      + Create Key
    </button>
  </div>

  <!-- Keys List -->
  {#if loading}
    <div class="text-center py-12">
      <div class="animate-spin h-10 w-10 border-b-2 border-blue-600 rounded-full mx-auto"></div>
    </div>

  {:else if error}
    <div class="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded">
      {error}
    </div>

  {:else if keys.length === 0}
    <div class="text-center bg-white p-8 rounded-lg shadow">
      <p class="text-gray-600">No keys available</p>
      <button
        class="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        on:click={openCreateModal}
      >
        Create Your First Key
      </button>
    </div>

  {:else}
    <div class="bg-white shadow rounded-lg overflow-hidden">
      <table class="min-w-full">
        <thead class="bg-gray-100">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500">Key</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500">TTL</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500">Actions</th>
          </tr>
        </thead>

        <tbody class="divide-y divide-gray-200">
          {#each keys as key}
            <tr>
              <td class="px-6 py-4 font-mono text-sm">{key}</td>

              <td class="px-6 py-4 text-sm text-gray-600">--</td>

              <td class="px-6 py-4 text-right text-sm">
                <button
                  class="text-blue-600 hover:text-blue-900 mr-4"
                  on:click={() => openEditModal(key)}
                >
                  Edit
                </button>
                <button
                  class="text-red-600 hover:text-red-900"
                  on:click={() => handleDelete(key)}
                >
                  Delete
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- ============================ -->
<!-- Create / Edit MODAL          -->
<!-- ============================ -->

{#if showCreateModal}
<div class="fixed inset-0 flex items-center justify-center z-50 modal-bg">
  <div class="bg-white p-8 rounded-lg max-w-md w-full shadow-xl">
    <h2 class="text-2xl font-bold mb-4">
      {editMode ? "Edit Key" : "Create New Key"}
    </h2>

    <form on:submit|preventDefault={editMode ? handleUpdate : handleCreate}>
      <label class="block mb-2 text-gray-700">Key</label>
      <input
        type="text"
        bind:value={formKey}
        class="w-full border px-3 py-2 rounded mb-4"
        placeholder="user:1001"
        required
        disabled={editMode}
      />

      <label class="block mb-2 text-gray-700">Value</label>
      <textarea
        bind:value={formValue}
        class="w-full border px-3 py-2 rounded mb-4"
        rows="4"
        required
      ></textarea>

      <label class="block mb-2 text-gray-700">TTL (seconds)</label>
      <input
        type="number"
        bind:value={formTTL}
        class="w-full border px-3 py-2 rounded mb-4"
        placeholder="Leave blank for no expiry"
        min="0"
      />

      <div class="flex gap-4 mt-6">
        <button
          type="submit"
          class="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
        >
          {editMode ? "Update" : "Create"}
        </button>

        <button
          type="button"
          class="flex-1 bg-gray-300 py-2 rounded hover:bg-gray-400"
          on:click={() => (showCreateModal = false)}
        >
          Cancel
        </button>
      </div>
    </form>
  </div>
</div>
{/if}
