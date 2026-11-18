function dispenser() {
  return {
    tab: 'home',
    state: { pills: [], schedule: [], next: null, busy: null, simulation: false },
    history: [],
    clock: '',
    offline: false,
    confirm: null,
    editor: null,
    toast: { text: '', kind: '' },
    _toastTimer: null,

    init() {
      const tick = () => {
        this.clock = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      };
      tick();
      setInterval(tick, 1000);
      this.refresh();
      setInterval(() => this.refresh(), 3000);
    },

    async api(method, url, body) {
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data = null;
      try { data = await r.json(); } catch (e) { /* empty body */ }
      return { ok: r.ok, data };
    },

    async refresh() {
      try {
        const r = await this.api('GET', '/api/state');
        if (r.ok) this.state = r.data;
        if (this.tab === 'history') {
          const h = await this.api('GET', '/api/history');
          if (h.ok) this.history = h.data;
        }
        this.offline = false;
      } catch (e) {
        this.offline = true;
      }
    },

    go(t) { this.tab = t; this.refresh(); },

    pill(id) {
      return this.state.pills.find(p => p.id === id) || { name: id, color: '#888' };
    },

    say(text, kind) {
      this.toast = { text, kind: kind || '' };
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => (this.toast.text = ''), 3500);
    },

    // ---- confirm dialog
    ask(title, text, ok, action) { this.confirm = { title, text, ok, action }; },
    confirmOk() {
      const a = this.confirm.action;
      this.confirm = null;
      a();
    },

    // ---- actions
    async dispense(id) {
      this.state.busy = id;
      const r = await this.api('POST', '/api/dispense', { pill: id });
      this.say(r.data ? r.data.message : 'Request failed', r.ok ? 'ok' : 'bad');
      this.refresh();
    },

    async toggle(e) {
      await this.api('PUT', '/api/schedule/' + e.id, { enabled: !e.enabled });
      this.refresh();
    },

    async remove(e) {
      await this.api('DELETE', '/api/schedule/' + e.id);
      this.refresh();
    },

    openEditor(e) {
      if (e) {
        const [h, m] = e.time.split(':').map(Number);
        this.editor = { id: e.id, h, m, pill: e.pill };
      } else {
        this.editor = { id: null, h: 8, m: 0, pill: this.state.pills[0].id };
      }
    },
    step(part, d) {
      if (part === 'h') this.editor.h = (this.editor.h + d + 24) % 24;
      else this.editor.m = (this.editor.m + d + 60) % 60;
    },
    pad(n) { return String(n).padStart(2, '0'); },
    async saveEditor() {
      const e = this.editor;
      const body = { time: this.pad(e.h) + ':' + this.pad(e.m), pill: e.pill };
      const r = e.id
        ? await this.api('PUT', '/api/schedule/' + e.id, body)
        : await this.api('POST', '/api/schedule', body);
      if (!r.ok) return this.say((r.data && r.data.error) || 'Could not save', 'bad');
      this.editor = null;
      this.refresh();
    },

    async setCount(p, n) {
      if (n < 0) return;
      const r = await this.api('POST', '/api/pills/' + p.id + '/refill', { count: n });
      if (!r.ok) this.say((r.data && r.data.error) || 'Could not save', 'bad');
      this.refresh();
    },

    // ---- formatting
    nextLabel() {
      const at = new Date(this.state.next.at);
      const now = new Date(this.state.now);
      const same = at.toDateString() === now.toDateString();
      return (same ? 'Today ' : 'Tomorrow ') + this.state.next.time;
    },
    fmt(ts) {
      const d = new Date(ts);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
        d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
    statusText(h) {
      const how = h.source === 'schedule' ? 'Scheduled' : 'Manual';
      if (h.status === 'ok') return how;
      if (h.status === 'empty') return 'Hopper empty';
      return 'Error';
    },
  };
}
