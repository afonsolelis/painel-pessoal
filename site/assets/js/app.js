const { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } = window.APP_CONFIG;
const REST = `${SUPABASE_URL}/rest/v1`;
const NEWS_LIMIT = 300;

const state = { articles: [], lang: "all", source: "all", query: "" };
const $ = (sel) => document.querySelector(sel);

const storage = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* modo privado */ } },
};

async function api(path) {
  const res = await fetch(`${REST}/${path}`, {
    headers: { apikey: SUPABASE_PUBLISHABLE_KEY, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} em ${path.split("?")[0]}`);
  return res.json();
}

const safeUrl = (u) => {
  try { const url = new URL(u); return ["http:", "https:"].includes(url.protocol) ? url.href : null; }
  catch { return null; }
};

const rtf = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });
function relativeTime(iso) {
  const diff = (new Date(iso) - Date.now()) / 1000;
  const units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit);
  }
  return "agora";
}
const dateFmt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" });
const normalize = (s) => (s || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

/* ---------------------------------- Notícias --------------------------------- */

function filtered() {
  const q = normalize(state.query);
  return state.articles.filter((a) =>
    (state.lang === "all" || a.language === state.lang) &&
    (state.source === "all" || a.source_slug === state.source) &&
    (!q || normalize(`${a.title} ${a.summary || ""}`).includes(q)));
}

function renderCard(a, tpl) {
  const node = tpl.content.cloneNode(true);
  const link = node.querySelector(".card__link");
  link.href = safeUrl(a.url) ?? "#";
  link.setAttribute("aria-label", `${a.title} — ${a.source_name} (abre em nova aba)`);
  const img = node.querySelector("img");
  const src = safeUrl(a.image_url);
  if (src) {
    img.src = src;
    img.addEventListener("error", () => img.parentElement.classList.add("card__media--empty"), { once: true });
  } else {
    img.parentElement.classList.add("card__media--empty");
    img.remove();
  }
  node.querySelector(".card__source").textContent = a.source_name;
  node.querySelector(".card__lang").textContent = a.language === "pt" ? "PT" : "EN";
  const time = node.querySelector(".card__time");
  time.dateTime = a.published_at;
  time.textContent = relativeTime(a.published_at);
  time.title = dateFmt.format(new Date(a.published_at));
  node.querySelector(".card__title").textContent = a.title;
  const summary = node.querySelector(".card__summary");
  if (a.summary) summary.textContent = a.summary; else summary.remove();
  node.querySelector(".card").lang = a.language === "pt" ? "pt-BR" : "en";
  return node;
}

function renderNews() {
  const grid = $("#news-grid");
  const tpl = $("#card-template");
  const items = filtered();
  const frag = document.createDocumentFragment();
  items.forEach((a) => frag.appendChild(renderCard(a, tpl)));
  grid.replaceChildren(frag);
  grid.setAttribute("aria-busy", "false");
  $("#status").textContent = items.length
    ? `${items.length} manchete${items.length > 1 ? "s" : ""}`
    : "Nenhuma manchete encontrada para esse filtro.";
}

function renderSources() {
  const bySlug = new Map();
  for (const a of state.articles) {
    if (state.lang !== "all" && a.language !== state.lang) continue;
    const s = bySlug.get(a.source_slug) || { name: a.source_name, count: 0 };
    s.count += 1;
    bySlug.set(a.source_slug, s);
  }
  if (state.source !== "all" && !bySlug.has(state.source)) state.source = "all";

  const make = (slug, label) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.dataset.source = slug;
    b.setAttribute("aria-pressed", String(state.source === slug));
    b.textContent = label;
    return b;
  };
  const chips = [make("all", "Todas as fontes")];
  [...bySlug.entries()]
    .sort((a, b) => a[1].name.localeCompare(b[1].name))
    .forEach(([slug, s]) => chips.push(make(slug, `${s.name} · ${s.count}`)));
  $("#sources").replaceChildren(...chips);
}

function setLang(lang) {
  state.lang = lang;
  storage.set("f1.lang", lang);
  document.querySelectorAll("[data-lang]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  renderSources();
  renderNews();
}

/* ---------------------------------- Temporada -------------------------------- */

function renderNextRace(race) {
  const body = $("#next-race .panel__body");
  if (!race) { body.textContent = "Temporada encerrada. Até o próximo ano!"; return; }
  const start = new Date(race.race_start);
  const title = document.createElement("p");
  title.className = "race__name";
  title.textContent = race.race_name;
  const where = document.createElement("p");
  where.className = "race__where";
  where.textContent = `Etapa ${race.round} · ${race.circuit_name} — ${race.locality ?? ""}, ${race.country ?? ""}`;
  const when = document.createElement("p");
  when.className = "race__when";
  when.textContent = `Largada: ${dateFmt.format(start)}`;
  const countdown = document.createElement("p");
  countdown.className = "race__countdown";
  countdown.setAttribute("aria-label", "Contagem regressiva");
  const extra = [];
  if (race.qualifying_start) extra.push(`Classificação: ${dateFmt.format(new Date(race.qualifying_start))}`);
  if (race.sprint_start) extra.push(`Sprint: ${dateFmt.format(new Date(race.sprint_start))}`);
  const sessions = document.createElement("p");
  sessions.className = "race__where";
  sessions.textContent = extra.join(" · ");

  const tick = () => {
    const s = Math.max(0, Math.floor((start - Date.now()) / 1000));
    if (s === 0) { countdown.textContent = "Corrida em andamento"; return; }
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    countdown.textContent = `${d}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m`;
  };
  tick();
  setInterval(tick, 30_000);
  body.replaceChildren(title, where, countdown, when, ...(extra.length ? [sessions] : []));
}

function renderStandings(el, rows, label) {
  if (!rows.length) { el.replaceChildren(Object.assign(document.createElement("li"), { textContent: "Sem dados." })); return; }
  const items = rows.map((r) => {
    const li = document.createElement("li");
    const pos = document.createElement("span"); pos.className = "standings__pos"; pos.textContent = r.position ?? "–";
    const name = document.createElement("span"); name.className = "standings__name";
    const strong = document.createElement("strong"); strong.textContent = label(r).main;
    const small = document.createElement("small"); small.textContent = label(r).sub;
    name.append(strong, small);
    const pts = document.createElement("span"); pts.className = "standings__pts";
    pts.textContent = `${Number(r.points)} pts`;
    li.append(pos, name, pts);
    return li;
  });
  el.replaceChildren(...items);
}

const latestSeason = (rows) => rows.filter((r) => r.season === rows[0]?.season);

/* ------------------------------------ Boot ----------------------------------- */

async function loadNews() {
  try {
    state.articles = await api(
      `f1_news_feed?select=id,title,summary,url,image_url,language,published_at,collected_at,source_slug,source_name` +
      `&order=published_at.desc&limit=${NEWS_LIMIT}`);
    const last = state.articles.reduce((m, a) => (a.collected_at > m ? a.collected_at : m), "");
    $("#updated").textContent = last ? `Atualizado ${relativeTime(last)}` : "Sem coletas ainda";
    renderSources();
    renderNews();
  } catch (err) {
    console.error(err);
    $("#news-grid").setAttribute("aria-busy", "false");
    $("#news-grid").replaceChildren();
    $("#status").textContent = "Não foi possível carregar as manchetes. Tente novamente mais tarde.";
    $("#updated").textContent = "Offline";
  }
}

async function loadSeason() {
  const since = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
  const [races, drivers, teams] = await Promise.allSettled([
    api(`f1_races?select=*&race_start=gte.${encodeURIComponent(since)}&order=race_start.asc&limit=1`),
    api("f1_driver_standings?select=*&order=season.desc,position.asc.nullslast&limit=40"),
    api("f1_constructor_standings?select=*&order=season.desc,position.asc.nullslast&limit=20"),
  ]);
  if (races.status === "fulfilled") renderNextRace(races.value[0]);
  else $("#next-race .panel__body").textContent = "Indisponível.";
  renderStandings($("#drivers"), drivers.status === "fulfilled" ? latestSeason(drivers.value).slice(0, 10) : [],
    (r) => ({ main: `${r.given_name} ${r.family_name}`, sub: r.constructor_name ?? "" }));
  renderStandings($("#teams"), teams.status === "fulfilled" ? latestSeason(teams.value) : [],
    (r) => ({ main: r.name, sub: `${r.wins} vitória${r.wins === 1 ? "" : "s"}` }));
}

function bindEvents() {
  document.querySelectorAll("[data-lang]").forEach((b) =>
    b.addEventListener("click", () => setLang(b.dataset.lang)));
  $("#sources").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-source]");
    if (!chip) return;
    state.source = chip.dataset.source;
    renderSources();
    renderNews();
  });
  let t;
  $("#search").addEventListener("input", (e) => {
    clearTimeout(t);
    t = setTimeout(() => { state.query = e.target.value.trim(); renderNews(); }, 150);
  });
}

function showSkeletons() {
  const grid = $("#news-grid");
  grid.replaceChildren(...Array.from({ length: 6 }, () =>
    Object.assign(document.createElement("div"), { className: "card skeleton skeleton--card" })));
}

const savedLang = storage.get("f1.lang");
if (["all", "pt", "en"].includes(savedLang)) state.lang = savedLang;
document.querySelectorAll("[data-lang]").forEach((b) =>
  b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
bindEvents();
showSkeletons();
loadNews();
loadSeason();
