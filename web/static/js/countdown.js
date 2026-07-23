(function () {
  "use strict";

  const consoleEl = document.getElementById("console");
  if (!consoleEl) return;

  const slug = consoleEl.dataset.slug;
  const els = {
    days: document.getElementById("d-days"),
    hours: document.getElementById("d-hours"),
    minutes: document.getElementById("d-minutes"),
    seconds: document.getElementById("d-seconds"),
    subtitle: document.getElementById("subtitle"),
    digits: document.getElementById("digits"),
    liveBanner: document.getElementById("live-banner"),
  };

  // Seed from the server-rendered data attributes so the very first paint
  // (and every render thereafter, even if a later /api/countdowns sync
  // fails or momentarily doesn't include this slug) is correct immediately
  // — the countdown no longer depends entirely on a fetch() resolving
  // before it can show anything other than 00:00:00:00.
  let targetMs = consoleEl.dataset.target ? new Date(consoleEl.dataset.target).getTime() : null;
  let liveMessage = consoleEl.dataset.liveMessage || null;
  let finished = false;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function renderRemaining() {
    if (finished) return;
    if (targetMs === null || Number.isNaN(targetMs)) return;

    const diff = targetMs - Date.now();
    if (diff <= 0) {
      finish();
      return;
    }

    const totalSeconds = Math.floor(diff / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    els.days.textContent = pad(days);
    els.hours.textContent = pad(hours);
    els.minutes.textContent = pad(minutes);
    els.seconds.textContent = pad(seconds);
  }

  function finish() {
    finished = true;
    els.digits.style.display = "none";
    els.subtitle.style.display = "none";
    els.liveBanner.hidden = false;
    consoleEl.classList.add("console-live");
  }

  async function syncFromServer() {
    try {
      const res = await fetch("/api/countdowns", { cache: "no-store" });
      const list = await res.json();
      const item = list.find((c) => c.slug === slug);
      if (!item) return;

      liveMessage = item.live_message;

      if (item.status === "completed" || item.total_seconds <= 0) {
        finish();
        return;
      }

      targetMs = new Date(item.target_datetime_utc).getTime();
    } catch (err) {
      // Network hiccup: keep ticking locally from the last known target.
      console.warn("MOFIX countdown sync failed, retrying shortly.", err);
    }
  }

  // Render immediately from the server-embedded data (no flash of zeros),
  // then tick every second locally for a smooth display, and re-sync with
  // the server periodically so the timer never drifts and reacts to admin
  // edits (new target time, stop/start, completion, etc).
  if (consoleEl.dataset.status === "completed") {
    finish();
  } else {
    renderRemaining();
  }
  syncFromServer().then(renderRemaining);
  setInterval(renderRemaining, 1000);
  setInterval(syncFromServer, 20000);
})();
