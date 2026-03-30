/**
 * NoteShare App JS
 * Dark mode, keyboard shortcuts, voice, search, notifications,
 * drag-drop, TTS, chatbot, PWA install, infinite scroll
 */

// ── Dark Mode ─────────────────────────────────────────────────
const DarkMode = {
  init() {
    const saved = localStorage.getItem('ns_theme') || 'light';
    this.apply(saved);
  },
  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ns_theme', theme);
    const btn = document.getElementById('dark-toggle');
    if (btn) btn.innerHTML = theme === 'dark'
      ? '<i class="bi bi-sun-fill"></i>'
      : '<i class="bi bi-moon-fill"></i>';
  },
  toggle() {
    const cur = localStorage.getItem('ns_theme') || 'light';
    this.apply(cur === 'dark' ? 'light' : 'dark');
  }
};
DarkMode.init();

// ── PWA Install ───────────────────────────────────────────────
let _deferredInstall = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _deferredInstall = e;
  const btn = document.getElementById('install-btn');
  if (btn) btn.style.display = 'flex';
});

function installPWA() {
  if (!_deferredInstall) return;
  _deferredInstall.prompt();
  _deferredInstall.userChoice.then(() => { _deferredInstall = null; });
}

// Register service worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}

// ── Keyboard Shortcuts ────────────────────────────────────────
const KB = {
  hint: null,
  hintTimer: null,
  init() {
    this.hint = document.getElementById('kb-hint');
    document.addEventListener('keydown', e => {
      const tag = document.activeElement.tagName;
      if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
      this.handle(e);
    });
  },
  handle(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const si = document.getElementById('global-search');
      if (si) { si.focus(); si.select(); }
      this.show('Ctrl+K · Search');
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
      e.preventDefault(); location.href = '/notes/upload';
      this.show('Ctrl+U · Upload');
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
      e.preventDefault(); DarkMode.toggle();
      this.show('Ctrl+D · Dark Mode');
    }
    if (e.key === 'Escape') {
      document.querySelectorAll('.notif-dropdown,.search-results,.history-dropdown').forEach(el => el.classList.remove('show'));
    }
    if (e.key === '?' && !e.ctrlKey) {
      this.showHelp();
    }
  },
  show(text) {
    if (!this.hint) return;
    this.hint.textContent = text;
    this.hint.classList.add('show');
    clearTimeout(this.hintTimer);
    this.hintTimer = setTimeout(() => this.hint.classList.remove('show'), 2000);
  },
  showHelp() {
    const help = [
      ['Ctrl+K', 'Search'],
      ['Ctrl+U', 'Upload note'],
      ['Ctrl+D', 'Toggle dark mode'],
      ['?', 'Show shortcuts'],
      ['Esc', 'Close panels'],
    ];
    const modal = document.getElementById('kb-modal');
    if (modal) {
      document.getElementById('kb-modal-body').innerHTML = help.map(([k,v]) =>
        `<div class="d-flex justify-content-between py-1"><span>${v}</span><kbd>${k}</kbd></div>`
      ).join('');
      new bootstrap.Modal(modal).show();
    }
  }
};
KB.init();

// ── Global Smart Search ───────────────────────────────────────
const Search = {
  timer: null,
  init() {
    const inp = document.getElementById('global-search');
    const box = document.getElementById('search-results');
    if (!inp || !box) return;

    inp.addEventListener('input', () => {
      clearTimeout(this.timer);
      const q = inp.value.trim();
      if (q.length < 2) { box.classList.remove('show'); return; }
      this.timer = setTimeout(() => this.run(q, box), 300);
    });

    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter' && inp.value.trim()) {
        location.href = `/notes/?q=${encodeURIComponent(inp.value.trim())}`;
      }
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('.search-wrap')) box.classList.remove('show');
    });
  },
  async run(q, box) {
    try {
      const res  = await fetch(`/search/live?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!data.results?.length) {
        box.innerHTML = `<div class="notif-empty">No results for "${q}"</div>`;
      } else {
        box.innerHTML = data.results.map(r =>
          `<a class="sr-item" href="/notes/${r.id}">
            <i class="bi bi-file-earmark-text text-primary"></i>
            <div><div style="font-size:.85rem;font-weight:600">${r.title}</div>
            <div style="font-size:.75rem;color:#9ca3af">${r.subject || 'General'} · ${r.author}</div></div>
          </a>`
        ).join('');
      }
      box.classList.add('show');
    } catch(e) {}
  }
};
Search.init();

// ── Live Notifications ────────────────────────────────────────
const Notifs = {
  lastId: 0,
  init() {
    this.poll();
    setInterval(() => this.poll(), 15000); // poll every 15s
  },
  async poll() {
    try {
      const res  = await fetch(`/notifications/live?after=${this.lastId}`);
      const data = await res.json();
      if (data.notifications?.length) {
        this.lastId = data.notifications[0].id;
        this.updateBell(data.unread_count);
        data.notifications.forEach(n => this.toast(n));
      }
    } catch(e) {}
  },
  updateBell(count) {
    const badge = document.getElementById('notif-badge');
    const sidebar = document.getElementById('sidebar-notif-badge');
    [badge, sidebar].forEach(el => {
      if (!el) return;
      el.textContent = count;
      el.style.display = count > 0 ? 'flex' : 'none';
    });
  },
  toast(n) {
    const icons = { like:'❤️', comment:'💬', follow:'👤', admin:'🛡️' };
    const div   = document.createElement('div');
    div.className = 'alert alert-info alert-dismissible fade show shadow-sm';
    div.style.cssText = 'font-size:.85rem;max-width:320px';
    div.innerHTML = `${icons[n.type]||'🔔'} ${n.message}
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    const stack = document.querySelector('.toast-stack');
    if (stack) { stack.appendChild(div); setTimeout(() => div.remove(), 5000); }
  },
  async loadDropdown() {
    const drop = document.getElementById('notif-dropdown');
    if (!drop) return;
    try {
      const res  = await fetch('/notifications/dropdown');
      const data = await res.json();
      if (!data.notifications?.length) {
        drop.querySelector('.notif-body').innerHTML = '<div class="notif-empty">🎉 All caught up!</div>';
        return;
      }
      const icons = { like:'❤️', comment:'💬', follow:'👤', admin:'🛡️' };
      const colors = { like:'#fee2e2', comment:'#dbeafe', follow:'#d1fae5', admin:'#ede9fe' };
      drop.querySelector('.notif-body').innerHTML = data.notifications.map(n =>
        `<a class="notif-item ${n.is_read ? '' : 'unread'}" href="${n.link || '#'}">
          <div class="ni-icon" style="background:${colors[n.type]||'#f3f4f6'}">${icons[n.type]||'🔔'}</div>
          <div><div class="ni-text">${n.message}</div>
          <div class="ni-time">${n.created_at?.slice(0,16)||''}</div></div>
        </a>`
      ).join('');
    } catch(e) {}
  },
  toggleDropdown() {
    const drop = document.getElementById('notif-dropdown');
    if (!drop) return;
    const showing = drop.classList.contains('show');
    if (!showing) { this.loadDropdown(); }
    drop.classList.toggle('show');
    if (!showing) {
      setTimeout(() => document.addEventListener('click', function close(e) {
        if (!e.target.closest('.notif-bell')) { drop.classList.remove('show'); document.removeEventListener('click', close); }
      }), 10);
    }
  }
};
Notifs.init();

// ── Drag & Drop File Upload ───────────────────────────────────
function initDragDrop(zoneId, inputId) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  ['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, e => {
    e.preventDefault(); zone.classList.add('dragover');
  }));
  ['dragleave','drop'].forEach(ev => zone.addEventListener(ev, e => {
    e.preventDefault(); zone.classList.remove('dragover');
  }));
  zone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length) {
      input.files = files;
      zone.classList.add('has-file');
      zone.querySelector('p').textContent = `✅ ${files[0].name} (${(files[0].size/1024/1024).toFixed(2)} MB)`;
    }
  });
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files.length) {
      zone.classList.add('has-file');
      zone.querySelector('p').textContent = `✅ ${input.files[0].name}`;
    }
  });
}

// ── Text-to-Speech ────────────────────────────────────────────
const TTS = {
  utterance: null,
  bar: null,
  init() { this.bar = document.getElementById('tts-bar'); },
  speak(text) {
    if (!window.speechSynthesis) { alert('TTS not supported in this browser'); return; }
    this.stop();
    this.utterance = new SpeechSynthesisUtterance(text);
    this.utterance.rate = 0.9; this.utterance.lang = 'en-US';
    this.utterance.onend = () => { if (this.bar) this.bar.classList.remove('show'); };
    speechSynthesis.speak(this.utterance);
    if (this.bar) this.bar.classList.add('show');
  },
  stop() {
    speechSynthesis.cancel();
    if (this.bar) this.bar.classList.remove('show');
  }
};
TTS.init();

// ── Voice Search ──────────────────────────────────────────────
function startVoiceSearch() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { alert('Voice search not supported in this browser'); return; }
  const r = new SpeechRecognition();
  r.lang = 'en-US'; r.interimResults = false;
  const btn = document.getElementById('voice-search-btn');
  if (btn) btn.classList.add('listening');
  r.onresult = e => {
    const q = e.results[0][0].transcript;
    const si = document.getElementById('global-search');
    if (si) { si.value = q; si.dispatchEvent(new Event('input')); }
    if (btn) btn.classList.remove('listening');
  };
  r.onerror = () => { if (btn) btn.classList.remove('listening'); };
  r.start();
}

// ── AI Chatbot ────────────────────────────────────────────────
const Chatbot = {
  open: false,
  history: [],
  noteId: null,
  init(noteId = null) {
    this.noteId = noteId;
    const win = document.getElementById('chatbot-window');
    const fab = document.getElementById('chatbot-fab');
    if (!win || !fab) return;
    this.addMessage('bot', `Hi! 👋 I'm your AI study assistant. ${noteId ? 'Ask me anything about this note!' : 'Ask me any academic question!'}`);
  },
  toggle() {
    const win = document.getElementById('chatbot-window');
    if (!win) return;
    this.open = !this.open;
    win.classList.toggle('show', this.open);
    if (this.open) setTimeout(() => document.getElementById('chatbot-inp')?.focus(), 100);
  },
  addMessage(role, text) {
    const box  = document.getElementById('chatbot-msgs');
    if (!box) return;
    const div  = document.createElement('div');
    div.className = role === 'bot' ? 'bot-msg' : 'user-msg';
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  },
  async send() {
    const inp = document.getElementById('chatbot-inp');
    if (!inp) return;
    const q = inp.value.trim();
    if (!q) return;
    inp.value = '';
    this.addMessage('user', q);
    this.history.push({role: 'user', content: q});
    this.addMessage('bot', '⏳ Thinking...');
    try {
      const res  = await fetch('/ai/chat', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q, note_id: this.noteId, history: this.history.slice(-6)})
      });
      const data = await res.json();
      const msgs = document.querySelectorAll('#chatbot-msgs .bot-msg');
      const last = msgs[msgs.length - 1];
      if (last) last.textContent = data.answer || 'Sorry, I could not answer that.';
      this.history.push({role: 'assistant', content: data.answer});
    } catch(e) {
      const msgs = document.querySelectorAll('#chatbot-msgs .bot-msg');
      const last = msgs[msgs.length - 1];
      if (last) last.textContent = 'Connection error. Please try again.';
    }
  },
  keydown(e) { if (e.key === 'Enter') this.send(); }
};

// ── Infinite Scroll ───────────────────────────────────────────
const InfiniteScroll = {
  page: 1, loading: false, done: false,
  init(containerSelector, loadUrl) {
    this.container = document.querySelector(containerSelector);
    this.loadUrl   = loadUrl;
    if (!this.container) return;
    window.addEventListener('scroll', () => {
      if (this.loading || this.done) return;
      const rect = this.container.getBoundingClientRect();
      if (rect.bottom < window.innerHeight + 300) this.loadMore();
    });
  },
  async loadMore() {
    this.loading = true;
    this.page++;
    const spinner = document.getElementById('infinite-spinner');
    if (spinner) spinner.classList.add('show');
    try {
      const url = this.loadUrl + '&page=' + this.page;
      const res = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
      const data = await res.json();
      if (data.html) this.container.insertAdjacentHTML('beforeend', data.html);
      if (!data.has_more) this.done = true;
    } catch(e) {}
    if (spinner) spinner.classList.remove('show');
    this.loading = false;
  }
};

// ── Exam Mode (Quiz timer) ────────────────────────────────────
const ExamMode = {
  timer: null, remaining: 0, totalQ: 0, score: 0, current: 0, questions: [],
  start(questions, timeSecs) {
    this.questions = questions; this.totalQ = questions.length;
    this.remaining = timeSecs; this.score = 0; this.current = 0;
    this.render();
    this.timer = setInterval(() => {
      this.remaining--;
      document.getElementById('exam-timer').textContent = this.formatTime(this.remaining);
      if (this.remaining <= 0) this.finish();
    }, 1000);
  },
  formatTime(s) { return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`; },
  render() {
    const q   = this.questions[this.current];
    const box = document.getElementById('exam-box');
    if (!box || !q) return;
    box.innerHTML = `
      <div class="mb-2 text-muted small">Question ${this.current+1} of ${this.totalQ}</div>
      <h6 class="fw-semibold mb-3">${q.question}</h6>
      <div class="d-flex flex-column gap-2">
        ${q.options.map((o,i) => `
          <button class="btn btn-outline-secondary text-start exam-opt" data-idx="${i}" onclick="ExamMode.answer('${o.replace(/'/g,"\\'")}')">
            ${String.fromCharCode(65+i)}. ${o}
          </button>`).join('')}
      </div>`;
  },
  answer(chosen) {
    const q = this.questions[this.current];
    if (chosen === q.answer) this.score++;
    this.current++;
    if (this.current >= this.totalQ) this.finish();
    else this.render();
  },
  finish() {
    clearInterval(this.timer);
    const pct = Math.round((this.score / this.totalQ) * 100);
    const box = document.getElementById('exam-box');
    if (box) box.innerHTML = `
      <div class="text-center py-3">
        <div style="font-size:3rem">${pct>=70?'🎉':pct>=40?'📚':'💪'}</div>
        <h4 class="mt-2">Score: ${this.score}/${this.totalQ} (${pct}%)</h4>
        <p class="text-muted">${pct>=70?'Excellent!':pct>=40?'Good effort — keep studying!':'Keep practicing!'}</p>
        <div class="progress mt-3" style="height:10px">
          <div class="progress-bar ${pct>=70?'bg-success':pct>=40?'bg-warning':'bg-danger'}"
               style="width:${pct}%"></div>
        </div>
        <button class="btn btn-primary mt-3" onclick="location.reload()">Try Again</button>
      </div>`;
    // Save score
    fetch('/study/exam-score', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({score: this.score, total: this.totalQ, pct})}).catch(()=>{});
  }
};

// ── Note Version Control ──────────────────────────────────────
async function saveVersion(noteId, content) {
  await fetch(`/notes/${noteId}/version`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content})
  });
}

// ── Expose globals ────────────────────────────────────────────
window.DarkMode    = DarkMode;
window.Notifs      = Notifs;
window.Chatbot     = Chatbot;
window.TTS         = TTS;
window.ExamMode    = ExamMode;
window.installPWA  = installPWA;
window.startVoiceSearch = startVoiceSearch;
window.initDragDrop     = initDragDrop;
