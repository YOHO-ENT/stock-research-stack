const state = {
  services: [],
  health: new Map(),
  checkedAt: null,
};

const body = document.querySelector("#services-body");
const refreshButton = document.querySelector("#refresh");
const summary = document.querySelector("#summary");

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

async function loadServices() {
  const payload = await fetchJson("/api/services");
  state.services = payload.services || [];
  render();
}

async function refreshHealth() {
  refreshButton.disabled = true;
  summary.textContent = "Checking";
  try {
    const payload = await fetchJson("/api/health");
    state.health = new Map((payload.results || []).map((result) => [result.id, result]));
    state.checkedAt = payload.checked_at;
    render();
  } catch (error) {
    summary.textContent = error.message;
  } finally {
    refreshButton.disabled = false;
  }
}

function render() {
  if (!state.services.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">No services</td></tr>';
    return;
  }

  const counts = { ok: 0, down: 0, skipped: 0 };
  const rows = state.services.map((service) => {
    const health = state.health.get(service.id) || { status: "unknown" };
    if (counts[health.status] !== undefined) counts[health.status] += 1;
    return serviceRow(service, health);
  });

  body.innerHTML = rows.join("");
  document.querySelector("#ok-count").textContent = counts.ok;
  document.querySelector("#down-count").textContent = counts.down;
  document.querySelector("#skipped-count").textContent = counts.skipped;
  document.querySelector("#checked-at").textContent = formatTime(state.checkedAt);
  summary.textContent = `${state.services.length} services`;
}

function serviceRow(service, health) {
  const urlCell = service.local_url && service.local_url.startsWith("http")
    ? `<a class="open-link" href="${escapeAttr(service.local_url)}" target="_blank" rel="noopener noreferrer">Open</a><span class="muted">${escapeHtml(service.local_url)}</span>`
    : `<span class="muted">${escapeHtml(service.local_url || "No URL")}</span>`;
  const latency = Number.isInteger(health.latency_ms) ? `${health.latency_ms} ms` : "-";
  const message = health.message ? `<span class="muted">${escapeHtml(health.message)}</span>` : "";
  return `
    <tr>
      <td>
        <span class="service-name">${escapeHtml(service.name || service.id)}</span>
        <span class="service-id">${escapeHtml(service.id || "")}</span>
      </td>
      <td>${escapeHtml(service.component_type || "-")}</td>
      <td>
        <span class="status ${escapeAttr(health.status || "unknown")}">${escapeHtml(health.status || "unknown")}</span>
        ${message}
      </td>
      <td>${latency}</td>
      <td>${urlCell}</td>
      <td class="role">${escapeHtml(service.role || "")}</td>
    </tr>
  `;
}

function formatTime(value) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

refreshButton.addEventListener("click", refreshHealth);

loadServices()
  .then(refreshHealth)
  .catch((error) => {
    summary.textContent = error.message;
    body.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(error.message)}</td></tr>`;
  });

setInterval(refreshHealth, 30000);

