// app.js

// ── WebSocket Manager (Real-Time Push) ──────────────────────────────────
let socket = null;
let reconnectInterval = 5000;

function startWebSocketConnection() {
    // WebSocket is not supported on Vercel serverless.
    // Notifications are handled by the local polling loop (checkScheduleForNotifications).
    console.log('[Notifications] Using local polling for reminders (Vercel mode).');
}

// ── Notification Engine (High Precision) ───────────────────────────────
let notificationTimer = null;

function startNotificationLoop() {
    if (notificationTimer) clearInterval(notificationTimer);
    notificationTimer = setInterval(checkScheduleForNotifications, 30000);
    checkScheduleForNotifications();
}

function checkScheduleForNotifications() {
    if (!currentUser) return;
    if (!currentActiveSchedule.length) {
        return;
    }

    const now = new Date();
    const nowStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const todayDateStr = now.toISOString().split('T')[0];
    
    // JS 0=Sun, 1=Mon...6=Sat. Convert to 0=Mon...6=Sun
    let todayDOW = now.getDay(); 
    let todayWeekday = todayDOW === 0 ? 6 : todayDOW - 1;

    currentActiveSchedule.forEach(item => {
        if (item.time === nowStr) {
            const isDaily = item.frequency === 'daily';
            const isTodayDate = item.specific_date === todayDateStr;
            const isTodayWeekday = item.recurring_days && item.recurring_days.includes(todayWeekday);

            if (isDaily || isTodayDate || isTodayWeekday) {
                const notifKey = `notif_${currentUser.user_id}_${item.medication}_${item.time}_${todayDateStr}`;
                if (!localStorage.getItem(notifKey)) {
                    triggerNotification(item);
                    localStorage.setItem(notifKey, 'triggered');
                }
            }
        }
    });
}

function triggerNotification(item) {
    const notifKey = `box_notif_${currentUser.user_id}_${item.medication}_${item.time}`;
    const activeId = `active_${notifKey.replace(/[^a-zA-Z0-9]/g, '_')}`;

    if (!document.getElementById(activeId)) {
        renderNotification(item, notifKey, activeId);
    }

    // Audio Cue
    const sound = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
    sound.play().catch(() => console.log('Audio blocked'));

    // Desktop Notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(`💊 Time for ${item.medication}`, {
            body: `Instructions: ${item.instructions || 'None'}`,
            icon: '/favicon.ico'
        });
    }
}

function renderNotification(item, notifKey, activeId) {
    const container = document.getElementById('notification-container');
    const emptyState = document.getElementById('notif-empty-state');
    if (emptyState) emptyState.style.display = 'none';

    const div = document.createElement('div');
    div.className = 'notification-item urgent';
    div.id = activeId;
    div.innerHTML = `
        <div class="notif-header">
            <span class="notif-title">💊 ${item.medication}</span>
            <span class="notif-time">${item.time}</span>
        </div>
        <div class="notif-body">
            Time to take your medication! <br>
            <i>${item.instructions || 'No instructions.'}</i>
        </div>
        <button class="btn-primary" style="padding: 0.4rem 0.8rem; font-size: 0.85rem;" onclick="dismissNotification('${notifKey}', '${activeId}')">Mark as Done</button>
    `;
    container.prepend(div);
    updateNotificationBadge(1);
}

function dismissNotification(notifKey, divId) {
    const div = document.getElementById(divId);
    if (div) {
        div.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
        div.style.opacity = '0';
        div.style.transform = 'translateX(10px)';
        setTimeout(() => {
            div.remove();
            updateNotificationBadge(-1);
            checkEmptyNotificationState();
        }, 300);
    }
    localStorage.setItem(notifKey, new Date().toISOString());
}

function updateNotificationBadge(delta) {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    let current = parseInt(badge.textContent || '0') + delta;
    if (current < 0) current = 0;
    badge.textContent = current;
    if (current > 0) badge.classList.remove('hidden');
    else badge.classList.add('hidden');
}

function checkEmptyNotificationState() {
    const container = document.getElementById('notification-container');
    const items = Array.from(container.children).filter(el => el.id !== 'notif-empty-state');
    if (items.length === 0) {
        let emptyState = document.getElementById('notif-empty-state');
        if (emptyState) emptyState.style.display = 'block';
    }
}

// ── Advanced Scheduling UI Helpers ──────────────────────────────
function toggleScheduleUI() {
    const type = document.getElementById('schedule-type').value;
    document.getElementById('row-specific-date').classList.toggle('hidden', type !== 'specific');
    document.getElementById('row-recurring-days').classList.toggle('hidden', type !== 'recurring');
}

// ── Core Application Logic ───────────────────────────────────────────
let currentUser = null;
let currentActiveSchedule = [];
let pendingSchedule = [];

document.addEventListener('DOMContentLoaded', () => {
    initSession();
});

function initSession() {
    const saved = localStorage.getItem('heyBossUser');
    if (saved) {
        currentUser = JSON.parse(saved);
        showDashboard();
    }
}

function switchAuthTab(tab) {
    const loginForm = document.getElementById('form-login');
    const regForm = document.getElementById('form-register');
    const loginTab = document.getElementById('tab-login');
    const regTab = document.getElementById('tab-register');

    if (tab === 'login') {
        loginForm.classList.remove('hidden');
        regForm.classList.add('hidden');
        loginTab.classList.add('active');
        regTab.classList.remove('active');
    } else {
        loginForm.classList.add('hidden');
        regForm.classList.remove('hidden');
        loginTab.classList.remove('active');
        regTab.classList.add('active');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const err = document.getElementById('login-error');

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (res.ok) {
            currentUser = data.user;
            localStorage.setItem('heyBossUser', JSON.stringify(currentUser));
            showDashboard();
        } else {
            err.textContent = data.detail || 'Login failed';
        }
    } catch {
        err.textContent = 'Connection error';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('reg-name').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const phone = document.getElementById('reg-phone').value;
    const err = document.getElementById('reg-error');

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, email, password, phone, reminder_opt: true })
        });
        const data = await res.json();
        if (res.ok) {
            currentUser = data.user;
            localStorage.setItem('heyBossUser', JSON.stringify(currentUser));
            showDashboard();
        } else {
            err.textContent = data.detail || 'Registration failed';
        }
    } catch {
        err.textContent = 'Connection error';
    }
}

function showDashboard() {
    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');
    document.getElementById('user-greeting').textContent = `Welcome, ${currentUser.name}`;
    
    startWebSocketConnection();
    startNotificationLoop();
    fetchSchedule();

    if ('Notification' in window && Notification.permission !== 'granted') {
        Notification.requestPermission();
    }
}

function logout() {
    currentUser = null;
    localStorage.removeItem('heyBossUser');
    location.reload();
}

async function fetchSchedule() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/schedule/${currentUser.user_id}`);
        const data = await res.json();
        if (res.ok) {
            currentActiveSchedule = data.schedule || [];
            renderSchedule();
        }
    } catch (e) {
        console.error('Fetch error:', e);
    }
}

function renderSchedule() {
    const tbody = document.getElementById('schedule-tbody');
    if (!currentActiveSchedule.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No schedule generated yet.</td></tr>';
        return;
    }

    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    tbody.innerHTML = currentActiveSchedule.map(item => {
        let [h, m] = item.time.split(':');
        h = parseInt(h);
        const ampm = h >= 12 ? 'PM' : 'AM';
        const h12 = h % 12 || 12;
        const timeStr = `${h12}:${m} ${ampm}`;

        let whenStr = 'Daily';
        if (item.specific_date) {
            whenStr = new Date(item.specific_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        } else if (item.recurring_days && item.recurring_days.length > 0) {
            if (item.recurring_days.length === 7) whenStr = 'Daily';
            else whenStr = item.recurring_days.map(d => dayNames[d]).join(', ');
        }

        return `
            <tr>
                <td>${item.medication}</td>
                <td style="font-size: 0.85rem; color: var(--text-secondary);">${whenStr}</td>
                <td>${timeStr}</td>
                <td>${item.instructions || ''}</td>
                <td>
                    <button class="btn-secondary" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" 
                            onclick="markAsDone('${item.medication}', '${item.time}')">Done</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function markAsDone(medication, time) {
    if (!confirm(`Mark ${medication} as taken?`)) return;
    try {
        const res = await fetch(`/api/schedule/${currentUser.user_id}/${encodeURIComponent(medication)}/${encodeURIComponent(time)}`, {
            method: 'DELETE'
        });
        if (res.ok) {
            // Play celebratory tune
            const successSound = new Audio('https://assets.mixkit.co/active_storage/sfx/1435/1435-preview.mp3');
            successSound.play().catch(e => console.log('Audio playback failed:', e));
            
            document.getElementById('congrats-dialog').classList.remove('hidden');
            fetchSchedule();
        }
    } catch (e) {
        console.error('Operation failed', e);
    }
}

async function handleManualSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-manual-save');
    btn.disabled = true;

    const med = document.getElementById('manual-med').value;
    const type = document.getElementById('schedule-type').value;
    const hour = parseInt(document.getElementById('manual-hour').value);
    const min = document.getElementById('manual-min').value.padStart(2, '0');
    const ampm = document.getElementById('manual-ampm').value;
    const inst = document.getElementById('manual-inst').value;

    let h24 = hour;
    if (ampm === "PM" && hour !== 12) h24 += 12;
    if (ampm === "AM" && hour === 12) h24 = 0;
    const time = `${h24.toString().padStart(2, '0')}:${min}`;

    const item = { medication: med, time, instructions: inst, frequency: type };

    if (type === 'specific') {
        item.specific_date = document.getElementById('manual-date').value;
        if (!item.specific_date) {
            alert('Please select a date');
            btn.disabled = false;
            return;
        }
    } else if (type === 'recurring') {
        const selectedDays = [];
        for (let i = 0; i < 7; i++) {
            if (document.getElementById(`day-${i}`).checked) selectedDays.push(i);
        }
        if (selectedDays.length === 0) {
            alert('Please select at least one day');
            btn.disabled = false;
            return;
        }
        item.recurring_days = selectedDays;
    }

    try {
        const res = await fetch('/api/save_schedule', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: currentUser.user_id, schedule: [item] })
        });
        const data = await res.json();
        if (res.ok) {
            e.target.reset();
            toggleScheduleUI();
            fetchSchedule();
        } else {
            // Show the exact DB error to help with debugging
            const errMsg = data.detail || JSON.stringify(data);
            console.error('Save failed (server):', errMsg);
            alert(`Failed to save schedule. Server error:\n\n${errMsg}`);
        }
    } catch (err) {
        console.error('Save failed (network):', err);
        alert('Network error when saving. Check console.');
    }
    btn.disabled = false;
}

function approveSchedule() {
    // Reverted AI Parser logic not strictly needed if chat is removed, 
    // but kept for backward compatibility if user approves a last parse.
}

function rejectSchedule() {
    document.getElementById('validation-dialog').classList.add('hidden');
}
