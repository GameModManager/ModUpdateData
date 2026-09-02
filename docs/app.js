const MANIFEST_URLS = [
  "../data/manifest.json",
  "https://raw.githubusercontent.com/GameModManager/ModUpdateData/main/data/manifest.json",
];

function shardUrl(file) {
  // file is "data/00000-00999.json"
  const rawBase = "https://raw.githubusercontent.com/GameModManager/ModUpdateData/main/";
  return rawBase + file;
}

function icon(game, status) {
  if (status === "deleted") return "\u26AB";
  if (game === "SE") return "\uD83D\uDFE2";
  return ({ compatible: "\uD83D\uDFE2", convertible: "\uD83D\uDD35", incompatible: "\uD83D\uDD34", "legacy-compatible": "\uD83D\uDFE2", new: "\uD83D\uDFE2", obsolete: "\uD83D\uDFE4", ported: "\uD83D\uDFE2", unknown: "\u26AA" })[status] || "\u26AA";
}

function el(name, cb) {
  const e = document.createElement(name);
  if (cb) cb.call(e, e);
  return e;
}

let allData = [];
let canonicalMods = [];
let filteredMods = [];
let currentPage = 1;
const PAGE_SIZE = 100; // configurable: mods per page
const canonicalIndexMap = new Map(); // id -> original index for stable sort reset
let currentQuery = "";
let sortInfo = { thIndex: -1, state: 0, asc: true }; // active sort for re-apply after filter
let showAll = false;

async function fetchJson(urls) {
  let lastErr;
  for (const u of urls) {
    try {
      const r = await fetch(u, { cache: "no-cache" });
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return { data: await r.json(), url: u };
    } catch (e) { lastErr = e; }
  }
  throw lastErr;
}

async function load() {
  let manifest, manifestUrl;
  try {
    const res = await fetchJson(MANIFEST_URLS);
    manifest = res.data; manifestUrl = res.url;
  } catch (e) {
    document.querySelector("h1").innerText = "Failed to load manifest: " + e;
    throw e;
  }
  // Fetch shards - try relative first, fallback to raw
  const baseIsRaw = manifestUrl.includes("raw.githubusercontent");
  const shardFetches = manifest.shards.map(s => {
    const url = baseIsRaw ? shardUrl(s.file) : "../" + s.file;
    const fallback = shardUrl(s.file);
    const urls = url === fallback ? [url] : [url, fallback];
    return fetchJson(urls).then(r => r.data).catch(e => { console.warn("shard fetch failed", s.file, e); return []; });
  });
  const shardArrays = await Promise.all(shardFetches);
  allData = shardArrays.flat();
  // Sort like tasairis: by sortable
  allData.sort((a, b) => (a.sortable || a.title || "").localeCompare(b.sortable || b.title || ""));
  canonicalMods = allData.filter(m => m.id === m.canonical);
  canonicalMods.forEach((m, i) => canonicalIndexMap.set(m.id, i));
  filteredMods = canonicalMods.slice();

  document.getElementById("meta-text").textContent =
    `${manifest.generated_at.slice(0, 10)} - ${manifest.total_mods} mods in ${manifest.total_shards} shards - source ${manifest.source || ""}`;

  ensureTbody();
  renderPage(1);
  delete document.body.dataset.loading;
  applySortable();
  setupFilter();
  setupPagination();
  setupPopup();
}

function ensureTbody() {
  let tbody = document.querySelector("#table tbody");
  if (!tbody) {
    tbody = el("TBODY");
    document.getElementById("table").appendChild(tbody);
  }
  return tbody;
}

function createRow(m) {
  const others = allData.filter(o => o.canonical === m.canonical && o.id !== m.id);
  const tr = el("TR");
  tr.id = String(m.id);
  tr.dataset.index = String(canonicalIndexMap.get(m.id) ?? 0);
  tr.appendChild(el("TD", td => td.textContent = String(m.id)));
  tr.appendChild(el("TD", td => {
    if (m.status !== "deleted" && m.game === "SE" && !others.find(o => o.game === "LE")) {
      const em = el("EM"); em.textContent = "(made for SE)"; td.appendChild(em);
    } else td.textContent = m.status;
  }));
  tr.appendChild(el("TD", td => td.textContent = m.category));
  tr.appendChild(el("TD", td => {
    td.dataset.sort = m.sortable || m.title || "";
    td.append(icon(m.game, m.status) + " ");
    if (others.length) td.append(m.game + ": ");
    if (m.href) {
      const a = el("A"); a.href = "https://www.loverslab.com/files/file/" + m.href + "/"; a.textContent = m.title; a.target = "_blank"; td.appendChild(a);
    } else td.append(m.title);
    if (m.obsolete_successor || m.obsolete_alternative || m.obsolete_reason) td.append(" \u2620\uFE0F");
    if (m.note) td.append(" \uD83D\uDCDD");
    if (m.other_link) td.append(" \uD83D\uDD17");
    if (m.automated) { const b = el("SPAN"); b.className = "badge"; b.textContent = "automated"; b.style.background = "#fde8e8"; td.append(" "); td.appendChild(b); }
    for (const o of others) {
      td.appendChild(el("BR"));
      td.append(icon(o.game, o.status) + " " + o.game + ": ");
      if (o.href) { const a = el("A"); a.href = "https://www.loverslab.com/files/file/" + o.href; a.textContent = o.title; a.target = "_blank"; td.appendChild(a); }
      else td.append(o.title);
    }
  }));
  tr.appendChild(el("TD", td => { td.dataset.sort = m.updated; td.textContent = new Date(m.updated).toDateString(); }));
  return tr;
}

function getPageCount() {
  if (showAll) return 1;
  return Math.max(1, Math.ceil(filteredMods.length / PAGE_SIZE));
}

function updateStats() {
  const total = canonicalMods.length;
  const shown = filteredMods.length;
  if (showAll) {
    if (shown === 0) {
      document.getElementById("stats").textContent = `0 shown / ${total} total (all on one page)`;
    } else if (shown === total && currentQuery === "") {
      document.getElementById("stats").textContent = `${total} canonical mods shown (all on one page)`;
    } else {
      document.getElementById("stats").textContent = `${shown} shown / ${total} total (all on one page)`;
    }
    return;
  }
  const start = shown === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const end = Math.min(currentPage * PAGE_SIZE, shown);
  const range = shown === 0 ? "0" : `${start}-${end}`;
  // keep existing expectation: "X shown / Y total" plus page range for pagination context
  if (shown === total && currentQuery === "") {
    document.getElementById("stats").textContent = `${total} canonical mods shown - page ${currentPage} of ${getPageCount()} (${range})`;
  } else {
    document.getElementById("stats").textContent = `${shown} shown / ${total} total - page ${currentPage} of ${getPageCount()} (${range})`;
  }
}

function updatePaginationControls() {
  const pageCount = getPageCount();
  const prev = document.getElementById("prev-page");
  const next = document.getElementById("next-page");
  const info = document.getElementById("page-info");
  if (showAll) {
    if (prev) { prev.disabled = true; prev.style.display = "none"; }
    if (next) { next.disabled = true; next.style.display = "none"; }
    if (info) {
      if (filteredMods.length === 0) info.textContent = "No results";
      else info.textContent = "All on one page";
    }
    return;
  } else {
    if (prev) prev.style.display = "";
    if (next) next.style.display = "";
  }
  if (prev) prev.disabled = currentPage <= 1;
  if (next) next.disabled = currentPage >= pageCount || filteredMods.length === 0;
  if (info) {
    if (filteredMods.length === 0) info.textContent = "No results - Page 0 of 0";
    else info.textContent = `Page ${currentPage} of ${pageCount}`;
  }
}

function renderPage(page) {
  const tbody = ensureTbody();
  if (showAll) {
    currentPage = 1;
    const frag = document.createDocumentFragment();
    for (let i = 0; i < filteredMods.length; i++) {
      frag.appendChild(createRow(filteredMods[i]));
    }
    tbody.replaceChildren(frag);
    updateStats();
    updatePaginationControls();
    return;
  }
  const pageCount = getPageCount();
  if (page < 1) page = 1;
  if (page > pageCount) page = pageCount;
  currentPage = page;
  // efficient rendering: build DocumentFragment for current page only
  const frag = document.createDocumentFragment();
  const start = (currentPage - 1) * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, filteredMods.length);
  for (let i = start; i < end; i++) {
    frag.appendChild(createRow(filteredMods[i]));
  }
  // replace tbody contents in one DOM operation
  tbody.replaceChildren(frag);
  updateStats();
  updatePaginationControls();
}

function setupPagination() {
  document.getElementById("prev-page").addEventListener("click", () => {
    if (currentPage > 1) renderPage(currentPage - 1);
  });
  document.getElementById("next-page").addEventListener("click", () => {
    if (currentPage < getPageCount()) renderPage(currentPage + 1);
  });
  const showAllEl = document.getElementById("show-all");
  if (showAllEl) {
    showAllEl.addEventListener("change", () => {
      showAll = showAllEl.checked;
      renderPage(1);
    });
  }
}

function applySortable() {
  const headers = [...document.querySelectorAll("#table thead th")];
  const state = new Map();
  let sortingBy = null;
  headers.forEach((th, i) => {
    if (!th.dataset.hasOwnProperty("sortable")) return;
    const label = th.textContent.trim();
    th.textContent = "\uD83D\uDD03 " + label;
    const iconEl = el("SPAN");
    iconEl.textContent = "";
    th.appendChild(iconEl);
    state.set(th, 0);
    const dir = th.dataset.hasOwnProperty("sortinv") ? -1 : 1;
    th.addEventListener("click", () => {
      if (sortingBy && sortingBy !== th) { state.set(sortingBy, 0); sortingBy.querySelector("span").textContent = ""; }
      sortingBy = th;
      const s = (3 + state.get(th) + dir) % 3;
      state.set(th, s);
      if (s === 0) {
        iconEl.textContent = "";
        sortInfo = { thIndex: i, state: 0, asc: true };
        // reset to original order (stable by canonicalIndexMap) but keep current filter
        filteredMods.sort((a, b) => (canonicalIndexMap.get(a.id) ?? 0) - (canonicalIndexMap.get(b.id) ?? 0));
      } else {
        const asc = s === 1;
        iconEl.textContent = asc ? " \u2B06\uFE0F" : " \u2B07\uFE0F";
        sortInfo = { thIndex: i, state: s, asc };
        // column 3 = Mod (sortable), column 4 = Last Updated (updated)
        const isModCol = i === 3;
        filteredMods.sort((a, b) => {
          const av = isModCol ? (a.sortable || a.title || "") : (a.updated || "");
          const bv = isModCol ? (b.sortable || b.title || "") : (b.updated || "");
          const cmp = av.localeCompare(bv);
          return asc ? cmp : -cmp;
        });
      }
      renderPage(1);
    });
  });
}

function matchesFilter(mod, q) {
  // filter on data array by title, id, category, status (case-insensitive)
  const hay = `${mod.title || ""} ${mod.id} ${mod.category || ""} ${mod.status || ""}`.toLowerCase();
  return hay.includes(q);
}

function applyFilter(q) {
  currentQuery = q;
  if (!q) {
    filteredMods = canonicalMods.slice();
  } else {
    filteredMods = canonicalMods.filter(m => matchesFilter(m, q));
  }
  // re-apply current sort if header is in sorted state
  if (sortInfo.state !== 0) {
    const isModCol = sortInfo.thIndex === 3;
    filteredMods.sort((a, b) => {
      const av = isModCol ? (a.sortable || a.title || "") : (a.updated || "");
      const bv = isModCol ? (b.sortable || b.title || "") : (b.updated || "");
      const cmp = av.localeCompare(bv);
      return sortInfo.asc ? cmp : -cmp;
    });
  }
  renderPage(1);
}

function setupFilter() {
  const inp = document.getElementById("search");
  let debounceTimer = null;
  const DEBOUNCE_MS = 300;
  inp.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const q = inp.value.trim().toLowerCase();
      applyFilter(q);
    }, DEBOUNCE_MS);
  });
}

function setupPopup() {
  const popup = document.getElementById("details-popup");
  popup.addEventListener("click", e => { if (e.target === popup) popup.classList.remove("visible"); });
  document.getElementById("details-popup-background").addEventListener("click", () => popup.classList.remove("visible"));
  document.getElementById("table").addEventListener("click", e => {
    if (e.target.closest("a[href]")) return;
    const id = e.target.closest("tr[id]")?.id;
    if (!id) return;
    const relevant = allData.filter(m => String(m.canonical) === String(id));
    if (!relevant.length) return;
    relevant.sort((a, b) => String(a.id) === String(id) ? -1 : String(b.id) === String(id) ? 1 : (a.sortable || "").localeCompare(b.sortable || ""));
    while (popup.firstChild) popup.firstChild.remove();
    const tpl = document.getElementById("details-popup-template");
    relevant.forEach(mod => {
      const details = tpl.cloneNode(true);
      details.removeAttribute("id"); details.style.display = "block";
      details.querySelectorAll("[data-template]").forEach(elem => {
        const v = (function (mod) { return eval(this.dataset.template); }).call(elem, mod);
        if (v !== undefined && v !== null) elem.textContent = String(v);
      });
      details.querySelectorAll("ul.notes").forEach(ul => {
        const add = (label, arr) => { if (!arr) return; const li = el("LI"); li.textContent = label + ": " + arr.join("; "); ul.appendChild(li); };
        add("Obsolete reason", mod.obsolete_reason);
        add("Successor", mod.obsolete_successor);
        add("Alternative", mod.obsolete_alternative);
        if (mod.note) mod.note.forEach(n => { const li = el("LI"); li.textContent = n; ul.appendChild(li); });
        if (mod.other_link) mod.other_link.forEach(l => { const li = el("LI"); const a = el("A"); a.href = l.href; a.textContent = l.text || l.href; a.target = "_blank"; li.appendChild(a); ul.appendChild(li); });
        if (!ul.children.length) ul.remove();
      });
      popup.appendChild(details);
    });
    popup.classList.add("visible");
  });
}

load().catch(e => { console.error(e); document.body.innerHTML += "<pre>" + String(e) + "</pre>"; });
