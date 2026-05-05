const BASE_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'https://api-service-production-46be.up.railway.app';

export const API = {
  getToken() {
    return localStorage.getItem('ragdesk_token');
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('ragdesk_token', token);
    } else {
      localStorage.removeItem('ragdesk_token');
    }
  },

  async request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;

    const headers = {
      ...options.headers
    };

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
      ...options,
      headers
    };

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'An error occurred');
      }
      return data;
    } catch (error) {
      console.error(`API Error on ${endpoint}:`, error);
      throw error;
    }
  },

  // Auth Endpoints
  async login(username, password) {
    // FastAPI OAuth2PasswordRequestForm requires form data
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    // We remove Content-Type to let fetch set it automatically with boundary
    const response = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Login failed');

    this.setToken(data.access_token);
    return data;
  },

  async register(email, password, orgName) {
    return this.request('/auth/register', {
      method: 'POST',
      body: { email, password, org_name: orgName }
    });
  },

  // Knowledge Base Endpoints
  async getKnowledgeBases() {
    return this.request('/kbs');
  },

  async createKnowledgeBase(name, description) {
    return this.request('/kbs', {
      method: 'POST',
      body: { name, description }
    });
  },

  // Document Endpoints
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/documents/upload', {
      method: 'POST',
      body: formData
    });
  },

  // Chat Endpoints
  async chatWithKb(kbId, query, chatId = null) {
    return this.request('/chat', {
      method: 'POST',
      body: { kb_id: kbId, message: query, chat_id: chatId }
    });
  },

  async submitFeedback(messageId, rating, note) {
    return this.request('/feedback', {
      method: 'POST',
      body: { message_id: messageId, rating, note }
    });
  }
};

export function showAlert(containerId, message, type = 'error') {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = `
    <div class="alert alert-${type} animate-fade-in">
      <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'}" style="margin-top: 3px;"></i>
      <div>${message}</div>
    </div>
  `;

  setTimeout(() => {
    container.innerHTML = '';
  }, 5000);
}

export function requireAuth() {
  if (!API.getToken() && !window.location.pathname.endsWith('login.html')) {
    window.location.href = 'login.html';
  }
}
