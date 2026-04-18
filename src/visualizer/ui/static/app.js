"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  mixFile: null,
  style: null,
  palette: null,
  styles: [],
  palettes: [],
  renderJobId: null,
  indexJobId: null,
  libTracks: [],
};

// ---------- tabs ----------
$$(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.classList.remove("active"));
    $$(".tab-panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("#tab-" + t.dataset.tab).classList.add("active");
    if (t.dataset.tab === "library") refreshLibrary();
  });
});

// ---------- style + palette tiles ----------
async function loadStylesPalettes() {
  const [styles, palettes] = await Promise.all([
    fetch("/api/styles").then((r) => r.json()),
    fetch("/api/palettes").then((r) => r.json()),
  ]);
  state.styles = styles;
  state.palettes = palettes;
  renderStyleGrid();
  renderPaletteGrid();
}

function renderStyleGrid() {
  const grid = $("#styles-grid");
  grid.innerHTML = "";
  state.styles.forEach((s) => {
    const div = document.createElement("div");
    div.className = "tile";
    div.dataset.name = s.name;
    div.innerHTML = `
      <img class="preview" src="${s.preview}" alt="${s.name}" onerror="this.style.background='#222';this.removeAttribute('src');" />
      <div class="name">${s.name}</div>`;
    div.addEventListener("click", () => selectStyle(s.name));
    grid.appendChild(div);
  });
  if (state.styles.length) selectStyle(state.styles[0].name);
}

function selectStyle(name) {
  state.style = name;
  $$("#styles-grid .tile").forEach((t) =>
    t.classList.toggle("selected", t.dataset.name === name)
  );
}

function renderPaletteGrid() {
  const grid = $("#palettes-grid");
  grid.innerHTML = "";
  state.palettes.forEach((p) => {
    const div = document.createElement("div");
    div.className = "tile";
    div.dataset.name = p.name;
    const hasPreview = p.preview;
    div.innerHTML = `
      <img class="preview" src="${p.preview}" alt="${p.name}" onerror="this.outerHTML='<div class=&quot;swatch&quot; style=&quot;background:linear-gradient(180deg,${p.bg[0]},${p.bg[1]})&quot;></div>'" />
      <div class="name">${p.name}</div>`;
    div.addEventListener("click", () => selectPalette(p.name));
    grid.appendChild(div);
  });
  if (state.palettes.length) selectPalette(state.palettes[0].name);
}

function selectPalette(name) {
  state.palette = name;
  $$("#palettes-grid .tile").forEach((t) =>
    t.classList.toggle("selected", t.dataset.name === name)
  );
}

// ---------- mix file picker ----------
const dropZone = $("#drop-zone");
const fileInput = $("#mix-file");
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length) setMixFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) setMixFile(e.target.files[0]);
});

function setMixFile(f) {
  state.mixFile = f;
  $("#dropzone-text").textContent = f.name;
  $("#mix-meta").textContent = `${(f.size / 1e6).toFixed(1)} MB`;
  if (!$("#output-filename").value) {
    const stem = f.name.replace(/\.[^.]+$/, "");
    $("#output-filename").value = stem + ".mp4";
  }
}

// ---------- render submit ----------
$("#render-btn").addEventListener("click", async () => {
  $("#render-error").textContent = "";
  if (!state.mixFile) { $("#render-error").textContent = "Pick a mix file first."; return; }
  if (!state.style) { $("#render-error").textContent = "Pick a style."; return; }
  if (!state.palette) { $("#render-error").textContent = "Pick a palette."; return; }
  const outName = $("#output-filename").value.trim();
  if (!outName) { $("#render-error").textContent = "Set an output file name."; return; }

  const fd = new FormData();
  fd.append("mix", state.mixFile);
  fd.append("style", state.style);
  fd.append("palette", state.palette);
  fd.append("output_filename", outName);
  fd.append("artist", $("#artist").value);
  fd.append("mix_name", $("#mix-name").value);
  fd.append("title", $("#title").value);
  fd.append("auto_tracklist", $("#auto-tracklist").checked ? "true" : "false");
  fd.append("write_tracklist", $("#write-tracklist").checked ? "true" : "false");
  fd.append("chapters", $("#chapters").checked ? "true" : "false");

  $("#render-btn").disabled = true;

  try {
    const res = await fetch("/api/render", { method: "POST", body: fd });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || res.statusText);
    }
    const data = await res.json();
    state.renderJobId = data.job_id;
    showRenderProgress(data.output_path);
    streamJob(data.job_id, onRenderEvent);
  } catch (e) {
    $("#render-error").textContent = "Failed: " + e.message;
    $("#render-btn").disabled = false;
  }
});

function showRenderProgress(outputPath) {
  $("#render-progress").classList.remove("hidden");
  $("#rp-phase").textContent = "queued";
  $("#rp-eta").textContent = "";
  $("#rp-fill").style.width = "0%";
  $("#rp-message").textContent = "";
  $("#rp-log").textContent = "";
  $("#rp-done").classList.add("hidden");
  $("#rp-output").textContent = outputPath;
}

function onRenderEvent(ev) {
  $("#rp-phase").textContent = ev.phase;
  $("#rp-fill").style.width = (ev.progress * 100).toFixed(1) + "%";
  $("#rp-message").textContent = ev.message || "";
  $("#rp-eta").textContent = formatEta(ev.eta_sec);
  $("#rp-log").textContent = (ev.log || []).join("\n");
  $("#rp-log").scrollTop = $("#rp-log").scrollHeight;
  if (ev.status === "done") {
    $("#rp-fill").style.width = "100%";
    $("#rp-eta").textContent = "";
    $("#rp-done").classList.remove("hidden");
    $("#render-btn").disabled = false;
    $("#rp-output").textContent = ev.output_path || "";
    $("#rp-reveal").onclick = () => reveal(ev.output_path);
  } else if (ev.status === "error") {
    $("#rp-phase").textContent = "error";
    $("#rp-message").textContent = ev.error || ev.message || "render failed";
    $("#render-btn").disabled = false;
  }
}

function formatEta(sec) {
  if (sec === null || sec === undefined) return "";
  if (sec < 60) return `~${Math.round(sec)}s left`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec - m * 60);
  return `~${m}m ${s}s left`;
}

async function reveal(path) {
  if (!path) return;
  try {
    await fetch("/api/reveal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
  } catch (e) { console.error(e); }
}

// ---------- SSE ----------
function streamJob(jobId, onEvent) {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.onmessage = (msg) => {
    try {
      const ev = JSON.parse(msg.data);
      onEvent(ev);
      if (ev.status === "done" || ev.status === "error") es.close();
    } catch (e) { console.error("bad event", e); }
  };
  es.onerror = () => { es.close(); };
  return es;
}

// ---------- library ----------
async function refreshLibrary() {
  const [stats, tracks] = await Promise.all([
    fetch("/api/library/stats").then((r) => r.json()),
    fetch("/api/library/tracks").then((r) => r.json()),
  ]);
  $("#lib-tracks").textContent = stats.tracks.toLocaleString();
  $("#lib-hashes").textContent = stats.hashes.toLocaleString();
  $("#lib-size").textContent = formatBytes(stats.db_size_bytes);
  $("#lib-path").textContent = stats.db_path;
  state.libTracks = tracks;
  renderLibTable();
}

function renderLibTable() {
  const q = $("#lib-search").value.trim().toLowerCase();
  const rows = state.libTracks.filter((t) => {
    if (!q) return true;
    return (
      t.artist.toLowerCase().includes(q) ||
      t.title.toLowerCase().includes(q) ||
      t.path.toLowerCase().includes(q)
    );
  });
  const tbody = $("#lib-table");
  tbody.innerHTML = rows.map((t) => `
    <tr>
      <td>${escapeHtml(t.artist)}</td>
      <td>${escapeHtml(t.title)}</td>
      <td class="path">${escapeHtml(t.path)}</td>
    </tr>`).join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}

function formatBytes(n) {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 ? 1 : 0)} ${units[i]}`;
}

$("#lib-search").addEventListener("input", renderLibTable);

$("#lib-upload").addEventListener("change", async (e) => {
  if (!e.target.files.length) return;
  const fd = new FormData();
  for (const f of e.target.files) fd.append("files", f);
  const res = await fetch("/api/library/upload", { method: "POST", body: fd });
  if (!res.ok) { alert(await res.text()); return; }
  const data = await res.json();
  startIndexProgress(data.job_id);
  e.target.value = "";
});

$("#index-folder-btn").addEventListener("click", async () => {
  const folder = $("#index-folder-path").value.trim();
  if (!folder) return;
  const res = await fetch("/api/library/index-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder }),
  });
  if (!res.ok) { alert(await res.text()); return; }
  const data = await res.json();
  startIndexProgress(data.job_id);
});

$("#rebuild-btn").addEventListener("click", async () => {
  const folder = $("#rebuild-folder-path").value.trim();
  if (!folder) return;
  if (!confirm(`Wipe DB and rebuild from "${folder}"? Current tracks will be re-indexed.`)) return;
  const res = await fetch("/api/library/rebuild", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder }),
  });
  if (!res.ok) { alert(await res.text()); return; }
  const data = await res.json();
  startIndexProgress(data.job_id);
});

function startIndexProgress(jobId) {
  $("#index-progress").classList.remove("hidden");
  $("#ip-phase").textContent = "queued";
  $("#ip-fill").style.width = "0%";
  $("#ip-message").textContent = "";
  state.indexJobId = jobId;
  streamJob(jobId, onIndexEvent);
}

function onIndexEvent(ev) {
  $("#ip-phase").textContent = ev.phase;
  $("#ip-fill").style.width = (ev.progress * 100).toFixed(1) + "%";
  $("#ip-message").textContent = ev.message || "";
  $("#ip-eta").textContent = formatEta(ev.eta_sec);
  if (ev.status === "done" || ev.status === "error") {
    refreshLibrary();
  }
}

// ---------- boot ----------
loadStylesPalettes();
refreshLibrary();
