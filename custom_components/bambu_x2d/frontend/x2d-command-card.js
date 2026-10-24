/* X2D Command Card — ships with the X2D Command Center integration.
   Tabs: Live · Soak · Control · Files · Objects · Filament · Timelapse · Insights
   Zero dependencies, theme-aware, works from a phone. */

const DOMAIN = "bambu_x2d";
const ICONS = {
  live: "M19 8h-1V3H6v5H5c-1.7 0-3 1.3-3 3v6h4v4h12v-4h4v-6c0-1.7-1.3-3-3-3M8 5h8v3H8zm8 14H8v-4h8zm3-7c-.6 0-1-.4-1-1s.4-1 1-1 1 .4 1 1-.4 1-1 1",
  soak: "M12 3c-1.1 0-2 .9-2 2v6.3c-1.2.9-2 2.2-2 3.7 0 2.5 2 4.5 4.5 4.5S17 17.5 17 15c0-1.6-.8-2.9-2-3.7V5c0-1.1-.9-2-2-2m0 2c.6 0 1 .4 1 1v6.8l.5.3c.9.5 1.5 1.5 1.5 2.4 0 1.7-1.3 3-3 3s-3-1.3-3-3c0-1 .6-1.9 1.5-2.4l.5-.3V6c0-.6.4-1 1-1",
  control: "M7 2v2h2v2H5c-1.1 0-2 .9-2 2v2h2V8h14v2h2V8c0-1.1-.9-2-2-2h-4V4h2V2zm-4 10v10h18V12zm4 3h2v4H7zm4 0h2v4h-2zm4 0h2v4h-2z",
  files: "M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8zm4 18H6V4h7v5h5z",
  objects: "M21 16.5c0 .4-.2.7-.5.9l-7.9 4.4c-.2.1-.4.2-.6.2s-.4-.1-.6-.2l-7.9-4.4c-.3-.2-.5-.5-.5-.9v-9c0-.4.2-.7.5-.9l7.9-4.4c.2-.1.4-.2.6-.2s.4.1.6.2l7.9 4.4c.3.2.5.5.5.9z",
  filament: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12m0 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4",
  timelapse: "M4 6H2v14c0 1.1.9 2 2 2h14v-2H4zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2m-9 11V5l5.5 4.5z",
  insights: "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2M9 17H7v-7h2zm4 0h-2V7h2zm4 0h-2v-4h2z",
  cloud: "M19.4 10a7.5 7.5 0 0 0-14-2A6 6 0 0 0 6 20h13a5 5 0 0 0 .4-10",
  lan: "M10 2v4H8.5C7.7 6 7 6.7 7 7.5V9H3v6h4v1.5c0 .8.7 1.5 1.5 1.5H10v4h4v-4h1.5c.8 0 1.5-.7 1.5-1.5V15h4V9h-4V7.5C17 6.7 16.3 6 15.5 6H14V2z",
  wrench: "M22.7 19 13.6 9.9a6 6 0 0 0-7.8-7.6l4 4L7 9.1l-4-4a6 6 0 0 0 7.6 7.8l9.1 9.1c.4.4 1 .4 1.4 0l1.6-1.6c.4-.4.4-1 0-1.4",
  bulb: "M12 2a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.3A7 7 0 0 0 12 2M9 20a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-1H9z",
  queue: "M3 5h18v2H3zm0 6h12v2H3zm0 6h18v2H3zm16-5 3 3-3 3v-6",
  drop: "M12 2s-6 7.2-6 11.5A6 6 0 0 0 12 20a6 6 0 0 0 6-6.5C18 9.2 12 2 12 2",
};
const TABS = ["live", "soak", "control", "files", "objects", "filament", "timelapse", "insights"];
const SPEEDS = ["silent", "standard", "sport", "ludicrous"];
const STATE = {
  running: { c: "var(--x2d-ok)", label: "Printing" },
  pause: { c: "var(--x2d-warn)", label: "Paused" },
  finish: { c: "var(--x2d-blue)", label: "Finished" },
  failed: { c: "var(--x2d-bad)", label: "Failed" },
  prepare: { c: "var(--x2d-purple)", label: "Preparing" },
  slicing: { c: "var(--x2d-purple)", label: "Slicing" },
  idle: { c: "var(--x2d-dim)", label: "Idle" },
};
const SEV = { alert: "var(--x2d-bad)", warn: "var(--x2d-warn)", tip: "var(--x2d-blue)", info: "var(--x2d-dim)" };

const h = (tag, attrs = {}, ...children) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(c));
  }
  return el;
};
const icon = (name, size = 18) => {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.style.cssText = `width:${size}px;height:${size}px;fill:currentColor;flex:none`;
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", ICONS[name] || name);
  svg.append(p);
  return svg;
};
const ring = (pct, size, color) => {
  const r = (size - 8) / 2, c = 2 * Math.PI * r;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.style.cssText = `width:${size}px;height:${size}px;flex:none;transform:rotate(-90deg)`;
  const mk = (stroke, dash) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    el.setAttribute("cx", size / 2); el.setAttribute("cy", size / 2); el.setAttribute("r", r);
    el.setAttribute("fill", "none"); el.setAttribute("stroke", stroke); el.setAttribute("stroke-width", 5);
    el.setAttribute("stroke-linecap", "round");
    if (dash != null) { el.setAttribute("stroke-dasharray", `${dash} ${c}`); el.style.transition = "stroke-dasharray .6s"; }
    return el;
  };
  svg.append(mk("var(--x2d-track)", null), mk(color, (c * Math.min(pct, 100)) / 100));
  return svg;
};
const fmtMin = (m) => (m == null ? "—" : m >= 60 ? `${Math.floor(m / 60)}h ${Math.round(m % 60)}m` : `${Math.round(m)}m`);
const fmtClock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "—");
const fmtMB = (b) => `${(b / 1048576).toFixed(1)} MB`;
const fmtDate = (sec) => new Date(sec * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

class X2DCommandCard extends HTMLElement {
  static getConfigElement() { return document.createElement("x2d-command-card-editor"); }
  static getStubConfig() { return { tabs: TABS }; }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    let tab = localStorage.getItem("x2d_card_tab") || "live";
    if (tab === "history") tab = "insights";
    this._tab = TABS.includes(tab) ? tab : "live";
    this._data = null;
    this._db = null;
    this._unsub = null;
    this._confirm = null;
    this._renameTarget = null;
    this._sheet = null;
    this._skipSel = new Set();
    this._noPrinter = false;
  }

  setConfig(config) { this._config = { tabs: TABS, ...config }; }
  getCardSize() { return 10; }

  set hass(hass) {
    this._hass = hass;
    if (!this._unsub && hass) this._subscribe();
  }

  async _subscribe() {
    this._unsub = () => {};
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        (data) => { this._data = data; this._noPrinter = false; this._render(); },
        { type: `${DOMAIN}/subscribe`, ...(this._config.entry_id ? { entry_id: this._config.entry_id } : {}) },
      );
    } catch (e) {
      // not_found: integration loaded, no printer yet. unknown_command: integration not loaded at all
      // (no printer and no `bambu_x2d:` line) — either way, invite the user to enroll.
      this._noPrinter = !!e && (["not_found", "unknown_command"].includes(e.code) || /no printer|unknown command/i.test(e.message || ""));
      this._error = e.message || "subscription failed";
      this._render();
    }
  }
  disconnectedCallback() { if (this._unsub) { this._unsub(); this._unsub = null; } }
  connectedCallback() { if (this._hass && !this._unsub) this._subscribe(); }

  // ---------------- helpers
  _svc(service, data = {}) {
    const payload = { ...data };
    if (this._data) payload.entry_id = this._data.entry_id;
    return this._hass.callService(DOMAIN, service, payload).catch((e) => this._toast(e.message));
  }
  _setSetting(key, value) {
    return this._hass.callWS({ type: `${DOMAIN}/set_setting`, entry_id: this._data.entry_id, key, value })
      .catch((e) => this._toast(e.message));
  }
  async _loadDb() {
    if (this._db) return this._db;
    try { this._db = await this._hass.callWS({ type: `${DOMAIN}/filament_db` }); } catch (e) { this._db = { materials: {} }; }
    this._render();
    return this._db;
  }
  async _sign(path) {
    this._sigCache = this._sigCache || new Map();
    const hit = this._sigCache.get(path);
    if (hit && hit.exp > Date.now()) return hit.url;
    const res = await this._hass.callWS({ type: "auth/sign_path", path, expires: 1800 });
    this._sigCache.set(path, { url: res.path, exp: Date.now() + 1500 * 1000 });
    return res.path;
  }
  _hydrateMedia(root) {
    for (const el of root.querySelectorAll("[data-sign-src]")) {
      const p = el.getAttribute("data-sign-src");
      this._sign(p).then((u) => { if (el.getAttribute("data-sign-src") === p) el.src = u; }).catch(() => {});
    }
    for (const el of root.querySelectorAll("[data-sign-poster]")) {
      const p = el.getAttribute("data-sign-poster");
      this._sign(p).then((u) => { if (el.getAttribute("data-sign-poster") === p) el.poster = u; }).catch(() => {});
    }
  }
  _toast(message) {
    const ev = new Event("hass-notification", { bubbles: true, composed: true });
    ev.detail = { message };
    this.dispatchEvent(ev);
  }
  _ask(text, fn) { this._confirm = { text, fn }; this._render(); }
  _nav(path) {
    history.pushState(null, "", path);
    this.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
    window.dispatchEvent(new CustomEvent("location-changed"));
  }
  _lookupDb(name, infoIdx) {
    if (!this._db) return null;
    const mats = Object.values(this._db.materials || {});
    if (infoIdx) {
      const hit = mats.find((m) => (m.info_idx || []).some((p) => infoIdx.toUpperCase().startsWith(p)));
      if (hit) return hit;
    }
    const n = (name || "").toLowerCase();
    if (!n) return null;
    let best = null, len = 0;
    for (const m of mats) for (const a of m.aliases || []) if (n.includes(a) && a.length > len) { best = m; len = a.length; }
    return best || mats.find((m) => n.split(" ")[0] === m.family.toLowerCase()) || null;
  }

  // ---------------- render
  _render() {
    const root = this.shadowRoot;
    root.textContent = "";
    root.append(this._styles());
    const card = h("ha-card");
    if (this._noPrinter) {
      card.append(this._landing());
      root.append(card);
      return;
    }
    if (!this._data) {
      card.append(this._error
        ? h("div", { class: "pad dim" }, `X2D Command Card: ${this._error}`)
        : h("div", { class: "pad" },
            h("div", { class: "skeleton", style: "height:180px" }),
            h("div", { class: "skeleton", style: "height:20px;width:60%;margin-top:10px" }),
            h("div", { class: "skeleton", style: "height:14px;width:40%;margin-top:8px" })));
      root.append(card);
      return;
    }
    card.append(this._header(), this._tabbar(), this[`_tab_${this._tab}`]?.() || h("div"));
    if (this._confirm) card.append(this._confirmBar());
    root.append(card);
    this._hydrateMedia(card);
  }

  _styles() {
    const s = document.createElement("style");
    s.textContent = `
      :host {
        --x2d-ok: var(--success-color, #22a559);
        --x2d-warn: #f0a020;
        --x2d-bad: var(--error-color, #e5484d);
        --x2d-blue: #3f8cff;
        --x2d-purple: #8e6fd8;
        --x2d-teal: #1d9e75;
        --x2d-dim: var(--secondary-text-color);
        --x2d-track: rgba(128,128,128,.18);
        --x2d-chip: var(--secondary-background-color);
        --x2d-r: 14px;
        --pad: 14px;
      }
      ha-card { overflow: hidden; }
      .pad { padding: var(--pad); }
      .dim { color: var(--x2d-dim); }
      .skeleton { border-radius: 12px; background: var(--x2d-track); animation: shimmer 1.4s ease infinite; }
      @keyframes shimmer { 50% { opacity: .5; } }
      @keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--dot) 45%, transparent); }
                         60% { box-shadow: 0 0 0 7px transparent; } }
      /* ---------- header */
      .hdr { display: flex; align-items: center; gap: 11px; padding: 13px var(--pad) 9px; }
      .hdr .dot { width: 11px; height: 11px; border-radius: 50%; flex: none; background: var(--dot); }
      .hdr .dot.live { animation: pulse 2s infinite; }
      .hdr .name { font-weight: 650; font-size: 16.5px; letter-spacing: .1px; }
      .hdr .sub { font-size: 11.5px; color: var(--x2d-dim); margin-top: 1px; }
      .hdr .right { margin-left: auto; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
      .chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 9px; border-radius: 999px;
        background: var(--x2d-chip); font-size: 11px; font-weight: 500; white-space: nowrap; }
      .chip svg { width: 12px; height: 12px; }
      .chip.warn { background: color-mix(in srgb, var(--x2d-warn) 16%, transparent); color: var(--x2d-warn); }
      .chip.bad { background: color-mix(in srgb, var(--x2d-bad) 14%, transparent); color: var(--x2d-bad); }
      .chip.good { background: color-mix(in srgb, var(--x2d-ok) 14%, transparent); color: var(--x2d-ok); }
      .chip.blue { background: color-mix(in srgb, var(--x2d-blue) 13%, transparent); color: var(--x2d-blue); }
      /* ---------- tabs */
      .tabs { display: flex; gap: 3px; padding: 4px 8px 8px; overflow-x: auto; scrollbar-width: none; }
      .tabs::-webkit-scrollbar { display: none; }
      .tabs button { display: flex; flex-direction: column; align-items: center; gap: 3px; min-width: 58px;
        padding: 7px 8px; border: none; border-radius: 12px; background: none; cursor: pointer;
        color: var(--x2d-dim); font-size: 10px; font-weight: 550; transition: background .15s, color .15s; }
      .tabs button:hover { background: var(--x2d-track); }
      .tabs button.on { color: var(--primary-color);
        background: color-mix(in srgb, var(--primary-color) 12%, transparent); }
      /* ---------- primitives */
      .row { display: flex; gap: 8px; align-items: center; }
      .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
      .grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
      .tile { background: var(--x2d-chip); border-radius: 12px; padding: 9px 11px; }
      .tile .v { font-size: 17px; font-weight: 650; letter-spacing: .2px; }
      .tile .l { font-size: 10px; color: var(--x2d-dim); margin-top: 1px; }
      .btn { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px;
        padding: 10px 4px; border-radius: 13px; border: none; cursor: pointer; font-size: 11px; font-weight: 550;
        background: var(--x2d-chip); color: var(--primary-text-color);
        transition: transform .08s, filter .15s; }
      .btn:hover { filter: brightness(1.06); }
      .btn:active { transform: scale(.96); }
      .btn:disabled { opacity: .35; cursor: default; transform: none; }
      .btn.green { background: color-mix(in srgb, var(--x2d-ok) 14%, transparent); color: var(--x2d-ok); }
      .btn.amber { background: color-mix(in srgb, var(--x2d-warn) 15%, transparent); color: var(--x2d-warn); }
      .btn.red { background: color-mix(in srgb, var(--x2d-bad) 12%, transparent); color: var(--x2d-bad); }
      .btn.blue { background: color-mix(in srgb, var(--x2d-blue) 12%, transparent); color: var(--x2d-blue); }
      .btn.purple { background: color-mix(in srgb, var(--x2d-purple) 13%, transparent); color: var(--x2d-purple); }
      .btn.solid { background: var(--primary-color); color: var(--text-primary-color, #fff); }
      .bar { position: relative; height: 15px; border-radius: 8px; background: var(--x2d-track); overflow: hidden; }
      .bar > div { height: 100%; border-radius: 8px; transition: width .5s; }
      .bar span { position: absolute; inset: 0; font-size: 10px; font-weight: 650; text-align: center; line-height: 15px; }
      .sect { font-size: 10.5px; font-weight: 650; color: var(--x2d-dim); text-transform: uppercase;
        letter-spacing: .6px; margin: 13px 0 7px; display: flex; align-items: center; justify-content: space-between; }
      select, input[type=text], input[type=number], input[type=datetime-local] { background: var(--x2d-chip);
        color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 10px;
        padding: 7px 9px; font: inherit; font-size: 13px; max-width: 100%; }
      input[type=range] { width: 100%; accent-color: var(--primary-color); }
      .list { display: flex; flex-direction: column; gap: 6px; }
      .item { display: flex; align-items: center; gap: 9px; background: var(--x2d-chip); border-radius: 12px;
        padding: 8px 11px; font-size: 12.5px; }
      .item .grow { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .item .d2 { font-size: 10.5px; color: var(--x2d-dim); }
      .iconbtn { border: none; background: none; cursor: pointer; color: var(--x2d-dim); padding: 5px;
        border-radius: 8px; font-size: 14px; line-height: 1; }
      .iconbtn:hover { background: var(--x2d-track); color: var(--primary-text-color); }
      .gal { display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 8px; }
      .clip { border-radius: 12px; overflow: hidden; background: var(--x2d-chip); cursor: pointer;
        border: 2px solid transparent; transition: border-color .15s; }
      .clip.sel { border-color: var(--primary-color); }
      .clip img { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; background: #16181d; }
      .clip .cap { padding: 5px 8px; font-size: 10px; line-height: 1.35; }
      video { width: 100%; border-radius: var(--x2d-r); background: #000; display: block; }
      .confirm { display: flex; gap: 8px; align-items: center; padding: 11px var(--pad);
        background: color-mix(in srgb, var(--x2d-bad) 9%, transparent); font-size: 12.5px; }
      .confirm button { padding: 7px 15px; border-radius: 9px; border: none; cursor: pointer; font-weight: 600; }
      .steps { display: flex; gap: 5px; font-size: 10.5px; font-weight: 550; }
      .steps div { flex: 1; text-align: center; padding: 5px 0; border-radius: 9px; background: var(--x2d-chip); }
      .steps .done { background: color-mix(in srgb, var(--x2d-ok) 20%, transparent); color: var(--x2d-ok); }
      .steps .cur { background: color-mix(in srgb, var(--x2d-warn) 24%, transparent); color: var(--x2d-warn); }
      .jog { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; max-width: 250px; }
      .jog button { aspect-ratio: 1.55; border-radius: 12px; border: none; cursor: pointer; font-weight: 650;
        font-size: 13px; background: color-mix(in srgb, var(--x2d-blue) 11%, transparent); color: var(--x2d-blue);
        transition: transform .08s; }
      .jog button:active { transform: scale(.94); }
      .jog button.z { background: color-mix(in srgb, var(--x2d-teal) 13%, transparent); color: var(--x2d-teal); }
      .jog button.misc { background: var(--x2d-chip); color: var(--primary-text-color); font-size: 10px; font-weight: 550; }
      .jog button:disabled { opacity: .35; }
      .objrow.skipped { opacity: .45; text-decoration: line-through; }
      table.hist { width: 100%; border-collapse: collapse; font-size: 11.5px; }
      table.hist td, table.hist th { padding: 6px; text-align: left; border-bottom: 1px solid var(--divider-color); }
      table.hist th { color: var(--x2d-dim); font-weight: 600; font-size: 10.5px; text-transform: uppercase; letter-spacing: .4px; }
      .sw { display: flex; justify-content: space-between; align-items: center; padding: 7px 0; font-size: 12.5px; }
      .toggle { width: 38px; height: 21px; border-radius: 11px; background: var(--x2d-track); position: relative;
        cursor: pointer; flex: none; transition: background .2s; }
      .toggle.on { background: var(--primary-color); }
      .toggle::after { content: ""; position: absolute; top: 2.5px; left: 2.5px; width: 16px; height: 16px;
        border-radius: 50%; background: #fff; transition: left .2s; box-shadow: 0 1px 2px rgba(0,0,0,.25); }
      .toggle.on::after { left: 19px; }
      .mbar { height: 6px; border-radius: 3px; background: var(--x2d-track); overflow: hidden; flex: 1; }
      .mbar div { height: 100%; border-radius: 3px; }
      .advice { border-left: 3px solid var(--sev); border-radius: 10px; padding: 8px 11px;
        background: color-mix(in srgb, var(--sev) 7%, transparent); font-size: 12px; }
      .advice b { display: block; font-size: 12.5px; margin-bottom: 2px; }
      .advice .d2 { font-size: 11px; color: var(--x2d-dim); }
      .sheet { background: var(--x2d-chip); border-radius: var(--x2d-r); padding: 12px; margin-top: 8px;
        animation: slidein .18s ease; }
      @keyframes slidein { from { opacity: 0; transform: translateY(-4px); } }
      .spec { display: grid; grid-template-columns: 1fr 1fr; gap: 5px 12px; font-size: 11.5px; margin: 8px 0; }
      .spec div b { font-weight: 650; }
      .spec .k { color: var(--x2d-dim); font-size: 10px; text-transform: uppercase; letter-spacing: .4px; }
      /* ---------- landing */
      .land { padding: 34px 22px 26px; text-align: center; }
      .land .halo { width: 86px; height: 86px; margin: 0 auto 16px; border-radius: 26px; display: flex;
        align-items: center; justify-content: center; color: var(--primary-color);
        background: color-mix(in srgb, var(--primary-color) 10%, transparent); animation: float 4s ease-in-out infinite; }
      @keyframes float { 50% { transform: translateY(-5px); } }
      .land h1 { font-size: 21px; font-weight: 700; margin: 0 0 6px; letter-spacing: .2px; }
      .land .tag { font-size: 13px; color: var(--x2d-dim); margin: 0 auto 22px; max-width: 420px; line-height: 1.5; }
      .feat { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; max-width: 460px; margin: 0 auto 24px; text-align: left; }
      .feat div { background: var(--x2d-chip); border-radius: 13px; padding: 11px 12px; font-size: 11.5px; line-height: 1.45; }
      .feat div b { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 3px; }
      .feat svg { width: 14px; height: 14px; color: var(--primary-color); }
      .land .cta { display: inline-flex; align-items: center; gap: 8px; padding: 13px 26px; border-radius: 14px;
        border: none; cursor: pointer; font-size: 14.5px; font-weight: 650; background: var(--primary-color);
        color: var(--text-primary-color, #fff); transition: transform .1s, filter .15s; }
      .land .cta:hover { filter: brightness(1.08); }
      .land .cta:active { transform: scale(.97); }
      .land .hint { font-size: 11px; color: var(--x2d-dim); margin-top: 16px; line-height: 1.55; }
    `;
    return s;
  }

  _toggle(on, cb) { return h("div", { class: `toggle${on ? " on" : ""}`, onclick: cb }); }
  _tile(v, l) { return h("div", { class: "tile" }, h("div", { class: "v" }, String(v)), h("div", { class: "l" }, l)); }

  // ================================================================ LANDING
  _landing() {
    const wrap = h("div", { class: "land" });
    wrap.append(
      h("div", { class: "halo" }, icon("live", 46)),
      h("h1", {}, "X2D Command Center"),
      h("p", { class: "tag" },
        "Your printer's home inside Home Assistant — live control, heat soak, timelapse studio, ",
        "filament science and print insights. All local, with optional Bambu-cloud hybrid."),
      h("div", { class: "feat" },
        h("div", {}, h("b", {}, icon("cloud"), "One-minute enrollment"), "Sign in with your Bambu account — it finds the printer, access code and LAN address for you."),
        h("div", {}, h("b", {}, icon("soak"), "Garage-grade heat soak"), "Material presets, cold-weather scaling and a learned heat-rate model, ready before you are."),
        h("div", {}, h("b", {}, icon("filament"), "Filament science built in"), "Thermal, drying and bonding data for 17 materials — the app warns before the print fails."),
        h("div", {}, h("b", {}, icon("timelapse"), "Timelapse studio"), "Frame-per-layer capture, auto-render, GIFs and a library you can cast to the TV.")),
      h("button", { class: "cta", onclick: () => this._nav(`/config/integrations/add?domain=${DOMAIN}`) },
        icon("live", 18), "Connect your X2D"),
      h("div", { class: "hint" },
        "Printer not here yet? This screen is ready and waiting. When it arrives: power it up, join it to Wi-Fi, ",
        h("br"),
        "then tap the button — scanning, cloud sign-in and manual setup are all offered."),
      h("div", { style: "margin-top:14px" },
        h("button", { class: "btn", style: "display:inline-flex;flex-direction:row;padding:8px 16px", onclick: () => { this._noPrinter = false; this._error = null; this._unsub = null; this._subscribe(); this._render(); } },
          "I've added it — reconnect")));
    return wrap;
  }

  // ================================================================ HEADER / TABS
  _header() {
    const d = this._data, st = d.state;
    const meta = STATE[st.gcode_state] || STATE.idle;
    const chips = [];
    const conn = d.connection || {};
    if (!d.connected) chips.push(h("span", { class: "chip bad" }, icon("lan"), "offline"));
    else chips.push(h("span", { class: "chip" + (conn.link === "cloud" ? " blue" : "") },
      icon(conn.link === "cloud" ? "cloud" : "lan"),
      conn.mode === "hybrid" ? `hybrid·${conn.link}` : conn.link));
    if (d.controls_ok === false) chips.push(h("span", { class: "chip bad", title: "Enable LAN Only + Developer Mode on the printer" }, "controls rejected"));
    if (st.hms.length) chips.push(h("span", { class: "chip bad" }, `${st.hms.length} HMS`));
    const alerts = (d.advisor || []).filter((w) => w.severity === "alert" || w.severity === "warn");
    if (alerts.length) chips.push(h("span", { class: "chip warn", onclick: () => { this._tab = "insights"; this._render(); }, style: "cursor:pointer" }, icon("bulb"), String(alerts.length)));
    if (d.env.too_cold) chips.push(h("span", { class: "chip bad" }, `❄ ${Math.round(d.env.ambient_f)}°F`));
    else if (d.env.ambient_f != null) chips.push(h("span", { class: "chip" }, `${Math.round(d.env.ambient_f)}°F${d.env.rh != null ? ` · ${Math.round(d.env.rh)}%` : ""}`));
    if (d.pace.drift > 10) chips.push(h("span", { class: "chip warn" }, `+${d.pace.drift}m`));
    if (d.timelapse.recording) chips.push(h("span", { class: "chip warn" }, `● ${d.timelapse.frames}`));
    if (d.soak.active) chips.push(h("span", { class: "chip warn" }, icon("soak"), d.soak.phase));
    if (d.queue?.length) chips.push(h("span", { class: "chip blue" }, icon("queue"), String(d.queue.length)));
    return h("div", { class: "hdr", style: `--dot:${meta.c}` },
      h("div", { class: "dot" + (st.gcode_state === "running" ? " live" : "") }),
      h("div", {},
        h("div", { class: "name" }, d.name),
        h("div", { class: "sub" }, `${meta.label}${st.stage && !["idle", st.gcode_state].includes(st.stage) ? " · " + st.stage.replace(/_/g, " ") : ""}`)),
      h("div", { class: "right" }, chips));
  }

  _tabbar() {
    const bar = h("div", { class: "tabs" });
    for (const t of this._config.tabs) {
      if (!TABS.includes(t)) continue;
      bar.append(h("button", {
        class: this._tab === t ? "on" : "",
        onclick: () => { this._tab = t; localStorage.setItem("x2d_card_tab", t); this._render(); },
      }, icon(t), t));
    }
    return bar;
  }

  _confirmBar() {
    const c = this._confirm;
    return h("div", { class: "confirm" },
      h("span", { style: "flex:1" }, c.text),
      h("button", { style: "background:var(--x2d-bad);color:#fff", onclick: () => { const fn = c.fn; this._confirm = null; fn(); } }, "Yes"),
      h("button", { style: "background:var(--x2d-chip);color:var(--primary-text-color)", onclick: () => { this._confirm = null; this._render(); } }, "No"));
  }

  // ================================================================ LIVE
  _tab_live() {
    const d = this._data, st = d.state;
    const wrap = h("div", { class: "pad", style: "padding-top:4px" });
    const cam = d.entities.camera && this._hass.states[d.entities.camera];
    if (cam && cam.attributes.entity_picture) {
      wrap.append(h("img", {
        src: cam.attributes.entity_picture + `&cachebust=${Math.floor(Date.now() / 10000)}`,
        style: "width:100%;border-radius:var(--x2d-r);aspect-ratio:16/9;object-fit:cover;background:#16181d;cursor:pointer",
        onclick: () => { const ev = new Event("hass-more-info", { bubbles: true, composed: true }); ev.detail = { entityId: d.entities.camera }; this.dispatchEvent(ev); },
      }));
    }
    const active = ["running", "pause", "prepare"].includes(st.gcode_state);
    const color = (STATE[st.gcode_state] || STATE.idle).c;

    // job row with progress ring
    const jobRow = h("div", { class: "row", style: "margin-top:12px;gap:13px" });
    const ringWrap = h("div", { style: "position:relative;flex:none" }, ring(st.percent, 64, color),
      h("div", { style: "position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700" }, `${st.percent}%`));
    jobRow.append(ringWrap, h("div", { style: "min-width:0;flex:1" },
      h("div", { style: "font-weight:650;font-size:14.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" },
        st.task || (active ? "Untitled job" : "No active job")),
      h("div", { class: "d2", style: "font-size:11.5px;color:var(--x2d-dim);margin-top:2px" },
        active ? `Layer ${st.layer}/${st.total_layers} · ${fmtMin(st.remaining_min)} left` : "Pick a file in Files, or send one from the slicer"),
      h("div", { class: "d2", style: "font-size:11.5px;color:var(--x2d-dim)" },
        active ? `ETA ${fmtClock(d.pace.printer_eta)}${d.pace.drift > 5 ? ` (+${d.pace.drift}m)` : ""} · pace ${fmtClock(d.pace.eta)}` : "")));
    wrap.append(jobRow);

    // controls
    const btns = h("div", { class: "grid4", style: "margin-top:12px" });
    if (st.gcode_state === "running")
      btns.append(h("button", { class: "btn amber", onclick: () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"pause"}}' }) }, "⏸", "Pause"));
    if (st.gcode_state === "pause")
      btns.append(h("button", { class: "btn green", onclick: () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"resume"}}' }) }, "▶", "Resume"));
    if (active)
      btns.append(h("button", { class: "btn red", onclick: () => this._ask("Abort the current print?", () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"stop"}}' })) }, "⏹", "Stop"));
    const lightOn = st.lights.chamber_light === "on";
    btns.append(h("button", {
      class: "btn" + (lightOn ? " amber" : ""),
      onclick: () => this._svc("send_command", { payload: JSON.stringify({ system: { sequence_id: "0", command: "ledctrl", led_node: "chamber_light", led_mode: lightOn ? "off" : "on", led_on_time: 500, led_off_time: 500, loop_times: 0, interval_time: 0 } }) }),
    }, "💡", "Light"));
    btns.append(h("button", { class: "btn blue", onclick: () => this._svc("refresh") }, "⟳", "Refresh"));
    if (!active && d.queue?.length)
      btns.append(h("button", { class: "btn green", onclick: () => this._ask(`Bed clear? Start ${d.queue[0].file}?`, () => this._svc("queue_start_next")) }, "⏭", `Next (${d.queue.length})`));
    wrap.append(btns);

    // speed
    const spd = h("div", { class: "grid4", style: "margin-top:8px" });
    SPEEDS.forEach((name, i) => spd.append(h("button", {
      class: "btn" + (st.speed === name ? " green" : ""),
      onclick: () => this._svc("send_command", { payload: JSON.stringify({ print: { sequence_id: "0", command: "print_speed", param: String(i + 1) } }) }),
    }, name === "ludicrous" ? "🚀" : "⚡", name)));
    wrap.append(h("div", { class: "sect" }, "Speed"), spd);

    // thermals
    const noz = st.nozzles[st.active_nozzle] || st.nozzles[0] || {};
    wrap.append(h("div", { class: "sect" }, "Thermals"), h("div", { class: "grid3" },
      this._tile(`${Math.round(noz.temp ?? 0)}°`, `nozzle → ${Math.round(noz.target ?? 0)}°`),
      this._tile(`${Math.round(st.bed ?? 0)}°`, `bed → ${Math.round(st.bed_target ?? 0)}°`),
      this._tile(`${Math.round(st.chamber ?? 0)}°`, st.chamber_target ? `chamber → ${Math.round(st.chamber_target)}°` : "chamber")));
    if (st.nozzles.length > 1)
      wrap.append(h("div", { class: "grid2", style: "margin-top:7px" },
        ...st.nozzles.map((n) => this._tile(`${Math.round(n.temp ?? 0)}° / ${Math.round(n.target ?? 0)}°`,
          `nozzle ${n.id + 1}${n.id === st.active_nozzle ? " · active" : ""} · ${n.diameter ?? "?"} mm`))));

    // pace & cost
    wrap.append(h("div", { class: "sect" }, "Pace & cost"), h("div", { class: "grid3" },
      this._tile(d.pace.spl ? `${d.pace.spl}s` : "—", "per layer"),
      this._tile(d.pace.lph ?? "—", "layers/h"),
      this._tile(fmtMin(d.pace.elapsed), "elapsed"),
      this._tile(d.job?.weight_g ? `${Math.round(d.job.weight_g)}g` : "—", "filament"),
      this._tile(d.job?.cost?.total != null ? d.job.cost.total.toFixed(2) : "—", "job cost"),
      this._tile(d.job?.energy_kwh ? d.job.energy_kwh.toFixed(2) : "—", "kWh")));

    if (d.pairing)
      wrap.append(h("div", { class: "advice", style: `--sev:${d.pairing.kind === "risky" ? "var(--x2d-bad)" : "var(--x2d-blue)"};margin-top:10px` },
        h("b", {}, `Multi-material: ${d.pairing.kind.replace("-", " ")} (${d.pairing.families.join(" + ")})`),
        h("span", { class: "d2" }, d.pairing.pairs[0]?.note || "")));

    if (st.hms.length) {
      const list = h("div", { class: "list", style: "margin-top:7px" });
      for (const e of st.hms) list.append(h("div", { class: "advice", style: "--sev:var(--x2d-bad)" },
        h("b", {}, e.code), h("span", { class: "d2" }, e.text || ""), " ",
        h("a", { href: e.wiki, target: "_blank", style: "font-size:11px" }, "wiki ↗")));
      wrap.append(h("div", { class: "sect" }, "HMS"), list);
    }
    return wrap;
  }

  // ================================================================ SOAK
  _tab_soak() {
    const d = this._data, s = d.soak, set = d.settings;
    const wrap = h("div", { class: "pad" });
    const phases = ["heating", "soaking", "ready"];
    const map = { warming_ambient: -0.5, heating: 0, soaking: 1, ready: 2, keep_warm: 2 };
    const idx = map[s.phase] ?? -1;
    wrap.append(h("div", { class: "steps" }, ...phases.map((p, i) =>
      h("div", { class: idx > i ? "done" : Math.floor(idx) === i ? "cur" : "" }, p))));
    wrap.append(h("div", { class: "bar", style: "margin:9px 0" },
      h("div", { style: `width:${s.progress}%;background:${s.phase === "aborted" ? "var(--x2d-bad)" : s.progress >= 100 ? "var(--x2d-ok)" : "var(--x2d-warn)"}` }),
      h("span", {}, `${s.progress}%`)));
    const status = s.phase === "idle" ? `Idle · would take ~${fmtMin(s.remaining)} (${s.required}m hold)`
      : s.phase === "soaking" ? `Held ${s.held}/${s.required} min · ready ~${fmtClock(s.ready_at)}`
      : s.phase === "aborted" ? "Aborted — chamber stalled"
      : ["ready", "keep_warm"].includes(s.phase) ? "Soaked — ready to print"
      : `${s.phase.replace("_", " ")} · ~${fmtMin(s.remaining)} · ready ~${fmtClock(s.ready_at)}`;
    wrap.append(h("div", { style: "font-size:12.5px;color:var(--x2d-dim);margin-bottom:9px" }, status));

    const presets = s.presets || {};
    wrap.append(h("div", { class: "sect" }, "Material"),
      h("select", { style: "width:100%", onchange: (e) => this._setSetting("soak_preset", e.target.value) },
        ...Object.entries(presets).map(([k, p]) => h("option", { value: k, selected: set.soak_preset === k }, p.label))));
    wrap.append(h("div", { class: "grid3", style: "margin-top:8px" },
      this._numTile("chamber °C", set.soak_chamber, 0, 65, (v) => this._setSetting("soak_chamber", v)),
      this._numTile("bed °C", set.soak_bed, 0, 120, (v) => this._setSetting("soak_bed", v)),
      this._numTile("hold min", set.soak_hold, 0, 120, (v) => this._setSetting("soak_hold", v))));
    if (d.env.ambient_f != null && s.required > set.soak_hold)
      wrap.append(h("div", { style: "font-size:11px;color:var(--x2d-dim);margin-top:5px" },
        `❄ Cold room: +${(s.required - set.soak_hold).toFixed(0)} min → ${s.required} min hold`));

    wrap.append(h("div", { class: "grid2", style: "margin-top:11px" },
      s.active
        ? h("button", { class: "btn red", onclick: () => this._svc("cancel_heat_soak") }, "✕", "Cancel & cool")
        : h("button", { class: "btn green", onclick: () => this._svc("start_heat_soak") }, "🔥", `Start soak (~${fmtMin(s.remaining)})`),
      h("button", {
        class: "btn" + (set.soak_autostart ? " green" : ""),
        onclick: () => this._setSetting("soak_autostart", !set.soak_autostart),
      }, set.soak_autostart ? "▶" : "🔔", set.soak_autostart ? "Auto-start print" : "Notify only")));
    if (set.soak_autostart)
      wrap.append(h("div", { style: "font-size:11px;color:var(--x2d-dim);margin-top:5px" },
        set.sd_selected ? `Will start: ${set.sd_selected}` : "⚠ No file selected (Files tab)"));

    const rb = set.soak_ready_by ? new Date(set.soak_ready_by) : null;
    const toLocal = (dt) => new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    wrap.append(h("div", { class: "sect" }, "Ready by"), h("div", { class: "row" },
      h("input", {
        type: "datetime-local", value: rb ? toLocal(rb) : "", style: "flex:1",
        onchange: (e) => this._setSetting("soak_ready_by", e.target.value ? new Date(e.target.value).toISOString() : null),
      }),
      h("button", {
        class: "btn" + (set.soak_armed ? " blue" : ""), style: "min-width:88px",
        onclick: () => this._setSetting("soak_armed", !set.soak_armed),
      }, "⏰", set.soak_armed ? `starts ${fmtClock(s.start_at)}` : "Arm")));

    wrap.append(h("div", { class: "sect" }, "Behaviour"));
    const sw = (label, key) => h("div", { class: "sw" }, h("span", {}, label),
      this._toggle(!!set[key], () => this._setSetting(key, !set[key])));
    wrap.append(sw("Longer soak when the room is cold", "soak_cold_scaling"));
    wrap.append(sw("Use room heater below startup floor", "soak_use_heater"));
    wrap.append(h("div", { style: "font-size:11px;color:var(--x2d-dim);margin-top:6px" },
      `Learned chamber heat rate: ${s.rate} °C/min · deeper tuning in the integration's Options`));
    return wrap;
  }

  _numTile(label, value, min, max, cb) {
    return h("div", { class: "tile" },
      h("input", {
        type: "number", value, min, max,
        style: "width:100%;border:none;background:none;font-size:16px;font-weight:650;color:inherit;padding:0",
        onchange: (e) => cb(Number(e.target.value)),
      }),
      h("div", { class: "l" }, label));
  }

  // ================================================================ CONTROL
  _tab_control() {
    const d = this._data, st = d.state;
    const wrap = h("div", { class: "pad" });
    if (d.controls_ok === false)
      wrap.append(h("div", { class: "advice", style: "--sev:var(--x2d-bad);margin-bottom:9px" },
        h("b", {}, "Printer refused the last command"),
        h("span", { class: "d2" }, "Enable LAN Only Mode + Developer Mode on the printer screen for control.")));
    const idle = !["running", "prepare"].includes(st.gcode_state);
    this._jogStep = this._jogStep ?? 10;

    wrap.append(h("div", { class: "sect" }, "Motion",
      h("select", { style: "padding:3px 7px;font-size:11px", onchange: (e) => { this._jogStep = Number(e.target.value); } },
        ...[0.1, 1, 10, 50].map((v) => h("option", { value: v, selected: v === this._jogStep }, `${v} mm`)))));
    const jog = (axis, dir) => this._svc("jog", { axis, distance: dir * this._jogStep });
    const jb = (label, cls, fn) => h("button", { class: cls, disabled: !idle, onclick: fn }, label);
    wrap.append(h("div", { class: "jog" },
      jb("Y+", "", () => jog("Y", 1)), jb("Z+", "z", () => jog("Z", 1)), jb("🏠", "misc", () => this._svc("home")),
      jb("X−", "", () => jog("X", -1)), jb("Y−", "", () => jog("Y", -1)), jb("X+", "", () => jog("X", 1)),
      jb("Z−", "z", () => jog("Z", -1)),
      jb("Motors off", "misc", () => this._svc("send_gcode", { gcode: "M84" })),
      jb("Sync", "misc", () => this._svc("refresh"))));

    wrap.append(h("div", { class: "sect" }, "Heaters"));
    const heat = (label, cur, tgt, max, fn) => h("div", { class: "tile" },
      h("div", { class: "row", style: "justify-content:space-between" },
        h("span", { class: "v" }, `${Math.round(cur ?? 0)}°`),
        h("input", { type: "number", value: Math.round(tgt ?? 0), min: 0, max, style: "width:62px;padding:4px 6px", onchange: (e) => fn(Number(e.target.value)) })),
      h("div", { class: "l" }, label));
    const noz = st.nozzles[st.active_nozzle] || st.nozzles[0] || {};
    wrap.append(h("div", { class: "grid3" },
      heat("nozzle", noz.temp, noz.target, 320, (v) => this._svc("send_gcode", { gcode: `M104 S${v}` })),
      heat("bed", st.bed, st.bed_target, 120, (v) => this._svc("send_gcode", { gcode: `M140 S${v}` })),
      heat("chamber", st.chamber, st.chamber_target, 65, (v) => this._svc("send_gcode", { gcode: `M141 S${v}` }))));
    wrap.append(h("div", { class: "grid3", style: "margin-top:7px" },
      h("button", { class: "btn green", onclick: () => this._svc("send_gcode", { gcode: "M104 S220\nM140 S55" }) }, "🔥", "PLA 220/55"),
      h("button", { class: "btn amber", onclick: () => this._svc("send_gcode", { gcode: "M104 S260\nM140 S100\nM141 S60" }) }, "🔥", "ABS 260/100/60"),
      h("button", { class: "btn blue", onclick: () => this._svc("send_gcode", { gcode: "M104 S0\nM140 S0\nM141 S0" }) }, "❄", "Cool all")));

    this._extLen = this._extLen ?? 10;
    const cold = (noz.temp ?? 0) < 170;
    wrap.append(h("div", { class: "sect" }, "Extruder"), h("div", { class: "row" },
      h("input", { type: "number", value: this._extLen, min: 1, max: 100, style: "width:64px", onchange: (e) => { this._extLen = Number(e.target.value); } }),
      h("span", { style: "font-size:11px;color:var(--x2d-dim)" }, "mm"),
      h("button", { class: "btn amber", style: "flex:1", disabled: cold, onclick: () => this._svc("extrude", { distance: this._extLen }) }, "⬇", cold ? "nozzle cold" : "Extrude"),
      h("button", { class: "btn amber", style: "flex:1", disabled: cold, onclick: () => this._svc("extrude", { distance: this._extLen, direction: "retract" }) }, "⬆", "Retract")));

    wrap.append(h("div", { class: "sect" }, "Fans"));
    for (const [key, label] of [["part", "Part"], ["aux", "Aux"], ["chamber", "Exhaust"]]) {
      const v = st.fans[key] ?? 0;
      wrap.append(h("div", { class: "row", style: "margin-bottom:5px" },
        h("span", { style: "width:52px;font-size:11.5px" }, label),
        h("input", {
          type: "range", min: 0, max: 100, step: 5, value: v,
          onchange: (e) => this._svc("send_gcode", { gcode: `M106 P${{ part: 1, aux: 2, chamber: 3 }[key]} S${Math.round(e.target.value * 2.55)}` }),
        }),
        h("span", { style: "width:36px;font-size:11.5px;text-align:right" }, `${v}%`)));
    }

    wrap.append(h("div", { class: "sect" }, "AI detectors (pause on detect)"));
    const xrow = h("div", { class: "grid3" });
    for (const [mod, label] of [["spaghetti_detector", "Spaghetti"], ["first_layer_inspector", "1st layer"], ["buildplate_marker_detector", "Plate"]]) {
      const on = !!st.xcam[mod];
      xrow.append(h("button", {
        class: "btn" + (on ? " green" : ""),
        onclick: () => this._svc("send_command", { payload: JSON.stringify({ xcam: { sequence_id: "0", command: "xcam_control_set", module_name: mod, control: !on, enable: !on, print_halt: true } }) }),
      }, on ? "👁" : "◌", label));
    }
    wrap.append(xrow);

    wrap.append(h("div", { class: "sect" }, "Calibration (idle only)"), h("div", { class: "grid3" },
      h("button", { class: "btn", disabled: !idle, onclick: () => this._ask("Run bed levelling?", () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"calibration","option":2}}' })) }, "📐", "Bed level"),
      h("button", { class: "btn", disabled: !idle, onclick: () => this._ask("Run vibration calibration?", () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"calibration","option":4}}' })) }, "📳", "Vibration"),
      h("button", { class: "btn", disabled: !idle, onclick: () => this._ask("Run full calibration (10+ min)?", () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"calibration","option":14}}' })) }, "🎛", "Full")));

    wrap.append(h("div", { class: "sect" }, "Console"));
    const gIn = h("input", { type: "text", placeholder: "G-code, e.g. M141 S40", style: "flex:1" });
    gIn.addEventListener("keydown", (e) => { if (e.key === "Enter") this._svc("send_gcode", { gcode: gIn.value }); });
    wrap.append(h("div", { class: "row", style: "margin-bottom:6px" }, gIn,
      h("button", { class: "btn purple", onclick: () => this._svc("send_gcode", { gcode: gIn.value }) }, "➤", "Send")));
    const jIn = h("input", { type: "text", placeholder: '{"pushing":{"command":"pushall"}}', style: "flex:1" });
    wrap.append(h("div", { class: "row" }, jIn,
      h("button", { class: "btn purple", onclick: () => this._svc("send_command", { payload: jIn.value }) }, "➤", "JSON")));
    return wrap;
  }

  // ================================================================ FILES (+ queue)
  _tab_files() {
    const d = this._data, set = d.settings;
    const wrap = h("div", { class: "pad" });
    const idle = !["running", "prepare", "pause"].includes(d.state.gcode_state);
    const lan = d.connection?.has_lan !== false;

    if (!lan)
      wrap.append(h("div", { class: "advice", style: "--sev:var(--x2d-blue);margin-bottom:9px" },
        h("b", {}, "Cloud-only mode"),
        h("span", { class: "d2" }, "File browsing/upload needs the LAN link — set a LAN address in Options → Connection.")));

    const file = h("input", { type: "file", accept: ".3mf", style: "display:none" });
    file.addEventListener("change", async () => {
      if (!file.files.length) return;
      const fd = new FormData();
      fd.append("file", file.files[0]);
      this._toast(`Uploading ${file.files[0].name}…`);
      try {
        const resp = await fetch(`/api/${DOMAIN}/${d.entry_id}/upload`, {
          method: "POST", body: fd, headers: { Authorization: `Bearer ${this._hass.auth.data.access_token}` },
        });
        const out = await resp.json();
        this._toast(resp.ok ? `Uploaded ${out.remote}` : `Upload failed: ${out.error}`);
        if (resp.ok) this._svc("refresh");
      } catch (e) { this._toast(`Upload failed: ${e.message}`); }
    });
    wrap.append(file, h("div", { class: "grid2" },
      h("button", { class: "btn blue", disabled: !lan, onclick: () => file.click() }, "⬆", "Upload .3mf to printer"),
      h("button", { class: "btn", onclick: () => this._svc("refresh") }, "⟳", "Refresh list")));

    wrap.append(h("div", { class: "sect" }, "Print options"));
    const opts = [["print_use_ams", "AMS"], ["print_bed_level", "Bed level"], ["print_layer_inspect", "1st layer"],
                  ["print_timelapse", "Timelapse"], ["print_flow_cali", "Flow cal"], ["print_vibration", "Vibration"]];
    const og = h("div", { class: "grid3" });
    for (const [key, label] of opts) og.append(h("button", {
      class: "btn" + (set[key] ? " green" : ""), onclick: () => this._setSetting(key, !set[key]),
    }, set[key] ? "✓" : "○", label));
    wrap.append(og, h("div", { class: "row", style: "margin-top:7px" },
      h("span", { style: "font-size:11.5px;color:var(--x2d-dim)" }, "Plate"),
      h("input", { type: "number", min: 1, max: 16, value: set.print_plate, style: "width:62px", onchange: (e) => this._setSetting("print_plate", Number(e.target.value)) })));

    // ---- queue
    wrap.append(h("div", { class: "sect" }, `Queue · ${d.queue.length}`,
      h("span", { class: "row", style: "gap:5px;font-size:10px;text-transform:none;letter-spacing:0" },
        "auto-continue", this._toggle(!!set.queue_auto, () => this._setSetting("queue_auto", !set.queue_auto)))));
    if (d.queue.length) {
      const ql = h("div", { class: "list" });
      d.queue.forEach((q, i) => ql.append(h("div", { class: "item" },
        h("span", { style: "font-weight:650;color:var(--x2d-dim);font-size:11px;width:16px" }, String(i + 1)),
        h("div", { class: "grow" }, q.file, h("div", { class: "d2" }, `plate ${q.plate}`)),
        h("button", { class: "iconbtn", onclick: () => this._svc("queue_remove", { index: i }) }, "✕"))));
      wrap.append(ql, h("div", { class: "grid2", style: "margin-top:7px" },
        h("button", { class: "btn green", disabled: !idle, onclick: () => this._ask(`Bed clear? Start ${d.queue[0].file}?`, () => this._svc("queue_start_next")) }, "⏭", "Start next"),
        h("button", { class: "btn red", onclick: () => this._ask("Clear the whole queue?", () => this._svc("queue_clear")) }, "🗑", "Clear queue")));
    } else {
      wrap.append(h("div", { style: "font-size:11.5px;color:var(--x2d-dim)" },
        "Queue files below with ➕ — they start one after another (notification between prints, or auto with a 90 s grace)."));
    }

    // ---- SD list
    wrap.append(h("div", { class: "sect" }, `On printer · ${d.sd_files.length}`));
    const list = h("div", { class: "list" });
    for (const f of d.sd_files.slice(0, 60)) {
      const selq = set.sd_selected === f.path;
      list.append(h("div", { class: "item", style: selq ? "outline:2px solid var(--primary-color)" : "" },
        h("div", { class: "grow", style: "cursor:pointer", onclick: () => this._setSetting("sd_selected", f.path) },
          h("div", {}, f.name), h("div", { class: "d2" }, `${fmtMB(f.size)} · ${f.modify || ""}`)),
        h("button", { class: "iconbtn", title: "Queue", onclick: () => this._svc("queue_add", { file: f.path }) }, "➕"),
        h("button", { class: "iconbtn", title: "Print now", disabled: !idle,
          onclick: () => this._ask(`Print ${f.name} (plate ${set.print_plate})?`, () => this._svc("print_file", { file: f.path })) }, "🖨"),
        h("button", { class: "iconbtn", title: "Delete from printer",
          onclick: () => this._ask(`Delete ${f.name} from the printer?`, () => this._svc("delete_sd_file", { file: f.path })) }, "🗑")));
    }
    if (!d.sd_files.length) list.append(h("div", { class: "item" }, lan ? "No .3mf files found — upload one or refresh." : "Unavailable in cloud-only mode."));
    wrap.append(list);
    if (set.sd_selected) wrap.append(h("button", {
      class: "btn green", style: "width:100%;margin-top:9px", disabled: !idle,
      onclick: () => this._ask(`Start ${set.sd_selected}?`, () => this._svc("print_file", { file: set.sd_selected })),
    }, "🖨", idle ? `Print selected (plate ${set.print_plate})` : "Printer busy"));
    return wrap;
  }

  // ================================================================ OBJECTS
  _tab_objects() {
    const d = this._data;
    const wrap = h("div", { class: "pad" });
    const meta = d.job_meta;
    if (!meta || !meta.objects?.length) {
      wrap.append(h("div", { class: "item" }, d.job ? "Object list not available for this job yet." : "Objects appear here during a print — tap to exclude them from the rest of the job."));
      return wrap;
    }
    const skipped = new Set(d.state.skipped);
    const bboxes = meta.objects.filter((o) => o.bbox);
    if (bboxes.length) {
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 256 256");
      svg.style.cssText = "width:100%;max-width:300px;display:block;margin:0 auto;background:var(--x2d-chip);border-radius:var(--x2d-r)";
      for (const o of bboxes) {
        const [x1, y1, x2, y2] = o.bbox;
        const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        r.setAttribute("x", x1); r.setAttribute("y", 256 - y2); r.setAttribute("width", Math.max(x2 - x1, 2)); r.setAttribute("height", Math.max(y2 - y1, 2));
        r.setAttribute("rx", 3);
        const isSel = this._skipSel.has(o.id);
        r.setAttribute("fill", skipped.has(o.id) ? "rgba(128,128,128,.35)" : isSel ? "var(--x2d-bad)" : "var(--x2d-ok)");
        r.setAttribute("opacity", skipped.has(o.id) ? "1" : "0.75");
        r.style.cursor = "pointer";
        r.addEventListener("click", () => this._toggleSkip(o.id));
        const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
        t.textContent = `${o.name}${skipped.has(o.id) ? " (skipped)" : ""}`;
        r.append(t);
        svg.append(r);
      }
      wrap.append(svg, h("div", { style: "font-size:10.5px;color:var(--x2d-dim);text-align:center;margin:5px 0 9px" },
        "Bed map — tap an object to mark it, then confirm below"));
    }
    const list = h("div", { class: "list" });
    for (const o of meta.objects) {
      const done = skipped.has(o.id);
      list.append(h("div", { class: "item objrow" + (done ? " skipped" : "") },
        h("input", { type: "checkbox", disabled: done, checked: this._skipSel.has(o.id), onchange: () => this._toggleSkip(o.id) }),
        h("div", { class: "grow" }, o.name, done ? " · skipped" : ""),
        h("span", { class: "d2" }, `#${o.id}`)));
    }
    wrap.append(list);
    if (this._skipSel.size) wrap.append(h("button", {
      class: "btn red", style: "width:100%;margin-top:9px",
      onclick: () => this._ask(`Skip ${this._skipSel.size} object(s) for the rest of this print? This can't be undone.`,
        () => { this._svc("skip_objects", { objects: [...this._skipSel] }); this._skipSel.clear(); }),
    }, "🚫", `Skip ${this._skipSel.size} selected`));
    return wrap;
  }

  _toggleSkip(id) {
    if (this._skipSel.has(id)) this._skipSel.delete(id); else this._skipSel.add(id);
    this._render();
  }

  // ================================================================ FILAMENT
  _tab_filament() {
    const d = this._data;
    const wrap = h("div", { class: "pad" });
    if (!this._db) this._loadDb();
    for (const ams of d.amss) {
      const n = ams.id < 128 ? ams.id + 1 : `HT${ams.id - 127}`;
      const hum = ams.humidity_pct != null ? `${ams.humidity_pct}%` : `${ams.humidity_index ?? "?"}/5`;
      const humBad = (ams.humidity_index ?? 0) >= 4;
      wrap.append(h("div", { class: "sect" }, `AMS ${n}`,
        h("span", { style: "text-transform:none;letter-spacing:0;display:flex;gap:6px" },
          ams.temp != null && h("span", {}, `${Math.round(ams.temp)}°C`),
          h("span", { style: humBad ? "color:var(--x2d-bad)" : "" }, "💧", hum),
          ams.drying_min ? h("span", { style: "color:var(--x2d-warn)" }, `drying ${fmtMin(ams.drying_min)}`) : null)));
      const grid = h("div", { class: "grid4" });
      for (const t of ams.trays) grid.append(this._trayTile(t));
      wrap.append(grid);
    }
    if (d.external.length) {
      wrap.append(h("div", { class: "sect" }, "External"));
      const grid = h("div", { class: "grid4" });
      for (const t of d.external) grid.append(this._trayTile(t));
      wrap.append(grid);
    }
    if (this._sheet) {
      const tray = [...d.amss.flatMap((a) => a.trays), ...d.external].find((t) => t.key === this._sheet);
      if (tray) wrap.append(this._traySheet(tray));
    }
    if (d.pairing)
      wrap.append(h("div", { class: "advice", style: `--sev:${d.pairing.kind === "risky" ? "var(--x2d-bad)" : "var(--x2d-blue)"};margin-top:10px` },
        h("b", {}, `This job: ${d.pairing.kind.replace("-", " ")} (${d.pairing.families.join(" + ")})`),
        ...d.pairing.pairs.map((p) => h("div", { class: "d2", style: "margin-top:2px" }, `${p.pair}: ${p.verdict} — ${p.note}`))));
    wrap.append(h("div", { class: "grid2", style: "margin-top:11px" },
      h("button", { class: "btn amber", onclick: () => this._ask("Unload the current filament?", () => this._svc("unload_filament")) }, "⬆", "Unload"),
      h("button", { class: "btn", onclick: () => this._svc("send_command", { payload: '{"print":{"sequence_id":"0","command":"ams_control","param":"resume"}}' }) }, "⟳", "AMS resume")));
    return wrap;
  }

  _trayTile(t) {
    const active = this._data.state.tray_now === t.global;
    const open = this._sheet === t.key;
    return h("div", {
      class: "tile", style: `border-top:5px solid #${t.color || "666"};cursor:pointer;padding:8px 9px;${active ? "outline:2px solid var(--primary-color);" : ""}${open ? "filter:brightness(1.12);" : ""}`,
      onclick: () => { this._sheet = open ? null : t.key; this._loadDb(); this._render(); },
    },
      h("div", { style: "font-size:11.5px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" },
        t.present ? (t.name || t.type) : "Empty"),
      h("div", { class: "l" }, `${t.ams === 254 ? "ext" : `slot ${t.slot + 1}`}${t.remain != null ? ` · ${t.remain}%` : ""}${active ? " · ◉" : ""}`));
  }

  _traySheet(t) {
    const rec = t.present ? this._lookupDb(t.name || t.type, t.info_idx) : null;
    const sheet = h("div", { class: "sheet" });
    const head = h("div", { class: "row", style: "justify-content:space-between" },
      h("div", { class: "row" },
        h("span", { style: `width:16px;height:16px;border-radius:50%;background:#${t.color || "666"};flex:none` }),
        h("b", { style: "font-size:14px" }, t.present ? (t.name || t.type) : "Empty slot"),
        rec && h("span", { class: "chip" }, rec.family)),
      h("button", { class: "iconbtn", onclick: () => { this._sheet = null; this._render(); } }, "✕"));
    sheet.append(head);
    if (!t.present) {
      sheet.append(h("div", { class: "d2", style: "margin-top:6px" }, "Load a spool and the AMS will identify Bambu filament by RFID; set third-party filament in Bambu Studio."));
      return sheet;
    }
    if (!rec) {
      sheet.append(h("div", { class: "d2", style: "margin-top:6px" }, this._db ? "Not in the materials database — printing specs come from the spool's profile." : "Loading materials database…"));
    } else {
      const amsLabel = { yes: "AMS ✓", ht_only: "AMS HT / dryer only", external: "External spool only" }[rec.ams];
      sheet.append(h("div", { class: "spec" },
        h("div", {}, h("div", { class: "k" }, "nozzle"), h("b", {}, `${rec.nozzle[0]}–${rec.nozzle[1]} °C`)),
        h("div", {}, h("div", { class: "k" }, "bed"), h("b", {}, `${rec.bed[0]}–${rec.bed[1]} °C`)),
        h("div", {}, h("div", { class: "k" }, "chamber"), h("b", {}, rec.chamber ? `~${rec.chamber} °C (${rec.enclosure})` : "open / cool")),
        h("div", {}, h("div", { class: "k" }, "drying"), h("b", {}, rec.dry ? `${rec.dry[0]} °C · ${rec.dry[1]} h` : "—"),
          h("span", { class: "d2" }, ` hygro ${rec.hygro}/5`)),
        h("div", {}, h("div", { class: "k" }, "strength / stiffness"), h("b", {}, `${rec.tensile_mpa} MPa · ${rec.flex_mod_mpa} MPa`)),
        h("div", {}, h("div", { class: "k" }, "heat deflection"), h("b", {}, rec.hdt_c ? `${rec.hdt_c} °C` : rec.shore ? `shore ${rec.shore}` : "—")),
        h("div", {}, h("div", { class: "k" }, "feed"), h("b", {}, amsLabel)),
        h("div", {}, h("div", { class: "k" }, "nozzle wear"), h("b", { style: rec.abrasive ? "color:var(--x2d-bad)" : "" },
          rec.abrasive ? "abrasive — hardened only" : "non-abrasive"))));
      sheet.append(h("div", { class: "d2", style: "margin-top:2px" }, rec.notes));
      if (rec.use_cases?.length)
        sheet.append(h("div", { style: "margin-top:7px;display:flex;gap:5px;flex-wrap:wrap" },
          ...rec.use_cases.map((u) => h("span", { class: "chip" }, u))));
    }
    const btns = h("div", { class: "grid3", style: "margin-top:10px" });
    btns.append(h("button", { class: "btn green", onclick: () => this._ask(`Load ${t.name || t.type}?`, () => this._svc("load_filament", { tray: t.global })) }, "⬇", "Load"));
    if (rec?.dry && t.ams !== 254)
      btns.append(h("button", {
        class: "btn blue",
        onclick: () => this._ask(`Dry AMS ${t.ams + 1} at ${rec.dry[0]} °C for ${rec.dry[1]} h? (AMS 2 Pro / HT)`,
          () => this._svc("dry_filament", { ams: t.ams + 1, temperature: rec.dry[0], minutes: rec.dry[1] * 60 })),
      }, "♨", `Dry ${rec.dry[0]}°·${rec.dry[1]}h`));
    btns.append(h("button", { class: "btn amber", onclick: () => this._ask("Unload the current filament?", () => this._svc("unload_filament")) }, "⬆", "Unload"));
    sheet.append(btns);
    return sheet;
  }

  // ================================================================ TIMELAPSE
  _tab_timelapse() {
    const d = this._data, tl = d.timelapse;
    const wrap = h("div", { class: "pad" });
    this._clip = this._clip ?? tl.library[0]?.name;
    const cur = tl.library.find((c) => c.name === this._clip);
    if (cur) {
      if (cur.name.endsWith(".gif")) wrap.append(h("img", { "data-sign-src": cur.url, style: "width:100%;border-radius:var(--x2d-r)" }));
      else {
        const vid = h("video", { controls: true, playsinline: true, preload: "metadata", "data-sign-src": cur.url });
        if (cur.thumb) vid.setAttribute("data-sign-poster", cur.thumb);
        wrap.append(vid);
      }
      wrap.append(h("div", { style: "font-size:11px;color:var(--x2d-dim);margin:5px 0 9px" },
        `${cur.name} · ${fmtMB(cur.size)}${cur.secs ? ` · ${cur.secs}s` : ""} · ${fmtDate(cur.mtime)}${cur.source === "printer" ? " · from printer SD" : ""}`));
      if (this._renameTarget === cur.name) {
        const inp = h("input", { type: "text", value: cur.name.replace(/\.(mp4|gif|avi)$/, ""), style: "flex:1" });
        const apply = () => {
          const name = inp.value.trim();
          this._renameTarget = null;
          if (name) { this._clip = null; this._svc("rename_timelapse", { clip: cur.name, name }); }
          else this._render();
        };
        inp.addEventListener("keydown", (e) => { if (e.key === "Enter") apply(); });
        wrap.append(h("div", { class: "row", style: "margin-bottom:8px" }, inp,
          h("button", { class: "btn green", onclick: apply }, "✓", "Rename")));
      }
      wrap.append(h("div", { class: "grid4", style: "margin-bottom:8px" },
        h("button", { class: "btn purple", disabled: tl.rendering, onclick: () => this._svc("speed_up_timelapse", { clip: cur.name, factor: 4 }) }, "⏩", "×4 copy"),
        h("button", { class: "btn blue", disabled: tl.rendering || cur.name.endsWith(".gif"), onclick: () => this._svc("make_gif", { clip: cur.name }) }, "🎞", "GIF"),
        h("button", { class: "btn", onclick: () => { this._renameTarget = cur.name; this._render(); } }, "✎", "Rename"),
        h("button", { class: "btn red", onclick: () => this._ask(`Delete ${cur.name}?`, () => { this._clip = null; this._svc("delete_timelapse", { clip: cur.name }); }) }, "🗑", "Delete")),
        h("div", { class: "grid2", style: "margin-bottom:8px" },
          h("button", { class: "btn", onclick: () => this._sign(cur.url).then((u) => window.open(u, "_blank")) }, "⬇", "Open / download"),
          h("button", { class: "btn purple", disabled: tl.rendering || cur.name.endsWith(".gif"), onclick: () => this._svc("speed_up_timelapse", { clip: cur.name, factor: 8 }) }, "⏩", "×8 copy")));
    } else {
      wrap.append(h("div", { class: "item", style: "margin-bottom:9px" },
        tl.recording ? `Recording — ${tl.frames} frames so far. The clip renders when the print finishes.` : "No clips yet — they render automatically when a print finishes."));
    }
    if (tl.rendering) wrap.append(h("div", { class: "advice", style: "--sev:var(--x2d-purple);margin-bottom:9px" }, h("b", {}, "⏳ Rendering…")));

    wrap.append(h("div", { class: "sect" }, `Library · ${tl.library.length} clips · ${tl.total_mb} MB`,
      h("button", { class: "iconbtn", title: "Pull printer SD timelapses", style: "font-size:11px",
        onclick: () => { this._toast("Pulling from printer…"); this._svc("pull_printer_timelapses"); } }, "⇩ SD")));
    const gal = h("div", { class: "gal" });
    for (const c of tl.library) {
      gal.append(h("div", { class: "clip" + (c.name === this._clip ? " sel" : ""), onclick: () => { this._clip = c.name; this._render(); } },
        c.thumb ? h("img", { "data-sign-src": c.thumb, loading: "lazy" }) : h("div", { style: "aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;font-size:22px" }, c.name.endsWith(".gif") ? "🎞" : "🎬"),
        h("div", { class: "cap" },
          h("div", { style: "font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, c.task || c.name),
          h("div", { style: "color:var(--x2d-dim)" }, `${fmtDate(c.mtime)} · ${fmtMB(c.size)}${c.secs ? ` · ${c.secs}s` : ""}`))));
    }
    wrap.append(gal);
    if (d.sd_timelapses.length)
      wrap.append(h("div", { style: "font-size:11px;color:var(--x2d-dim);margin-top:9px" },
        `${d.sd_timelapses.length} more on the printer's SD card — ⇩ SD copies the newest here.`));
    return wrap;
  }

  // ================================================================ INSIGHTS
  _tab_insights() {
    const d = this._data, st = d.stats;
    const wrap = h("div", { class: "pad" });

    // advisor
    const adv = d.advisor || [];
    if (adv.length) {
      wrap.append(h("div", { class: "sect" }, "Advisor"));
      const al = h("div", { class: "list" });
      for (const w of adv) al.append(h("div", { class: "advice", style: `--sev:${SEV[w.severity] || "var(--x2d-dim)"}` },
        h("b", {}, w.title), h("div", { class: "d2" }, w.detail),
        w.action && h("div", { class: "d2", style: "margin-top:3px;font-weight:600" }, `→ ${w.action}`)));
      wrap.append(al);
    }

    // stats
    const ok = st.finished || 0, bad = st.failed || 0, rate = ok + bad ? Math.round((100 * ok) / (ok + bad)) : 100;
    wrap.append(h("div", { class: "sect" }, "Lifetime"), h("div", { class: "grid4" },
      this._tile(ok, "finished"), this._tile(bad, "failed"), this._tile(`${rate}%`, "success"),
      this._tile(`${Math.round((st.print_seconds || 0) / 3600)}h`, "print time")));
    wrap.append(h("div", { class: "grid3", style: "margin-top:7px" },
      this._tile(`${((st.filament_g || 0) / 1000).toFixed(1)}kg`, "filament"),
      this._tile((st.filament_cost || 0).toFixed(0), "filament cost"),
      this._tile(`${(st.energy_kwh || 0).toFixed(1)}kWh`, "energy")));
    const byType = Object.entries(st.by_type || {});
    if (byType.length) {
      const total = byType.reduce((a, [, v]) => a + v, 0) || 1;
      const colors = ["var(--x2d-ok)", "var(--x2d-blue)", "var(--x2d-warn)", "var(--x2d-purple)", "var(--x2d-bad)", "var(--x2d-teal)"];
      const bar = h("div", { style: "display:flex;height:12px;border-radius:6px;overflow:hidden;margin-top:8px" });
      byType.forEach(([t, g], i) => bar.append(h("div", { style: `width:${(100 * g) / total}%;background:${colors[i % 6]}`, title: `${t}: ${Math.round(g)} g` })));
      wrap.append(bar, h("div", { style: "font-size:10.5px;color:var(--x2d-dim);margin-top:4px" },
        byType.map(([t, g]) => `${t} ${Math.round(g)}g`).join(" · ")));
    }

    // maintenance
    const items = d.maintenance || [];
    if (items.length) {
      wrap.append(h("div", { class: "sect" }, "Maintenance"));
      const ml = h("div", { class: "list" });
      for (const m of items) {
        const col = m.due ? "var(--x2d-bad)" : m.pct >= 75 ? "var(--x2d-warn)" : "var(--x2d-ok)";
        ml.append(h("div", { class: "item", title: m.desc },
          h("div", { style: "flex:1;min-width:0" },
            h("div", { class: "row", style: "justify-content:space-between" },
              h("span", { style: "font-size:12px;font-weight:550;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, m.label),
              h("span", { class: "d2", style: m.due ? "color:var(--x2d-bad);font-weight:650" : "" },
                m.due ? "due" : m.interval_h ? `${Math.round(m.due_in_h)}h left` : `${Math.round(m.due_in_h)}g left`)),
            h("div", { class: "row", style: "margin-top:5px" },
              h("div", { class: "mbar" }, h("div", { style: `width:${m.pct}%;background:${col}` })))),
          h("button", { class: "iconbtn", title: "Mark done",
            onclick: () => this._ask(`Mark "${m.label}" as done?`, () => this._svc("maintenance_done", { item: m.key })) }, "✓")));
      }
      wrap.append(ml);
    }

    // history
    wrap.append(h("div", { class: "sect" }, "Recent jobs"));
    const table = h("table", { class: "hist" },
      h("tr", {}, h("th", {}, "Job"), h("th", {}, ""), h("th", {}, "Time"), h("th", {}, "g"), h("th", {}, "Cost")));
    for (const j of d.history) {
      const rc = { finished: "✅", failed: "❌", cancelled: "⏹" }[j.result] || "·";
      const cost = ((j.filament_cost || 0) + (j.energy_cost || 0)) || null;
      table.append(h("tr", {},
        h("td", { style: "max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap", title: j.name }, j.name),
        h("td", {}, `${rc}${j.recovered ? "†" : ""}`),
        h("td", {}, fmtMin(Math.round((j.duration_s || 0) / 60))),
        h("td", {}, j.weight_g ? Math.round(j.weight_g) : "—"),
        h("td", {}, cost ? cost.toFixed(2) : "—")));
    }
    if (!d.history.length) table.append(h("tr", {}, h("td", { colspan: 5, class: "dim" }, "No jobs recorded yet — stats build as you print.")));
    wrap.append(table);
    return wrap;
  }
}

class X2DCommandCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; }
  _render() {
    this.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.style.cssText = "padding:8px;display:flex;flex-direction:column;gap:8px;font-size:13px";
    wrap.append(Object.assign(document.createElement("div"), { textContent: "Tabs to show (comma list):" }));
    const inp = document.createElement("input");
    inp.style.cssText = "padding:6px;font:inherit";
    inp.value = (this._config.tabs || TABS).join(", ");
    inp.addEventListener("change", () => {
      const tabs = inp.value.split(",").map((s) => s.trim()).filter((t) => TABS.includes(t));
      this._config = { ...this._config, tabs: tabs.length ? tabs : TABS };
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
    });
    wrap.append(inp);
    const hint = document.createElement("div");
    hint.style.cssText = "opacity:.6;font-size:11px";
    hint.textContent = `Available: ${TABS.join(", ")}. Optional: entry_id for a specific printer.`;
    wrap.append(hint);
    this.append(wrap);
  }
}

if (!customElements.get("x2d-command-card")) customElements.define("x2d-command-card", X2DCommandCard);
if (!customElements.get("x2d-command-card-editor")) customElements.define("x2d-command-card-editor", X2DCommandCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "x2d-command-card")) {
  window.customCards.push({
    type: "x2d-command-card",
    name: "X2D Command Card",
    description: "The complete Bambu X2D control center: live, heat soak, control, files & queue, objects, filament science, timelapse, insights.",
    preview: true,
  });
}
