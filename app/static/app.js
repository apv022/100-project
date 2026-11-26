function dispenser() {
  return {
    tab: 'home',
    tabs: [['home', 'Home'], ['schedule', 'Schedule'], ['meds', 'Meds'], ['history', 'History'], ['settings', 'Settings']],
    dayNames: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'],
    state: { containers: [], schedule: [], pending: [], next: null, busy: null, driver: '', alarm: false,
             unread: 0, latest: [], settings: {}, ocr: false, push: false },
    history: [],
    notes: [],
    notesOpen: false,
    settingsForm: {},
    clock: '',
    offline: false,
    confirm: null,
    editor: null,
    rx: null,
    refill: null,
    scanning: null,
    scanTarget: null,
    soundOn: false,
    toast: { text: '', kind: '' },
    _toastTimer: null,
    _seenNotes: null,
    _seenDoses: null,
    _lastAlarmBeep: 0,
    _audio: null,

    init() {
      try { this.soundOn = localStorage.getItem('soundOn') === '1'; } catch (e) { /* private mode */ }
      const tick = () => {
        this.clock = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      };
      tick();
      setInterval(tick, 1000);
      this.refresh();
      setInterval(() => this.refresh(), 3000);
    },

    async api(method, url, body) {
      const opts = { method };
      if (body instanceof FormData) opts.body = body;
      else if (body !== undefined) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
      }
      const r = await fetch(url, opts);
      let data = null;
      try { data = await r.json(); } catch (e) { /* empty body */ }
      return { ok: r.ok, data };
    },
    post(url, body) { return this.api('POST', url, body); },

    async refresh() {
      try {
        const r = await this.api('GET', '/api/state');
        if (!r.ok) throw new Error('state');
        const first = !this.state.driver;
        this.state = r.data;
        if (first) this.settingsForm = { ...r.data.settings };
        this.react(first);
        if (this.tab === 'history') {
          const h = await this.api('GET', '/api/history');
          if (h.ok) this.history = h.data;
        }
        this.offline = false;
      } catch (e) {
        this.offline = true;
      }
    },

    // sounds + browser notifications for things that happened since last poll
    react(first) {
      const doseIds = this.state.pending.map(d => d.id);
      if (!first && doseIds.some(id => !this._seenDoses.includes(id))) this.beep('dose');
      this._seenDoses = doseIds;
      if (this.state.alarm && Date.now() - this._lastAlarmBeep > 15000) {
        this._lastAlarmBeep = Date.now();
        this.beep('alarm');
      }
      const ids = this.state.latest.map(n => n.id);
      if (!first && 'Notification' in window && Notification.permission === 'granted') {
        for (const n of this.state.latest) {
          if (!n.read && !this._seenNotes.includes(n.id)) {
            try { new Notification(n.title, { body: n.message, tag: n.id }); } catch (e) { /* not allowed here */ }
          }
        }
      }
      this._seenNotes = ids;
    },

    beep(kind) {
      if (!this.soundOn) return;
      try {
        this._audio = this._audio || new (window.AudioContext || window.webkitAudioContext)();
        const ctx = this._audio;
        const n = kind === 'alarm' ? 6 : 3;
        for (let i = 0; i < n; i++) {
          const o = ctx.createOscillator(), g = ctx.createGain();
          o.frequency.value = kind === 'alarm' ? (i % 2 ? 660 : 990) : 880;
          o.connect(g); g.connect(ctx.destination);
          const t = ctx.currentTime + i * 0.3;
          g.gain.setValueAtTime(0.25, t);
          g.gain.setValueAtTime(0, t + 0.18);
          o.start(t); o.stop(t + 0.2);
        }
      } catch (e) { /* no audio */ }
    },

    go(t) { this.tab = t; this.refresh(); },

    container(id) { return this.state.containers.find(c => c.id === id); },
    color(id) { const c = this.container(id); return c ? c.color : '#888'; },
    label(id) { const c = this.container(id); return c ? c.label : id; },

    say(text, kind) {
      this.toast = { text, kind: kind || '' };
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => (this.toast.text = ''), 3500);
    },
    fail(r, fallback) { this.say((r.data && (r.data.error || r.data.message)) || fallback, 'bad'); },

    ask(title, text, ok, action) { this.confirm = { title, text, ok, action }; },
    confirmOk() { const a = this.confirm.action; this.confirm = null; a(); },

    // ---- dispensing + doses
    async dispense(id) {
      this.state.busy = id;
      const r = await this.post('/api/dispense', { pill: id });
      this.say(r.data ? r.data.message : 'Request failed', r.ok ? 'ok' : 'bad');
      this.refresh();
    },
    async doseAction(d, action) {
      const r = await this.post('/api/doses/' + d.id + '/' + action);
      if (r.ok) this.say(action === 'taken' ? 'Great, logged as taken.' : 'Dose skipped.', 'ok');
      else this.fail(r, 'Could not update');
      this.refresh();
    },

    // ---- schedule
    async toggle(e) { await this.api('PUT', '/api/schedule/' + e.id, { enabled: !e.enabled }); this.refresh(); },
    async remove(e) { await this.api('DELETE', '/api/schedule/' + e.id); this.refresh(); },
    openEditor(e) {
      if (e) {
        const [h, m] = e.time.split(':').map(Number);
        this.editor = { id: e.id, h, m, pill: e.pill, qty: e.qty, days: [...e.days] };
      } else {
        const c = this.state.containers[0];
        this.editor = { id: null, h: 8, m: 0, pill: c.id, qty: c.rx.dose_qty, days: [0, 1, 2, 3, 4, 5, 6] };
      }
    },
    step(part, d) {
      if (part === 'h') this.editor.h = (this.editor.h + d + 24) % 24;
      else this.editor.m = (this.editor.m + d + 60) % 60;
    },
    toggleDay(i) {
      const days = this.editor.days;
      this.editor.days = days.includes(i) ? days.filter(x => x !== i) : [...days, i].sort();
    },
    pad(n) { return String(n).padStart(2, '0'); },
    async saveEditor() {
      const e = this.editor;
      const body = { time: this.pad(e.h) + ':' + this.pad(e.m), pill: e.pill, qty: e.qty, days: e.days };
      const r = e.id ? await this.api('PUT', '/api/schedule/' + e.id, body) : await this.post('/api/schedule', body);
      if (!r.ok) return this.fail(r, 'Could not save');
      this.editor = null;
      this.refresh();
    },
    daysText(days) {
      if (days.length === 7) return 'Every day';
      if (days.join() === '0,1,2,3,4') return 'Weekdays';
      if (days.join() === '5,6') return 'Weekends';
      return days.map(d => this.dayNames[d]).join(' ');
    },

    // ---- prescriptions
    openRx(c, scan) {
      this.rx = { id: c.id, f: { ...c.rx }, scan: scan || null, applyTimes: !!(scan && scan.times.length) };
      if (scan) {
        Object.assign(this.rx.f, scan.fields);
        if (scan.fields.quantity !== undefined && !('remaining' in scan.fields)) this.rx.f.remaining = scan.fields.quantity;
      }
    },
    async saveRx() {
      const { id, f, scan, applyTimes } = this.rx;
      const body = {};
      for (const k of ['name', 'strength', 'instructions', 'rx_number', 'prescriber', 'pharmacy', 'filled_on']) body[k] = f[k] || '';
      for (const k of ['dose_qty', 'quantity', 'remaining', 'refills_left']) body[k] = Number(f[k]) || 0;
      const r = await this.api('PUT', '/api/prescriptions/' + id, body);
      if (!r.ok) return this.fail(r, 'Could not save');
      if (scan && applyTimes && scan.times.length) {
        const s = await this.post('/api/prescriptions/' + id + '/schedule', { times: scan.times, qty: body.dose_qty });
        if (!s.ok) return this.fail(s, 'Saved, but the schedule could not be set');
      }
      this.rx = null;
      this.say('Prescription saved', 'ok');
      this.refresh();
    },
    async adjust(c, delta) {
      const r = await this.post('/api/prescriptions/' + c.id + '/adjust', { delta });
      if (!r.ok) this.fail(r, 'Could not save');
      this.refresh();
    },
    openRefill(c) {
      this.refill = { id: c.id, label: c.label, count: c.rx.quantity, refills_left: c.rx.refills_left,
                      use_refill: c.rx.refills_left > 0 };
    },
    async saveRefill() {
      const f = this.refill;
      const r = await this.post('/api/prescriptions/' + f.id + '/refill',
        { count: Number(f.count) || 0, use_refill: !!f.use_refill });
      if (!r.ok) return this.fail(r, 'Could not refill');
      this.refill = null;
      this.say('Refilled', 'ok');
      this.refresh();
    },

    // ---- label scanning
    pickImage(c) { this.scanTarget = c; this.$refs.file.value = ''; this.$refs.file.click(); },
    async scanPicked(ev) {
      const file = ev.target.files[0];
      const c = this.scanTarget;
      if (!file || !c) return;
      this.scanning = c.id;
      try {
        const fd = new FormData();
        fd.append('image', await this.shrink(file), 'label.jpg');
        const r = await this.post('/api/scan', fd);
        if (!r.ok) return this.fail(r, 'Could not read the label');
        this.openRx(c, r.data);
      } catch (e) {
        this.say('Upload failed', 'bad');
      } finally {
        this.scanning = null;
      }
    },
    async shrink(file, max = 2000) {
      // Phone photos are huge; a smaller image makes OCR on the Pi much faster.
      try {
        const img = await createImageBitmap(file);
        const s = Math.min(1, max / Math.max(img.width, img.height));
        const cv = document.createElement('canvas');
        cv.width = Math.round(img.width * s);
        cv.height = Math.round(img.height * s);
        cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
        return await new Promise(res => cv.toBlob(b => res(b || file), 'image/jpeg', 0.92));
      } catch (e) {
        return file;
      }
    },

    // ---- notifications + settings
    async openNotes() {
      const r = await this.api('GET', '/api/notifications');
      this.notes = r.ok ? r.data : [];
      this.notesOpen = true;
      await this.post('/api/notifications/read');
      this.refresh();
    },
    async saveSettings() {
      const r = await this.api('PUT', '/api/settings', this.settingsForm);
      if (!r.ok) return this.fail(r, 'Could not save');
      this.settingsForm = { ...r.data };
      this.say('Settings saved', 'ok');
      this.refresh();
    },
    saveLocal() {
      try { localStorage.setItem('soundOn', this.soundOn ? '1' : '0'); } catch (e) { /* ignore */ }
      if (this.soundOn) this.beep('dose');
    },
    noteButton() {
      if (!('Notification' in window)) return 'Notifications not supported in this browser';
      return { granted: 'Phone notifications: ON', denied: 'Notifications blocked in browser settings' }[Notification.permission]
        || 'Turn on phone notifications';
    },
    async enableBrowserNotes() {
      if (!('Notification' in window)) return;
      await Notification.requestPermission();
      this.state = { ...this.state };   // re-render the button text
    },

    // ---- formatting
    nextLabel() {
      const at = new Date(this.state.next.at), now = new Date(this.state.now);
      const days = Math.round((new Date(at.toDateString()) - new Date(now.toDateString())) / 86400000);
      const when = days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : at.toLocaleDateString([], { weekday: 'short' });
      return when + ' ' + this.state.next.time;
    },
    fmt(ts) {
      const d = new Date(ts);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
        d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
    statusText(h) {
      const t = { ok: h.source === 'schedule' ? 'Dispensed (sched.)' : 'Dispensed', empty: 'Container empty',
                  no_pill: 'Nothing came out', error: 'Hardware error', taken: 'Taken ✓', skipped: 'Skipped',
                  not_taken: 'NOT taken' };
      return (t[h.status] || h.status) + (h.qty > 1 ? ' ×' + h.qty : '');
    },
  };
}
