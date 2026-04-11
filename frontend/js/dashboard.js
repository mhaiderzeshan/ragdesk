import { API, showAlert, requireAuth } from './utils/api.js';

document.addEventListener('DOMContentLoaded', async () => {
  requireAuth();

  const logoutBtn = document.getElementById('logout-btn');
  const kbGrid = document.getElementById('kb-grid');
  const newKbBtn = document.getElementById('new-kb-btn');
  const modalOverlay = document.getElementById('kb-modal');
  const closeModal = document.getElementById('close-modal');
  const kbForm = document.getElementById('kb-form');

  logoutBtn.addEventListener('click', () => {
    API.setToken(null);
    window.location.href = 'login.html';
  });

  // Modal logic
  newKbBtn.addEventListener('click', () => modalOverlay.classList.add('active'));
  closeModal.addEventListener('click', () => modalOverlay.classList.remove('active'));
  modalOverlay.addEventListener('click', (e) => {
    if(e.target === modalOverlay) modalOverlay.classList.remove('active');
  });

  kbForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('kb-name').value;
    const desc = document.getElementById('kb-desc').value;
    
    try {
      await API.createKnowledgeBase(name, desc);
      modalOverlay.classList.remove('active');
      kbForm.reset();
      showAlert('dashboard-alert-container', 'Knowledge Base created successfully!', 'success');
      loadKnowledgeBases();
    } catch (error) {
      showAlert('dashboard-alert-container', error.message);
    }
  });

  async function loadKnowledgeBases() {
    try {
      kbGrid.innerHTML = '<div class="glass-panel card" style="opacity:0.5; align-items:center; justify-content:center; display:flex;"><i class="fas fa-spinner fa-spin"></i></div>';
      const kbs = await API.getKnowledgeBases();
      
      if (kbs.length === 0) {
        kbGrid.innerHTML = `
          <div class="glass-panel card" style="grid-column: 1 / -1; align-items: center; text-align: center; padding: 3rem;">
            <i class="fas fa-folder-open" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 1rem;"></i>
            <h3>No Knowledge Bases Found</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Create your first knowledge base to start uploading documents.</p>
            <button class="btn btn-primary" onclick="document.getElementById('new-kb-btn').click()">Create One Now</button>
          </div>
        `;
        return;
      }

      kbGrid.innerHTML = kbs.map(kb => `
        <div class="glass-panel card animate-fade-in" data-kb-id="${kb.id}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <h3 class="card-title"><i class="fas fa-book"></i> ${kb.name}</h3>
            <span class="source-badge">ID: ${kb.id.substring(0,8)}</span>
          </div>
          <p style="color: var(--text-secondary); margin-top: 10px; font-size: 0.9rem;">${kb.description || 'No description provided.'}</p>
          
          <div style="margin-top: 1.5rem; border-top: 1px solid var(--surface-border); padding-top: 1rem;">
            <label class="form-label" style="font-size: 0.8rem;">Upload Document</label>
            <div style="display: flex; gap: 8px;">
              <input type="file" id="file-${kb.id}" accept=".pdf,.txt,.docx" style="padding: 6px; font-size: 0.8rem;">
              <button class="btn btn-secondary upload-btn" data-kb-id="${kb.id}" style="padding: 6px 12px; font-size: 0.8rem;">Upload</button>
            </div>
          </div>
        </div>
      `).join('');

      // Attach upload handlers
      document.querySelectorAll('.upload-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation(); // Prevent card click event if we add one later
          const kbId = e.target.getAttribute('data-kb-id');
          const fileInput = document.getElementById(`file-${kbId}`);
          const file = fileInput.files[0];
          
          if (!file) {
            showAlert('dashboard-alert-container', 'Please select a file first.');
            return;
          }

          const originalText = e.target.innerHTML;
          e.target.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
          e.target.disabled = true;

          try {
            await API.uploadDocument(file);
            showAlert('dashboard-alert-container', `Document ${file.name} uploaded successfully!`, 'success');
            fileInput.value = '';
          } catch (error) {
            showAlert('dashboard-alert-container', `Upload failed: ${error.message}`);
          } finally {
            e.target.innerHTML = originalText;
            e.target.disabled = false;
          }
        });
      });

    } catch (error) {
      kbGrid.innerHTML = `
        <div class="alert alert-error" style="grid-column: 1 / -1;">
          Failed to load knowledge bases: ${error.message}
        </div>
      `;
    }
  }

  loadKnowledgeBases();
});
