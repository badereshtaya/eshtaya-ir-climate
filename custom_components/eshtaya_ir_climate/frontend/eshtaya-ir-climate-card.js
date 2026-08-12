/*
 * Eshtaya IR Climate Card v0.2.0
 * Standalone Home Assistant custom card — no external JS/CSS dependencies.
 */
const CARD_VERSION = "0.2.0";

const MODE_META = {
  off:      { label: "Off",  icon: "power",    hue: 218, accent: "#6f7b91" },
  cool:     { label: "Cool", icon: "snow",     hue: 198, accent: "#38bdf8" },
  heat:     { label: "Heat", icon: "sun",      hue: 18,  accent: "#fb923c" },
  auto:     { label: "Auto", icon: "auto",     hue: 170, accent: "#2dd4bf" },
  fan_only: { label: "Fan",  icon: "fan",      hue: 145, accent: "#34d399" },
  dry:      { label: "Dry",  icon: "drop",     hue: 264, accent: "#a78bfa" },
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function icon(name, size = 22) {
  const common = `width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"`;
  const paths = {
    power: `<path d="M12 2v10"/><path d="M6.4 5.7a9 9 0 1 0 11.2 0"/>`,
    snow: `<path d="M12 2v20M4.2 6.5l15.6 11M19.8 6.5l-15.6 11M8.5 4.5 12 7l3.5-2.5M8.5 19.5 12 17l3.5 2.5M3.8 10l4 .4.4-4M20.2 14l-4-.4-.4 4"/>`,
    sun: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"/>`,
    auto: `<path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.7"/><path d="M20 4v4.7h-4.7"/><path d="M20 12a8 8 0 0 1-13.7 5.6L4 15.3"/><path d="M4 20v-4.7h4.7"/>`,
    fan: `<circle cx="12" cy="12" r="2"/><path d="M12 10c-1.5-3.4-.7-6.2 1.2-7.1 1.6-.7 3.7.2 4 2 .4 2.4-1.8 4.3-5.2 5.1Z"/><path d="M10.3 13c-3.7.4-6-1.2-6.2-3.3-.2-1.7 1.3-3.4 3.1-3.1 2.4.4 3.3 3.2 3.1 6.4Z"/><path d="M13.2 13.5c2.2 3 2.1 5.9.4 7.1-1.4 1-3.7.5-4.3-1.2-.8-2.3 1-4.6 3.9-5.9Z"/>`,
    drop: `<path d="M12 2s6 6.5 6 12a6 6 0 0 1-12 0c0-5.5 6-12 6-12Z"/><path d="M9.2 15.3c.5 1.3 1.5 2 2.8 2.2"/>`,
    plus: `<path d="M12 5v14M5 12h14"/>`,
    minus: `<path d="M5 12h14"/>`,
    temp: `<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z"/><path d="M12 9v7"/>`,
    humidity: `<path d="M12 3s5 5.7 5 10a5 5 0 0 1-10 0c0-4.3 5-10 5-10Z"/>`,
    chevron: `<path d="m9 18 6-6-6-6"/>`,
  };
  return `<svg ${common}>${paths[name] || paths.auto}</svg>`;
}

class EshtayaIRClimateCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._lastSignature = "";
    this._previewTemp = null;
  }

  static getConfigElement() {
    return document.createElement("eshtaya-ir-climate-card-editor");
  }

  static getStubConfig(hass) {
    const climate = Object.keys(hass?.states || {}).find((id) => id.startsWith("climate."));
    return climate ? { entity: climate } : {};
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Eshtaya IR Climate Card requires a climate entity.");
    if (!String(config.entity).startsWith("climate.")) throw new Error("The entity must be a climate entity.");
    this._config = {
      show_current_temperature: true,
      show_humidity: true,
      show_fan: true,
      name: "",
      ...config,
    };
    this._lastSignature = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    const st = hass.states[this._config.entity];
    const signature = st
      ? JSON.stringify([
          st.state,
          st.attributes.temperature,
          st.attributes.current_temperature,
          st.attributes.current_humidity,
          st.attributes.fan_mode,
          st.attributes.hvac_modes,
          st.attributes.fan_modes,
          st.attributes.min_temp,
          st.attributes.max_temp,
          st.attributes.target_temp_step,
          st.attributes.friendly_name,
          st.attributes.eshtaya_ir_climate,
        ])
      : "missing";
    if (signature !== this._lastSignature) {
      this._lastSignature = signature;
      this._previewTemp = null;
      this._render();
    }
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return {
      rows: 7,
      columns: 6,
      min_rows: 6,
      min_columns: 3,
    };
  }

  _state() {
    return this._hass?.states?.[this._config?.entity] || null;
  }

  _friendlyName(st) {
    if (this._config?.name) return this._config.name;
    if (this._hass?.formatEntityName && st) {
      try {
        return this._hass.formatEntityName(
          st,
          [{ type: "device" }, { type: "entity" }],
          { separator: " · " }
        );
      } catch (_) {}
    }
    return st?.attributes?.friendly_name || this._config?.entity || "IR Climate";
  }

  _modeMeta(mode) {
    return MODE_META[mode] || MODE_META.auto;
  }

  _call(service, data) {
    if (!this._hass) return;
    this._hass.callService("climate", service, {
      entity_id: this._config.entity,
      ...data,
    });
  }

  _setMode(mode) {
    this._call("set_hvac_mode", { hvac_mode: mode });
  }

  _setTemp(temp) {
    const st = this._state();
    if (!st) return;
    const min = Number(st.attributes.min_temp ?? 16);
    const max = Number(st.attributes.max_temp ?? 30);
    const step = Number(st.attributes.target_temp_step ?? 1) || 1;
    const clamped = Math.min(max, Math.max(min, Number(temp)));
    const rounded = Math.round(clamped / step) * step;
    this._previewTemp = rounded;
    this._updateTempVisual(rounded);
    this._call("set_temperature", { temperature: rounded });
  }

  _adjustTemp(delta) {
    const st = this._state();
    if (!st) return;
    const step = Number(st.attributes.target_temp_step ?? 1) || 1;
    const current = Number(
      this._previewTemp ?? st.attributes.temperature ?? st.attributes.current_temperature ?? 24
    );
    this._setTemp(current + delta * step);
  }

  _setFan(mode) {
    this._call("set_fan_mode", { fan_mode: mode });
  }

  _moreInfo() {
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId: this._config.entity };
    this.dispatchEvent(ev);
  }

  _updateTempVisual(value) {
    const root = this.shadowRoot;
    const st = this._state();
    if (!root || !st) return;
    const min = Number(st.attributes.min_temp ?? 16);
    const max = Number(st.attributes.max_temp ?? 30);
    const pct = max > min ? ((value - min) / (max - min)) * 100 : 50;
    const num = root.querySelector(".target-value");
    const range = root.querySelector("input[type=range]");
    const dial = root.querySelector(".dial");
    if (num) num.textContent = Number.isInteger(value) ? value : value.toFixed(1);
    if (range) range.value = value;
    if (dial) dial.style.setProperty("--temp-pct", `${Math.max(0, Math.min(100, pct))}%`);
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    root.querySelector("[data-action=more]")?.addEventListener("click", () => this._moreInfo());
    root.querySelector("[data-action=minus]")?.addEventListener("click", () => this._adjustTemp(-1));
    root.querySelector("[data-action=plus]")?.addEventListener("click", () => this._adjustTemp(1));

    root.querySelectorAll("[data-mode]").forEach((el) => {
      el.addEventListener("click", () => this._setMode(el.dataset.mode));
    });
    root.querySelectorAll("[data-fan]").forEach((el) => {
      el.addEventListener("click", () => this._setFan(el.dataset.fan));
    });

    const range = root.querySelector("input[type=range]");
    range?.addEventListener("input", (ev) => {
      this._previewTemp = Number(ev.target.value);
      this._updateTempVisual(this._previewTemp);
    });
    range?.addEventListener("change", (ev) => this._setTemp(Number(ev.target.value)));
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const st = this._state();

    if (!st) {
      this.shadowRoot.innerHTML = `
        <style>${this._styles()}</style>
        <div class="card unavailable">
          <div class="unavailable-title">Eshtaya IR Climate</div>
          <div>Entity <b>${esc(this._config.entity)}</b> was not found.</div>
        </div>`;
      return;
    }

    const mode = st.state || "off";
    const meta = this._modeMeta(mode);
    const isOn = mode !== "off" && mode !== "unavailable" && mode !== "unknown";
    const target = Number(
      this._previewTemp ?? st.attributes.temperature ?? st.attributes.current_temperature ?? 24
    );
    const current = st.attributes.current_temperature;
    const humidity = st.attributes.current_humidity;
    const min = Number(st.attributes.min_temp ?? 16);
    const max = Number(st.attributes.max_temp ?? 30);
    const step = Number(st.attributes.target_temp_step ?? 1) || 1;
    const pct = max > min ? Math.max(0, Math.min(100, ((target - min) / (max - min)) * 100)) : 50;
    const hvacModes = (st.attributes.hvac_modes || ["off", "cool", "heat", "auto", "fan_only", "dry"])
      .filter((m) => m !== "off");
    const fanModes = st.attributes.fan_modes || [];
    const currentFan = st.attributes.fan_mode;

    const modeButtons = hvacModes.map((m) => {
      const mm = this._modeMeta(m);
      return `<button class="mode-btn ${mode === m ? "active" : ""}" data-mode="${esc(m)}" title="${esc(mm.label)}">
        <span class="mode-icon">${icon(mm.icon, 18)}</span>
        <span>${esc(mm.label)}</span>
      </button>`;
    }).join("");

    const fanButtons = fanModes.map((fan) => `
      <button class="fan-btn ${currentFan === fan ? "active" : ""}" data-fan="${esc(fan)}">
        ${esc(String(fan).replaceAll("_", " "))}
      </button>
    `).join("");

    const name = this._friendlyName(st);
    const showCurrent = this._config.show_current_temperature !== false && current !== undefined;
    const showHumidity = this._config.show_humidity !== false && humidity !== undefined;
    const showFan = this._config.show_fan !== false && fanModes.length > 0;

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <article class="card ${isOn ? "on" : "off"} mode-${esc(mode)}"
        style="--mode-hue:${meta.hue};--accent:${meta.accent};--temp-pct:${pct}%">
        <div class="ambient" aria-hidden="true">
          <span class="orb orb-a"></span>
          <span class="orb orb-b"></span>
          <span class="air air-1"></span>
          <span class="air air-2"></span>
          <span class="air air-3"></span>
        </div>

        <header class="header">
          <button class="title-wrap" data-action="more" aria-label="Open more info">
            <span class="eyebrow">ESHTAYA IR CLIMATE</span>
            <span class="title">${esc(name)}</span>
            <span class="status"><i></i>${isOn ? esc(meta.label) : "Off"}</span>
          </button>
          <button class="power ${isOn ? "active" : ""}" data-mode="${isOn ? "off" : (hvacModes[0] || "cool")}" aria-label="${isOn ? "Turn off" : "Turn on"}">
            ${icon("power", 24)}
          </button>
        </header>

        <section class="hero">
          <div class="dial">
            <div class="dial-glow"></div>
            <div class="dial-inner">
              <div class="target-caption">TARGET</div>
              <div class="temperature">
                <span class="target-value">${Number.isInteger(target) ? target : target.toFixed(1)}</span><span class="degree">°</span>
              </div>
              <div class="mode-inline">${icon(meta.icon, 16)} ${esc(meta.label)}</div>
            </div>
          </div>

          <div class="stepper" aria-label="Target temperature controls">
            <button data-action="minus" aria-label="Decrease temperature">${icon("minus", 20)}</button>
            <div class="range-wrap">
              <input type="range" min="${min}" max="${max}" step="${step}" value="${target}" aria-label="Target temperature">
              <div class="range-labels"><span>${min}°</span><span>${max}°</span></div>
            </div>
            <button data-action="plus" aria-label="Increase temperature">${icon("plus", 20)}</button>
          </div>
        </section>

        ${(showCurrent || showHumidity) ? `
        <section class="metrics">
          ${showCurrent ? `
            <div class="metric">
              <span class="metric-icon">${icon("temp", 20)}</span>
              <span><small>ROOM</small><strong>${esc(current)}°</strong></span>
            </div>` : ""}
          ${showHumidity ? `
            <div class="metric">
              <span class="metric-icon">${icon("humidity", 20)}</span>
              <span><small>HUMIDITY</small><strong>${esc(humidity)}%</strong></span>
            </div>` : ""}
        </section>` : ""}

        <section class="modes">
          <div class="section-label"><span>Mode</span><span>${esc(meta.label)}</span></div>
          <div class="mode-grid">${modeButtons}</div>
        </section>

        ${showFan ? `
        <section class="fans">
          <div class="section-label">
            <span>Fan speed</span>
            <span class="fan-live">${icon("fan", 15)} ${esc(currentFan || "")}</span>
          </div>
          <div class="fan-grid">${fanButtons}</div>
        </section>` : ""}

        <footer>
          <span>Cloud control</span>
          <span class="dot-sep">•</span>
          <span>${esc(this._config.entity)}</span>
          <span class="version">v${CARD_VERSION}</span>
        </footer>
      </article>
    `;
    this._bindEvents();
  }

  _styles() {
    return `
      :host {
        display: block;
        color: var(--primary-text-color, #f8fafc);
        font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
      }
      * { box-sizing: border-box; }
      button, input { font: inherit; }
      button { -webkit-tap-highlight-color: transparent; }
      .card {
        position: relative;
        overflow: hidden;
        min-height: 510px;
        padding: 20px;
        border-radius: var(--ha-card-border-radius, 24px);
        background:
          radial-gradient(circle at 15% 0%, hsla(var(--mode-hue), 96%, 66%, .18), transparent 36%),
          radial-gradient(circle at 100% 25%, hsla(calc(var(--mode-hue) + 25), 92%, 58%, .13), transparent 42%),
          linear-gradient(155deg, rgba(20, 29, 46, .98), rgba(8, 14, 25, .99));
        color: #f8fafc;
        box-shadow:
          0 16px 42px rgba(0, 0, 0, .28),
          inset 0 1px 0 rgba(255, 255, 255, .08);
        border: 1px solid rgba(255,255,255,.08);
        isolation: isolate;
        transition: background .45s ease, box-shadow .45s ease;
      }
      .card.on {
        box-shadow:
          0 18px 50px hsla(var(--mode-hue), 75%, 34%, .24),
          0 12px 34px rgba(0,0,0,.28),
          inset 0 1px 0 rgba(255,255,255,.11);
      }
      .ambient { position:absolute; inset:0; z-index:-1; pointer-events:none; overflow:hidden; }
      .orb {
        position:absolute; border-radius:999px; filter: blur(30px); opacity:.14;
        background: var(--accent); transition: background .4s ease;
      }
      .orb-a { width:180px; height:180px; right:-55px; top:60px; animation: drift 9s ease-in-out infinite alternate; }
      .orb-b { width:120px; height:120px; left:-45px; bottom:90px; opacity:.09; animation: drift 11s ease-in-out infinite alternate-reverse; }
      .air {
        position:absolute; width:180px; height:28px; border-top:1px solid hsla(var(--mode-hue), 90%, 72%, .22);
        border-radius:50%; opacity:0; transform:translateX(-80px) skewX(-12deg);
      }
      .on .air { animation: airflow 5.2s linear infinite; }
      .air-1 { top:128px; left:12%; animation-delay:0s!important; }
      .air-2 { top:160px; left:36%; animation-delay:1.7s!important; }
      .air-3 { top:205px; left:4%; animation-delay:3.4s!important; }
      @keyframes airflow {
        0% { opacity:0; transform:translateX(-90px) scaleX(.75); }
        18% { opacity:.55; }
        78% { opacity:.12; }
        100% { opacity:0; transform:translateX(260px) scaleX(1.15); }
      }
      @keyframes drift {
        from { transform:translate3d(0,0,0) scale(.92); }
        to { transform:translate3d(-28px,22px,0) scale(1.08); }
      }
      .header { display:flex; align-items:flex-start; gap:14px; justify-content:space-between; }
      .title-wrap {
        min-width:0; padding:0; border:0; background:transparent; color:inherit; text-align:left; cursor:pointer;
        display:flex; flex-direction:column; gap:3px;
      }
      .eyebrow { font-size:9px; letter-spacing:.19em; color:rgba(226,232,240,.48); font-weight:800; }
      .title { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:19px; font-weight:760; letter-spacing:-.025em; }
      .status { display:flex; align-items:center; gap:7px; margin-top:3px; color:rgba(226,232,240,.68); font-size:12px; }
      .status i { display:block; width:6px; height:6px; border-radius:50%; background:#64748b; box-shadow:0 0 0 4px rgba(100,116,139,.08); }
      .on .status i { background:var(--accent); box-shadow:0 0 0 4px hsla(var(--mode-hue),90%,60%,.10),0 0 15px hsla(var(--mode-hue),90%,60%,.65); }
      .power {
        width:48px; height:48px; border-radius:16px; flex:0 0 auto; display:grid; place-items:center; cursor:pointer;
        color:#94a3b8; border:1px solid rgba(255,255,255,.09); background:rgba(255,255,255,.055);
        transition:transform .18s ease, background .25s ease, color .25s ease, box-shadow .25s ease;
      }
      .power:active { transform:scale(.92); }
      .power.active {
        color:white; background:linear-gradient(145deg, var(--accent), hsla(var(--mode-hue),75%,42%,.95));
        box-shadow:0 8px 24px hsla(var(--mode-hue),85%,48%,.28), inset 0 1px 0 rgba(255,255,255,.28);
      }
      .hero { padding:15px 0 6px; display:flex; flex-direction:column; align-items:center; }
      .dial {
        --size:min(49vw, 188px);
        width:var(--size); height:var(--size); border-radius:50%; position:relative; display:grid; place-items:center;
        background:
          conic-gradient(from 225deg,
            var(--accent) 0 var(--temp-pct),
            rgba(148,163,184,.13) var(--temp-pct) 75%,
            transparent 75% 100%);
        filter:drop-shadow(0 10px 28px rgba(0,0,0,.24));
      }
      .dial::before {
        content:""; position:absolute; inset:7px; border-radius:50%;
        background:linear-gradient(150deg, rgba(31,41,58,.98), rgba(9,15,27,.99));
        box-shadow:inset 0 0 0 1px rgba(255,255,255,.07), inset 0 -18px 36px rgba(0,0,0,.25);
      }
      .dial::after {
        content:""; position:absolute; inset:-2px; border-radius:50%; pointer-events:none;
        background:conic-gradient(from 225deg, hsla(var(--mode-hue),100%,80%,.0), hsla(var(--mode-hue),100%,78%,.35), transparent 48%);
        -webkit-mask:radial-gradient(circle, transparent 67%, #000 69%);
        mask:radial-gradient(circle, transparent 67%, #000 69%);
        opacity:.7;
      }
      .on .dial-glow {
        position:absolute; inset:18%; border-radius:50%; background:hsla(var(--mode-hue),100%,60%,.12);
        filter:blur(24px); animation:pulse 2.7s ease-in-out infinite;
      }
      @keyframes pulse { 50% { transform:scale(1.16); opacity:.52; } }
      .dial-inner { position:relative; z-index:2; text-align:center; display:flex; flex-direction:column; align-items:center; }
      .target-caption { font-size:9px; letter-spacing:.18em; color:rgba(226,232,240,.48); font-weight:800; }
      .temperature { line-height:.95; margin:5px 0 7px; display:flex; align-items:flex-start; }
      .target-value { font-size:58px; font-weight:300; letter-spacing:-.075em; }
      .degree { font-size:24px; margin-top:7px; margin-left:3px; color:var(--accent); }
      .mode-inline {
        display:flex; align-items:center; gap:6px; padding:5px 9px; border-radius:999px;
        font-size:11px; color:rgba(241,245,249,.72); background:rgba(255,255,255,.045);
        border:1px solid rgba(255,255,255,.055);
      }
      .stepper { width:100%; display:grid; grid-template-columns:42px 1fr 42px; gap:11px; align-items:center; margin-top:13px; }
      .stepper > button {
        width:42px; height:42px; border:1px solid rgba(255,255,255,.08); border-radius:14px;
        background:rgba(255,255,255,.05); color:#e2e8f0; display:grid; place-items:center; cursor:pointer;
        transition:.16s ease;
      }
      .stepper > button:active { transform:scale(.91); background:rgba(255,255,255,.11); }
      .range-wrap { min-width:0; }
      input[type=range] {
        width:100%; height:5px; margin:0; border-radius:999px; appearance:none; -webkit-appearance:none; outline:none;
        background:linear-gradient(90deg, hsla(var(--mode-hue),84%,55%,.33), rgba(148,163,184,.16));
        cursor:pointer;
      }
      input[type=range]::-webkit-slider-thumb {
        appearance:none; -webkit-appearance:none; width:18px; height:18px; border-radius:50%;
        background:white; border:5px solid var(--accent); box-shadow:0 2px 12px hsla(var(--mode-hue),80%,50%,.42);
      }
      input[type=range]::-moz-range-thumb {
        width:9px; height:9px; border-radius:50%; background:white; border:5px solid var(--accent);
        box-shadow:0 2px 12px hsla(var(--mode-hue),80%,50%,.42);
      }
      .range-labels { display:flex; justify-content:space-between; margin-top:7px; font-size:9px; color:rgba(226,232,240,.35); }
      .metrics { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; margin-top:10px; }
      .metric {
        display:flex; align-items:center; gap:10px; min-width:0; padding:10px 12px; border-radius:16px;
        background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.055);
      }
      .metric-icon { width:32px; height:32px; display:grid; place-items:center; border-radius:11px; color:var(--accent); background:hsla(var(--mode-hue),80%,55%,.09); }
      .metric span:last-child { display:flex; flex-direction:column; gap:1px; }
      .metric small { font-size:8px; letter-spacing:.12em; color:rgba(226,232,240,.4); font-weight:800; }
      .metric strong { font-size:16px; font-weight:650; }
      .modes, .fans { margin-top:13px; }
      .section-label { display:flex; align-items:center; justify-content:space-between; margin:0 2px 7px; font-size:10px; color:rgba(226,232,240,.48); text-transform:uppercase; letter-spacing:.09em; }
      .section-label span:last-child { color:rgba(241,245,249,.7); }
      .mode-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(58px,1fr)); gap:7px; }
      .mode-btn {
        min-width:0; min-height:55px; padding:7px 4px; border-radius:15px; cursor:pointer;
        border:1px solid rgba(255,255,255,.055); background:rgba(255,255,255,.035); color:rgba(226,232,240,.58);
        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; font-size:9px; font-weight:650;
        transition:transform .18s ease, color .2s ease, background .2s ease, border-color .2s ease;
      }
      .mode-btn:active, .fan-btn:active { transform:scale(.94); }
      .mode-btn.active {
        color:#fff; background:hsla(var(--mode-hue),80%,55%,.15); border-color:hsla(var(--mode-hue),85%,65%,.26);
        box-shadow:inset 0 0 18px hsla(var(--mode-hue),80%,50%,.05);
      }
      .mode-icon { line-height:0; }
      .fans .section-label .fan-live { display:flex; align-items:center; gap:5px; }
      .on .fan-live svg { animation:spin 2.4s linear infinite; }
      @keyframes spin { to { transform:rotate(360deg); } }
      .fan-grid { display:flex; gap:7px; }
      .fan-btn {
        flex:1; min-width:0; padding:8px 6px; border-radius:12px; cursor:pointer; overflow:hidden; text-overflow:ellipsis;
        border:1px solid rgba(255,255,255,.055); background:rgba(255,255,255,.035); color:rgba(226,232,240,.55);
        text-transform:capitalize; font-size:10px; transition:.18s ease;
      }
      .fan-btn.active { color:white; background:hsla(var(--mode-hue),80%,55%,.14); border-color:hsla(var(--mode-hue),85%,65%,.24); }
      footer {
        display:flex; align-items:center; gap:6px; margin-top:14px; color:rgba(148,163,184,.34);
        font-size:8px; white-space:nowrap; overflow:hidden;
      }
      footer span:nth-child(3) { overflow:hidden; text-overflow:ellipsis; }
      footer .version { margin-left:auto; }
      .unavailable {
        min-height:120px; padding:20px; border-radius:var(--ha-card-border-radius,20px);
        background:var(--ha-card-background,var(--card-background-color,#fff)); color:var(--primary-text-color);
      }
      .unavailable-title { font-weight:700; font-size:18px; margin-bottom:8px; }
      @media (max-width: 360px) {
        .card { padding:16px; min-height:490px; }
        .dial { --size:166px; }
        .target-value { font-size:52px; }
        .mode-grid { gap:5px; }
        .mode-btn { min-height:50px; }
      }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation:none!important; transition:none!important; }
      }
    `;
  }
}

class EshtayaIRClimateCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _emit(config) {
    this._config = config;
    const event = new Event("config-changed", { bubbles: true, composed: true });
    event.detail = { config };
    this.dispatchEvent(event);
  }

  _render() {
    if (!this.shadowRoot) return;
    const climates = Object.entries(this._hass?.states || {})
      .filter(([id]) => id.startsWith("climate."))
      .sort((a, b) => {
        const an = a[1].attributes.friendly_name || a[0];
        const bn = b[1].attributes.friendly_name || b[0];
        return an.localeCompare(bn);
      });

    const entity = this._config.entity || "";
    const options = climates.map(([id, st]) =>
      `<option value="${esc(id)}" ${id === entity ? "selected" : ""}>${esc(st.attributes.friendly_name || id)} — ${esc(id)}</option>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;padding:8px 0;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,sans-serif)}
        .form{display:grid;gap:14px}
        label{display:grid;gap:6px;font-size:13px;font-weight:600}
        input,select{width:100%;padding:10px 11px;border-radius:10px;border:1px solid var(--divider-color,#d7dce2);background:var(--card-background-color,#fff);color:var(--primary-text-color);font:inherit}
        .checks{display:grid;gap:8px}
        .check{display:flex;align-items:center;gap:9px;font-size:13px}
        .check input{width:auto}
        small{font-weight:400;color:var(--secondary-text-color)}
      </style>
      <div class="form">
        <label>Climate entity
          <select data-key="entity">
            <option value="">Select entity…</option>
            ${options}
          </select>
        </label>
        <label>Card name <small>Optional — leave empty to use the Home Assistant entity/device name.</small>
          <input data-key="name" value="${esc(this._config.name || "")}" placeholder="Living room AC">
        </label>
        <div class="checks">
          <label class="check"><input type="checkbox" data-key="show_current_temperature" ${this._config.show_current_temperature !== false ? "checked" : ""}> Show room temperature</label>
          <label class="check"><input type="checkbox" data-key="show_humidity" ${this._config.show_humidity !== false ? "checked" : ""}> Show humidity</label>
          <label class="check"><input type="checkbox" data-key="show_fan" ${this._config.show_fan !== false ? "checked" : ""}> Show fan controls</label>
        </div>
      </div>
    `;

    this.shadowRoot.querySelectorAll("[data-key]").forEach((el) => {
      const eventName = el.type === "text" ? "input" : "change";
      el.addEventListener(eventName, () => {
        const key = el.dataset.key;
        const value = el.type === "checkbox" ? el.checked : el.value;
        const next = { ...this._config, [key]: value };
        if (key === "name" && !value) delete next.name;
        this._emit(next);
      });
    });
  }
}

if (!customElements.get("eshtaya-ir-climate-card")) {
  customElements.define("eshtaya-ir-climate-card", EshtayaIRClimateCard);
}
if (!customElements.get("eshtaya-ir-climate-card-editor")) {
  customElements.define("eshtaya-ir-climate-card-editor", EshtayaIRClimateCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "eshtaya-ir-climate-card")) {
  window.customCards.push({
    type: "eshtaya-ir-climate-card",
    name: "Eshtaya IR Climate",
    description: "Animated premium climate control card for IR air conditioners.",
    preview: true,
    documentationURL: "https://github.com/eshtaya/eshtaya-ir-climate",
    getEntitySuggestion: (hass, entityId) => {
      if (!entityId?.startsWith("climate.")) return null;
      const state = hass?.states?.[entityId];
      if (!state) return null;
      return {
        config: {
          type: "custom:eshtaya-ir-climate-card",
          entity: entityId,
        },
      };
    },
  });
}

console.info(
  `%c ESHTAYA IR CLIMATE %c v${CARD_VERSION} `,
  "background:#0f172a;color:#67e8f9;font-weight:800;padding:4px 7px;border-radius:5px 0 0 5px",
  "background:#164e63;color:#ecfeff;font-weight:700;padding:4px 7px;border-radius:0 5px 5px 0"
);
