import "./styles/style.scss";
import { loadBoard, saveBoard } from './utils/storage';
import type { Task, TaskStatus , BoardData } from './data/types';
import { exportBoard, importBoard } from './utils/exportimport';
import { renderAnalytics } from './analytics/AnalyticsPage';

const statuses: TaskStatus[] = ['todo', 'in-progress', 'done'];
const boardEl = document.getElementById('board')!;
const boardData = loadBoard();
const activeTimers = new Map<string, number>();
const activeSeconds = new Map<string, number>();

function updateTaskPriorities(tasks: Task[]) {
  const now = new Date();
  tasks.forEach(task => {
    if (!task.deadline) {
      task.priority = undefined;
      return;
    }
    const deadline = new Date(task.deadline);
    const diff = deadline.getTime() - now.getTime();
    if (diff <= 2 * 24 * 60 * 60 * 1000 && diff >= 0) {
      task.priority = 'urgent';
    } else if (diff > 3 * 24 * 60 * 60 * 1000) {
      task.priority = 'secondary';
    } else if (diff < 0) {
      task.priority = 'postpone';
    } else {
      task.priority = undefined;
    }
  });
}

function createTaskCard(task: Task): HTMLElement {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.draggable = true;
  card.dataset.id = task.id;

  card.innerHTML = `
    <div class="deadline-bar"></div>
    <strong>${task.title}</strong>
    <span>Проект: ${task.project}</span>
    <span>План: ${task.plannedMinutes} мин</span>
    <span>Выполнено: <span class="spent">${task.spentMinutes}</span> мин</span>
    <span>Срок: ${task.deadline}</span>
    <span class="timer-display"></span>
    <div class="task-buttons">
      <button class="btn small start-btn">▶ Старт</button>
      <button class="btn small add-btn">➕ Минуты</button>
      <button class="btn small delete-btn">🗑 Удалить</button>
      <button class="repeat-btn btn">
        ${task.repeat ? '✅ Повтор включен' : '🔁 Повторять'}
      </button>
      <button class="btn small pause-btn">Пауза</button>
    </div>
  `;

  const startBtn = card.querySelector('.start-btn') as HTMLButtonElement;
  const addBtn = card.querySelector('.add-btn') as HTMLButtonElement;
  const deleteBtn = card.querySelector('.delete-btn') as HTMLButtonElement;
  const timerDisplay = card.querySelector('.timer-display') as HTMLSpanElement;
  const spentSpan = card.querySelector('.spent') as HTMLSpanElement;
  const deadlineBar = card.querySelector('.deadline-bar') as HTMLDivElement;

  // Полоска слева по сроку
  const now = new Date();
  const deadline = new Date(task.deadline);
  const created = new Date(task.createdAt || task.deadline);
  const total = deadline.getTime() - created.getTime();
  const passed = now.getTime() - created.getTime();
  const ratio = total > 0 ? passed / total : 0;

  if (ratio < 0.5) {
    deadlineBar.style.backgroundColor = 'var(--green)';
  } else if (ratio < 0.9) {
    deadlineBar.style.backgroundColor = 'var(--yellow)';
  } else {
    deadlineBar.style.backgroundColor = 'var(--red)';
  }

  // Отображение текста на кнопке
  if (task.status === 'in-progress') {
    startBtn.textContent = '✔ Завершить';
  } else {
    startBtn.textContent = '▶ Старт';
  }

  // Удаление задачи
  deleteBtn.addEventListener('click', () => {
    if (confirm('Удалить эту задачу?')) {
      const index = boardData.tasks.findIndex(t => t.id === task.id);
      if (index !== -1) {
        boardData.tasks.splice(index, 1);
        saveBoard(boardData);
        renderBoard();
      }
    }
  });

  // Добавление минут вручную
  addBtn.addEventListener('click', () => {
    const input = prompt('Сколько минут добавить?');
    const extra = Number(input);
    if (!isNaN(extra) && extra > 0) {
      task.spentMinutes += extra;
      spentSpan.textContent = task.spentMinutes.toString();
      saveBoard(boardData);
      alert(`Добавлено ${extra} минут.`);
    } else {
      alert('Введите корректное число минут.');
    }
  });

  const pauseBtn = card.querySelector('.pause-btn') as HTMLButtonElement;
  pauseBtn.style.display = task.status === 'in-progress' ? 'inline-block' : 'none';

  let isPaused = false;

  pauseBtn.addEventListener('click', () => {
    const intervalId = activeTimers.get(task.id);
    const secondsElapsed = activeSeconds.get(task.id) ?? 0;

    if (!isPaused) {
      if (intervalId !== undefined) {
        clearInterval(intervalId);
        activeTimers.delete(task.id);
      }
      task.startTime = undefined;
      timerDisplay.textContent = `⏸ На паузе (${secondsElapsed} сек)`;
      pauseBtn.textContent = '▶️ Возобновить';
      isPaused = true;
    } else {
      task.startTime = Date.now();
      startTimer(task, spentSpan, timerDisplay);
      pauseBtn.textContent = '⏸ Пауза';
      isPaused = false;
    }

    saveBoard(boardData);
  });

  // Обработка кнопки "Повторять"
  const repeatBtn = card.querySelector('.repeat-btn') as HTMLButtonElement;
  repeatBtn.addEventListener('click', () => {
    if (task.repeat) {
      if (confirm('Отключить повторение задачи?')) {
        task.repeat = false;
        task.repeatInterval = undefined;
        saveBoard(boardData);
        renderBoard();
        return;
      }
    } else {
      const interval = prompt(
        'Выберите интервал повторения:\n- daily (ежедневно)\n- weekly (еженедельно)\n- monthly (ежемесячно)',
        task.repeatInterval || 'daily'
      );
      if (!interval || !['daily', 'weekly', 'monthly'].includes(interval)) {
        alert('Некорректный интервал!');
        return;
      }
      task.repeat = true;
      task.repeatInterval = interval;
      saveBoard(boardData);
      renderBoard();
    }
  });

  // Если завершена
  if (task.status === 'done') {
    timerDisplay.textContent = `✅ Выполнено за ${task.spentMinutes} мин`;
    startBtn.remove();
    addBtn.remove();
    return card;
  }

  // Продолжаем таймер
  if (task.startTime && task.status === 'in-progress') {
    const secondsElapsed = Math.floor((Date.now() - task.startTime) / 1000);
    activeSeconds.set(task.id, secondsElapsed);
    timerDisplay.textContent = `⏱ ${secondsElapsed} сек`;
    spentSpan.textContent = task.spentMinutes.toString();
    startTimer(task, spentSpan, timerDisplay);
  }

  // Обработка нажатия "Старт" или "Завершить"
  startBtn.addEventListener('click', () => {
    if (task.status === 'todo') {
      task.status = 'in-progress';
      task.startTime = Date.now();
      activeSeconds.set(task.id, 0);
      saveBoard(boardData);
      startTimer(task, spentSpan, timerDisplay);
      renderBoard();
      return;
    }

    if (task.status === 'in-progress') {
      const confirmed = confirm('Завершить задачу?');
      if (!confirmed) return;

      const intervalId = activeTimers.get(task.id);
      if (intervalId !== undefined) {
        clearInterval(intervalId);
        activeTimers.delete(task.id);
        const secondsElapsed = activeSeconds.get(task.id) ?? 0;
        task.spentMinutes += Math.floor(secondsElapsed / 60);
        activeSeconds.delete(task.id);
      }

      task.startTime = undefined;

      // Если задача повторяющаяся — обновляем дедлайн и возвращаем в todo
      if (task.repeat && task.repeatInterval) {
        const currentDeadline = new Date(task.deadline);
        switch (task.repeatInterval) {
          case 'daily':
            currentDeadline.setDate(currentDeadline.getDate() + 1);
            break;
          case 'weekly':
            currentDeadline.setDate(currentDeadline.getDate() + 7);
            break;
          case 'monthly':
            currentDeadline.setMonth(currentDeadline.getMonth() + 1);
            break;
        }
        task.deadline = currentDeadline.toISOString().split('T')[0];
        task.status = 'todo';
        task.spentMinutes = 0;
      } else {
        task.status = 'done';
      }

      saveBoard(boardData);
      renderBoard();
    }
  });

  // Если вручную вернули обратно в "todo"
  if (task.status === 'todo') {
    const intervalId = activeTimers.get(task.id);
    if (intervalId !== undefined) {
      clearInterval(intervalId);
      activeTimers.delete(task.id);
    }
    activeSeconds.delete(task.id);
    task.startTime = undefined;
    startBtn.textContent = '▶ Старт';
    timerDisplay.textContent = '';
    spentSpan.textContent = task.spentMinutes.toString();
  }

  return card;
}

function startTimer(task: Task, spentSpan: HTMLElement, timerDisplay: HTMLElement) {
  const taskId = task.id;
  let seconds = activeSeconds.get(taskId) ?? 0;
  if (!task.startTime) task.startTime = Date.now();
  timerDisplay.textContent = `⏱ ${seconds} сек`;

  const interval = window.setInterval(() => {
    seconds++;
    activeSeconds.set(taskId, seconds);
    timerDisplay.textContent = `⏱ ${seconds} сек`;
    if (seconds % 60 === 0) {
      task.spentMinutes += 1;
      spentSpan.textContent = task.spentMinutes.toString();
    }
    saveBoard(boardData);
  }, 1000);

  activeTimers.set(taskId, interval);
  saveBoard(boardData);
}

function renderBoard() {
  updateTaskPriorities(boardData.tasks); 
  boardEl.innerHTML = '';
  statuses.forEach(status => {
    const column = document.createElement('div');
    column.className = 'kanban-column';
    column.dataset.status = status;
    column.innerHTML = `<h3>${getStatusName(status)}</h3>`;
    const container = document.createElement('div');
    container.className = 'kanban-tasks';

    column.addEventListener('dragover', (e) => {
      e.preventDefault();
      column.classList.add('drag-over');
    });
    column.addEventListener('dragleave', () => {
      column.classList.remove('drag-over');
    });
    column.addEventListener('drop', (e) => {
      column.classList.remove('drag-over');
      onDrop(e, status);
    });

    boardData.tasks
      .filter(task => task.status === status)
      .forEach(task => {
        const card = createTaskCard(task);
        card.addEventListener('dragstart', onDragStart);
        container.appendChild(card);
      });

    column.appendChild(container);
    boardEl.appendChild(column);
  });
}

function onDragStart(e: DragEvent) {
  const target = e.target as HTMLElement;
  if (target?.dataset?.id) {
    e.dataTransfer?.setData('text/plain', target.dataset.id);
  }
}

function onDrop(e: DragEvent, newStatus: TaskStatus) {
  e.preventDefault();
  const taskId = e.dataTransfer?.getData('text/plain');
  if (!taskId) return;

  const task = boardData.tasks.find(t => t.id === taskId);
  if (!task) return;

  task.status = newStatus;

  if (newStatus === 'done') {
    const intervalId = activeTimers.get(taskId);
    if (intervalId !== undefined) {
      clearInterval(intervalId);
      activeTimers.delete(taskId);
      const secondsElapsed = activeSeconds.get(taskId) ?? 0;
      task.spentMinutes += Math.floor(secondsElapsed / 60);
      activeSeconds.delete(taskId);
    }
    if (task.startTime) {
      const extra = Math.floor((Date.now() - task.startTime) / 1000);
      task.spentMinutes += Math.floor(extra / 60);
      task.startTime = undefined;
    }
  }

  saveBoard(boardData);

  renderBoard();
}

function getStatusName(status: TaskStatus): string {
  switch (status) {
    case 'todo': return 'Запланировано';
    case 'in-progress': return 'В процессе';
    case 'done': return 'Готово';
  }
}

const form = document.getElementById('task-form') as HTMLFormElement;
form?.addEventListener('submit', (e) => {
  e.preventDefault();
  const titleInput = document.getElementById('task-title') as HTMLInputElement;
  const projectInput = document.getElementById('task-project') as HTMLInputElement;
  const minutesInput = document.getElementById('task-minutes') as HTMLInputElement;
  const deadlineInput = document.getElementById('task-deadline') as HTMLInputElement;

  const title = titleInput.value.trim();
  const project = projectInput.value.trim();
  const plannedMinutes = parseInt(minutesInput.value);
  const deadline = deadlineInput.value;

  if (!title || !project || !deadline || isNaN(plannedMinutes)) {
    alert("Пожалуйста, заполните все поля.");
    return;
  }

  const newTask: Task = {
    id: Date.now().toString(),
    title,
    project,
    plannedMinutes,
    spentMinutes: 0,
    deadline,
    status: 'todo'
  };

  boardData.tasks.push(newTask);
  saveBoard(boardData);
  renderBoard();
  form.reset();
});

if (boardData.tasks.length === 0) {
  boardData.tasks.push({
    id: '1',
    title: 'Написать Kanban',
    project: 'FocusBoard',
    plannedMinutes: 90,
    spentMinutes: 0,
    deadline: new Date().toISOString().split('T')[0],
    status: 'todo'
  });
  saveBoard(boardData);
}
renderBoard();

const themeToggle = document.getElementById('theme-toggle')!;
const root = document.documentElement;
const savedTheme = localStorage.getItem('theme');
if (savedTheme) root.setAttribute('data-theme', savedTheme);
themeToggle.addEventListener('click', () => {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
});

// Импорт / экспорт
document.getElementById('export-btn')?.addEventListener('click', () => exportBoard());
document.getElementById('import-btn')?.addEventListener('click', () => {
  const input = document.getElementById('import-input') as HTMLInputElement;
  input.click();
});
document.getElementById('import-input')?.addEventListener('change', () => {
  const file = (document.getElementById('import-input') as HTMLInputElement).files?.[0];
  if (!file) return;
  importBoard(file)
    .then(() => {
      alert('Импорт завершён.');
      renderBoard();
    })
    .catch(() => alert('Ошибка при импорте.'));
});

// Аналитика и переключатели
const analyticsBtn = document.getElementById("analytics-btn") as HTMLButtonElement;
const kanbanBtn = document.getElementById("kanban-btn") as HTMLButtonElement;
const taskForm = document.getElementById("task-form") as HTMLElement;
const analyticsContainer = document.getElementById("analytics") as HTMLElement;
const sectionTasksSection = document.getElementById("section-tasks")!;
const boardSection = document.getElementById("board")!;

analyticsBtn.addEventListener("click", () => {
  boardSection.style.display = "none";
  analyticsContainer.style.display = "flex";
  sectionTasksSection.style.display = "none";
  taskForm.style.display = "none";
  renderAnalytics(boardData);
});
kanbanBtn.addEventListener("click", () => {
  boardSection.style.display = "flex";
  analyticsContainer.style.display = "none";
  sectionTasksSection.style.display = "none";
  taskForm.style.display = "flex";
  renderBoard();
});

document.querySelectorAll('.section-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const section = (btn as HTMLButtonElement).dataset.section!;
    boardSection.style.display = 'none';
    analyticsContainer.style.display = 'none';
    taskForm.style.display = 'none';
    sectionTasksSection.style.display = 'block';
    renderSectionTasks(section);
  });
});

function renderSectionTasks(section: string) {
  let filtered: Task[];
  if (section === 'repeat') {
    filtered = boardData.tasks.filter(task => task.repeat);
  } else {
    updateTaskPriorities(boardData.tasks);
    filtered = boardData.tasks.filter(task => task.priority === section);
  }
  sectionTasksSection.innerHTML = `
    <h2 class="section-title">${getSectionTitle(section)}</h2>
    <button id="back-to-board" class="btn" style="margin-bottom:20px;">← Назад к доске</button>
    ${filtered.map(renderTaskCardHTML).join('') || '<p>Нет задач в этом разделе.</p>'}
  `;
  document.getElementById('back-to-board')?.addEventListener('click', () => {
    sectionTasksSection.style.display = 'none';
    boardSection.style.display = 'flex';
    taskForm.style.display = 'flex';
    renderBoard();
  });
}

function getSectionTitle(section: string): string {
  switch (section) {
    case 'urgent': return '⚡ Срочные задачи';
    case 'secondary': return '📌 Второстепенные задачи';
    case 'postpone': return '🕒 Перенести на потом';
    case 'repeat': return '🔁 Повторяющиеся задачи';
    default: return '';
  }
}

function renderTaskCardHTML(task: Task): string {
  return `
    <div class="task-card">
      <strong>${task.title}</strong>
      <span>Проект: ${task.project}</span>
      <span>Минут: ${task.plannedMinutes}</span>
      <span>Дедлайн: ${task.deadline}</span>
      ${task.repeat ? `<span>Следующее появление: ${task.deadline}</span>` : ''}
      <button class="repeat-btn" data-task-id="${task.id}">
        ${task.repeat ? '🔁 Повторяется' : '↻ Повторять'}
      </button>
    </div>
  `;
}

// PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('✅ Service Worker зарегистрирован:', reg.scope))
      .catch(err => console.error('❌ Ошибка регистрации SW:', err));
  });
}