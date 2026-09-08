/**
 * Runs on every authenticated page.
 *
 * Opens the one socket, wires the shared chrome (notification bell, presence
 * rail, tabs), and gets out of the way. Per-page modules load separately and
 * subscribe to the bus.
 */

import { api } from "./api.js";
import { bus } from "./bus.js";
import { store } from "./store.js";
import { toast } from "./toast.js";
import { realtime } from "../realtime/realtime-client.js";
import { initTabs } from "./tabs.js";

async function boot() {
  if (!store.user) return; // login page — nothing to boot

  initTabs();
  initLogout();

  if (store.features.notifications) {
    const { initNotifications } = await import("../features/notifications.js");
    initNotifications();
  }

  if (store.features.presence) {
    const { initPresence } = await import("../features/presence.js");
    initPresence();
  }

  // A visible signal when the connection drops. Silence during an outage is
  // how a user ends up trusting a stale screen.
  let offlineToast = null;
  bus.on("realtime:closed", () => {
    // TEMPORARILY DISABLED: Suppress "Reconnecting..." toast on cPanel
    // if (!offlineToast) {
    //   offlineToast = toast.warning("Reconnecting…", { timeout: 0 });
    // }
  });
  bus.on("realtime:open", () => {
    if (offlineToast) {
      offlineToast();
      offlineToast = null;
    }
  });

  realtime.connect();
}

function initLogout() {
  const form = document.getElementById("logout-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api.post("/auth/logout/");
    } finally {
      // Redirect regardless: if the request failed, the local session is
      // still the thing we want gone.
      realtime.close();
      window.location.href = "/login/";
    }
  });
}

document.addEventListener("DOMContentLoaded", boot);

// Exposed for the browser console during development.
window.__ops = { api, bus, store, realtime, toast };
