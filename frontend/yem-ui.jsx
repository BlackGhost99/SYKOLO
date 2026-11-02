import React from "react";

/* Composants visuels communs à toutes les pages YEM (maquettes de référence : docs/maquettes). */

const ICONS = {
  home: <><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6.5h5V21"/></>,
  users: <><circle cx="9" cy="8" r="3.2"/><path d="M3 20v-1.6c0-3 2.7-5.2 6-5.2s6 2.2 6 5.2V20"/><path d="M15.5 5.2a3 3 0 0 1 0 5.6"/><path d="M17.5 13.6c2.2.5 3.5 2.2 3.5 4.6V20"/></>,
  adduser: <><circle cx="9" cy="8" r="3.2"/><path d="M3 20v-1.6c0-3 2.7-5.2 6-5.2s6 2.2 6 5.2V20"/><path d="M18.5 7.5v6M15.5 10.5h6"/></>,
  card: <><rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 9.5h19M6 15h4"/></>,
  alert: <><path d="M10.3 3.6 2.4 17.4A2 2 0 0 0 4.1 20.4h15.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4.5M12 17.2h.01"/></>,
  file: <><path d="M6 2.5h8.5l4 4V21.5H6z"/><path d="M14 2.5v4.5h4.5M9 12h6M9 16h6"/></>,
  calendar: <><rect x="3" y="4.5" width="18" height="16.5" rx="2"/><path d="M8 2.5v4M16 2.5v4M3 9.5h18"/></>,
  idcard: <><rect x="2.5" y="4.5" width="19" height="15" rx="2"/><circle cx="8.5" cy="11" r="2.2"/><path d="M5 16.5c.6-1.6 1.9-2.4 3.5-2.4s2.9.8 3.5 2.4M14.5 9.5h4M14.5 13h4"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></>,
  school: <><path d="M3 21h18M4.5 21V10.5L12 6l7.5 4.5V21"/><path d="M2.5 11.5 12 5.5l9.5 6M9.5 21v-5h5v5M8 13h.01M16 13h.01"/></>,
  search: <><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></>,
  bell: <><path d="M18 8.5a6 6 0 0 0-12 0c0 6.5-2.5 8-2.5 8h17S18 15 18 8.5"/><path d="M10.2 20a2 2 0 0 0 3.6 0"/></>,
  coins: <><ellipse cx="9" cy="6" rx="6" ry="2.6"/><path d="M3 6v3.5c0 1.4 2.7 2.6 6 2.6s6-1.2 6-2.6V6"/><path d="M3 9.5V13c0 1.4 2.7 2.6 6 2.6"/><path d="M3 13v3.5c0 1.4 2.7 2.6 6 2.6"/><ellipse cx="15.5" cy="13.5" rx="5.5" ry="2.4"/><path d="M10 13.5v3.3c0 1.3 2.5 2.4 5.5 2.4s5.5-1.1 5.5-2.4v-3.3"/></>,
  layers: <><path d="m12 3 9 4.8-9 4.8-9-4.8L12 3Z"/><path d="m3 12 9 4.8 9-4.8M3 16.2 12 21l9-4.8"/></>,
  barchart: <><path d="M5 20V12M10 20V6M15 20v-9M20 20V9"/><path d="M3 20.5h18"/></>,
  trendup: <><path d="M5 19 19 5"/><path d="M9 5h10v10"/></>,
  trenddown: <><path d="M5 5 19 19"/><path d="M19 9v10H9"/></>,
  equal: <path d="M6 9.5h12M6 14.5h12"/>,
  bolt: <path d="M13 2 4.5 13.5H12L11 22l8.5-11.5H12L13 2Z"/>,
  crown: <><path d="m3 7 4.5 4L12 4.5 16.5 11 21 7l-2 11H5L3 7Z"/><path d="M5 21h14"/></>,
  wallet: <><path d="M3.5 7.5h15a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V7.5Z"/><path d="M3.5 7.5 15 3.5l1.5 4"/><path d="M15.5 13.5h5"/></>,
  plane: <><path d="m21.5 2.5-6.5 19-3.6-8.4L3 9.5l18.5-7Z"/><path d="M21.5 2.5 11.4 13.1"/></>,
  whatsapp: <><path d="M3.5 20.5 4.8 16A8.5 8.5 0 1 1 8 19.3l-4.5 1.2Z"/><path d="M9 8.3c.3-.6.8-.7 1.2-.4l.9 1.7c.1.3 0 .6-.2.8l-.5.5c.5 1.2 1.5 2.2 2.7 2.7l.5-.5c.2-.2.5-.3.8-.2l1.7.9c.3.4.2.9-.4 1.2-1.6.9-4-.2-5.6-1.8S8.1 9.9 9 8.3Z"/></>,
  message: <><path d="M4 4.5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4v-15a1 1 0 0 1 1-1Z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6 8.5 7 8.5-7"/></>,
  download: <><path d="M12 3.5v11.5M7 10.5l5 5 5-5"/><path d="M4 20.5h16"/></>,
  printer: <><path d="M6.5 9V3.5h11V9"/><rect x="6.5" y="14" width="11" height="7"/><path d="M6.5 18H4a1.5 1.5 0 0 1-1.5-1.5V10.5A1.5 1.5 0 0 1 4 9h16a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 20 18h-2.5"/></>,
  sliders: <><path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/></>,
  cap: <><path d="m2 9.5 10-5 10 5-10 5-10-5Z"/><path d="M6 11.6V16c3.5 2.6 8.5 2.6 12 0v-4.4M22 9.5v5"/></>,
  scale: <><path d="M12 3.5v17M5 7h14M8 20.5h8"/><path d="m5 7-3 6.5a3 3 0 0 0 6 0L5 7ZM19 7l-3 6.5a3 3 0 0 0 6 0L19 7Z"/></>,
  calculator: <><rect x="4.5" y="2.5" width="15" height="19" rx="2"/><path d="M8 6.5h8v3H8zM8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01M16 17h.01"/></>,
  check: <path d="m4.5 12.5 4.5 4.5L19.5 6.5"/>,
  checkcircle: <><circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.7 2.7L16.2 9.5"/></>,
  close: <path d="M6 6l12 12M18 6 6 18"/>,
  dots: <><circle cx="5" cy="12" r="1.3" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.3" fill="currentColor" stroke="none"/></>,
  chevron: <path d="m6 9 6 6 6-6"/>,
  chevronright: <path d="m9 6 6 6-6 6"/>,
  back: <path d="M20 12H4.5M10.5 6l-6 6 6 6"/>,
  menu: <path d="M4 6.5h16M4 12h16M4 17.5h16"/>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21c.8-4 4-6 8-6s7.2 2 8 6"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.7h.01"/></>,
  phone: <path d="M5 3.5h3.5l1.5 4.5-2.2 1.4a11 11 0 0 0 5.8 5.8l1.4-2.2 4.5 1.5V18a2 2 0 0 1-2 2A16 16 0 0 1 3 5.5a2 2 0 0 1 2-2Z"/>,
  paperclip: <path d="m20 11.5-7.8 7.8a5 5 0 0 1-7.1-7.1l8-8a3.4 3.4 0 0 1 4.8 4.8l-8 8a1.7 1.7 0 0 1-2.4-2.4l7.4-7.4"/>,
  hourglass: <><path d="M6 2.5h12M6 21.5h12"/><path d="M7.5 2.5c0 5 9 6 9 9.5s-9 4.5-9 9.5M16.5 2.5c0 5-9 6-9 9.5s9 4.5 9 9.5"/></>,
  filter: <path d="M3.5 4.5h17l-6.5 8v6l-4 2v-8l-6.5-8Z"/>,
  list: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6h.01M4 12h.01M4 18h.01"/></>,
  shield: <><path d="M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6L12 3Z"/><path d="m9 12 2 2 4-4"/></>,
  edit: <><path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/></>,
  trash: <><path d="M4 6.5h16M9 6.5V4h6v2.5M6 6.5l1 14h10l1-14M10 10.5v6M14 10.5v6"/></>,
  grip: <><circle cx="9" cy="6" r="1.1" fill="currentColor"/><circle cx="15" cy="6" r="1.1" fill="currentColor"/><circle cx="9" cy="12" r="1.1" fill="currentColor"/><circle cx="15" cy="12" r="1.1" fill="currentColor"/><circle cx="9" cy="18" r="1.1" fill="currentColor"/><circle cx="15" cy="18" r="1.1" fill="currentColor"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  send: <><path d="m21.5 2.5-6.5 19-3.6-8.4L3 9.5l18.5-7Z"/><path d="M21.5 2.5 11.4 13.1"/></>,
  excel: <><path d="M6 2.5h8.5l4 4V21.5H6z"/><path d="M14 2.5v4.5h4.5M9.5 11l4 5.5M13.5 11l-4 5.5"/></>,
  transfer: <><path d="M4 8h15M15 4l4 4-4 4"/><path d="M20 16H5M9 12l-4 4 4 4"/></>,
  mobile: <><rect x="6.5" y="2.5" width="11" height="19" rx="2"/><path d="M11 18.5h2"/></>,
  cash: <><ellipse cx="12" cy="6" rx="7.5" ry="2.8"/><path d="M4.5 6v4c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6M4.5 10v4c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-4M4.5 14v4c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-4"/></>,
  lock: <><rect x="4.5" y="10.5" width="15" height="10.5" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5.5l3.5 2"/></>,
  receipt: <><path d="M5.5 2.5h13V21.5l-2.2-1.5-2.1 1.5-2.2-1.5-2.2 1.5-2.1-1.5-2.2 1.5Z"/><path d="M9 7.5h6M9 11.5h6M9 15.5h4"/></>,
  logout: <><path d="M9.5 20.5H5a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 5 3.5h4.5"/><path d="M15.5 16.5 20 12l-4.5-4.5M20 12H9"/></>,
  palette: <><path d="M12 3a9 9 0 1 0 0 18c1.2 0 1.7-.8 1.7-1.6 0-1.3-1.2-1.6-1.2-2.8 0-.9.7-1.6 1.6-1.6h2.4A4.5 4.5 0 0 0 21 10.5C21 6.4 17 3 12 3Z"/><circle cx="7.5" cy="11" r="1.1"/><circle cx="10.5" cy="7" r="1.1"/><circle cx="15" cy="7.2" r="1.1"/></>,
};

export function Icon({ name, size = 20, className = "", strokeWidth = 1.7 }) {
  return <svg className={`yd-icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONS[name] || ICONS.file}</svg>;
}

/* Logo YEM : livre ouvert vert + mot-symbole, identique aux maquettes. */
export function BookMark({ size = 56, className = "" }) {
  return <svg className={className} width={size} height={size * 0.78} viewBox="0 0 64 50" aria-hidden="true">
    <path d="M4 9.5c9-1.5 18 .5 26.5 6.8V47C22 41 13 39.4 4 40.6Z" fill="#2f7a35"/>
    <path d="M60 9.5c-9-1.5-18 .5-26.5 6.8V47C42 41 51 39.4 60 40.6Z" fill="#2f7a35"/>
    <path d="M8.5 4c7.5-.3 15 2.3 21 7.6v4.2C23.7 11 16.4 8.6 8.5 8.6Z" fill="#4c9a4f"/>
    <path d="M55.5 4c-7.5-.3-15 2.3-21 7.6v4.2c5.8-4.8 13.1-7.2 21-7.2Z" fill="#4c9a4f"/>
    <path d="M1 13.5v31.5c10-1.6 20.5.4 31 5 10.5-4.6 21-6.6 31-5V13.5" fill="none" stroke="#1f5a26" strokeWidth="2.6" strokeLinejoin="round"/>
    <path d="M9 17c6-.4 11.5 1.3 16.5 4.6M9 23c6-.4 11.5 1.3 16.5 4.6M9 29c6-.4 11.5 1.3 16.5 4.6M55 17c-6-.4-11.5 1.3-16.5 4.6M55 23c-6-.4-11.5 1.3-16.5 4.6M55 29c-6-.4-11.5 1.3-16.5 4.6" stroke="#ffffff" strokeOpacity=".35" strokeWidth="1.4" fill="none"/>
  </svg>;
}
export function YemLogo({ compact = false }) {
  return <div className={`yd-logo ${compact ? "compact" : ""}`} role="img" aria-label="YEM – Gestion scolaire et universitaire">
    <BookMark size={compact ? 44 : 60}/>
    <div><b>YEM</b><span>Gestion scolaire &amp; universitaire</span></div>
  </div>;
}

export function Button({ children, primary = false, icon, className = "", onClick, type = "button", disabled, ariaLabel }) {
  return <button type={type} disabled={disabled} aria-label={ariaLabel} className={`yd-btn ${primary ? "primary" : ""} ${className}`} onClick={onClick}>{icon && <Icon name={icon} size={20}/>}{children !== undefined && <span>{children}</span>}</button>;
}
export function Status({ children, tone = "green" }) { return <span className={`yd-status ${tone}`}>{children}</span>; }

export function Trend({ dir = "up", value, label }) {
  return <small className={`yd-trend ${dir}`}><Icon name={dir === "up" ? "trendup" : dir === "down" ? "trenddown" : "equal"} size={16} strokeWidth={2}/>{value && <b>{value}</b>}<span>{label}</span></small>;
}
export function Metric({ icon, label, value, trend, trendValue, trendLabel, className = "" }) {
  return <div className={`yd-metric ${className}`}><Icon name={icon} size={30} strokeWidth={1.5}/><div><div className="yd-metric-label">{label}</div><strong>{value}</strong>{(trendValue || trendLabel) && <Trend dir={trend} value={trendValue} label={trendLabel}/>}</div></div>;
}
export function Card({ title, icon, children, className = "", right, subtitle, count }) {
  return <section className={`yd-card ${className}`}>
    {title && <div className="yd-card-title"><h2>{icon && <Icon name={icon} size={24} strokeWidth={1.6}/>}<span>{title}</span>{count && <em>{count}</em>}</h2>{right}</div>}
    {subtitle && <p className="yd-card-sub">{subtitle}</p>}
    {children}
  </section>;
}
export function Table({ headers, rows, className = "", selected, align = {} }) {
  return <div className="yd-table-wrap"><table className={className}><thead><tr>{headers.map((h, i) => <th key={i} className={align[i] || ""}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i} className={selected === i ? "selected" : ""}>{r.map((c, j) => <td key={j} className={align[j] || ""}>{c}</td>)}</tr>)}</tbody></table></div>;
}
export function InfoRow({ k, v, icon, highlight, vIcon }) {
  return <div className={`yd-info-row ${highlight ? "highlight" : ""}`}><span>{icon && <Icon name={icon} size={20}/>}{k}</span><b>{vIcon && <Icon name={vIcon} size={18} className="wa"/>}<span>{v}</span></b></div>;
}
export function Note({ children }) { return <div className="yd-note"><Icon name="info" size={20}/><div>{children}</div></div>; }
export function SelectBox({ icon, label, value, className = "" }) {
  return <div className={`yd-select ${className}`}>{icon && <Icon name={icon} size={22}/>}<span>{label && <>{label} : </>}<b>{value}</b></span><Icon name="chevron" size={18} className="chev"/></div>;
}
export function SearchBox({ placeholder, value, onChange, className = "" }) {
  return <label className={`yd-search ${className}`}><Icon name="search" size={20}/><input placeholder={placeholder} aria-label={placeholder} value={value} onChange={onChange}/></label>;
}
export function Toggle({ on = true, label }) { return <span className="yd-toggle-wrap"><span className={`yd-toggle ${on ? "on" : ""}`} aria-hidden="true"/>{label}</span>; }
export function Check({ on = true }) { return <span className={`yd-check ${on ? "on" : ""}`} aria-hidden="true">{on && <Icon name="check" size={14} strokeWidth={3}/>}</span>; }

/* Anneau segmenté (SVG, compatible CSP sans style en ligne). */
const DONUT_COLORS = ["#2f6b37", "#6d9b73", "#adc8aa", "#dfe4df"];
export function Donut({ values, centerTop, centerBottom, legend, size = 190 }) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const r = 70, c = 2 * Math.PI * r;
  let offset = 0;
  return <div className="yd-donut-wrap">
    <svg className="yd-donut" width={size} height={size} viewBox="0 0 200 200" role="img" aria-label={`${centerTop} ${centerBottom}`}>
      <circle cx="100" cy="100" r={r} fill="none" stroke="#eef1ee" strokeWidth="44"/>
      {values.map((v, i) => { const len = (v / total) * c; const el = <circle key={i} cx="100" cy="100" r={r} fill="none" stroke={DONUT_COLORS[i % 4]} strokeWidth="44" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 100 100)"/>; offset += len; return el; })}
      <text x="100" y="96" textAnchor="middle" className="donut-top">{centerTop}</text>
      {String(centerBottom).split("\n").map((t, i) => <text key={i} x="100" y={116 + i * 16} textAnchor="middle" className="donut-bottom">{t}</text>)}
    </svg>
    <div className="yd-legend">{legend.map((x, i) => <div key={i}><i className={`c${i}`}/><span><b>{x[0]}</b>{x[1] && <small>{x[1]}</small>}</span></div>)}</div>
  </div>;
}

/* Courbe des encaissements avec axes, valeurs et dernier point mis en évidence. */
export function LineChart({ points, labels, min = 5000000, max = 10000000, step = 1000000 }) {
  const W = 560, H = 230, L = 78, R = 20, T = 18, B = 34;
  const x = i => L + 26 + i * ((W - L - R - 52) / (points.length - 1));
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));
  const ticks = []; for (let v = min; v <= max; v += step) ticks.push(v);
  const fmt = v => v.toLocaleString("fr-FR").replace(/ | /g, " ");
  const path = points.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  const last = points.length - 1;
  return <svg className="yd-linechart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Évolution des encaissements">
    <defs><linearGradient id="ydArea" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#2f6b37" stopOpacity=".22"/><stop offset="1" stopColor="#2f6b37" stopOpacity="0"/></linearGradient></defs>
    {ticks.map(v => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="grid"/><text x={L - 10} y={y(v) + 4} textAnchor="end" className="axis">{fmt(v)}</text></g>)}
    <line x1={L} x2={L} y1={T} y2={H - B} className="axisline"/>
    <path d={`${path} L${x(last)},${H - B} L${x(0)},${H - B} Z`} fill="url(#ydArea)"/>
    <path d={path} className="line"/>
    {points.map((v, i) => <g key={i}><circle cx={x(i)} cy={y(v)} r="4.5" className="dot"/>
      {i < last && <text x={x(i) + (i === 0 ? 6 : 0)} y={y(v) - 11} textAnchor={i === 0 ? "start" : "middle"} className="val">{fmt(v)}</text>}
      <text x={x(i)} y={H - 10} textAnchor="middle" className="axis">{labels[i]}</text></g>)}
    <g><rect x={x(last) - 44} y={y(points[last]) - 34} width="88" height="22" rx="4" className="tip"/><text x={x(last)} y={y(points[last]) - 19} textAnchor="middle" className="tiptext">{fmt(points[last])}</text></g>
  </svg>;
}

export function BarList({ items, max, unit = "familles" }) {
  const top = max || Math.max(...items.map(i => i[1]));
  return <div className="yd-barlist">{items.map(([label, v]) => <div key={label}><span>{label}</span><div className="track"><svg viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true"><rect width={(v / top) * 100} height="10" rx="0"/></svg></div><b>{v} {unit}</b></div>)}
    <div className="yd-barlist-axis"><span/><div>{[0, 2, 4, 6, 8].map(t => <i key={t}>{t}</i>)}</div><b/></div><p>Nombre de familles</p></div>;
}

export const BrandContext = React.createContext({ banner: "" });
export function PageHeader({ title, subtitle, badge, badgeIcon, actions, banner = true }) {
  const brand = React.useContext(BrandContext);
  return <div className={`yd-hero ${banner ? "" : "nobanner"}`}>
    <div className="yd-hero-text"><div className="yd-hero-row"><h1>{title}</h1>{badge && <span className="yd-page-badge">{badgeIcon && <Icon name={badgeIcon} size={20}/>}{badge}</span>}</div><p>{subtitle}</p></div>
    {actions && <div className="yd-hero-actions">{actions}</div>}
    {banner && <div className="yd-school-banner" aria-hidden="true">{brand?.banner && <img src={brand.banner} alt=""/>}</div>}
  </div>;
}

export function QrCode({ size = 72, seed = 7 }) {
  const n = 21, cells = [];
  let s = seed * 9301 + 49297;
  const finder = (r, c) => { for (const [fr, fc] of [[0, 0], [0, n - 7], [n - 7, 0]]) { const rr = r - fr, cc = c - fc; if (rr >= 0 && rr < 7 && cc >= 0 && cc < 7) return (rr === 0 || rr === 6 || cc === 0 || cc === 6 || (rr >= 2 && rr <= 4 && cc >= 2 && cc <= 4)) ? 1 : 0; } return -1; };
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) { const f = finder(r, c); let on; if (f >= 0) on = f; else if ((r < 8 && c < 8) || (r < 8 && c > n - 9) || (r > n - 9 && c < 8)) on = 0; else { s = (s * 9301 + 49297) % 233280; on = s / 233280 > 0.52; } if (on) cells.push(<rect key={r + "-" + c} x={c} y={r} width="1.02" height="1.02"/>); }
  return <svg className="yd-qr" width={size} height={size} viewBox={`-1 -1 ${n + 2} ${n + 2}`} role="img" aria-label="QR code de vérification"><rect x="-1" y="-1" width={n + 2} height={n + 2} fill="#fff"/>{cells}</svg>;
}

export function Signature({ variant = 0 }) {
  return <svg className="yd-signature" viewBox="0 0 120 44" aria-hidden="true">{variant ? <path d="M6 30c12-14 20-22 26-16 5 5-10 20-3 18 9-3 14-20 22-18 6 2-2 14 4 14 7 0 10-12 16-12 5 0 2 10 8 9 8-2 14-8 34-12M10 36c30-4 60-6 100-8"/> : <path d="M8 28c8-10 16-20 22-15 6 6-8 18 0 17 8-1 12-17 20-15 6 2 0 12 6 12s9-10 14-10c6 0 2 9 8 8 9-1 16-9 34-14M12 35c28-3 62-5 98-6"/>}</svg>;
}

export const NAV = [
  ["dashboard", "home", "Tableau de bord"],
  ["students", "users", "Élèves"],
  ["admissions", "adduser", "Admissions"],
  ["payments", "card", "Paiements"],
  ["arrears", "alert", "Impayés & relances"],
  ["bulletins", "file", "Bulletins"],
  ["absences", "calendar", "Absences"],
  ["parents", "users", "Parents"],
  ["staff", "idcard", "Personnel"],
  ["settings", "settings", "Paramètres"],
];

/* Cadre commun : barre supérieure + menu latéral + zone de contenu. */
export function Shell({ schoolSelector, search, userName = "Mme la Directrice", userMenu, notifications = 3, nav = NAV, active, onNavigate, children, className = "" }) {
  return <div className={`yd-app ${className}`}>
    <header className="yd-topbar">
      <YemLogo/>
      <div className="yd-topbar-sep"/>
      {schoolSelector}
      {search || <SearchBox placeholder="Rechercher un élève, une famille, un paiement..." className="yd-global-search"/>}
      <div className="yd-bell" aria-label={notifications ? `${notifications} notifications` : "Notifications"}><Icon name="bell" size={26} strokeWidth={1.6}/>{notifications ? <i>{notifications}</i> : null}</div>
      <div className="yd-topbar-sep small"/>
      {userMenu || <div className="yd-user"><div className="yd-avatar"><Icon name="user" size={22} strokeWidth={0} className="filled"/></div><b>{userName}</b><Icon name="chevron" size={18}/></div>}
    </header>
    <aside className="yd-sidebar" aria-label="Navigation principale">{nav.map(([id, icon, label]) => <button type="button" key={id} className={active === id ? "active" : ""} aria-current={active === id ? "page" : undefined} onClick={() => onNavigate?.(id)}><Icon name={icon} size={24} strokeWidth={1.6}/><span>{label}</span></button>)}</aside>
    <main className="yd-content">{children}</main>
  </div>;
}
