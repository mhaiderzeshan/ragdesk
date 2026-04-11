import { API, showAlert } from './utils/api.js';

let isLoginMode = true;

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const toggleBtn = document.getElementById('toggle-auth-mode');
  const submitBtn = form.querySelector('button[type="submit"]');
  const orgNameGroup = document.getElementById('org-name-group');
  
  // If already logged in, redirect to dashboard
  if (API.getToken()) {
    window.location.href = 'index.html';
  }

  toggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    isLoginMode = !isLoginMode;
    submitBtn.innerHTML = isLoginMode ? 'Sign In <i class="fas fa-arrow-right"></i>' : 'Sign Up <i class="fas fa-user-plus"></i>';
    toggleBtn.textContent = isLoginMode ? 'Sign up' : 'Sign in back';
    e.target.parentElement.childNodes[0].nodeValue = isLoginMode ? "Don't have an account? " : "Already have an account? ";
    orgNameGroup.style.display = isLoginMode ? 'none' : 'block';
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = form.username.value;
    const password = form.password.value;
    const orgName = form['org-name'].value;

    const originalBtnHtml = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    submitBtn.disabled = true;

    try {
      if (isLoginMode) {
        await API.login(username, password);
        window.location.href = 'index.html';
      } else {
        if (!orgName.trim()) {
          showAlert('auth-alert-container', 'Organization name is required.');
          return;
        }
        await API.register(username, password, orgName);
        showAlert('auth-alert-container', 'Registration successful! Please sign in.', 'success');
        isLoginMode = true;
        submitBtn.innerHTML = 'Sign In <i class="fas fa-arrow-right"></i>';
        toggleBtn.textContent = 'Sign up';
        toggleBtn.parentElement.childNodes[0].nodeValue = "Don't have an account? ";
        orgNameGroup.style.display = 'none';
        form.password.value = '';
        form['org-name'].value = '';
      }
    } catch (error) {
      showAlert('auth-alert-container', error.message);
      submitBtn.innerHTML = originalBtnHtml;
    } finally {
      submitBtn.disabled = false;
    }
  });
});
