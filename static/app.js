// State
let authToken = localStorage.getItem('authToken');
let currentSalon = null;
let currentTask = null;
let salons = [];
let tasks = [];

// API helpers
async function apiRequest(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    logout();
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Request failed');
  }

  return response.json();
}

// Auth functions
async function login(username, password) {
  try {
    const data = await apiRequest('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    authToken = data.token;
    localStorage.setItem('authToken', authToken);
    showSalonsPage();
  } catch (error) {
    document.getElementById('loginError').textContent = error.message;
    document.getElementById('loginError').classList.remove('hidden');
  }
}

function logout() {
  authToken = null;
  localStorage.removeItem('authToken');
  showLoginPage();
}

// Page navigation
function hideAllPages() {
  document.getElementById('loginPage').classList.add('hidden');
  document.getElementById('salonsPage').classList.add('hidden');
  document.getElementById('salonDetailPage').classList.add('hidden');
  document.getElementById('salonFormPage').classList.add('hidden');
  document.getElementById('taskFormPage').classList.add('hidden');
}

function showLoginPage() {
  hideAllPages();
  document.getElementById('loginPage').classList.remove('hidden');
}

async function showSalonsPage() {
  hideAllPages();
  document.getElementById('salonsPage').classList.remove('hidden');
  await loadSalons();
  const stats = await loadStats();
  renderDashboard(stats);
  renderSalons();
}

async function showSalonDetailPage(salonId) {
  currentSalon = salons.find(s => s.id === salonId);
  if (!currentSalon) return;

  hideAllPages();
  document.getElementById('salonDetailPage').classList.remove('hidden');
  document.getElementById('currentSalonName').textContent = currentSalon.name;
  document.getElementById('salonTitle').textContent = currentSalon.name;
  document.getElementById('salonSubtitle').textContent = `Année ${currentSalon.year}${currentSalon.description ? ' - ' + currentSalon.description : ''}`;

  await loadSalonTasks(salonId);
  renderTasks();
}

function showSalonFormPage(salonId = null) {
  currentSalon = salonId ? salons.find(s => s.id === salonId) : null;

  hideAllPages();
  document.getElementById('salonFormPage').classList.remove('hidden');

  if (currentSalon) {
    document.getElementById('salonFormTitle').textContent = 'Éditer le salon';
    document.getElementById('salonFormHeading').textContent = 'Éditer le salon';
    document.getElementById('salonName').value = currentSalon.name;
    document.getElementById('salonYear').value = currentSalon.year;
    document.getElementById('salonDescription').value = currentSalon.description || '';
    document.getElementById('deleteSalonBtn').classList.remove('hidden');
  } else {
    document.getElementById('salonFormTitle').textContent = 'Nouveau Salon';
    document.getElementById('salonFormHeading').textContent = 'Créer un nouveau salon';
    document.getElementById('salonForm').reset();
    document.getElementById('deleteSalonBtn').classList.add('hidden');
  }
}

function showTaskFormPage(taskId = null) {
  currentTask = taskId ? tasks.find(t => t.id === taskId) : null;

  hideAllPages();
  document.getElementById('taskFormPage').classList.remove('hidden');

  // Populate parent task dropdown
  const parentSelect = document.getElementById('parentTask');
  parentSelect.innerHTML = '<option value="">Aucune (tâche principale)</option>';

  // Only show top-level tasks as potential parents (no subtasks)
  const topLevelTasks = tasks.filter(t => !t.parent_task_id && (!currentTask || t.id !== currentTask.id));
  topLevelTasks.forEach(task => {
    const option = document.createElement('option');
    option.value = task.id;
    option.textContent = task.name;
    parentSelect.appendChild(option);
  });

  if (currentTask) {
    document.getElementById('taskFormTitle').textContent = 'Éditer la tâche';
    document.getElementById('taskFormHeading').textContent = 'Éditer la tâche';
    document.getElementById('taskName').value = currentTask.name;
    document.getElementById('parentTask').value = currentTask.parent_task_id || '';
    document.getElementById('taskPriority').value = currentTask.priority;
    document.getElementById('taskDeadline').value = currentTask.deadline || '';
    document.getElementById('taskDescription').value = currentTask.description || '';
    document.getElementById('taskUrls').value = currentTask.urls || '';
    document.getElementById('deleteTaskBtn').classList.remove('hidden');
  } else {
    document.getElementById('taskFormTitle').textContent = 'Nouvelle Tâche';
    document.getElementById('taskFormHeading').textContent = 'Créer une nouvelle tâche';
    document.getElementById('taskForm').reset();
    document.getElementById('deleteTaskBtn').classList.add('hidden');
  }
}

// Data loading
async function loadSalons() {
  try {
    salons = await apiRequest('/api/salons');
  } catch (error) {
    console.error('Error loading salons:', error);
    salons = [];
  }
}

async function loadStats() {
  try {
    return await apiRequest('/api/stats');
  } catch (error) {
    console.error('Error loading stats:', error);
    return null;
  }
}

async function loadSalonTasks(salonId) {
  try {
    tasks = await apiRequest(`/api/salons/${salonId}/tasks`);
  } catch (error) {
    console.error('Error loading tasks:', error);
    tasks = [];
  }
}

// Rendering
function renderDashboard(stats) {
  const container = document.getElementById('dashboard');

  if (!stats) {
    container.innerHTML = '';
    return;
  }

  const overviewHTML = `
    <div class="dashboard-overview">
      <div class="stat-card">
        <div class="stat-value">${stats.total_salons}</div>
        <div class="stat-label">Salons</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.total_tasks}</div>
        <div class="stat-label">Tâches totales</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${stats.incomplete_tasks}</div>
        <div class="stat-label">Tâches en cours</div>
      </div>
      ${stats.urgent_tasks > 0 ? `
        <div class="stat-card urgent">
          <div class="stat-value">${stats.urgent_tasks}</div>
          <div class="stat-label">Tâches urgentes</div>
        </div>
      ` : ''}
      ${stats.upcoming_deadlines > 0 ? `
        <div class="stat-card warning">
          <div class="stat-value">${stats.upcoming_deadlines}</div>
          <div class="stat-label">Échéances (7 jours)</div>
        </div>
      ` : ''}
    </div>
  `;

  const salonsHTML = stats.salons && stats.salons.length > 0 ? `
    <div class="dashboard-salons">
      <h3>Aperçu par salon</h3>
      ${stats.salons.map(salon => {
        const hasUrgent = salon.urgent_tasks > 0;
        const hasUpcoming = !hasUrgent && salon.upcoming_tasks > 0;
        const cardClass = hasUrgent ? 'has-urgent' : hasUpcoming ? 'has-upcoming' : '';

        return `
          <div class="salon-stat-card ${cardClass}" onclick="showSalonDetailPage(${salon.id})">
            <div class="salon-stat-info">
              <div class="salon-stat-name">${salon.name}</div>
              <div class="salon-stat-year">${salon.year}</div>
            </div>
            <div class="salon-stat-badges">
              ${salon.incomplete_tasks > 0 ? `<span class="salon-stat-badge">${salon.incomplete_tasks} en cours</span>` : ''}
              ${salon.urgent_tasks > 0 ? `<span class="salon-stat-badge urgent">${salon.urgent_tasks} urgent${salon.urgent_tasks > 1 ? 's' : ''}</span>` : ''}
              ${salon.upcoming_tasks > 0 && salon.urgent_tasks === 0 ? `<span class="salon-stat-badge upcoming">${salon.upcoming_tasks} à venir</span>` : ''}
            </div>
          </div>
        `;
      }).join('')}
    </div>
  ` : '';

  container.innerHTML = overviewHTML + salonsHTML;
}

function renderSalons() {
  const container = document.getElementById('salonsList');

  if (salons.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--muted); padding: 40px;">Aucun salon. Créez-en un pour commencer !</p>';
    return;
  }

  container.innerHTML = salons.map(salon => `
    <div class="salon-card" onclick="showSalonDetailPage(${salon.id})">
      <div class="salon-year">${salon.year}</div>
      <div class="salon-name">${salon.name}</div>
      ${salon.description ? `<div class="salon-desc">${salon.description}</div>` : ''}
    </div>
  `).join('');
}

function calculateDeadlineAlert(deadline) {
  if (!deadline) return null;

  const now = new Date();
  const deadlineDate = new Date(deadline);
  const daysUntil = Math.ceil((deadlineDate - now) / (1000 * 60 * 60 * 24));

  if (daysUntil < 0) return 'urgent'; // Passed
  if (daysUntil <= 1) return 'urgent'; // Today or tomorrow
  if (daysUntil <= 7) return 'soon'; // Within a week
  if (daysUntil <= 30) return 'upcoming'; // Within a month

  return null;
}

function formatDeadline(deadline) {
  if (!deadline) return '';

  const deadlineDate = new Date(deadline);
  const now = new Date();
  const daysUntil = Math.ceil((deadlineDate - now) / (1000 * 60 * 60 * 24));

  if (daysUntil < 0) return `⚠️ Échéance dépassée de ${Math.abs(daysUntil)} jour(s)`;
  if (daysUntil === 0) return `🔴 Aujourd'hui`;
  if (daysUntil === 1) return `🔴 Demain`;
  if (daysUntil <= 7) return `🟡 Dans ${daysUntil} jours`;
  if (daysUntil <= 30) return `📅 Dans ${daysUntil} jours`;

  return `📅 ${deadlineDate.toLocaleDateString('fr-FR')}`;
}

function renderTasks() {
  const container = document.getElementById('tasksList');

  // Organize tasks: top-level tasks with their subtasks
  const topLevelTasks = tasks.filter(t => !t.parent_task_id);

  if (topLevelTasks.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--muted); padding: 40px;">Aucune tâche. Créez-en une pour commencer !</p>';
    return;
  }

  container.innerHTML = topLevelTasks.map(task => {
    const subtasks = tasks.filter(t => t.parent_task_id === task.id);
    const alert = calculateDeadlineAlert(task.deadline);
    const alertClass = alert === 'urgent' ? 'alert-urgent' : alert === 'soon' ? 'alert-soon' : '';

    return `
      <div class="task-item ${task.completed ? 'completed' : ''} ${task.deadline ? 'has-deadline' : ''} ${alertClass}">
        <div class="task-header">
          <input type="checkbox" class="task-checkbox" ${task.completed ? 'checked' : ''}
                 onchange="toggleTaskComplete(${task.id}, this.checked)">
          <div class="task-content">
            <div class="task-main">
              <div class="task-title-row">
                <div class="task-name ${task.completed ? 'completed' : ''}" onclick="showTaskFormPage(${task.id})">
                  ${task.name}
                </div>
                <div class="task-meta">
                  <span class="priority-badge priority-${task.priority}">Priorité ${task.priority}</span>
                  ${task.deadline ? `<span class="deadline-badge">${formatDeadline(task.deadline)}</span>` : ''}
                </div>
              </div>
              ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
              ${task.urls ? `<div class="task-urls">
                ${task.urls.split('\n').filter(u => u.trim()).map(url =>
                  `<a href="${url.trim()}" target="_blank" class="task-url-link">${url.trim()}</a>`
                ).join('')}
              </div>` : ''}
            </div>
          </div>
        </div>

        ${subtasks.length > 0 ? `
          <div class="subtasks">
            ${subtasks.map(subtask => `
              <div class="subtask-item ${subtask.completed ? 'completed' : ''}">
                <div style="display: flex; gap: 12px; align-items: start;">
                  <input type="checkbox" ${subtask.completed ? 'checked' : ''}
                         onchange="toggleTaskComplete(${subtask.id}, this.checked)"
                         style="margin-top: 3px; flex-shrink: 0; width: 16px; height: 16px;">
                  <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 500; font-size: 14px; ${subtask.completed ? 'text-decoration: line-through;' : ''}"
                         onclick="showTaskFormPage(${subtask.id})" style="cursor: pointer; margin-bottom: 4px;">
                      ${subtask.name}
                    </div>
                    ${subtask.description ? `<div style="color: var(--muted); font-size: 13px; margin-top: 6px; line-height: 1.5; white-space: pre-wrap;">${subtask.description}</div>` : ''}
                    ${subtask.urls ? `<div style="margin-top: 8px; display: flex; flex-direction: column; gap: 4px;">
                      ${subtask.urls.split('\n').filter(u => u.trim()).map(url =>
                        `<a href="${url.trim()}" target="_blank" class="task-url-link">${url.trim()}</a>`
                      ).join('')}
                    </div>` : ''}
                    ${subtask.deadline ? `<div style="font-size: 11px; margin-top: 8px; color: var(--muted);">${formatDeadline(subtask.deadline)}</div>` : ''}
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

// Actions
async function toggleTaskComplete(taskId, completed) {
  try {
    await apiRequest(`/api/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ completed }),
    });

    const task = tasks.find(t => t.id === taskId);
    if (task) task.completed = completed;

    renderTasks();
  } catch (error) {
    alert('Erreur lors de la mise à jour de la tâche');
    console.error(error);
  }
}

async function createOrUpdateSalon(event) {
  event.preventDefault();

  const name = document.getElementById('salonName').value;
  const year = parseInt(document.getElementById('salonYear').value);
  const description = document.getElementById('salonDescription').value;

  try {
    if (currentSalon) {
      await apiRequest(`/api/salons/${currentSalon.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name, year, description }),
      });
    } else {
      await apiRequest('/api/salons', {
        method: 'POST',
        body: JSON.stringify({ name, year, description }),
      });
    }

    showSalonsPage();
  } catch (error) {
    alert('Erreur : ' + error.message);
  }
}

async function deleteSalon() {
  if (!currentSalon) return;
  if (!confirm(`Supprimer le salon "${currentSalon.name}" et toutes ses tâches ?`)) return;

  try {
    await apiRequest(`/api/salons/${currentSalon.id}`, {
      method: 'DELETE',
    });

    showSalonsPage();
  } catch (error) {
    alert('Erreur : ' + error.message);
  }
}

async function createOrUpdateTask(event) {
  event.preventDefault();

  const name = document.getElementById('taskName').value;
  const parent_task_id = document.getElementById('parentTask').value || null;
  const priority = parseInt(document.getElementById('taskPriority').value);
  const deadline = document.getElementById('taskDeadline').value || null;
  const description = document.getElementById('taskDescription').value;
  const urls = document.getElementById('taskUrls').value;

  try {
    if (currentTask) {
      await apiRequest(`/api/tasks/${currentTask.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name, description, urls, priority, deadline }),
      });
    } else {
      await apiRequest('/api/tasks', {
        method: 'POST',
        body: JSON.stringify({
          salon_id: currentSalon.id,
          parent_task_id: parent_task_id ? parseInt(parent_task_id) : null,
          name,
          description,
          urls,
          priority,
          deadline,
        }),
      });
    }

    showSalonDetailPage(currentSalon.id);
  } catch (error) {
    alert('Erreur : ' + error.message);
  }
}

async function deleteTask() {
  if (!currentTask) return;
  if (!confirm(`Supprimer la tâche "${currentTask.name}" ?`)) return;

  try {
    await apiRequest(`/api/tasks/${currentTask.id}`, {
      method: 'DELETE',
    });

    showSalonDetailPage(currentSalon.id);
  } catch (error) {
    alert('Erreur : ' + error.message);
  }
}

// Event listeners
document.getElementById('loginForm').addEventListener('submit', (e) => {
  e.preventDefault();
  document.getElementById('loginError').classList.add('hidden');
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  login(username, password);
});

document.getElementById('logoutBtn').addEventListener('click', logout);
document.getElementById('newSalonBtn').addEventListener('click', () => showSalonFormPage());
document.getElementById('backToSalons').addEventListener('click', (e) => {
  e.preventDefault();
  showSalonsPage();
});
document.getElementById('newTaskBtn').addEventListener('click', () => showTaskFormPage());
document.getElementById('editSalonBtn').addEventListener('click', () => showSalonFormPage(currentSalon.id));

document.getElementById('cancelSalonForm').addEventListener('click', (e) => {
  e.preventDefault();
  showSalonsPage();
});
document.getElementById('cancelSalonFormBtn').addEventListener('click', () => showSalonsPage());
document.getElementById('salonForm').addEventListener('submit', createOrUpdateSalon);
document.getElementById('deleteSalonBtn').addEventListener('click', deleteSalon);

document.getElementById('backToSalonFromTask').addEventListener('click', (e) => {
  e.preventDefault();
  showSalonDetailPage(currentSalon.id);
});
document.getElementById('cancelTaskFormBtn').addEventListener('click', () => showSalonDetailPage(currentSalon.id));
document.getElementById('taskForm').addEventListener('submit', createOrUpdateTask);
document.getElementById('deleteTaskBtn').addEventListener('click', deleteTask);

// Initialize
async function init() {
  if (authToken) {
    try {
      await loadSalons();
      showSalonsPage();
    } catch (error) {
      localStorage.removeItem('authToken');
      authToken = null;
      showLoginPage();
    }
  } else {
    showLoginPage();
  }
}

init();
