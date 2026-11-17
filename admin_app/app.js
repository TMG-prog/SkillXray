"use strict";

let token = null;
let usersPage = 1;
const offsets = { roles: 0, postings: 0, esco: 0 };
const $ = (selector) => document.querySelector(selector);
const status = (message, error = false) => {
  const element = $("#status");
  element.textContent = message;
  element.classList.toggle("error", error);
};
const text = (tag, value, className) => {
  const el = document.createElement(tag);
  el.textContent = value == null ? "" : String(value);
  if (className) el.className = className;
  return el;
};
function action(label, handler, danger = false) {
  const button = text("button", label, danger ? "danger" : "secondary");
  button.type = "button";
  button.addEventListener("click", () => run(handler));
  return button;
}
async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.json !== undefined) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers, body: options.json === undefined ? options.body : JSON.stringify(options.json) });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* use HTTP status */ }
    if (response.status === 401 && token) signout();
    throw new Error(message);
  }
  return options.download ? response.blob() : response.json();
}
async function run(fn) {
  try { status(""); await fn(); } catch (error) { console.error(error); status(error instanceof Error ? error.message : "Request failed.", true); }
}
function signout() {
  token = null;
  $("#console").hidden = true;
  $("#signout").hidden = true;
  $("#login-view").hidden = false;
  $("#login-form").reset();
}
function showRows(selector, rows, render) {
  const list = $(selector);
  list.replaceChildren();
  if (!rows.length) list.append(text("p", "No records found.", "empty"));
  rows.forEach((row) => list.append(render(row)));
}
function row(title, subtitle, buttons = []) {
  const el = text("article", "", "row");
  const info = document.createElement("div");
  info.append(text("h4", title), text("p", subtitle));
  const actions = text("div", "", "actions");
  buttons.forEach((button) => actions.append(button));
  el.append(info, actions);
  return el;
}
function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }
function setForm(form, values) {
  for (const [key, value] of Object.entries(values)) {
    const field = form.elements.namedItem(key);
    if (!field) continue;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = Array.isArray(value) ? value.join(", ") : value ?? "";
  }
  form.closest("details").open = true;
  form.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function encode(value) { return encodeURIComponent(value); }

$("#login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const result = await api("/api/login", { method: "POST", json: formValues(event.target) });
    token = result.access_token;
    event.target.reset();
    $("#login-view").hidden = true; $("#console").hidden = false; $("#signout").hidden = false;
    await loadUsers();
  });
});
$("#signout").addEventListener("click", signout);
$("#navigation").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-section]");
  if (!button) return;
  document.querySelectorAll("#navigation button").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll("#console > .section").forEach((item) => { item.hidden = item.id !== button.dataset.section; });
  run(async () => {
    if (button.dataset.section === "users") await loadUsers();
    if (button.dataset.section === "taxonomy") { await loadRoles(); await loadEsco(); await loadChanges(); }
    if (button.dataset.section === "datasets") { await loadPostings(); await loadDatasets(); }
    if (button.dataset.section === "resources") await loadResources();
  });
});

let currentUsers = [];
let usersHasNext = false;
function renderUsers() {
  showRows("#users-list", currentUsers, (user) => {
    const suspended = user.banned_until && new Date(user.banned_until) > new Date();
    return row(user.full_name || user.email || user.id, `${user.email || ""} · ${suspended ? "Suspended" : "Active"}`, [
      action("Edit name", async () => {
        const name = prompt("Profile name", user.full_name || "");
        if (name === null) return;
        await api(`/api/users/${encode(user.id)}/profile`, { method: "PUT", json: { full_name: name } });
        await loadUsers(); status("Profile updated.");
      }),
      action(suspended ? "Reactivate" : "Suspend", async () => {
        if (!confirm(`${suspended ? "Reactivate" : "Suspend"} this user?`)) return;
        await api(`/api/users/${encode(user.id)}/suspension`, { method: "PUT", json: { suspended: !suspended } });
        await loadUsers(); status("Account updated.");
      }, !suspended),
    ]);
  });
}
$("#user-search").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { usersPage = 1; run(loadUsers); }
});
async function loadUsers() {
  const result = await api(`/api/users?page=${usersPage}&search=${encode($("#user-search").value)}`);
  currentUsers = result.users;
  usersHasNext = result.has_next;
  $("#users-page").textContent = `Page ${usersPage}`;
  renderUsers();
}
async function loadRoles() {
  const result = await api(`/api/roles?search=${encode($("#role-search").value)}&offset=${offsets.roles}`);
  $("#roles-page").textContent = `From ${offsets.roles + 1}`;
  showRows("#roles-list", result.roles, (item) => row(item.title, item.description || item.model_role || "No description", [
    action("Edit", () => setForm($("#role-form"), item)),
    action("Delete", async () => {
      if (!confirm(`Delete role "${item.title}"?`)) return;
      await api(`/api/roles/${encode(item.id)}`, { method: "DELETE" }); await loadRoles(); status("Role deleted.");
    }, true),
  ]));
}
$("#role-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const data = formValues(event.target); const id = data.id; delete data.id;
    for (const key of ["description", "model_role", "search_query", "title_pattern"]) data[key] = data[key].trim() || null;
    await api(id ? `/api/roles/${encode(id)}` : "/api/roles", { method: id ? "PUT" : "POST", json: data });
    event.target.reset(); await loadRoles(); status("Role saved.");
  });
});
const taxonomyKeys = { skill: ["conceptUri"], occupation: ["conceptUri"], skill_relation: ["originalSkillUri", "relatedSkillUri", "relationType"], broader_relation: ["conceptUri", "broaderUri"] };
async function loadEsco() {
  const kind = $("#esco-kind").value;
  const result = await api(`/api/esco/${encode(kind)}?search=${encode($("#esco-search").value)}&offset=${offsets.esco}`);
  $("#esco-page").textContent = `${result.total} results`;
  showRows("#esco-list", result.rows, (item) => row(item.preferredLabel || item.conceptLabel || item.originalSkillUri || item.conceptUri, item.conceptUri || item.relatedSkillUri || "", [
    action("Stage edit", () => setForm($("#taxonomy-form"), { kind, operation: "upsert", record: JSON.stringify(item, null, 2) })),
    action("Stage delete", () => setForm($("#taxonomy-form"), { kind, operation: "delete", record: JSON.stringify(item, null, 2) }), true),
  ]));
}
$("#esco-kind").addEventListener("change", () => { offsets.esco = 0; run(loadEsco); });
async function loadChanges() {
  const result = await api("/api/taxonomy-changes");
  showRows("#changes-list", result.changes, (item) => row(`${item.kind} · ${item.operation}`, item.record_key, [
    action("Edit", () => setForm($("#taxonomy-form"), { ...item, record: JSON.stringify(item.record, null, 2) })),
    action("Remove", async () => {
      if (!confirm("Remove this staged change?")) return;
      await api(`/api/taxonomy-changes/${encode(item.id)}`, { method: "DELETE" }); await loadChanges(); status("Staged change removed.");
    }, true),
  ]));
}
$("#taxonomy-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const data = formValues(event.target);
    let record;
    try { record = JSON.parse(data.record); } catch { throw new Error("Enter valid record JSON."); }
    const keys = taxonomyKeys[data.kind];
    if (!record || typeof record !== "object" || keys.some((key) => typeof record[key] !== "string" || !record[key].trim())) throw new Error(`Record requires: ${keys.join(", ")}.`);
    await api("/api/taxonomy-changes", { method: "PUT", json: { kind: data.kind, operation: data.operation, record_key: keys.map((key) => record[key].trim()).join("|"), record } });
    event.target.reset(); await loadChanges(); status("ESCO change staged.");
  });
});
async function loadPostings() {
  const result = await api(`/api/postings?search=${encode($("#posting-search").value)}&offset=${offsets.postings}`);
  $("#postings-page").textContent = `From ${offsets.postings + 1}`;
  showRows("#postings-list", result.postings, (item) => row(item.title, `${item.company || "Unknown company"} · ${item.role_key} · ${item.provider}`, [
    action("Delete", async () => {
      if (!confirm(`Delete posting "${item.title}"?`)) return;
      await api(`/api/postings/${encode(item.id)}`, { method: "DELETE" }); await loadPostings(); status("Posting deleted; restart the analysis backend to refresh profiles.");
    }, true),
  ]));
}
$("#posting-import").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const result = await api("/api/postings/import", { method: "POST", body: new FormData(event.target) });
    event.target.reset(); await loadPostings(); status(`Imported ${result.imported} postings; restart the analysis backend to refresh profiles.`);
  });
});
async function loadDatasets() {
  const result = await api("/api/datasets");
  showRows("#datasets-list", result.files, (file) => row(file.name.split("__").slice(1).join("__"), file.created_at || "", [
    action("Download", async () => saveBlob(await api(`/api/datasets/${encode(file.name)}`, { download: true }), file.name.split("__").slice(1).join("__"))),
    action("Delete", async () => {
      if (!confirm("Permanently delete this dataset file?")) return;
      await api(`/api/datasets/${encode(file.name)}`, { method: "DELETE" }); await loadDatasets(); status("Dataset file deleted.");
    }, true),
  ]));
}
$("#dataset-upload").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    await api("/api/datasets", { method: "POST", body: new FormData(event.target) });
    event.target.reset(); await loadDatasets(); status("Dataset uploaded.");
  });
});
async function loadResources() {
  const result = await api("/api/resources");
  showRows("#resources-list", result.resources, (item) => row(item.title, `${item.provider} · ${item.published ? "Published" : "Draft"} · ${item.keywords.join(", ")}`, [
    action("Edit", () => setForm($("#resource-form"), item)),
    action("Delete", async () => {
      if (!confirm(`Delete resource "${item.title}"?`)) return;
      await api(`/api/resources/${encode(item.id)}`, { method: "DELETE" }); await loadResources(); status("Resource deleted.");
    }, true),
  ]));
}
$("#resource-form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(async () => {
    const data = formValues(event.target); const id = data.id; delete data.id;
    data.keywords = data.keywords.split(",").map((item) => item.trim()).filter(Boolean);
    data.priority = Number(data.priority); data.published = event.target.elements.published.checked;
    await api(id ? `/api/resources/${encode(id)}` : "/api/resources", { method: id ? "PUT" : "POST", json: data });
    event.target.reset(); await loadResources(); status("Resource saved.");
  });
});
document.addEventListener("click", (event) => {
  const name = event.target.closest("[data-action]")?.dataset.action;
  if (!name) return;
  run(async () => {
    if (name === "load-users") { usersPage = 1; await loadUsers(); }
    if (name === "users-prev") { usersPage = Math.max(1, usersPage - 1); await loadUsers(); }
    if (name === "users-next") { if (usersHasNext) usersPage++; await loadUsers(); }
    if (name === "load-roles") { offsets.roles = 0; await loadRoles(); }
    if (name === "roles-prev" || name === "roles-next") { offsets.roles = Math.max(0, offsets.roles + (name.endsWith("next") ? 50 : -50)); await loadRoles(); }
    if (name === "clear-role") $("#role-form").reset();
    if (name === "load-esco") { offsets.esco = 0; await loadEsco(); }
    if (name === "esco-prev" || name === "esco-next") { offsets.esco = Math.max(0, offsets.esco + (name.endsWith("next") ? 50 : -50)); await loadEsco(); }
    if (name === "load-changes") await loadChanges();
    if (name === "export-changes") saveBlob(await api("/api/taxonomy-export", { download: true }), "esco-changes.json");
    if (name === "load-postings") { offsets.postings = 0; await loadPostings(); }
    if (name === "postings-prev" || name === "postings-next") { offsets.postings = Math.max(0, offsets.postings + (name.endsWith("next") ? 50 : -50)); await loadPostings(); }
    if (name === "load-datasets") await loadDatasets();
    if (name === "load-resources") await loadResources();
    if (name === "clear-resource") $("#resource-form").reset();
  });
});
