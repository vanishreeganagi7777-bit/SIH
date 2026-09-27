// Change this if your FastAPI backend runs elsewhere.
const API_BASE = "http://127.0.0.1:8000";
// Authentication is hosted by the Flask application, separately from the
// FastAPI data API and any local frontend development server.
const AUTH_BASE = "http://127.0.0.1:5000";

function logoutUrl() {
  const landingPage = new URL("/", window.location.origin).href;
  return `${AUTH_BASE}/logout?return_to=${encodeURIComponent(landingPage)}`;
}

const NAV_ITEMS = [
  { href: "/dashboard/", active: "index.html", icon: "⛰", label: "Map Explorer" },
  { href: "/dashboard/watershed.html", active: "watershed.html", icon: "💧", label: "Water Shed" },
  { href: "/dashboard/geo-images.html", active: "geo-images.html", icon: "📍", label: "Geo Tagged Images" },
  { href: "/dashboard/report.html", active: "report.html", icon: "📝", label: "Reports" },
  { href: "/dashboard/report-status.html", active: "report-status.html", icon: "📊", label: "Report Status" },
  { href: "/dashboard/chatbot.html", active: "chatbot.html", icon: "💬", label: "Chatbot" },
];

function renderSidebar(activeHref) {
  const nav = NAV_ITEMS.map(item => `
    <a class="nav-link ${item.active === activeHref ? "active" : ""}" href="${item.href}">
      <span class="nav-icon">${item.icon}</span>${item.label}
    </a>`).join("");

  return `
  <aside class="sidebar">
    <div class="brand">ECORA<span>.</span><small>TRACK · ANALYZE · GROW</small></div>
    <nav class="nav-links">${nav}</nav>
    <a class="logout-link" href="${logoutUrl()}">⏻ Logout</a>
  </aside>`;
}

function mountShell(activeHref, mainHtml) {
  document.getElementById("app").innerHTML = `
    <div class="app-shell">
      ${renderSidebar(activeHref)}
      <main class="main">${mainHtml}</main>
    </div>`;
}

async function apiGet(path) {
  const selectedLocation = JSON.parse(localStorage.getItem("ecoraSelectedLocation") || "null");
  const separator = path.includes("?") ? "&" : "?";
  const locationQuery = selectedLocation?.name ? `${separator}location=${encodeURIComponent(selectedLocation.name)}` : "";
  const res = await fetch(`${API_BASE}${path}${locationQuery}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// Logout must pass through Flask to clear the authentication session, then
// return to the visual explore.html landing page currently being used.
document.addEventListener("click", async (event) => {
  const logout = event.target.closest(".logout-link");
  if (!logout) return;
  event.preventDefault();
  window.location.assign(logoutUrl());
});
