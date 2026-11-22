const state = {
  meetings: [],
  id: null,
  data: null,
  tab: "summary",
  showArchived: false,
  sort: localStorage.getItem("dikteSort") || "created_desc",
  query: "",
};

const $ = (sel) => document.querySelector(sel);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const hhmmss = (sec) => {
  sec = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(sec / 3600)).padStart(2, "0");
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
};
const toSec = (t) => {
  const p = String(t || "0:0:0").split(":").map(Number);
  return (p[0] || 0) * 3600 + (p[1] || 0) * 60 + (p[2] || 0);
};

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/* ---------------- sidebar ---------------- */
/* ---------------- drawer mobile ---------------- */
function openDrawer() {
  document.querySelector(".sidebar")?.classList.add("open");
  $("#backdrop").hidden = false;
}
function closeDrawer() {
  document.querySelector(".sidebar")?.classList.remove("open");
  $("#backdrop").hidden = true;
}
$("#drawerBtn").onclick = () => {
  const el = document.querySelector(".sidebar");
  if (el.classList.contains("open")) closeDrawer(); else openDrawer();
};
$("#backdrop").onclick = closeDrawer;
$("#mSettingsBtn").onclick = () => { closeDrawer(); openSettings(); };

/* ---------------- pengaturan ---------------- */
let settingsCache = null;

async function openSettings() {
  const st = await api("/api/settings");
  settingsCache = st;
  const g = $("#setGeminiKey");
  g.value = "";
  g.placeholder = st.gemini_api_key.configured
    ? `tersimpan ••••${st.gemini_api_key.tail}` : "belum diisi";
  const jt = $("#setJiraToken");
  jt.value = "";
  jt.placeholder = st.jira_api_token.configured
    ? `tersimpan ••••${st.jira_api_token.tail}` : "belum diisi";
  $("#setGeminiModel").value = st.gemini_model || "gemini-3.6-flash";
  $("#setJiraBase").value = st.jira_base_url || "";
  $("#setJiraEmail").value = st.jira_email || "";
  $("#setJiraProject").value = st.jira_project_key || "";
  $("#setJiraEpic").value = st.jira_epic_field || "";
  $("#setJiraPriority").checked = !!st.jira_set_priority;
  $("#geminiStatus").textContent = "";
  $("#jiraStatus").textContent = "";
  $("#saveStatus").textContent = "";
  $("#settingsModal").hidden = false;
}

function closeSettings() {
  $("#settingsModal").hidden = true;
}

function settingsPayload() {
  return {
    gemini_api_key: $("#setGeminiKey").value.trim(),
    gemini_model: $("#setGeminiModel").value,
    jira_base_url: $("#setJiraBase").value.trim(),
    jira_email: $("#setJiraEmail").value.trim(),
    jira_api_token: $("#setJiraToken").value.trim(),
    jira_project_key: $("#setJiraProject").value.trim().toUpperCase(),
    jira_epic_field: $("#setJiraEpic").value.trim(),
    jira_set_priority: $("#setJiraPriority").checked,
  };
}

async function saveSettings() {
  const st = $("#saveStatus");
  try {
    const r = await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settingsPayload()),
    });
    settingsCache = r.settings;
    $("#setGeminiKey").value = "";
    $("#setJiraToken").value = "";
    const g = settingsCache.gemini_api_key;
    $("#setGeminiKey").placeholder = g.configured ? `tersimpan ••••${g.tail}` : "belum diisi";
    const j = settingsCache.jira_api_token;
    $("#setJiraToken").placeholder = j.configured ? `tersimpan ••••${j.tail}` : "belum diisi";
    st.textContent = "tersimpan";
    st.className = "status ok";
  } catch (e) {
    st.textContent = "gagal: " + e.message;
    st.className = "status err";
  }
}

async function testConnection(kind) {
  const el = kind === "gemini" ? $("#geminiStatus") : $("#jiraStatus");
  el.textContent = "menguji…";
  el.className = "status";
  try {
    const r = await api(`/api/settings/test/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settingsPayload()),
    });
    el.textContent = r.message || (r.ok ? "ok" : "gagal");
    el.className = "status " + (r.ok ? "ok" : "err");
  } catch (e) {
    el.textContent = "gagal: " + e.message;
    el.className = "status err";
  }
}

async function clearCredentials() {
  if (!confirm("Hapus API key Gemini dan token Jira yang tersimpan?")) return;
  await api("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clear_keys: ["gemini_api_key", "jira_api_token"] }),
  });
  await openSettings();
  $("#saveStatus").textContent = "kredensial dihapus";
  $("#saveStatus").className = "status ok";
}

$("#settingsBtn").onclick = openSettings;
$("#settingsClose").onclick = closeSettings;
$("#saveSettings").onclick = saveSettings;
$("#testGemini").onclick = () => testConnection("gemini");
$("#testJira").onclick = () => testConnection("jira");
$("#clearKeys").onclick = clearCredentials;
$("#settingsModal").addEventListener("click", (ev) => {
  if (ev.target.id === "settingsModal") closeSettings();
});

/* ---------------- proses rekaman baru ---------------- */
const pollers = new Map();

function renderJob(job) {
  const el = document.getElementById(`job-${job.id}`) || document.createElement("div");
  el.id = `job-${job.id}`;
  const name = job.message && job.state === "running" ? job.message : "";
  el.className = `job ${job.state === "error" ? "error" : job.state === "done" ? "done" : ""}`;
  const cancellable = job.state === "running" || job.state === "queued";
  el.innerHTML = `
    <div class="name">${esc(job.filename || job.id)}${cancellable ? ` <button class="x" data-cancel="${esc(job.id)}" title="Batalkan">×</button>` : ""}</div>
    <div class="step">${esc(job.state === "error" ? job.error || "gagal" : job.step || "menunggu")}${name ? " · " + esc(name) : ""}</div>
    <div class="bar"><i style="width:${Math.min(100, job.progress || 0)}%"></i></div>`;
  if (!el.parentNode) $("#jobs").prepend(el);
}

function pollJob(jobId) {
  if (pollers.has(jobId)) return;
  const tick = async () => {
    try {
      const job = await api(`/api/job/${jobId}`);
      renderJob(job);
      if (job.state === "done") {
        clearInterval(pollers.get(jobId));
        pollers.delete(jobId);
        await loadMeetings();
        if (job.meeting_id) openMeeting(job.meeting_id);
        setTimeout(() => document.getElementById(`job-${jobId}`)?.remove(), 8000);
      } else if (job.state === "error" || job.state === "cancelled") {
        clearInterval(pollers.get(jobId));
        pollers.delete(jobId);
      }
    } catch (e) {
      clearInterval(pollers.get(jobId));
      pollers.delete(jobId);
    }
  };
  tick();
  pollers.set(jobId, setInterval(tick, 2000));
}

async function loadJobs() {
  try {
    const jobs = await api("/api/jobs");
    jobs.filter((j) => j.state === "running" || j.state === "queued").forEach((j) => {
      j.filename = j.filename || "rekaman";
      renderJob(j);
      pollJob(j.id);
    });
  } catch (e) { /* diamkan */ }
}

function uploadFile(file) {
  const jobId = "upload-" + Date.now();
  renderJob({ id: jobId, filename: file.name, state: "running", step: "mengunggah", progress: 1 });
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  xhr.upload.onprogress = (ev) => {
    if (ev.lengthComputable) renderJob({ id: jobId, filename: file.name, state: "running", step: "mengunggah", progress: Math.round((ev.loaded / ev.total) * 100) });
  };
  xhr.onload = async () => {
    if (xhr.status !== 200) {
      renderJob({ id: jobId, filename: file.name, state: "error", error: `upload gagal (${xhr.status})`, progress: 100 });
      return;
    }
    const info = JSON.parse(xhr.responseText);
    renderJob({ id: jobId, filename: file.name, state: "running", step: "memulai pipeline", progress: 100 });
    const r = await api("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: info.path }),
    });
    document.getElementById(`job-${jobId}`)?.remove();
    const job = { id: r.job, filename: file.name, state: "running", step: "antre", progress: 0 };
    renderJob(job);
    pollJob(r.job);
  };
  xhr.onerror = () => renderJob({ id: jobId, filename: file.name, state: "error", error: "koneksi terputus", progress: 100 });
  xhr.send(file);
}

$("#pickBtn").onclick = () => $("#fileInput").click();
$("#fileInput").onchange = (ev) => {
  const f = ev.target.files?.[0];
  if (f) uploadFile(f);
  ev.target.value = "";
};

async function loadMeetings() {
  state.meetings = await api("/api/meetings");
  loadJobs();
  renderMeetings();
  const target =
    state.meetings.find((m) => m.id === state.id) ||
    state.meetings.find((m) => !m.archived);
  if (target) openMeeting(target.id);
}

function renderMeetings() {
  const box = $("#meetings");
  if (!state.meetings.length) {
    box.innerHTML = '<div class="empty">Belum ada rapat.<br>Jalankan pipeline dulu.</div>';
    return;
  }
  const q = (state.query || "").toLowerCase();
  const match = (m) =>
    !q ||
    (m.title || "").toLowerCase().includes(q) ||
    (m.date || "").toLowerCase().includes(q);
  const shown = sortMeetings(
    state.meetings.filter((m) => (state.showArchived || !m.archived) && match(m))
  );
  const archivedCount = state.meetings.filter((m) => m.archived).length;

  if (!shown.length) {
    box.innerHTML = `<div class="empty">Tidak ada rapat yang cocok dengan “${esc(state.query)}”.</div>` +
      (archivedCount
        ? `<button class="archive-toggle" id="toggleArchive">${
            state.showArchived ? "Sembunyikan arsip" : "Tampilkan arsip"
          } (${archivedCount})</button>`
        : "");
    const t0 = $("#toggleArchive");
    if (t0)
      t0.onclick = () => {
        state.showArchived = !state.showArchived;
        renderMeetings();
      };
    return;
  }

  box.innerHTML =
    shown
      .map(
        (m) => `
      <div class="meeting-row">
        <button class="meeting-item ${m.id === state.id ? "active" : ""}" data-id="${esc(m.id)}">
          <span class="t">${esc(m.title)}${m.archived ? ' <span class="badge">arsip</span>' : ""}</span>
          <span class="m">${esc(m.date)} · ${Math.round(m.duration_min)} mnt · ${m.counts.decisions} keputusan · ${m.counts.stories} story</span>
        </button>
        <button class="more" data-more="${esc(m.id)}" title="Aksi">⋯</button>
      </div>`
      )
      .join("") +
    (archivedCount
      ? `<button class="archive-toggle" id="toggleArchive">${
          state.showArchived ? "Sembunyikan arsip" : "Tampilkan arsip"
        } (${archivedCount})</button>`
      : "");

  box.querySelectorAll(".meeting-item").forEach((el) => {
    el.onclick = () => openMeeting(el.dataset.id);
  });
  box.querySelectorAll(".more").forEach((el) => {
    el.onclick = (ev) => {
      ev.stopPropagation();
      openCtx(el.dataset.more, ev.currentTarget);
    };
  });
  const t = $("#toggleArchive");
  if (t)
    t.onclick = () => {
      state.showArchived = !state.showArchived;
      renderMeetings();
    };
}

const SORTS = [
  ["created_desc", "Terbaru dibuat"],
  ["created_asc", "Terlama dibuat"],
  ["meeting_desc", "Tanggal rapat terbaru"],
  ["meeting_asc", "Tanggal rapat terlama"],
  ["duration_desc", "Durasi terpanjang"],
  ["title_asc", "Judul A–Z"],
];

function sortMeetings(list) {
  const val = (m) => (m.date && m.date.length >= 10 ? m.date : "");
  const cmp = {
    created_desc: (a, b) => (b.created_at || 0) - (a.created_at || 0),
    created_asc: (a, b) => (a.created_at || 0) - (b.created_at || 0),
    meeting_desc: (a, b) =>
      (val(b) || String(b.created_at || "")).localeCompare(val(a) || String(a.created_at || "")),
    meeting_asc: (a, b) =>
      (val(a) || String(a.created_at || "")).localeCompare(val(b) || String(b.created_at || "")),
    duration_desc: (a, b) => (b.duration_min || 0) - (a.duration_min || 0),
    title_asc: (a, b) => (a.title || "").localeCompare(b.title || "", "id"),
  }[state.sort] || ((a, b) => (b.created_at || 0) - (a.created_at || 0));

  return list.slice().sort((a, b) => (a.archived === b.archived ? cmp(a, b) : a.archived ? 1 : -1));
}

/* ---------------- menu aksi rapat ---------------- */
let ctxTarget = null;

function positionMenu(menu, anchor) {
  const r = anchor.getBoundingClientRect();
  menu.hidden = false;
  const w = menu.offsetWidth;
  const h = menu.offsetHeight;
  menu.style.left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)) + "px";
  menu.style.top = Math.max(8, Math.min(r.bottom + 4, window.innerHeight - h - 8)) + "px";
}

function openCtx(id, anchor) {
  const m = state.meetings.find((x) => x.id === id);
  if (!m) return;
  ctxTarget = id;
  const menu = $("#ctxMenu");
  menu.querySelector('[data-act="archive"]').textContent = m.archived ? "Pulihkan" : "Arsipkan";
  positionMenu(menu, anchor);
}

function openSortMenu(anchor) {
  const menu = $("#sortMenu");
  menu.innerHTML = SORTS.map(
    ([key, label]) =>
      `<button data-sort="${key}" class="${state.sort === key ? "checked" : ""}">` +
      `<span class="tick">${state.sort === key ? "✓" : ""}</span>${label}</button>`
  ).join("");
  positionMenu(menu, anchor);
}

function closeCtx() {
  $("#ctxMenu").hidden = true;
  ctxTarget = null;
}

async function archiveMeeting(id, archived) {
  await api("/api/archive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, archived }),
  });
  await loadMeetings();
}

async function deleteMeeting(id) {
  const m = state.meetings.find((x) => x.id === id);
  const nama = m ? m.title : id;
  const ok = confirm(
    `Hapus permanen "${nama}"?\n\nTranskrip, dokumen, dan audio akan dihapus dan tidak bisa dikembalikan.`
  );
  if (!ok) return;
  await api("/api/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  if (state.id === id) state.id = null;
  await loadMeetings();
}

$("#ctxMenu").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button[data-act]");
  if (!btn) return;
  const id = ctxTarget;
  const act = btn.dataset.act;
  closeCtx();
  if (!id) return;
  const m = state.meetings.find((x) => x.id === id);
  if (act === "archive") await archiveMeeting(id, !(m && m.archived));
  if (act === "delete") await deleteMeeting(id);
});

document.addEventListener("click", (ev) => {
  if (!ev.target.closest("#ctxMenu") && !ev.target.closest(".more")) closeCtx();
  if (!ev.target.closest("#sortMenu") && !ev.target.closest("#sortBtn")) {
    $("#sortMenu").hidden = true;
    $("#sortBtn")?.classList.remove("active");
  }
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    closeCtx();
    $("#sortMenu").hidden = true;
    $("#sortBtn")?.classList.remove("active");
  }
});
window.addEventListener("resize", () => {
  closeCtx();
  $("#sortMenu").hidden = true;
  $("#sortBtn")?.classList.remove("active");
});

const sortBtn = $("#sortBtn");
if (sortBtn) {
  sortBtn.onclick = (ev) => {
    ev.stopPropagation();
    const menu = $("#sortMenu");
    if (!menu.hidden) {
      menu.hidden = true;
      sortBtn.classList.remove("active");
      return;
    }
    sortBtn.classList.add("active");
    openSortMenu(ev.currentTarget);
  };
}

$("#sortMenu").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-sort]");
  if (!btn) return;
  state.sort = btn.dataset.sort;
  localStorage.setItem("dikteSort", state.sort);
  $("#sortMenu").hidden = true;
  sortBtn.classList.remove("active");
  renderMeetings();
});

const searchEl = $("#searchInput");
if (searchEl) {
  searchEl.oninput = () => {
    state.query = searchEl.value.trim();
    renderMeetings();
  };
}

/* ---------------- buka rapat ---------------- */
async function openMeeting(id) {
  state.id = id;
  document.querySelectorAll(".meeting-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.id === id)
  );
  $("#content").innerHTML = '<div class="empty">Memuat…</div>';
  state.data = await api(`/api/meeting/${id}`);
  const { meta } = state.data;

  $("#title").textContent = meta.title || id;
  const mt = $("#mTitle");
  if (mt) mt.textContent = meta.title || id;
  closeDrawer();
  $("#sub").textContent = `${meta.date || ""} · ${Math.round(meta.duration_min || 0)} menit · ${(
    meta.topics || []
  ).join(" · ")}`;

  const player = $("#player");
  if (state.data.has_audio) {
    player.style.display = "";
    player.src = `/media/${id}`;
  } else {
    player.style.display = "none";
    player.removeAttribute("src");
  }

  renderTranscript();
  renderTabs();
  renderTab();
}

function segments() {
  const t = state.data?.transcript || {};
  return t.segments_data || t.segments || [];
}

function speakerName(spk) {
  const names = state.data?.speaker_names || {};
  return names[spk] || spk || "";
}

function renderSpeakers() {
  const segs = segments();
  const set = [...new Set(segs.map((s) => s.speaker).filter(Boolean))].sort();
  if (!set.length) return "";
  const inputs = set
    .map(
      (spk) => `<span class="spk-item">
        <span class="spk ${esc(spk)}">${esc(spk)}</span>
        <input data-spk="${esc(spk)}" placeholder="nama pembicara" value="${esc(state.data?.speaker_names?.[spk] || "")}">
      </span>`
    )
    .join("");
  return `<div class="speakers" title="Klik nama pembicara untuk mengubah — nama dipakai saat dokumen dibuat"><div class="speakers-scroll">${inputs}</div><span class="hint">klik untuk memberi nama — dipakai prompt berikutnya</span></div>`;
}

function renderTranscript() {
  const segs = segments();
  const pane = $("#transcript");
  if (!segs.length) {
    pane.innerHTML = '<div class="empty">Transkrip tidak tersedia.</div>';
    return;
  }
  pane.innerHTML = renderSpeakers() + segs
    .map(
      (s) => `<div class="seg" data-start="${s.start}" data-end="${s.end}">
        <span class="time" data-t="${s.start}">${hhmmss(s.start)}</span>
        <span class="txt">${s.speaker ? `<span class="spk ${esc(s.speaker)}">${esc(speakerName(s.speaker))}</span>` : ""}${esc(s.text)}</span>
      </div>`
    )
    .join("");
  pane.querySelectorAll(".speakers input").forEach((el) => {
    el.onchange = async () => {
      const names = {};
      names[el.dataset.spk] = el.value.trim();
      const r = await api("/api/speakers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: state.id, names }),
      });
      state.data.speaker_names = r.speaker_names;
      renderTranscript();
    };
  });
  pane.querySelectorAll(".seg").forEach((el) => {
    el.onclick = () => seek(Number(el.dataset.start));
  });
}

/* ---------------- tabs ---------------- */
const TABS = [
  ["summary", "Ringkasan"],
  ["decisions", "Keputusan"],
  ["requirements", "Kebutuhan"],
  ["actions", "Action"],
  ["questions", "Open"],
  ["epics", "Epic & Story"],
  ["brd", "BRD"],
  ["export", "Ekspor"],
];

function renderTabs() {
  const appr = state.data.approvals || {};
  $("#tabs").innerHTML = TABS.map(([k, label]) => {
    const approved = appr[k] ? " ✓" : "";
    return `<button class="tab ${state.tab === k ? "active" : ""}" data-tab="${k}">${label}${approved}</button>`;
  }).join("");
  $("#tabs").querySelectorAll(".tab").forEach((el) => {
    el.onclick = () => {
      state.tab = el.dataset.tab;
      renderTabs();
      renderTab();
    };
  });
}

function chips(evidence) {
  return (evidence || [])
    .map(
      (e) =>
        `<span class="chip" data-t="${toSec(e.t)}" title="${esc(e.quote)}">${esc(e.t)}</span>`
    )
    .join("");
}
function quoteOf(evidence) {
  const q = (evidence || [])[0]?.quote;
  return q ? `<div class="quote">“${esc(q)}”</div>` : "";
}

/* ref (R-01 / D-01) → waktu bukti pertama, agar bisa diklik */
function refChips(refs) {
  const facts = state.data.facts || {};
  const index = {};
  ["decisions", "requirements", "action_items", "open_questions"].forEach((k) =>
    (facts[k] || []).forEach((x) => (index[x.id] = x))
  );
  return (refs || [])
    .map((r) => {
      const item = index[r];
      const t = item?.evidence?.[0]?.t;
      return t
        ? `<span class="chip" data-t="${toSec(t)}" title="${esc(item.text || item.task || "")}">${esc(r)}</span>`
        : `<span class="chip" style="opacity:.55;cursor:default">${esc(r)}</span>`;
    })
    .join("");
}

/* ---------------- tab content ---------------- */
function renderTab() {
  const d = state.data;
  const f = d.facts || {};
  const a = d.artifacts || {};
  const box = $("#content");

  if (state.tab === "summary") {
    const s = f.summary || {};
    box.innerHTML = `
      <div class="card">
        <h3>Ringkasan singkat</h3>
        <ul class="clean">${(s.tldr || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p style="font-size:13px">${esc(s.narrative || "")}</p>
      </div>
      <div class="card">
        <h3>Topik</h3>
        ${(f.meeting?.topics || []).map((t) => `<span class="chip" style="cursor:default">${esc(t)}</span>`).join(" ")}
      </div>`;
    return;
  }

  if (state.tab === "decisions") {
    box.innerHTML = (f.decisions || [])
      .map(
        (x) => `<div class="card">
          <div class="meta">${esc(x.id)} · keyakinan ${esc(x.confidence || "-")}</div>
          <h3>${esc(x.text)}</h3>
          <div>${chips(x.evidence)}</div>
          ${quoteOf(x.evidence)}
        </div>`
      )
      .join("") || '<div class="empty">Tidak ada keputusan.</div>';
    return;
  }

  if (state.tab === "requirements") {
    box.innerHTML = (f.requirements || [])
      .map(
        (x) => `<div class="card">
          <div class="meta">${esc(x.id)} · ${esc(x.type)}</div>
          <h3>${esc(x.text)} <span class="tag ${esc(x.priority)}">${esc(x.priority)}</span></h3>
          ${x.rationale ? `<div class="quote">${esc(x.rationale)}</div>` : ""}
          <div>${chips(x.evidence)}</div>
          ${quoteOf(x.evidence)}
        </div>`
      )
      .join("") || '<div class="empty">Tidak ada kebutuhan.</div>';
    return;
  }

  if (state.tab === "actions") {
    box.innerHTML = (f.action_items || [])
      .map((x) => {
        const owner = x.owner_confidence === "explicit"
          ? `<span class="tag ok">owner pasti</span>`
          : `<span class="tag needs">owner terduga</span>`;
        return `<div class="card">
          <div class="meta">${esc(x.id)} ${owner}</div>
          <h3>${esc(x.task)}</h3>
          <div class="meta">Owner: ${esc(x.owner || "belum ditentukan")} · Status: ${esc(x.status)}</div>
          <div>${chips(x.evidence)}</div>
          ${quoteOf(x.evidence)}
        </div>`;
      })
      .join("") || '<div class="empty">Tidak ada action item.</div>';
    return;
  }

  if (state.tab === "questions") {
    box.innerHTML = (f.open_questions || [])
      .map(
        (x) => `<div class="card">
          <div class="meta">${esc(x.id)} <span class="tag needs">${esc(x.status)}</span></div>
          <h3>${esc(x.question)}</h3>
          ${x.note ? `<div class="quote">${esc(x.note)}</div>` : ""}
          <div>${chips(x.evidence)}</div>
        </div>`
      )
      .join("") || '<div class="empty">Tidak ada pertanyaan terbuka.</div>';
    return;
  }

  if (state.tab === "epics") {
    const appr = d.approvals?.epics;
    box.innerHTML = `
      <div class="approve">
        <button class="btn ${appr ? "" : "primary"}" id="approveEpics">${appr ? "Batalkan persetujuan" : "Setujui Epic & Story"}</button>
        <button class="btn" id="regenEpics">Buat ulang dokumen</button>
        <span class="meta">${appr ? "Sudah disetujui" : "Draft — belum disetujui"}</span>
      </div>` +
      (a.epics || [])
        .map(
          (ep) => `<div class="card">
            <div class="meta">${esc(ep.id)} · ${refChips(ep.refs)}</div>
            <h3>${esc(ep.title)}</h3>
            <p style="font-size:13px"><b>Tujuan:</b> ${esc(ep.goal || "")}</p>
            <p style="font-size:13px"><b>Nilai:</b> ${esc(ep.value || "")}</p>
            <p style="font-size:13px"><b>Metrik:</b> ${esc(ep.success_metric || "")}</p>
            ${(ep.stories || [])
              .map(
                (st) => `<div class="card" style="background:#fbfcfe">
                  <div class="meta">${esc(st.id)} · <span class="tag ${esc(st.priority)}">${esc(st.priority)}</span> · ${refChips(st.refs)}</div>
                  <h3>Sebagai ${esc(st.as_a)}, saya ingin ${esc(st.i_want)}, agar ${esc(st.so_that)}.</h3>
                  ${(st.acceptance || [])
                    .map(
                      (ac) => `<div class="ac"><b>Given</b> ${esc(ac.given)} <b>when</b> ${esc(ac.when)} <b>then</b> ${esc(ac.then)}</div>`
                    )
                    .join("")}
                </div>`
              )
              .join("")}
          </div>`
        )
        .join("") || '<div class="empty">Belum ada epic.</div>';

    const b = $("#approveEpics");
    if (b) b.onclick = () => setApproval("epics", !appr);
    const rb = $("#regenEpics");
    if (rb) rb.onclick = regenerate;
    return;
  }

  if (state.tab === "brd") {
    const brd = a.brd || {};
    const appr = d.approvals?.brd;
    box.innerHTML = `
      <div class="approve">
        <button class="btn ${appr ? "" : "primary"}" id="approveBrd">${appr ? "Batalkan persetujuan" : "Setujui BRD"}</button>
        <button class="btn" id="regenBrd">Buat ulang dokumen</button>
        <span class="meta">${appr ? "Sudah disetujui" : "Draft — belum disetujui"}</span>
      </div>
      <div class="card">
        <h3>${esc(brd.title || "BRD")}</h3>
        <p style="font-size:13px">${esc(brd.background || "")}</p>
      </div>
      <div class="card">
        <h3>Tujuan</h3>
        <ul class="clean">${(brd.objectives || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <h3 style="margin-top:12px">Metrik sukses</h3>
        <ul class="clean">${(brd.success_metrics || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      </div>
      <div class="card">
        <h3>Ruang lingkup</h3>
        <b style="font-size:12.5px">Termasuk</b>
        <ul class="clean">${(brd.in_scope || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <b style="font-size:12.5px">Tidak termasuk</b>
        <ul class="clean">${(brd.out_of_scope || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      </div>
      <div class="card">
        <h3>Kebutuhan bisnis</h3>
        ${(brd.business_requirements || [])
          .map(
            (r) => `<div style="margin:8px 0">
              <span class="tag ${esc(r.priority)}">${esc(r.priority)}</span>
              <b style="font-size:12.5px">${esc(r.id)}</b> ${esc(r.text)}
              <div>${refChips(r.refs)}</div>
            </div>`
          )
          .join("")}
      </div>
      <div class="card">
        <h3>Risiko</h3>
        ${(brd.risks || [])
          .map((r) => `<div style="margin:6px 0;font-size:13px"><b>${esc(r.risk)}</b> — ${esc(r.impact)}<div class="quote">Mitigasi: ${esc(r.mitigation)}</div></div>`)
          .join("")}
      </div>`;

    const b = $("#approveBrd");
    if (b) b.onclick = () => setApproval("brd", !appr);
    const rb = $("#regenerateBrd") || $("#regenBrd");
    if (rb) rb.onclick = regenerate;
    return;
  }

  if (state.tab === "export") {
    const docs = d.meta?.docs || {};
    const items = [
      ["brd_docx", "BRD (.docx)", "Dokumen untuk stakeholder"],
      ["epics_docx", "Epic & Story (.docx)", "Untuk tim developer"],
      ["summary_docx", "Ringkasan (.docx)", "Untuk catatan rapat"],
      ["brd", "BRD (.md)", "Markdown"],
      ["epics", "Epic & Story (.md)", "Markdown"],
      ["jira", "Jira import (.csv)", "16 issue siap impor"],
    ].filter(([k]) => docs[k]);
    const saved = localStorage.getItem("jiraProject") || "";
    box.innerHTML =
      (items
        .map(
          ([k, label, desc]) =>
            `<a class="dl" href="/doc/${state.id}/${k}" download><b>${label}</b><span>${desc}</span></a>`
        )
        .join("") || '<div class="empty">Belum ada dokumen.</div>') +
      `<div class="card" style="margin-top:14px">
        <h3>Kirim ke Jira</h3>
        <div class="meta">Membuat Epic + Story lewat REST API v3. Butuh JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN di .env.</div>
        <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
          <input id="jiraProject" placeholder="KODE PROYEK" value="${esc(saved)}"
                 style="font:inherit;font-size:12.5px;border:1px solid var(--line);border-radius:7px;padding:6px 9px;width:140px;text-transform:uppercase">
          <button class="btn primary" id="jiraSend">Kirim ke Jira</button>
          <button class="btn" id="jiraDry">Tes (dry-run)</button>
        </div>
        <pre id="jiraOut" style="white-space:pre-wrap;font-size:11.5px;color:var(--muted);margin:10px 0 0"></pre>
      </div>`;

    const send = async (dry) => {
      const project = ($("#jiraProject")?.value || "").trim().toUpperCase();
      if (!project) { $("#jiraOut").textContent = "Isi kode proyek dulu."; return; }
      localStorage.setItem("jiraProject", project);
      const out = $("#jiraOut");
      out.textContent = "mengirim…";
      try {
        const r = await api("/api/jira", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: state.id, project, dry_run: dry }),
        });
        out.textContent = r.output || (r.ok ? "selesai" : "gagal");
      } catch (e) {
        out.textContent = "gagal: " + e.message;
      }
    };
    const b1 = $("#jiraSend");
    if (b1) b1.onclick = () => send(false);
    const b2 = $("#jiraDry");
    if (b2) b2.onclick = () => send(true);
    return;
  }
}

async function cancelJob(jobId) {
  await api("/api/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: jobId }),
  });
}

async function regenerate() {
  const job = { id: "regen-" + Date.now(), filename: "bangun ulang dokumen", state: "running", step: "antre", progress: 0 };
  renderJob(job);
  const r = await api("/api/regenerate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: state.id }),
  });
  document.getElementById(`job-${job.id}`)?.remove();
  renderJob({ id: r.job, filename: "bangun ulang dokumen", state: "running", step: "antre", progress: 0 });
  pollJob(r.job);
}

async function setApproval(key, approved) {
  const r = await api("/api/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: state.id, key, approved }),
  });
  state.data.approvals = r.approvals;
  renderTabs();
  renderTab();
}

/* ---------------- audio sync ---------------- */
function seek(sec) {
  const player = $("#player");
  highlightAt(sec);
  if (state.data?.has_audio) {
    player.currentTime = Math.max(0, sec);
    player.play().catch(() => {});
  }
}

function highlightAt(sec) {
  const segs = document.querySelectorAll("#transcript .seg");
  let target = null;
  for (const el of segs) {
    const s = Number(el.dataset.start);
    const e = Number(el.dataset.end);
    if (sec + 0.01 >= s && sec < e) { target = el; break; }
  }
  if (!target && segs.length) {
    let best = null, bestDiff = Infinity;
    for (const el of segs) {
      const diff = Math.abs(Number(el.dataset.start) - sec);
      if (diff < bestDiff) { bestDiff = diff; best = el; }
    }
    target = best;
  }
  segs.forEach((el) => el.classList.remove("active"));
  if (target) {
    target.classList.add("active");
    target.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

document.addEventListener("click", (ev) => {
  const chip = ev.target.closest(".chip[data-t]");
  if (chip) seek(Number(chip.dataset.t));
  const cancel = ev.target.closest("[data-cancel]");
  if (cancel) cancelJob(cancel.dataset.cancel);
});

$("#player").addEventListener("timeupdate", (ev) => {
  const t = ev.target.currentTime;
  document.querySelectorAll("#transcript .seg.active").forEach((el) => {
    const s = Number(el.dataset.start), e = Number(el.dataset.end);
    if (t < s || t >= e) el.classList.remove("active");
  });
  for (const el of document.querySelectorAll("#transcript .seg")) {
    const s = Number(el.dataset.start), e = Number(el.dataset.end);
    if (t >= s && t < e) {
      if (!el.classList.contains("active")) {
        document.querySelectorAll("#transcript .seg.active").forEach((x) => x.classList.remove("active"));
        el.classList.add("active");
      }
      break;
    }
  }
});

loadMeetings().catch((e) => {
  $("#meetings").innerHTML = `<div class="empty">Gagal memuat: ${esc(e.message)}</div>`;
});
