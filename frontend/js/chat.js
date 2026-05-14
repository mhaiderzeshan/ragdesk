import { API, requireAuth } from './utils/api.js';

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const logoutBtn = document.getElementById('logout-btn');
  const kbSelect = document.getElementById('kb-select');
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatMessages = document.getElementById('chat-messages');
  const sendBtn = document.getElementById('send-btn');
  const clearChatBtn = document.getElementById('clear-chat-btn');
  
  let currentSessionId = null;

  logoutBtn.addEventListener('click', () => {
    API.setToken(null);
    window.location.href = 'login.html';
  });

  // Auto-resize textarea
  chatInput.addEventListener('input', function() {
    this.style.height = '60px'; // baseline
    this.style.height = (this.scrollHeight) + 'px';
  });

  // Handle Enter to submit (Shift+Enter for newline)
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (chatInput.value.trim() !== '' && !sendBtn.disabled) {
        chatForm.dispatchEvent(new Event('submit'));
      }
    }
  });

  // Load KBs for sidebar
  async function loadKBs() {
    try {
      const kbs = await API.getKnowledgeBases();
      if (kbs.length === 0) {
        kbSelect.innerHTML = '<option value="">No Knowledge Bases found</option>';
        return;
      }
      
      kbSelect.innerHTML = '<option value="">-- Select a Knowledge Base --</option>' + 
        kbs.map(kb => `<option value="${kb.id}">${kb.name}</option>`).join('');
    } catch (error) {
      kbSelect.innerHTML = '<option value="">Error loading KBs</option>';
      console.error(error);
    }
  }

  loadKBs();

  function appendMessage(role, content, sources = null, chatLogId = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message animate-fade-in ${role === 'user' ? 'user' : 'ai'}`;
    
    let sourceHtml = '';
    if (sources && sources.length > 0) {
      sourceHtml = `<div class="sources">
        <strong>Sources:</strong><br/>
        ${sources.map(s => {
          const displayName = s.document_name && s.document_name !== 'Unknown' 
            ? s.document_name 
            : 'Doc ' + (s.document_id ? s.document_id.substring(0,8) : 'Unknown');
          return `<span class="source-badge" title="Relevance: ${s.score ? s.score.toFixed(2) : 'N/A'}">${displayName}</span>`;
        }).join('')}
      </div>`;
    }

    let feedbackHtml = '';
    if (role === 'ai' && chatLogId) {
      feedbackHtml = `
        <div class="message-actions">
          <button class="btn-icon feedback-btn" data-log-id="${chatLogId}" data-rating="1" title="Helpful"><i class="far fa-thumbs-up"></i></button>
          <button class="btn-icon feedback-btn" data-log-id="${chatLogId}" data-rating="-1" title="Not Helpful"><i class="far fa-thumbs-down"></i></button>
        </div>
      `;
    }

    msgDiv.innerHTML = `
      <div class="message-avatar">
        ${role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>'}
      </div>
      <div>
        <div class="message-content">
          ${formatContent(content)}
          ${sourceHtml}
        </div>
        ${feedbackHtml}
      </div>
    `;
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Add feedback listeners
    if (role === 'ai' && chatLogId) {
      msgDiv.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const logId = e.currentTarget.getAttribute('data-log-id');
          const rating = parseInt(e.currentTarget.getAttribute('data-rating'));
          try {
            await API.submitFeedback(logId, rating, null);
            e.currentTarget.style.color = rating === 1 ? 'var(--success)' : 'var(--danger)';
            e.currentTarget.parentElement.style.opacity = '1';
          } catch (error) {
            console.error('Feedback error:', error);
          }
        });
      });
    }
  }

  function formatContent(text) {
    // Basic formatting for newlines and simple markdown
    let formatted = text.replace(/\\n/g, '<br/>').replace(/\n/g, '<br/>');
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    return formatted;
  }

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    const kbId = kbSelect.value;

    if (!query) return;
    if (!kbId) {
      alert("Please select a knowledge base from the left panel first.");
      return;
    }

    // Append user query
    appendMessage('user', query);
    chatInput.value = '';
    chatInput.style.height = '60px';
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    // Temporary loading indicator
    const loadingId = 'loading-' + Date.now();
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message ai animate-fade-in';
    loadingDiv.id = loadingId;
    loadingDiv.innerHTML = `
      <div class="message-avatar"><i class="fas fa-robot"></i></div>
      <div class="message-content">
        <i class="fas fa-circle-notch fa-spin"></i> Thinking...
      </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      // Call chat API
      const response = await API.chatWithKb(kbId, query, currentSessionId);
      
      // Update session ID if available
      if (response.chat_id) {
        currentSessionId = response.chat_id;
      }
      
      // Remove loading indicator
      document.getElementById(loadingId).remove();
      
      // Append AI response
      appendMessage('ai', response.answer, response.citations, response.message_id);
    } catch (error) {
      // Remove loading indicator
      document.getElementById(loadingId).remove();
      appendMessage('ai', `**Error:** ${error.message}`);
    } finally {
      sendBtn.disabled = false;
      sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
  });

  clearChatBtn.addEventListener('click', () => {
    currentSessionId = null;
    chatMessages.innerHTML = `
      <div class="message ai">
        <div class="message-avatar"><i class="fas fa-robot"></i></div>
        <div class="message-content">
          Chat cleared. New session started.
        </div>
      </div>
    `;
  });
});
