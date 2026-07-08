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
  const uploadForm = document.getElementById('artifact-upload-form');
  const fileInput = document.getElementById('artifact-file-input');
  const fileButton = document.getElementById('artifact-file-button');
  const uploadBtn = document.getElementById('artifact-upload-btn');
  const selectedFileLabel = document.getElementById('selected-file-label');
  const uploadHint = document.getElementById('upload-hint');
  const artifactsList = document.getElementById('artifacts-list');
  const artifactAlert = document.getElementById('artifact-alert');
  const refreshArtifactsBtn = document.getElementById('refresh-artifacts-btn');

  let currentSessionId = null;
  let documents = [];
  let pollTimer = null;
  let alertTimer = null;
  let currentChatController = null;  // AbortController for the in-flight chat request

  const activeStatuses = new Set(['pending', 'processing', 'queued']);
  const statusMeta = {
    pending: { label: 'Queued', icon: 'fa-clock' },
    queued: { label: 'Queued', icon: 'fa-clock' },
    processing: { label: 'Processing', icon: 'fa-circle-notch fa-spin' },
    completed: { label: 'Completed', icon: 'fa-check' },
    failed: { label: 'Failed', icon: 'fa-triangle-exclamation' }
  };

  logoutBtn.addEventListener('click', () => {
    stopPolling();
    API.setToken(null);
    window.location.href = 'login.html';
  });

  chatInput.addEventListener('input', function() {
    this.style.height = '56px';
    this.style.height = `${this.scrollHeight}px`;
  });

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (chatInput.value.trim() !== '' && !sendBtn.disabled) {
        chatForm.requestSubmit();
      }
    }
  });

  kbSelect.addEventListener('change', () => {
    // Cancel any in-flight chat for the previous KB so its response doesn't
    // land in the new KB's view (stale-response race).
    if (currentChatController) {
      currentChatController.abort();
      currentChatController = null;
    }
    currentSessionId = null;
    renderUploadState();
    renderArtifactList();
    loadDocuments();
  });

  fileButton.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', renderUploadState);
  refreshArtifactsBtn.addEventListener('click', loadDocuments);

  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    const kbId = kbSelect.value;

    if (!kbId) {
      showArtifactAlert('Select a knowledge base before uploading.', 'error');
      return;
    }

    if (!file) {
      showArtifactAlert('Choose a PDF first.', 'error');
      return;
    }

    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading';

    const optimisticId = `local-${Date.now()}`;
    documents = [
      {
        document_id: optimisticId,
        kb_id: kbId,
        filename: file.name,
        status: 'queued',
        created_at: new Date().toISOString()
      },
      ...documents
    ];
    renderArtifactList();

    try {
      const response = await API.uploadDocument(file, kbId);
      documents = documents.map((doc) => (
        doc.document_id === optimisticId
          ? {
              ...doc,
              document_id: response.document_id,
              status: normalizeStatus(response.status),
              filename: response.filename || doc.filename
            }
          : doc
      ));
      fileInput.value = '';
      renderUploadState();
      showArtifactAlert(`${response.filename} queued for processing.`, 'success');
      renderArtifactList();
      startPolling();
    } catch (error) {
      documents = documents.map((doc) => (
        doc.document_id === optimisticId
          ? { ...doc, status: 'failed', error_msg: error.message }
          : doc
      ));
      showArtifactAlert(`Upload failed: ${error.message}`, 'error');
      renderArtifactList();
    } finally {
      uploadBtn.innerHTML = '<i class="fas fa-cloud-arrow-up"></i> Upload';
      renderUploadState();
    }
  });

  async function loadKBs() {
    try {
      const kbs = await API.getKnowledgeBases();
      if (kbs.length === 0) {
        kbSelect.innerHTML = '<option value="">No knowledge bases found</option>';
        renderUploadState();
        return;
      }

      kbSelect.innerHTML = '<option value="">Select a knowledge base</option>' +
        kbs.map((kb) => `<option value="${escapeAttr(kb.id)}">${escapeHtml(kb.name)}</option>`).join('');
      renderUploadState();
      await loadDocuments();
    } catch (error) {
      kbSelect.innerHTML = '<option value="">Error loading knowledge bases</option>';
      showArtifactAlert(error.message, 'error');
    }
  }

  async function loadDocuments() {
    const selectedKbId = kbSelect.value;
    if (!selectedKbId) {
      documents = [];
      renderArtifactList();
      stopPolling();
      return;
    }

    try {
      refreshArtifactsBtn.disabled = true;
      const allDocuments = await API.getDocuments();
      documents = allDocuments
        .filter((doc) => String(doc.kb_id) === String(selectedKbId))
        .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      renderArtifactList();
      startPolling();
    } catch (error) {
      showArtifactAlert(`Could not load artifacts: ${error.message}`, 'error');
    } finally {
      refreshArtifactsBtn.disabled = false;
    }
  }

  function appendMessage(role, content, sources = null, chatLogId = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message animate-fade-in ${role === 'user' ? 'user' : 'ai'}`;

    const sourceHtml = sources && sources.length > 0
      ? `<div class="sources">
          <strong>Sources</strong>
          <div class="source-list">
            ${sources.map((source) => {
              const displayName = source.document_name && source.document_name !== 'Unknown'
                ? source.document_name
                : `Doc ${source.document_id ? String(source.document_id).substring(0, 8) : 'Unknown'}`;
              const score = typeof source.score === 'number' ? source.score.toFixed(2) : 'N/A';
              return `<span class="source-badge" title="Relevance: ${escapeAttr(score)}">${escapeHtml(displayName)}</span>`;
            }).join('')}
          </div>
        </div>`
      : '';

    const feedbackHtml = role === 'ai' && chatLogId
      ? `<div class="message-actions">
          <button class="btn-icon feedback-btn" data-log-id="${escapeAttr(chatLogId)}" data-rating="1" title="Helpful" aria-label="Helpful"><i class="far fa-thumbs-up"></i></button>
          <button class="btn-icon feedback-btn" data-log-id="${escapeAttr(chatLogId)}" data-rating="-1" title="Not helpful" aria-label="Not helpful"><i class="far fa-thumbs-down"></i></button>
        </div>`
      : '';

    msgDiv.innerHTML = `
      <div class="message-avatar">
        ${role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>'}
      </div>
      <div class="message-body">
        <div class="message-content">
          ${formatContent(content)}
          ${sourceHtml}
        </div>
        ${feedbackHtml}
      </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (role === 'ai' && chatLogId) {
      msgDiv.querySelectorAll('.feedback-btn').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          const logId = e.currentTarget.getAttribute('data-log-id');
          const rating = parseInt(e.currentTarget.getAttribute('data-rating'), 10);
          try {
            await API.submitFeedback(logId, rating, null);
            e.currentTarget.style.color = rating === 1 ? 'var(--success)' : 'var(--danger)';
            e.currentTarget.parentElement.style.opacity = '1';
          } catch (error) {
            showArtifactAlert(`Feedback failed: ${error.message}`, 'error');
          }
        });
      });
    }
  }

  function formatContent(text) {
    return escapeHtml(String(text || ''))
      .replace(/\\n/g, '<br>')
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  }

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    const kbId = kbSelect.value;

    if (!query) return;
    if (!kbId) {
      showArtifactAlert('Select a knowledge base before chatting.', 'error');
      return;
    }

    appendMessage('user', query);
    chatInput.value = '';
    chatInput.style.height = '56px';
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    const loadingId = `loading-${Date.now()}`;
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message ai animate-fade-in';
    loadingDiv.id = loadingId;
    loadingDiv.innerHTML = `
      <div class="message-avatar"><i class="fas fa-robot"></i></div>
      <div class="message-body">
        <div class="message-content thinking">
          <i class="fas fa-circle-notch fa-spin"></i> Thinking
        </div>
      </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      // Set up cancellation before the request fires so clear/switch can abort.
      currentChatController = new AbortController();
      const response = await API.chatWithKb(kbId, query, currentSessionId, currentChatController.signal);
      if (response.chat_id) {
        currentSessionId = response.chat_id;
      }
      document.getElementById(loadingId)?.remove();
      appendMessage('ai', response.answer, response.citations, response.message_id);
    } catch (error) {
      document.getElementById(loadingId)?.remove();
      // Aborted requests are intentional (KB switch / clear) — don't show an error bubble.
      if (error.name === 'AbortError') {
        /* silently ignore */
      } else {
        appendMessage('ai', `**Error:** ${error.message}`);
      }
    } finally {
      currentChatController = null;
      sendBtn.disabled = false;
      sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
  });

  clearChatBtn.addEventListener('click', () => {
    // Cancel any in-flight chat so the response doesn't arrive after the clear.
    if (currentChatController) {
      currentChatController.abort();
      currentChatController = null;
    }
    currentSessionId = null;
    chatMessages.innerHTML = `
      <div class="message ai">
        <div class="message-avatar"><i class="fas fa-robot"></i></div>
        <div class="message-body">
          <div class="message-content">Chat cleared. New session started.</div>
        </div>
      </div>
    `;
  });

  function renderArtifactList() {
    if (!kbSelect.value) {
      artifactsList.innerHTML = emptyArtifactHtml('Select a knowledge base.');
      return;
    }

    if (documents.length === 0) {
      artifactsList.innerHTML = emptyArtifactHtml('No artifacts yet.');
      return;
    }

    // Diff-update instead of full innerHTML rebuild each tick:
    //  - preserves scroll position within the list
    //  - avoids trashing/recreating DOM nodes every 4s during polling
    // Strategy: render once into a Map keyed by document_id, then on subsequent
    // renders update only what changed and add/remove rows as needed.

    // Build the set of ids we want present
    const desiredIds = new Set(documents.map((d) => String(d.document_id)));

    // Remove existing rows that are no longer present (or the placeholder/empty states)
    Array.from(artifactsList.children).forEach((child) => {
      const childId = child.getAttribute('data-doc-id');
      // keep empty-state placeholder; it will be replaced below
      if (childId && !desiredIds.has(childId)) {
        child.remove();
      } else if (!childId) {
        // leftover empty-state node — clear it so real rows can render
        child.remove();
      }
    });

    // Update or insert each document row in order
    documents.forEach((doc) => {
      const id = String(doc.document_id);
      const status = normalizeStatus(doc.status);
      const meta = statusMeta[status] || { label: status || 'Unknown', icon: 'fa-circle-question' };
      const createdAt = doc.created_at ? new Date(doc.created_at).toLocaleString() : 'Just now';
      const filename = escapeHtml(doc.filename || 'Untitled document');
      const errorHtml = doc.error_msg ? `<p class="artifact-error">${escapeHtml(doc.error_msg)}</p>` : '';

      let row = artifactsList.querySelector(`[data-doc-id="${CSS.escape(id)}"]`);

      if (!row) {
        // Create a new row skeleton; we'll mutate it for status/error changes later.
        row = document.createElement('article');
        row.className = 'artifact-item';
        row.setAttribute('data-doc-id', id);
        row.innerHTML = `
          <div class="artifact-icon"><i class="fas fa-file-pdf"></i></div>
          <div class="artifact-details">
            <div class="artifact-title-row">
              <h3>${filename}</h3>
              <span class="artifact-status"></span>
            </div>
            <p class="artifact-created"></p>
            <div class="artifact-error-slot"></div>
          </div>
        `;
        artifactsList.appendChild(row);
      }

      // Title (filename) rarely changes but update anyway.
      const titleEl = row.querySelector('.artifact-title-row h3');
      if (titleEl && titleEl.textContent !== (doc.filename || 'Untitled document')) {
        titleEl.textContent = doc.filename || 'Untitled document';
      }

      // Status pill
      const statusEl = row.querySelector('.artifact-status');
      const newClass = `artifact-status`;
      const newStatusClass = `status-${status}`;
      const newIcon = meta.icon;
      const newLabel = meta.label;
      // Only mutate if changed (avoids resetting CSS animations mid-spin).
      if (statusEl.dataset.status !== status) {
        statusEl.className = newStatusClass;
        statusEl.dataset.status = status;
        statusEl.innerHTML = `<i class="fas ${escapeAttr(newIcon)}"></i> ${escapeHtml(newLabel)}`;
        row.className = `artifact-item ${newStatusClass}`;
      }

      // Created timestamp
      const createdEl = row.querySelector('.artifact-created');
      if (createdEl) createdEl.textContent = createdAt;

      // Error slot
      const errorSlot = row.querySelector('.artifact-error-slot');
      if (errorSlot) {
        const currentError = errorSlot.querySelector('.artifact-error');
        const currentText = currentError ? currentError.textContent : '';
        if ((doc.error_msg || '') !== currentText) {
          errorSlot.innerHTML = errorHtml;
        }
      }
    });
  }

  function renderUploadState() {
    const file = fileInput.files[0];
    selectedFileLabel.textContent = file ? file.name : 'Upload PDF';
    uploadHint.textContent = kbSelect.value
      ? 'Choose a file for the selected knowledge base.'
      : 'Select a knowledge base to enable uploads.';
    uploadBtn.disabled = !kbSelect.value || !file;
  }

  // Polling cadence — exponential backoff while a doc is still processing,
  // reset to the base interval the moment any status changes.
  const POLL_BASE_MS = 4000;
  const POLL_MAX_MS = 30000;
  let pollIntervalMs = POLL_BASE_MS;
  let lastStatusSnapshot = '';

  function activeDocumentsList() {
    return documents.filter((doc) => (
      activeStatuses.has(normalizeStatus(doc.status)) && !String(doc.document_id).startsWith('local-')
    ));
  }

  function startPolling() {
    stopPolling();
    if (activeDocumentsList().length === 0) return;

    // Pause work when the tab is hidden — no point hammering the API in the
    // background. Resume immediately when the tab becomes visible again.
    const tick = async () => {
      if (document.hidden) {
        // Re-run soon; the visibilitychange handler below also resumes.
        pollTimer = setTimeout(tick, POLL_BASE_MS);
        return;
      }

      const activeDocuments = activeDocumentsList();
      if (activeDocuments.length === 0) {
        stopPolling();
        return;
      }

      try {
        const updates = await Promise.all(activeDocuments.map((doc) => API.getDocumentStatus(doc.document_id)));
        const snapshotBefore = JSON.stringify(documents.map((d) => [String(d.document_id), normalizeStatus(d.status)]));

        documents = documents.map((doc) => {
          const update = updates.find((item) => String(item.document_id) === String(doc.document_id));
          return update ? { ...doc, ...update } : doc;
        });
        renderArtifactList();

        const snapshotAfter = JSON.stringify(documents.map((d) => [String(d.document_id), normalizeStatus(d.status)]));
        if (snapshotBefore !== snapshotAfter) {
          // Something changed — go back to the fast interval.
          pollIntervalMs = POLL_BASE_MS;
        }

        if (activeDocumentsList().length === 0) {
          stopPolling();
          return;
        }

        // Back off exponentially (capped) until the next observation.
        pollTimer = setTimeout(tick, pollIntervalMs);
        pollIntervalMs = Math.min(pollIntervalMs * 2, POLL_MAX_MS);
      } catch (error) {
        showArtifactAlert(`Status refresh failed: ${error.message}`, 'error');
        stopPolling();
      }
    };

    pollIntervalMs = POLL_BASE_MS;
    pollTimer = setTimeout(tick, pollIntervalMs);
  }

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  // When the tab becomes visible again, jump back to the fast interval so the
  // user isn't staring at a stale "processing" badge after coming back.
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && pollTimer) {
      pollIntervalMs = POLL_BASE_MS;
    }
  });

  // Make sure no interval/timer outlives the page (avoids background fetches
  // on mobile tab-switch and any late callback into a torn-down DOM).
  window.addEventListener('beforeunload', () => {
    stopPolling();
    if (alertTimer) clearTimeout(alertTimer);
    if (currentChatController) currentChatController.abort();
  });

  function showArtifactAlert(message, type = 'success') {
    if (alertTimer) {
      clearTimeout(alertTimer);
    }
    artifactAlert.textContent = message;
    artifactAlert.className = `artifact-alert visible ${type}`;
    alertTimer = setTimeout(() => {
      artifactAlert.textContent = '';
      artifactAlert.className = 'artifact-alert';
      alertTimer = null;
    }, 4500);
  }

  function emptyArtifactHtml(message) {
    return `
      <div class="artifact-empty">
        <i class="fas fa-folder-open"></i>
        <span>${escapeHtml(message)}</span>
      </div>
    `;
  }

  function normalizeStatus(status) {
    return String(status || '').toLowerCase();
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }

  loadKBs();
});
