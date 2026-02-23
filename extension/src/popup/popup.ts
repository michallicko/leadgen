import { login, logout, getAuthState, storeAuthState } from '../common/auth';
import { getStatus } from '../common/api-client';
import { config } from '../common/config';
import type { AuthState } from '../common/types';

// --------------- DOM Elements ---------------
const header = document.getElementById('header') as HTMLDivElement;
const loginView = document.getElementById('login-view') as HTMLDivElement;
const namespaceView = document.getElementById('namespace-view') as HTMLDivElement;
const connectedView = document.getElementById('connected-view') as HTMLDivElement;
const loginForm = document.getElementById('login-form') as HTMLFormElement;
const emailInput = document.getElementById('email') as HTMLInputElement;
const passwordInput = document.getElementById('password') as HTMLInputElement;
const loginBtn = document.getElementById('login-btn') as HTMLButtonElement;
const loginError = document.getElementById('login-error') as HTMLDivElement;
const envBadge = document.getElementById('env-badge') as HTMLSpanElement;
const namespaceSelect = document.getElementById('namespace-select') as HTMLSelectElement;
const namespaceConfirm = document.getElementById('namespace-confirm') as HTMLButtonElement;
const userEmail = document.getElementById('user-email') as HTMLSpanElement;
const leadCount = document.getElementById('lead-count') as HTMLDivElement;
const activityCount = document.getElementById('activity-count') as HTMLDivElement;
const syncBtn = document.getElementById('sync-btn') as HTMLButtonElement;
const logoutBtn = document.getElementById('logout-btn') as HTMLButtonElement;
const syncStatus = document.getElementById('sync-status') as HTMLDivElement;

// --------------- Environment Badge ---------------
if (config.environment === 'staging') {
  envBadge.textContent = 'STAGING';
  envBadge.classList.remove('hidden');
  header.classList.add('staging');
}

// --------------- View Management ---------------
function showView(view: 'login' | 'namespace' | 'connected'): void {
  loginView.classList.toggle('hidden', view !== 'login');
  namespaceView.classList.toggle('hidden', view !== 'namespace');
  connectedView.classList.toggle('hidden', view !== 'connected');
}

async function showConnected(state: AuthState): Promise<void> {
  userEmail.textContent = state.user.email;
  showView('connected');

  try {
    const status = await getStatus();
    leadCount.textContent = String(status.total_leads_imported);
    activityCount.textContent = String(status.total_activities_synced);
  } catch {
    leadCount.textContent = '\u2014';
    activityCount.textContent = '\u2014';
  }
}

function showNamespacePicker(state: AuthState): void {
  // Clear existing options
  while (namespaceSelect.firstChild) {
    namespaceSelect.removeChild(namespaceSelect.firstChild);
  }
  for (const ns of Object.keys(state.user.roles)) {
    const opt = document.createElement('option');
    opt.value = ns;
    opt.textContent = ns;
    namespaceSelect.appendChild(opt);
  }
  showView('namespace');
}

// --------------- Initialization ---------------
async function init(): Promise<void> {
  const state = await getAuthState();
  if (state && state.namespace) {
    await showConnected(state);
  } else if (state && !state.namespace) {
    showNamespacePicker(state);
  } else {
    showView('login');
  }
}

// --------------- Login Handler ---------------
loginForm.addEventListener('submit', async (e: SubmitEvent) => {
  e.preventDefault();
  loginBtn.disabled = true;
  loginError.classList.add('hidden');

  try {
    const state = await login(emailInput.value, passwordInput.value);
    if (!state.namespace) {
      showNamespacePicker(state);
    } else {
      await showConnected(state);
    }
  } catch (err: unknown) {
    loginError.textContent = err instanceof Error ? err.message : 'Login failed';
    loginError.classList.remove('hidden');
  } finally {
    loginBtn.disabled = false;
  }
});

// --------------- Namespace Confirm ---------------
namespaceConfirm.addEventListener('click', async () => {
  const state = await getAuthState();
  if (!state) return;
  const updated: AuthState = { ...state, namespace: namespaceSelect.value };
  await storeAuthState(updated);
  await showConnected(updated);
});

// --------------- Sync Button ---------------
syncBtn.addEventListener('click', () => {
  syncStatus.textContent = 'Syncing activities...';
  chrome.runtime.sendMessage(
    { type: 'sync_activities' },
    (response?: { success: boolean; created?: number; error?: string }) => {
      if (chrome.runtime.lastError) {
        syncStatus.textContent = 'Sync failed: ' + chrome.runtime.lastError.message;
        return;
      }
      if (response?.success) {
        syncStatus.textContent = `Synced: ${response.created ?? 0} new activities`;
        // Refresh stats
        getStatus()
          .then((status) => {
            leadCount.textContent = String(status.total_leads_imported);
            activityCount.textContent = String(status.total_activities_synced);
          })
          .catch(() => {});
      } else {
        syncStatus.textContent = response?.error || 'Sync failed';
      }
    },
  );
});

// --------------- Logout Button ---------------
logoutBtn.addEventListener('click', async () => {
  await logout();
  showView('login');
  syncStatus.textContent = '';
});

// --------------- Start ---------------
init();
