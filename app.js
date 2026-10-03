/* Rural Clinic Explorer: story charts, world explorer, tabs. Data in data.js (window.DATA), built by eda/build_site_data.py. */
const D = window.DATA;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = {
  ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"), rule: css("--rule"), axis: css("--axis"),
  series: css("--series"), deep: css("--series-deep"), lantern: css("--lantern"), nodata: css("--nodata"), bad: css("--bad"),
};
const RAMP = [1, 2, 3, 4, 5, 6, 7].map(i => css(`--ramp-${i}`));
const OTHER = "#d5dbe1";
const FOCUS = {
  IDN: { name: "Indonesia", color: css("--indonesia") },
  IND: { name: "India", color: css("--india") },
};
const SINCE = 2015;
const WHO_MIN = 44.5, READY_NET = 60, READY_ELEC = 95;
const PS = { fontFamily: "Archivo, system-ui, sans-serif", fontSize: "12px", color: C.ink2, overflow: "visible", background: "transparent" };

const SEGMENTS = [
  { key: "sweet", label: "Online and powered, short of staff", color: C.deep },
  { key: "both", label: "Short of rails and staff", color: "#e8a0a9" },
  { key: "staffed", label: "Online and powered, staffed", color: "#cfd8dc" },
  { key: "norails", label: "Staffed, rails not ready", color: "#f5d39b" },
];
const SEG = Object.fromEntries(SEGMENTS.map(s => [s.key, s]));

const METRICS = {
  workforce: { label: "Health workers", unit: "per 10,000 people", fmt: v => v.toFixed(1) },
  rural: { label: "Rural share", unit: "% of people living in rural areas", fmt: v => Math.round(v) + "%" },
  internet: { label: "Online", unit: "% of people using the internet", fmt: v => Math.round(v) + "%" },
  mobile: { label: "Mobile", unit: "mobile subscriptions per 100 people", fmt: v => Math.round(v).toString() },
  electricity: { label: "Electricity", unit: "% of people with electricity", fmt: v => (v >= 99.5 ? v.toFixed(1) : Math.round(v)) + "%" },
  uhc: { label: "Service coverage", unit: "UHC service coverage index, 0 to 100", fmt: v => Math.round(v).toString() },
  tb: { label: "TB incidence", unit: "new TB cases per 100,000 people", fmt: v => Math.round(v).toString() },
  feasibility: { label: "Feasibility", unit: "digital rails vs health workers", categorical: true },
};
const NUMERIC = Object.keys(METRICS).filter(k => !METRICS[k].categorical);

function latest(metric, iso) {
  // workforce uses each component's latest value (same method as the EDA notebook); its series pairs same-year values
  if (metric === "workforce") { const w = D.wfLatest[iso]; return w ? { value: w[0], year: w[1] } : null; }
  const s = D.series[metric] && D.series[metric][iso];
  if (!s) return null;
  for (let i = s.length - 1; i >= 0; i--) if (s[i][0] >= SINCE) return { year: s[i][0], value: s[i][1] };
  return null;
}
function latestAll(metric) {
  return Object.keys(D.names).map(iso => ({ iso, name: D.names[iso], ...latest(metric, iso) })).filter(d => d.value != null);
}
const byIso = metric => new Map(latestAll(metric).map(d => [d.iso, d]));
function segment(iso) {
  const e = latest("electricity", iso), n = latest("internet", iso), w = latest("workforce", iso);
  if (!e || !n || !w) return null;
  const rails = e.value >= READY_ELEC && n.value >= READY_NET, short = w.value < WHO_MIN;
  return rails && short ? "sweet" : short ? "both" : rails ? "staffed" : "norails";
}

/* ---------------------------------------------------------------- story charts */
const story = {
  workforce(el) {
    const data = latestAll("workforce").sort((a, b) => a.value - b.value).map((d, i) => ({ ...d, i }));
    const below = data.filter(d => d.value < WHO_MIN).length / data.length;
    document.getElementById("n-below").textContent = Math.round(below * 100) + "%";
    document.getElementById("ps-below").textContent = Math.round(below * 100) + "%";
    document.getElementById("st1-focus").innerHTML = Object.entries(FOCUS).map(([iso, f]) => {
      const v = data.find(d => d.iso === iso);
      return v ? `<b style="color:${f.color}">${f.name} ${v.value.toFixed(1)}</b>` : "";
    }).join(" · ") + " per 10,000.";
    const f = iso => data.filter(d => d.iso === iso);
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 360, marginLeft: 44, marginTop: 40, style: PS,
      x: { type: "band", axis: null, padding: 0.12 },
      y: { label: "Health workers per 10,000", grid: true, domain: [0, 160], clamp: true },
      marks: [
        Plot.barY(data, { x: "i", y: d => Math.min(d.value, 160), fill: d => FOCUS[d.iso] ? FOCUS[d.iso].color : d.value < WHO_MIN ? RAMP[2] : OTHER,
          title: d => `${d.name}: ${d.value.toFixed(1)} (${d.year})`, tip: true }),
        Plot.ruleY([WHO_MIN], { stroke: C.ink, strokeDasharray: "4,3" }),
        Plot.text([WHO_MIN], { x: data[2].i, y: d => d, text: () => "WHO minimum 44.5", dy: -8, textAnchor: "start", fill: C.ink, fontWeight: 600 }),
        Plot.text([0], { x: data[Math.round(data.length * below * 0.45)].i, y: () => 120, text: () => "blue: below the minimum", fill: C.series, fontWeight: 600 }),
        Plot.text(f("IND"), { x: "i", y: "value", text: d => `India ${d.value.toFixed(1)}`, dy: -48, dx: -4, textAnchor: "end", fill: FOCUS.IND.color, fontWeight: 700 }),
        Plot.text(f("IDN"), { x: "i", y: "value", text: d => `Indonesia ${d.value.toFixed(1)}`, dy: -30, dx: 4, textAnchor: "start", fill: FOCUS.IDN.color, fontWeight: 700 }),
      ],
    }));
  },
  rural(el) {
    const net = byIso("internet"), wf = byIso("workforce");
    const data = latestAll("rural").filter(d => net.has(d.iso)).map(d => ({ iso: d.iso, name: d.name, rural: d.value, net: net.get(d.iso).value, wf: wf.get(d.iso)?.value }));
    const quad = data.filter(d => d.rural > 50 && d.net < 50);
    const short = quad.filter(d => d.wf != null && d.wf < WHO_MIN).length / quad.filter(d => d.wf != null).length;
    document.getElementById("n-offline").textContent = quad.length;
    document.querySelector("#st2 h2").textContent = `countries are majority rural and majority offline. ${Math.round(short * 100)}% of them are also short of health workers.`;
    const focus = data.filter(d => FOCUS[d.iso]);
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 380, marginLeft: 44, style: PS,
      x: { label: "Rural population (%)", domain: [0, 100], grid: true },
      y: { label: "Internet users (%)", domain: [0, 100], grid: true },
      marks: [
        Plot.rect([{}], { x1: 50, x2: 100, y1: 0, y2: 50, fill: C.bad, fillOpacity: 0.06 }),
        Plot.text([{}], { x: 98, y: 4, text: () => "rural and offline", textAnchor: "end", fill: C.bad, fontWeight: 600 }),
        Plot.dot(data.filter(d => !FOCUS[d.iso]), { x: "rural", y: "net", r: 4, fill: d => d.rural > 50 && d.net < 50 ? C.bad : C.axis, fillOpacity: 0.8,
          title: d => `${d.name}\nrural ${Math.round(d.rural)}%, online ${Math.round(d.net)}%`, tip: true }),
        Plot.dot(focus, { x: "rural", y: "net", r: 7, fill: d => FOCUS[d.iso].color, stroke: "#fff", strokeWidth: 2 }),
        Plot.text(focus, { x: "rural", y: "net", text: "name", dy: -14, fill: d => FOCUS[d.iso].color, fontWeight: 700 }),
      ],
    }));
  },
  queue(el) {
    const cap = 40;
    const data = D.queue.filter(d => d[0] >= 2).sort((a, b) => b[0] - a[0])
      .map(([n, w]) => ({ label: n === 4 ? "4 staff (full roster)" : `${n} staff`, wait: w, y: w == null ? cap : w }));
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 340, marginLeft: 44, marginTop: 30, style: PS,
      x: { label: null, domain: data.map(d => d.label), padding: 0.45 },
      y: { label: "Average wait before seeing someone (min)", domain: [0, cap * 1.15], grid: true },
      marks: [
        Plot.barY(data, { x: "label", y: "y", fill: d => d.wait == null ? C.bad : d.label.startsWith("4") ? C.series : C.lantern,
          fillOpacity: d => d.wait == null ? 0.18 : 1 }),
        Plot.text(data, { x: "label", y: "y", text: d => d.wait == null ? "never clears" : `${Math.round(d.wait)} min`, dy: -10,
          fill: d => d.wait == null ? C.bad : C.ink, fontWeight: 700, fontSize: 15 }),
        Plot.ruleY([0], { stroke: C.axis }),
      ],
    }));
  },
  hours(el) {
    const s = [{ k: "Rostered", v: 100 }, { k: "Present", v: 100 - D.key.health_worker_absence_avg_pct }, { k: "With patients", v: D.key.patient_facing_share_illustrative_pct }];
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 340, marginLeft: 44, marginTop: 30, style: PS,
      x: { label: null, domain: s.map(d => d.k), padding: 0.4 },
      y: { label: "% of rostered clinical time", domain: [0, 112], grid: true },
      marks: [
        Plot.barY(s, { x: "k", y: "v", fill: [OTHER, C.lantern, C.series] }),
        Plot.text(s, { x: "k", y: "v", text: d => Math.round(d.v) + "%", dy: -10, fill: C.ink, fontWeight: 700, fontSize: 16 }),
        Plot.text(s.slice(1), { x: "k", y: () => 6, text: (d, i) => i === 0 ? "minus absence" : "minus paperwork", fill: "#fff", fontWeight: 600 }),
        Plot.ruleY([0], { stroke: C.axis }),
      ],
    }));
  },
  feasibility(el) {
    const data = Object.keys(D.names).map(iso => {
      const n = latest("internet", iso), w = latest("workforce", iso), seg = segment(iso);
      return n && w && seg ? { iso, name: D.names[iso], net: n.value, wf: w.value, seg } : null;
    }).filter(Boolean);
    const sweet = data.filter(d => d.seg === "sweet");
    document.getElementById("n-sweet").textContent = sweet.length;
    const idn = data.find(d => d.iso === "IDN"), ind = data.find(d => d.iso === "IND");
    const mob = iso => Math.round(latest("mobile", iso).value), rur = iso => Math.round(latest("rural", iso).value);
    document.getElementById("st5-compare").innerHTML =
      `<b style="color:${FOCUS.IDN.color}">Indonesia</b>: ${Math.round(idn.net)}% online, ${mob("IDN")} mobile lines per 100 people, ${rur("IDN")}% rural. ` +
      `<b style="color:${FOCUS.IND.color}">India</b>: ${Math.round(ind.net)}% online, ${mob("IND")} per 100, ${rur("IND")}% rural. Same shortage of staff, different starting points.`;
    const focus = data.filter(d => FOCUS[d.iso]);
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 380, marginLeft: 48, style: PS,
      x: { label: "Internet users (%)", domain: [0, 100], grid: true },
      y: { label: "Health workers per 10,000 (log)", type: "log", domain: [2, 250], grid: true, tickFormat: d3.format("~s") },
      marks: [
        Plot.rect([{}], { x1: READY_NET, x2: 100, y1: 2, y2: WHO_MIN, fill: C.deep, fillOpacity: 0.07 }),
        Plot.text([{}], { x: 99, y: 2.6, text: () => "online and powered, short of staff", textAnchor: "end", fill: C.deep, fontWeight: 700 }),
        Plot.ruleY([WHO_MIN], { stroke: C.ink, strokeDasharray: "4,3" }),
        Plot.ruleX([READY_NET], { stroke: C.ink, strokeDasharray: "2,3" }),
        Plot.dot(data.filter(d => !FOCUS[d.iso]), { x: "net", y: "wf", r: 4, fill: d => d.seg === "sweet" ? C.deep : C.axis, fillOpacity: 0.8,
          title: d => `${d.name}\nonline ${Math.round(d.net)}%, ${d.wf.toFixed(1)} health workers per 10,000`, tip: true }),
        Plot.dot(focus, { x: "net", y: "wf", r: 7, fill: d => FOCUS[d.iso].color, stroke: "#fff", strokeWidth: 2 }),
        Plot.text(focus.filter(d => d.iso === "IDN"), { x: "net", y: "wf", text: "name", dy: -14, fill: FOCUS.IDN.color, fontWeight: 700 }),
        Plot.text(focus.filter(d => d.iso === "IND"), { x: "net", y: "wf", text: "name", dy: 16, fill: FOCUS.IND.color, fontWeight: 700 }),
      ],
    }));
  },
  pareto(el) {
    const PM = {
      people: { label: "People", noun: "people", value: iso => D.pop[iso]?.[0] },
      rural: { label: "Rural people", noun: "rural people", value: iso => D.pop[iso]?.[1] },
      tb: { label: "TB cases", noun: "TB cases", value: iso => { const t = latest("tb", iso), p = D.pop[iso]; return t && p ? t.value * p[0] / 1e5 : null; } },
      gap: { label: "Missing health workers", noun: "missing health workers", value: iso => { const w = latest("workforce", iso), p = D.pop[iso]; return w && p ? Math.max(0, WHO_MIN - w.value) * p[0] / 1e4 : null; } },
    };
    const PU = {
      sweet: { label: "Online and powered, short of staff", test: iso => segment(iso) === "sweet" },
      all: { label: "All understaffed countries", test: iso => { const w = latest("workforce", iso); return w && w.value < WHO_MIN; } },
    };
    const st = story.paretoState || (story.paretoState = { metric: "people", universe: "sweet" });
    const pills = (id, defs, keyName) => {
      const box = document.getElementById(id);
      box.replaceChildren(...Object.entries(defs).map(([k, d]) => {
        const b = document.createElement("button");
        b.className = "pill"; b.textContent = d.label; b.setAttribute("aria-pressed", st[keyName] === k);
        b.onclick = () => { st[keyName] = k; story.pareto(el); };
        return b;
      }));
    };
    pills("pareto-metric", PM, "metric"); pills("pareto-universe", PU, "universe");

    const rows = Object.keys(D.names).filter(PU[st.universe].test)
      .map(iso => ({ iso, name: D.names[iso], v: PM[st.metric].value(iso) })).filter(d => d.v != null && d.v > 0)
      .sort((a, b) => b.v - a.v);
    const total = d3.sum(rows, d => d.v);
    let cum = 0;
    rows.forEach((d, i) => { d.share = 100 * d.v / total; cum += d.share; d.cum = cum; d.rank = i + 1; });
    const two = d3.sum(rows.filter(d => FOCUS[d.iso]), d => d.share);
    const MAX = 15;
    const shown = rows.slice(0, MAX);
    if (rows.length > MAX) shown.push({ iso: "OTHER", name: `Other ${rows.length - MAX}`, share: 100 - rows[MAX - 1].cum, cum: 100, rank: MAX + 1 });
    const nUni = rows.length;
    document.getElementById("n-pareto").textContent = Math.round(two) + "%";
    if (st.metric === "people" && st.universe === "sweet") document.getElementById("ps-pareto").textContent = Math.round(two) + "%";
    document.getElementById("h-pareto").textContent = st.universe === "sweet"
      ? `of the ${PM[st.metric].noun} in the ${nUni} countries that are online and powered but short of staff are in Indonesia and India.`
      : `of the ${PM[st.metric].noun} across all ${nUni} understaffed countries are in Indonesia and India.`;
    const rk = iso => rows.find(d => d.iso === iso)?.rank;
    document.getElementById("p-pareto").innerHTML =
      `Two countries out of ${nUni}. <b style="color:${FOCUS.IND.color}">India</b> ranks ${ordinal(rk("IND"))} and <b style="color:${FOCUS.IDN.color}">Indonesia</b> ${ordinal(rk("IDN"))}. ` +
      (st.metric === "gap" && st.universe === "all" ? "Indonesia is close to the threshold, so its gap is smaller; its weight shows in people and TB cases." : "India brings scale; Indonesia brings readiness.");
    el.replaceChildren(Plot.plot({
      width: el.clientWidth, height: 380, marginLeft: 44, marginBottom: 78, marginTop: 24, style: PS,
      x: { label: null, domain: shown.map(d => d.name), tickRotate: -45, padding: 0.18 },
      y: { label: "% of total (bars) · cumulative % (line)", domain: [0, 100], grid: true },
      marks: [
        Plot.ruleY([80], { stroke: C.ink, strokeDasharray: "2,3" }),
        Plot.text([80], { x: shown[shown.length - 1].name, y: d => d, text: () => "80%", dy: -7, textAnchor: "end", fill: C.ink2 }),
        Plot.barY(shown, { x: "name", y: "share", fill: d => FOCUS[d.iso] ? FOCUS[d.iso].color : OTHER,
          title: d => `${d.name}: ${d.share.toFixed(1)}% of total, cumulative ${d.cum.toFixed(0)}%`, tip: true }),
        // tall bars get the label inside (the cumulative line starts at the first bar's top)
        Plot.text(shown.filter(d => FOCUS[d.iso] && d.share >= 15), { x: "name", y: "share", text: d => d.share.toFixed(0) + "%", dy: 14, fill: d => d.iso === "IND" ? C.ink : "#fff", fontWeight: 700, fontSize: 11 }),
        Plot.text(shown.filter(d => FOCUS[d.iso] && d.share < 15), { x: "name", y: "share", text: d => d.share.toFixed(0) + "%", dy: -8, fill: d => FOCUS[d.iso].color, fontWeight: 700 }),
        Plot.line(shown, { x: "name", y: "cum", stroke: C.ink2, strokeWidth: 1.8 }),
        Plot.dot(shown, { x: "name", y: "cum", r: 3, fill: C.ink2 }),
      ],
    }));
  },
};

let factMap;
function initFactMap() {
  if (factMap) return factMap.invalidateSize();
  document.getElementById("n-hours").textContent = D.facilityHoursPct + "%";
  factMap = L.map("factmap", { scrollWheelZoom: false, preferCanvas: true, attributionControl: true }).fitBounds([[-11, 94.5], [6.5, 141.5]]);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, attribution: "Basemap © Esri, HERE, Garmin | Facilities © OpenStreetMap contributors via healthsites.io" }).addTo(factMap);
  const r = L.canvas({ padding: 0.5 });
  // same dot size for both groups so the map does not overstate how many facilities list hours
  D.facilities.forEach(f => { if (!f[2]) L.circleMarker([f[0], f[1]], { renderer: r, radius: 2, stroke: false, fillColor: "#8a96a3", fillOpacity: 0.6 }).addTo(factMap); });
  D.facilities.forEach(f => { if (f[2]) L.circleMarker([f[0], f[1]], { renderer: r, radius: 2, stroke: false, fillColor: C.lantern, fillOpacity: 0.95 }).addTo(factMap); });
}

function drawStory() {
  story.workforce(document.getElementById("f-workforce"));
  story.rural(document.getElementById("f-rural"));
  story.queue(document.getElementById("f-queue"));
  story.hours(document.getElementById("f-hours"));
  story.feasibility(document.getElementById("f-feasibility"));
  story.pareto(document.getElementById("f-pareto"));
  initFactMap();
}

/* ---------------------------------------------------------------- explorer */
const state = { metric: "workforce", iso: "IDN" };
let worldMap, countryLayer, legendCtl, scale;

function buildControls() {
  const pills = document.getElementById("metric-pills");
  Object.entries(METRICS).forEach(([k, m]) => {
    const b = document.createElement("button");
    b.className = "pill"; b.textContent = m.label; b.dataset.metric = k; b.setAttribute("aria-pressed", k === state.metric);
    b.onclick = () => { state.metric = k; pills.querySelectorAll(".pill").forEach(p => p.setAttribute("aria-pressed", p.dataset.metric === k)); updateExplore(); };
    pills.appendChild(b); pills.append(" ");
  });
  const picker = document.getElementById("picker");
  Object.entries(FOCUS).forEach(([iso, f]) => {
    const b = document.createElement("button");
    b.className = "pill"; b.dataset.iso = iso; b.innerHTML = `<i class="dot" style="background:${f.color}"></i>${f.name}`;
    b.onclick = () => select(iso);
    picker.appendChild(b);
  });
  const sel = document.createElement("select");
  sel.setAttribute("aria-label", "Pick any country");
  sel.innerHTML = `<option value="">Any country…</option>` + Object.entries(D.names).sort((a, b) => a[1].localeCompare(b[1]))
    .map(([iso, n]) => `<option value="${iso}">${n}</option>`).join("");
  sel.onchange = () => sel.value && select(sel.value);
  picker.appendChild(sel);
}

function select(iso) {
  state.iso = iso;
  document.querySelectorAll("#picker .pill").forEach(p => p.setAttribute("aria-pressed", p.dataset.iso === iso));
  document.querySelector("#picker select").value = FOCUS[iso] ? "" : iso;
  updateExplore();
}

function initWorldMap() {
  worldMap = L.map("worldmap", { scrollWheelZoom: false, minZoom: 1, maxZoom: 6, zoomSnap: 0.25, worldCopyJump: false })
    .fitBounds([[-50, -150], [72, 165]]);
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, attribution: "Basemap © Esri, HERE, Garmin | Data: WHO GHO, World Bank WDI" }).addTo(worldMap);
  worldMap.createPane("labels"); worldMap.getPane("labels").style.zIndex = 650; worldMap.getPane("labels").style.pointerEvents = "none";
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, pane: "labels", opacity: 0.8 }).addTo(worldMap);
  return fetch("world.json").then(r => r.json()).then(topo => {
    const geo = topojson.feature(topo, topo.objects.countries);
    geo.features = geo.features.filter(f => f.id !== "010"); // no Antarctica
    geo.features.forEach(unwrapAntimeridian);
    setScale();
    countryLayer = L.geoJSON(geo, {
      style: styleFor,
      onEachFeature: (f, layer) => {
        layer.on("click", () => f.properties.iso3 && D.names[f.properties.iso3] && select(f.properties.iso3));
        layer.bindTooltip(() => tooltipFor(f), { sticky: true, className: "tt" });
      },
    }).addTo(worldMap);
    legendCtl = L.control({ position: "bottomleft" });
    legendCtl.onAdd = () => L.DomUtil.create("div", "maplegend");
    legendCtl.addTo(worldMap);
  });
}

// Rings that cross 180° (Russia, Fiji) would draw as world-wide stripes in Leaflet; shift their western half east.
function unwrapAntimeridian(f) {
  const fix = ring => {
    if (ring.some(p => p[0] > 160) && ring.some(p => p[0] < -160)) ring.forEach(p => { if (p[0] < 0) p[0] += 360; });
  };
  const g = f.geometry;
  if (!g) return;
  if (g.type === "Polygon") g.coordinates.forEach(fix);
  if (g.type === "MultiPolygon") g.coordinates.forEach(poly => poly.forEach(fix));
}

function fillFor(iso) {
  if (!iso) return C.nodata;
  if (METRICS[state.metric].categorical) { const s = segment(iso); return s ? SEG[s].color : C.nodata; }
  const v = latest(state.metric, iso);
  return v ? scale(v.value) : C.nodata;
}
function styleFor(f) {
  const iso = f.properties.iso3, sel = iso === state.iso;
  // selected country gets a thin dark outline only; no colour highlight
  return { fillColor: fillFor(iso), fillOpacity: 0.92, color: sel ? C.ink : "#ffffff", weight: sel ? 1.6 : 0.6 };
}
function tooltipFor(f) {
  const iso = f.properties.iso3, m = METRICS[state.metric];
  const name = (iso && D.names[iso]) || f.properties.name;
  if (m.categorical) { const s = iso && segment(iso); return `<b>${name}</b><br>${s ? SEG[s].label : "no recent data"}`; }
  const v = iso && latest(state.metric, iso);
  return `<b>${name}</b><br>${v ? `${m.label}: ${m.fmt(v.value)} (${v.year})` : "no recent data"}`;
}

function updateLegend() {
  const m = METRICS[state.metric], el = legendCtl.getContainer();
  if (m.categorical) {
    el.innerHTML = `<b>Feasibility</b><div style="margin:-3px 0 6px">online ≥ ${READY_NET}% and electricity ≥ ${READY_ELEC}%, vs WHO minimum ${WHO_MIN}</div>` +
      SEGMENTS.map(s => `<div><i class="dot" style="background:${s.color}"></i>${s.label}</div>`).join("") +
      `<div><i class="dot" style="background:${C.nodata};border:1px solid ${C.axis}"></i>no recent data</div>`;
    return;
  }
  const q = scale.quantiles();
  el.innerHTML = `<b>${m.label}</b><div style="margin:-3px 0 6px">${m.unit}</div>
    <div class="ramp">${RAMP.map(c => `<span style="background:${c}"></span>`).join("")}</div>
    <div class="ramp-labels"><span>under ${m.fmt(q[0])}</span><span>${m.fmt(q[q.length - 1])} or more</span></div>
    <div style="margin-top:6px"><i class="dot" style="background:${C.nodata};border:1px solid ${C.axis}"></i>no recent data
    ${state.metric === "workforce" ? `<br>WHO minimum: ${WHO_MIN} per 10,000` : ""}</div>`;
}

function setScale() {
  const metric = METRICS[state.metric].categorical ? "workforce" : state.metric;
  const all = latestAll(metric);
  scale = d3.scaleQuantile().domain(all.map(d => d.value)).range(RAMP);
  return all;
}

function updateExplore() {
  const all = setScale();
  if (countryLayer) {
    countryLayer.setStyle(styleFor);
    countryLayer.eachLayer(l => { if (l.feature.properties.iso3 === state.iso) l.bringToFront(); });
    updateLegend();
  }
  updatePanel(all);
}

function updatePanel(all) {
  const iso = state.iso, name = D.names[iso], m = METRICS[state.metric];
  document.getElementById("c-name").textContent = name;
  const wf = latest("workforce", iso), ru = latest("rural", iso), ne = latest("internet", iso), el = latest("electricity", iso), mo = latest("mobile", iso);
  const seg = segment(iso);
  const parts = [];
  if (wf) parts.push(`${name} has <b>${wf.value.toFixed(1)}</b> health workers per 10,000 people (${wf.year}), <b>${wf.value < WHO_MIN ? "below" : "above"}</b> the WHO minimum of ${WHO_MIN}.`);
  if (ru && ne) parts.push(`<b>${Math.round(ru.value)}%</b> of people live in rural areas and <b>${Math.round(ne.value)}%</b> are online.`);
  if (el && mo) parts.push(`Electricity reaches <b>${METRICS.electricity.fmt(el.value)}</b> of people, with <b>${Math.round(mo.value)}</b> mobile subscriptions per 100.`);
  if (seg === "sweet") parts.push(`<b>It has the digital rails but not the staff.</b>`);
  document.getElementById("c-summary").innerHTML = parts.join(" ") || "No recent data for this country.";

  document.getElementById("c-kpis").innerHTML = NUMERIC.map(k => {
    const v = latest(k, iso), mm = METRICS[k];
    return `<div class="kpi"><div class="l">${mm.label}</div><div class="v">${v ? mm.fmt(v.value) : "n/a"}</div><div class="s">${v ? v.year : "no data since " + SINCE}</div></div>`;
  }).join("");

  const rankEl = document.getElementById("c-rank");
  if (m.categorical) {
    document.getElementById("rank-title").textContent = "Feasibility check";
    document.getElementById("rank-sub").textContent = seg ? `${SEG[seg].label}. Bars show ${name} against each threshold.` : `Not enough recent data for ${name}.`;
    const rows = [
      { k: "Electricity %", v: el?.value, t: READY_ELEC, ok: v => v >= READY_ELEC },
      { k: "Online %", v: ne?.value, t: READY_NET, ok: v => v >= READY_NET },
      { k: "Health workers /10k", v: wf?.value, t: WHO_MIN, ok: v => v >= WHO_MIN },
    ].filter(r => r.v != null);
    rankEl.replaceChildren(Plot.plot({ width: rankEl.clientWidth, height: 120, marginLeft: 120, marginRight: 40, style: PS,
      x: { domain: [0, 100], grid: true, label: null, clamp: true }, y: { label: null, domain: rows.map(r => r.k) },
      marks: [
        Plot.barX(rows, { y: "k", x: d => Math.min(d.v, 100), fill: d => d.ok(d.v) ? C.deep : C.bad, fillOpacity: 0.85 }),
        Plot.tickX(rows, { y: "k", x: "t", stroke: C.ink, strokeWidth: 2 }),
        Plot.text(rows, { y: "k", x: d => Math.min(d.v, 100), text: d => d.v.toFixed(d.v < 100 ? 1 : 0), dx: 4, textAnchor: "start", fill: C.ink, fontWeight: 700 }),
      ] }));
  } else {
    const sorted = [...all].sort((a, b) => b.value - a.value).map((d, i) => ({ ...d, rank: i + 1 }));
    const me = sorted.find(d => d.iso === iso);
    document.getElementById("rank-title").textContent = `Where it ranks: ${m.label.toLowerCase()}`;
    document.getElementById("rank-sub").textContent = me ? `${name} is ${ordinal(me.rank)} of ${sorted.length} countries (highest first). ${m.unit}.` : `No recent ${m.label.toLowerCase()} data for ${name}.`;
    const marks = [
      Plot.barY(sorted, { x: "rank", y: "value", fill: d => d.iso === iso ? C.ink : FOCUS[d.iso] ? FOCUS[d.iso].color : OTHER,
        title: d => `${d.name}: ${m.fmt(d.value)} (${d.year})`, tip: true }),
    ];
    if (state.metric === "workforce") marks.push(Plot.ruleY([WHO_MIN], { stroke: C.ink, strokeDasharray: "4,3" }));
    if (me) marks.push(Plot.text([me], { x: "rank", y: "value", text: d => m.fmt(d.value), dy: -8, fill: C.ink, fontWeight: 700 }));
    const yMax = d3.quantile(sorted.map(d => d.value).sort(d3.ascending), 0.98) * 1.1;
    rankEl.replaceChildren(Plot.plot({ width: rankEl.clientWidth, height: 150, marginLeft: 36, marginTop: 18, style: PS,
      x: { type: "band", axis: null, padding: 0.1 }, y: { grid: true, label: null, domain: [0, Math.max(yMax, me ? me.value * 1.15 : 0)], clamp: true }, marks }));
  }

  // over time vs median (feasibility view shows internet use)
  const tm = m.categorical ? "internet" : state.metric;
  const series = (D.series[tm][iso] || []).map(([year, value]) => ({ year, value }));
  const byYear = d3.rollups(Object.values(D.series[tm]).flat(), v => v.length >= 40 ? d3.median(v, d => d[1]) : null, d => d[0])
    .filter(d => d[1] != null && d[0] >= 2000).map(([year, value]) => ({ year, value })).sort((a, b) => a.year - b.year);
  document.getElementById("trend-sub").textContent = series.length
    ? `${METRICS[tm].label}: ${name} (solid) vs the median country (dashed).` : `No ${METRICS[tm].label.toLowerCase()} history for ${name}.`;
  const tel = document.getElementById("c-trend"), col = FOCUS[iso] ? FOCUS[iso].color : C.ink;
  tel.replaceChildren(Plot.plot({ width: tel.clientWidth, height: 160, marginLeft: 36, style: PS,
    x: { label: null, tickFormat: d3.format("d"), domain: [2000, 2024] }, y: { grid: true, label: null, zero: true },
    marks: [
      Plot.line(byYear, { x: "year", y: "value", stroke: C.axis, strokeWidth: 2, strokeDasharray: "4,3" }),
      Plot.line(series, { x: "year", y: "value", stroke: col, strokeWidth: 2.5 }),
      Plot.dot(series.slice(-1), { x: "year", y: "value", fill: col, r: 3.5 }),
    ] }));
}
const ordinal = n => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");

/* ---------------------------------------------------------------- tabs, keys, resize */
let exploreReady = false;
function show(view) {
  document.querySelectorAll(".view").forEach(v => v.hidden = v.id !== view);
  document.querySelectorAll("nav.tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.view === view));
  if (view === "story") drawStory();
  if (view === "explore") {
    if (!exploreReady) { exploreReady = true; buildControls(); initWorldMap().then(() => select(state.iso)); }
    else { worldMap.invalidateSize(); updateExplore(); }
  }
  if (location.hash.slice(1) !== view) history.replaceState(null, "", "#" + view);
}
document.querySelectorAll("nav.tabs button").forEach(b => b.onclick = () => show(b.dataset.view));
show(["story", "explore", "method"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "story");

const stops = () => [...document.querySelectorAll("#story .intro, #story .step, #story .ps")];
document.addEventListener("keydown", e => {
  if (document.getElementById("story").hidden || ["SELECT", "INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  const s = stops(), cur = s.reduce((best, el, i) => Math.abs(el.getBoundingClientRect().top) < Math.abs(s[best].getBoundingClientRect().top) ? i : best, 0);
  if (["ArrowDown", "ArrowRight", "PageDown"].includes(e.key)) { e.preventDefault(); s[Math.min(cur + 1, s.length - 1)].scrollIntoView({ block: "start" }); }
  if (["ArrowUp", "ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); s[Math.max(cur - 1, 0)].scrollIntoView({ block: "start" }); }
});

let rt;
window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => {
  if (!document.getElementById("story").hidden) drawStory();
  if (!document.getElementById("explore").hidden && exploreReady) updateExplore();
}, 200); });
