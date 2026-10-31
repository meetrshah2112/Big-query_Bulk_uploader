const $ = (id) => document.getElementById(id);

// ---- tabs ----
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === name));
  if (name === "upload") updateTarget();
  if (name === "tables") loadTables();
}
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

// ---- settings (remembered in the browser) ----
const settings = () => ({
  project_id: $("project").value.trim(),
  dataset: $("dataset").value.trim(),
  location: $("location").value,
});
["project", "dataset", "location"].forEach((id) => {
  const saved = localStorage.getItem("bq_" + id);
  if (saved) $(id).value = saved;
  $(id).addEventListener("change", () => localStorage.setItem("bq_" + id, $(id).value.trim()));
});
function updateTarget() {
  const s = settings();
  $("target").textContent = s.project_id && s.dataset ? `${s.project_id}.${s.dataset}` : "(set on Connection tab)";
}
function msg(el, type, text) { el.className = "msg " + type; el.textContent = text; }
function esc(s) { const d = document.createElement("div"); d.textContent = s ?? ""; return d.innerHTML; }

// ---- 1. connection ----
$("checkBtn").addEventListener("click", async () => {
  const btn = $("checkBtn"); btn.disabled = true;
  msg($("connMsg"), "info", "Checking connection...");
  try {
    const r = await fetch("/api/check-connection", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings()),
    });
    const d = await r.json();
    msg($("connMsg"), d.ok ? "ok" : "err", (d.ok ? "OK: " : "Failed: ") + d.message);
  } catch (e) { msg($("connMsg"), "err", "Cannot reach the local server: " + e); }
  btn.disabled = false;
});

// ---- 2. upload (one request per file so progress is visible) ----
$("uploadBtn").addEventListener("click", async () => {
  const s = settings(), files = [...$("files").files];
  if (!s.project_id || !s.dataset) return msg($("uploadMsg"), "err", "Fill Project ID and Dataset on the Connection tab first.");
  if (!files.length) return msg($("uploadMsg"), "err", "Choose at least one file.");

  const btn = $("uploadBtn"); btn.disabled = true;
  const tbody = $("resultTable").querySelector("tbody");
  tbody.innerHTML = ""; $("resultTable").hidden = false;
  let ok = 0, bad = 0;

  for (let i = 0; i < files.length; i++) {
    msg($("uploadMsg"), "info", `Uploading ${i + 1} of ${files.length}: ${files[i].name}`);
    const row = tbody.insertRow();
    row.innerHTML = `<td>${esc(files[i].name)}</td><td></td><td></td><td class="s-Uploading">Uploading...</td><td></td>`;
    const fd = new FormData();
    fd.append("file", files[i]); fd.append("mode", $("mode").value);
    Object.entries(s).forEach(([k, v]) => fd.append(k, v));
    let results;
    try { results = (await (await fetch("/api/upload", { method: "POST", body: fd })).json()).results; }
    catch (e) { results = [{ file: files[i].name, table: "", rows: 0, status: "Failed", detail: String(e) }]; }
    row.remove();
    results.forEach((r) => {
      r.status === "Success" ? ok++ : bad++;
      tbody.insertRow().innerHTML = `<td>${esc(r.file)}</td><td>${esc(r.table)}</td><td>${r.rows}</td>
        <td class="s-${r.status}">${r.status}</td><td>${esc(r.detail)}</td>`;
    });
  }
  msg($("uploadMsg"), bad ? "err" : "ok", `Done. ${ok} table(s) succeeded, ${bad} failed.`);
  btn.disabled = false;
});

// ---- 3. tables in dataset ----
async function loadTables() {
  const s = settings(), tbody = $("tablesTable").querySelector("tbody");
  if (!s.project_id || !s.dataset) return msg($("tablesMsg"), "err", "Fill Project ID and Dataset on the Connection tab first.");
  msg($("tablesMsg"), "info", "Loading...");
  const d = await (await fetch("/api/tables?" + new URLSearchParams(s))).json();
  tbody.innerHTML = "";
  if (!d.ok) { $("tablesTable").hidden = true; return msg($("tablesMsg"), "err", d.message); }
  msg($("tablesMsg"), "ok", `${d.tables.length} table(s) in ${s.project_id}.${s.dataset}`);
  $("tablesTable").hidden = !d.tables.length;
  d.tables.forEach((t) => tbody.insertRow().innerHTML =
    `<td>${esc(t.table)}</td><td>${t.rows}</td><td>${t.columns}</td><td>${esc(t.modified)}</td>`);
}
$("refreshBtn").addEventListener("click", loadTables);
