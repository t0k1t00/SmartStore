// webapp/src/lib/api.js

// API configuration
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// Auth storage
export const authStore = {
  getToken: () => localStorage.getItem("token"),
  setToken: (token) => localStorage.setItem("token", token),
  clearToken: () => localStorage.removeItem("token"),
  isAuthenticated: () => !!localStorage.getItem("token"),
};

// API client
export const api = {
  async request(endpoint, options = {}) {
    const token = authStore.getToken();

    const headers = {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    };

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      authStore.clearToken();
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }

    let data;
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (err) {
      throw new Error("Backend returned invalid JSON");
    }

    if (!response.ok) {
      throw new Error(
        data.detail || data.error || data.message || "Request failed"
      );
    }

    return data;
  },

  // AUTH
  async login(username, password) {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!res.ok) throw new Error("Login failed");

    const data = await res.json();
    authStore.setToken(data.access_token);
    return data;
  },

  getCurrentUser() {
    return this.request("/auth/me");
  },

  // KEYS
  getKeys() {
    return this.request("/keys");
  },

  getKey(key) {
    return this.request(`/keys/${encodeURIComponent(key)}`);
  },

  createKey(key, value, ttl = null, data_type = "string") {
    return this.request("/keys", {
      method: "POST",
      body: JSON.stringify({ key, value, ttl, data_type }),
    });
  },

  updateKey(key, value, ttl = null, data_type = "string") {
    return this.request(`/keys/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ key, value, ttl, data_type }),
    });
  },

  deleteKey(key) {
    return this.request(`/keys/${encodeURIComponent(key)}`, {
      method: "DELETE",
    });
  },

  // STATS
  getStats() {
    return this.request("/stats");
  },

  // ML ENDPOINTS
  trainLSTM() {
    return this.request("/ml/train/lstm", { method: "POST" });
  },

  trainIForest() {
    return this.request("/ml/train/iforest", { method: "POST" });
  },

  trainProphet(periods = 30) {
    return this.request(`/ml/train/prophet?periods=${periods}`, {
      method: "POST",
    });
  },

  trainDBSCAN() {
    return this.request("/ml/train/dbscan", { method: "POST" });
  },

  getTrainingStatus(taskId) {
    return this.request(`/ml/train/status/${taskId}`);
  },

  getCachePredictions(keys, topK = 5) {
    return this.request(
      `/ml/predict/cache?recent_keys=${keys.join(",")}&top_k=${topK}`
    );
  },

  getForecast(periods = 30) {
    return this.request(`/ml/forecast?periods=${periods}`);
  },

  getClusters() {
    return this.request("/ml/clusters");
  },

  async trainModel(modelId) {
    if (modelId === "lstm") return await this.trainLSTM();
    if (modelId === "iforest") return await this.trainIForest();
    if (modelId === "prophet") return await this.trainProphet(30);
    if (modelId === "dbscan") return await this.trainDBSCAN();
    throw new Error("Unknown model type: " + modelId);
  },

  createEventSource(endpoint) {
    const token = authStore.getToken();
    return new EventSource(`${API_BASE_URL}${endpoint}?token=${token}`);
  },
};
