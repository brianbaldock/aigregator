// Tiny hash-based router for /bbs/.
// Routes are registered as { pattern: RegExp, render: (params, ctx) => HTMLContent }
// HTMLContent can be a string (assigned to mount.innerHTML) or an element.

const routes = [];

export function route(pattern, render) {
  routes.push({ pattern, render });
}

export function navigate(hash) {
  if (!hash.startsWith("#")) hash = "#" + hash;
  if (location.hash === hash) {
    // Force re-render even if hash unchanged
    handle();
  } else {
    location.hash = hash;
  }
}

function parseHash() {
  return location.hash.replace(/^#\/?/, "") || "";
}

let mountEl = null;
let context = {};
let currentCleanup = null;

export function start(mount, ctx, defaultPath) {
  mountEl = mount;
  context = ctx || {};
  window.addEventListener("hashchange", handle);
  if (!location.hash || location.hash === "#") {
    location.hash = "#/" + (defaultPath || "");
  } else {
    handle();
  }
}

function handle() {
  if (typeof currentCleanup === "function") {
    try { currentCleanup(); } catch (_) {}
    currentCleanup = null;
  }
  const path = parseHash();
  for (const r of routes) {
    const m = path.match(r.pattern);
    if (m) {
      const params = m.slice(1);
      const result = r.render(params, context);
      applyResult(result);
      return;
    }
  }
  // Fallback
  mountEl.textContent = `\nROUTE NOT FOUND: /${path}\n\n[B] BACK TO MENU`;
}

function applyResult(result) {
  if (result == null) return;
  if (typeof result === "string") {
    mountEl.innerHTML = result;
    return;
  }
  if (result instanceof Node) {
    mountEl.replaceChildren(result);
    return;
  }
  if (typeof result === "object") {
    if (result.html != null) mountEl.innerHTML = result.html;
    if (typeof result.cleanup === "function") currentCleanup = result.cleanup;
  }
}
