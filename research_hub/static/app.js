const VIEWS = {
  all: {
    title: "All Services",
    description: "All orchestrated local services.",
  },
  ui: {
    title: "UI & Dashboards",
    description: "Entry points meant to be opened by a person.",
  },
  backend: {
    title: "Backends",
    description: "APIs, gateways, pipelines, and command-line services.",
  },
};

const state = {
  services: [],
  health: new Map(),
  checkedAt: null,
  currentView: "ui",
};

const body = document.querySelector("#services-body");
const refreshButton = document.querySelector("#refresh");
const summary = document.querySelector("#summary");
const viewTitle = document.querySelector("#view-title");
const viewDescription = document.querySelector("#view-description");
const visibleCount = document.querySelector("#visible-count");
const overallDot = document.querySelector("#overall-dot");
const sidebar = document.querySelector("#sidebar");
const sidebarBackdrop = document.querySelector("#sidebar-backdrop");
const mobileNavToggle = document.querySelector("#mobile-nav-toggle");
const navButtons = Array.from(document.querySelectorAll(".nav-item"));

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
    overallDot.className = "health-dot down";
  } finally {
    refreshButton.disabled = false;
  }
}

function render() {
  const groups = groupedServices();
  updateNavCounts(groups);
  updateNavState();

  const current = VIEWS[state.currentView];
  const services = groups[state.currentView] || [];
  viewTitle.textContent = current.title;
  viewDescription.textContent = current.description;
  visibleCount.textContent = pluralize(services.length, "service");

  if (!services.length) {
    body.innerHTML = '<div class="empty">No services in this view</div>';
    updateCounts([]);
    return;
  }

  body.innerHTML = services.map((service) => serviceRow(service, getHealth(service.id))).join("");
  updateCounts(services);
}

function groupedServices() {
  const groups = { all: state.services, ui: [], backend: [] };
  for (const service of state.services) {
    if (isUiService(service)) {
      groups.ui.push(service);
    } else {
      groups.backend.push(service);
    }
  }
  return groups;
}

function isUiService(service) {
  const componentType = String(service.component_type || "").toLowerCase();
  return componentType.includes("ui") || componentType.includes("dashboard") || componentType.includes("web-ui");
}

function updateNavCounts(groups) {
  document.querySelector("#all-count").textContent = groups.all.length;
  document.querySelector("#ui-count").textContent = groups.ui.length;
  document.querySelector("#backend-count").textContent = groups.backend.length;
}

function updateNavState() {
  for (const button of navButtons) {
    const active = button.dataset.view === state.currentView;
    button.classList.toggle("is-active", active);
    if (active) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

function updateCounts(services) {
  const counts = { ok: 0, down: 0, skipped: 0 };
  for (const service of services) {
    const status = getHealth(service.id).status || "unknown";
    if (counts[status] !== undefined) {
      counts[status] += 1;
    }
  }

  document.querySelector("#ok-count").textContent = counts.ok;
  document.querySelector("#down-count").textContent = counts.down;
  document.querySelector("#skipped-count").textContent = counts.skipped;
  document.querySelector("#checked-at").textContent = formatTime(state.checkedAt);
  document.querySelector("#sidebar-ok-count").textContent = counts.ok;
  document.querySelector("#sidebar-down-count").textContent = counts.down;

  const total = services.length;
  if (!total) {
    summary.textContent = "No services";
    overallDot.className = "health-dot unknown";
  } else if (counts.down > 0) {
    summary.textContent = `${counts.down} down`;
    overallDot.className = "health-dot down";
  } else if (counts.ok > 0) {
    summary.textContent = "Healthy";
    overallDot.className = "health-dot ok";
  } else {
    summary.textContent = "Skipped";
    overallDot.className = "health-dot skipped";
  }
}

function getHealth(id) {
  return state.health.get(id) || { status: "unknown" };
}

function serviceRow(service, health) {
  const displayUrl = service.public_url || service.local_url || "No URL";
  const clickableUrl = service.public_url || service.local_url;
  const role = service.role || "";
  const componentType = service.component_type || "-";
  const healthMessage = health.message || "";
  const clickable = clickableUrl && clickableUrl.startsWith("http");
  const urlCell = `<span class="muted" title="${escapeAttr(displayUrl)}">${escapeHtml(displayUrl)}</span>`;
  const latency = Number.isInteger(health.latency_ms) ? `${health.latency_ms} ms` : "-";
  const message = healthMessage ? `<span class="status-message" title="${escapeAttr(healthMessage)}">${escapeHtml(healthMessage)}</span>` : "";
  const status = health.status || "unknown";
  return `
    <article
      class="service-row${clickable ? " is-clickable" : ""}"
      ${clickable ? `data-url="${escapeAttr(clickableUrl)}" role="link" tabindex="0" aria-label="Visit ${escapeAttr(service.name || service.id)}"` : ""}
    >
      <div class="service-title">
        <span class="service-name">${escapeHtml(service.name || service.id)}</span>
        <span class="service-id">${escapeHtml(service.id || "")}</span>
      </div>
      <div class="cell-type">
        <span class="row-label">Type</span>
        <span class="type-pill" title="${escapeAttr(componentType)}">${escapeHtml(componentType)}</span>
      </div>
      <div class="cell-status">
        <span class="row-label">Status</span>
        <span class="status ${escapeAttr(status)}">${escapeHtml(status)}</span>
        ${message}
      </div>
      <div class="cell-latency">
        <span class="row-label">Latency</span>
        <span class="latency">${latency}</span>
      </div>
      <div class="url-cell">
        <span class="row-label">URL</span>
        ${urlCell}
      </div>
      <div class="role" title="${escapeAttr(role)}">
        <span class="row-label">Role</span>
        ${escapeHtml(role)}
      </div>
    </article>
  `;
}

function formatTime(value) {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function pluralize(count, singular) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function openMobileNav(open) {
  sidebar.classList.toggle("is-open", open);
  sidebarBackdrop.hidden = !open;
  mobileNavToggle.setAttribute("aria-expanded", String(open));
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

for (const button of navButtons) {
  button.addEventListener("click", () => {
    state.currentView = button.dataset.view || "all";
    openMobileNav(false);
    render();
  });
}

mobileNavToggle.addEventListener("click", () => openMobileNav(!sidebar.classList.contains("is-open")));
sidebarBackdrop.addEventListener("click", () => openMobileNav(false));
body.addEventListener("click", (event) => {
  const row = event.target.closest(".service-row.is-clickable");
  if (row?.dataset.url) {
    window.open(row.dataset.url, "_blank", "noopener,noreferrer");
  }
});
body.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest(".service-row.is-clickable");
  if (row?.dataset.url) {
    event.preventDefault();
    window.open(row.dataset.url, "_blank", "noopener,noreferrer");
  }
});

loadServices()
  .then(refreshHealth)
  .catch((error) => {
    summary.textContent = error.message;
    overallDot.className = "health-dot down";
    body.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  });

setInterval(refreshHealth, 30000);
