const BASE_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'http://localhost:8080/api/v1';

// ─── HTML escaping helpers ────────────────────────────────────────
// Any server-supplied value interpolated into innerHTML MUST be escaped to
// prevent stored XSS (e.g. a KB name containing <img src=x onerror=...>).
export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Attribute escaping — quotes are the dangerous characters inside attributes.
export function escapeAttr(value) {
  return escapeHtml(value);
}

// ─── Auth helpers ─────────────────────────────────────────────────
function onLoginPage() {
  return window.location.pathname.toLowerCase().endsWith('login.html');
}

// Force the user back to login when a request is rejected as unauthenticated
// (e.g. expired JWT). Without this, every API call fails with a generic
// "Not authenticated" error and the app appears broken.
function handleUnauthorized() {
  API.setToken(null);
  if (!onLoginPage()) {
    window.location.href = 'login.html';
  }
}

// ─── Safe JSON parsing ────────────────────────────────────────────
// Guard against response.json() throwing SyntaxError on empty (204) or
// non-JSON (HTML gateway error) bodies, which would surface as a confusing
// "Unexpected end of JSON input" message.
async function parseJsonSafely(response) {
  const contentLength = response.headers.get('Content-Length');
  const contentType = response.headers.get('Content-Type') || '';
  if (contentLength === '0') return null;
  if (!contentType.includes('application/json')) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

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

      // 401 → token expired or invalid: clear it and bounce to login.
      if (response.status === 401) {
        handleUnauthorized();
        throw new Error('Your session has expired. Please sign in again.');
      }

      const data = await parseJsonSafely(response);

      if (!response.ok) {
        throw new Error((data && data.detail) || `Request failed (${response.status})`);
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

    if (response.status === 401) {
      handleUnauthorized();
      throw new Error('Incorrect email or password.');
    }

    const data = await parseJsonSafely(response);
    if (!response.ok) throw new Error((data && data.detail) || 'Login failed');

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
  async uploadDocument(file, kbId = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (kbId) {
      formData.append('kb_id', kbId);
    }
    return this.request('/documents/upload', {
      method: 'POST',
      body: formData
    });
  },

  async getDocuments() {
    return this.request('/documents');
  },

  async getDocumentStatus(documentId) {
    return this.request(`/documents/${documentId}/status`);
  },

  // Chat Endpoints
  // Accepts an optional AbortSignal so callers can cancel an in-flight request
  // (e.g. when the user clears the chat or switches knowledge base).
  async chatWithKb(kbId, query, chatId = null, signal) {
    return this.request('/chat', {
      method: 'POST',
      body: { kb_id: kbId, message: query, chat_id: chatId },
      signal
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

  // Escape the message — server-supplied detail strings may contain markup.
  const safeMessage = escapeHtml(message);
  const icon = type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle';

  container.innerHTML = `
    <div class="alert alert-${escapeAttr(type)} animate-fade-in">
      <i class="fas ${icon}" style="margin-top: 3px;"></i>
      <div>${safeMessage}</div>
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
