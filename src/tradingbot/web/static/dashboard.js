/* Replay dashboard: consumes engine events, never invents strategy numbers. */
(function () {
  "use strict";

  const runId = (window.__TB_RUN__ || {}).runId;
  if (!runId) return;

  const $ = function (id) { return document.getElementById(id); };
  const chart = new window.PriceChart($("price-chart"));
  const setups = new Map();
  const setupOrder = [];
  const updatedIds = new Set();
  let warnings = [];
  let lastSeq = -1;
  let status = "loading";
  let mode = "replay";
  let sawDone = false;
  let finished = false;
  let resultLoaded = false;
  let resultLoading = false;
  let lastActiveCount = 0;
  let progressTotal = 0;
  let currentSpeed = 10;
  let stream = null;
  let pollHandle = null;
  let sort = { key: "setup_id", dir: 1 };

  const signalBody = $("signals-body");
  const detailDialog = $("detail-dialog");

  function showError(message) {
    const el = $("run-error");
    if (!el) return;
    el.textContent = message;
    el.hidden = !message;
  }

  function setStatus(nextStatus) {
    status = nextStatus || status;
    const el = $("run-status");
    if (!el) return;
    const label = status === "finished" && mode === "replay" && !sawDone ? "stopped" : status;
    el.className = "status status-" + TB.statusSafe(label);
    el.textContent = String(label).replace(/_/g, " ");
    updateControls();
  }

  function updateControls() {
    const start = $("start-btn");
    const pause = $("pause-btn");
    const step = $("step-btn");
    const stop = $("stop-btn");
    const done = ["finished", "failed"].includes(status);
    if (start) start.disabled = done || status === "replaying";
    if (pause) pause.disabled = status !== "replaying";
    if (step) step.disabled = done || status === "replaying";
    if (stop) stop.disabled = done;
  }

  function setProgress(progress) {
    if (!progress) return;
    const total = Number(progress.total || progressTotal || 0);
    const index = Number(progress.index || 0);
    progressTotal = total;
    const pct = total ? Math.min(100, (index / total) * 100) : 0;
    const bar = $("run-progress-bar");
    const box = $("run-progress");
    if (bar) bar.style.width = pct.toFixed(2) + "%";
    if (box) box.setAttribute("aria-valuenow", pct.toFixed(0));
    const text = $("run-progress-text");
    if (text) text.textContent = index.toLocaleString() + " / " + total.toLocaleString() + " candles";
  }

  function setHeader(dataset, params, total) {
    if (dataset) {
      $("run-dataset").textContent = dataset;
      document.title = dataset + " · Replay · Mathematical Trading Bot";
    }
    const bits = [];
    bits.push(mode);
    if (total) bits.push(total.toLocaleString() + " candles");
    const summary = TB.paramSummary(params);
    if (summary) bits.push(summary);
    if (params && params.direction && params.direction !== "both") bits.push(params.direction + " only");
    $("run-subtitle").textContent = bits.join(" · ");
  }

  function setCurrentCandle(event) {
    const el = $("current-candle");
    if (!el) return;
    el.textContent =
      "candle " + (event.index + 1) + " · " + TB.fmtTime(event.candle.timestamp);
    lastActiveCount = Number(event.active_count || 0);
  }

  function renderMetrics(metrics) {
    const m = metrics || {};
    $("kpi-total").textContent = TB.fmtNumber(m.total_setups, 0);
    $("kpi-active").textContent = TB.fmtNumber(
      finished ? m.still_active_at_end : lastActiveCount, 0
    );
    const activeLabel = $("kpi-active-label");
    if (activeLabel) activeLabel.textContent = finished ? "Still active at end" : "Active now";
    $("kpi-hit").textContent = TB.fmtPct(m.target_hit_rate_pct);
    $("kpi-invalidation").textContent = TB.fmtPct(m.invalidation_rate_pct);
    $("kpi-completion").textContent = TB.fmtPct(m.completion_rate_pct);
    $("kpi-duration").textContent = TB.fmtDuration((m.duration || {}).avg_ms);
    $("kpi-frequency").textContent = TB.fmtNumber(m.setup_frequency_per_100_candles, 2);
    renderDirections(m);
  }

  function renderDirections(metrics) {
    const m = metrics || {};
    [["long", "direction-long"], ["short", "direction-short"]].forEach(function ([key, id]) {
      const block = m[key] || {};
      const el = $(id);
      if (!el) return;
      el.innerHTML = [
        ["Total", TB.fmtNumber(block.total, 0)],
        ["Target reached", TB.fmtNumber(block.target_reached, 0)],
        ["Invalidated", TB.fmtNumber(block.invalidated, 0)],
        ["Expired", TB.fmtNumber(block.expired, 0)],
        ["Hit rate", TB.fmtPct(block.target_hit_rate_pct)],
      ].map(function ([label, value]) {
        return "<dt>" + label + "</dt><dd>" + value + "</dd>";
      }).join("");
    });
  }

  function renderWarnings() {
    const list = $("warnings-list");
    const count = $("warning-count");
    if (count) count.textContent = String(warnings.length);
    if (!list) return;
    if (!warnings.length) {
      list.innerHTML = '<li class="empty">None.</li>';
      return;
    }
    list.innerHTML = warnings.slice(0, 200).map(function (warning) {
      return "<li><span class=\"mono\">candle " + TB.escapeHTML(warning.index) +
        "</span> · " + TB.escapeHTML(warning.text) + "</li>";
    }).join("");
  }

  function renderAssumptions(assumptions) {
    const list = $("assumptions-list");
    if (!list) return;
    if (!assumptions || !Object.keys(assumptions).length) {
      list.innerHTML = '<dd class="empty">No assumptions recorded.</dd>';
      return;
    }
    list.innerHTML = Object.keys(assumptions).map(function (key) {
      const value = assumptions[key];
      const text = typeof value === "object" && value !== null
        ? JSON.stringify(value, null, 2)
        : String(value);
      return "<dt>" + TB.escapeHTML(key) + "</dt><dd>" + TB.escapeHTML(text) + "</dd>";
    }).join("");
  }

  function setupValue(setup, key) {
    return setup[key] ? Number(setup[key].value) : null;
  }

  function sortValue(setup, key) {
    if (key === "status") return setup.final_status || "";
    if (key === "direction") return setup.direction || "";
    if (key === "monitored") return Number(setup.candles_monitored || 0);
    if (key === "mfe") return Number(setup.max_favorable_excursion || 0);
    if (key === "mae") return Number(setup.max_adverse_excursion || 0);
    if (key === "setup_id") return Number(setup.setup_id || 0);
    if (key === "target") return Number(setup.target || 0);
    return setupValue(setup, key) || 0;
  }

  function rowHTML(setup) {
    const meta = setup.setup_metadata || {};
    const fmtPoint = function (point) {
      if (!point) return "—";
      return '<span class="num">' + TB.fmtNumber(point.value, 6) + "</span>" +
        '<span class="sub">idx ' + TB.escapeHTML(point.candle_index ?? "—") + "</span>";
    };
    const mfe = Number(setup.max_favorable_excursion || 0) * 100;
    const mae = Number(setup.max_adverse_excursion || 0) * 100;
    return '<tr data-setup-id="' + TB.escapeHTML(setup.setup_id) + '" tabindex="0" role="button"' +
      (updatedIds.has(setup.setup_id) ? ' class="updated"' : "") + ">" +
      '<td class="num">' + TB.escapeHTML(setup.setup_id ?? "—") + "</td>" +
      "<td>" + TB.directionHTML(setup.direction) + "</td>" +
      "<td>" + fmtPoint(setup.a) + "</td>" +
      "<td>" + fmtPoint(setup.b) + "</td>" +
      "<td>" + fmtPoint(setup.c) + "</td>" +
      '<td class="num">' + TB.fmtNumber(setup.target, 6) + "</td>" +
      '<td class="num">' + TB.fmtNumber(meta.price_target, 6) + "</td>" +
      "<td>" + TB.statusHTML(setup.final_status) + "</td>" +
      '<td class="num">' + TB.fmtNumber(setup.candles_monitored, 0) + "</td>" +
      '<td class="num">' + TB.fmtNumber(mfe, 2) + "%</td>" +
      '<td class="num">' + TB.fmtNumber(mae, 2) + "%</td>" +
      '<td class="num">' + TB.fmtNumber(setup.cost_impact, 6) + "</td>" +
      "</tr>";
  }

  function renderSignals() {
    if (!signalBody) return;
    const direction = $("filter-direction").value;
    const statusFilter = $("filter-status").value;
    let list = setupOrder.map(function (id) { return setups.get(id); }).filter(Boolean);
    if (direction !== "all") list = list.filter(function (s) { return s.direction === direction; });
    if (statusFilter !== "all") list = list.filter(function (s) { return s.final_status === statusFilter; });
    list.sort(function (a, b) {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      if (av < bv) return -1 * sort.dir;
      if (av > bv) return 1 * sort.dir;
      return Number(a.setup_id || 0) - Number(b.setup_id || 0);
    });
    $("signal-count").textContent = "(" + setups.size + ")";
    if (!list.length) {
      signalBody.innerHTML = '<tr><td colspan="12" class="empty">' +
        (setups.size ? "No signals match these filters." : "No signals yet — press Start or Step.") +
        "</td></tr>";
      return;
    }
    signalBody.innerHTML = list.map(rowHTML).join("");
  }

  function touchSetup(setup) {
    if (setup.setup_id === null || setup.setup_id === undefined) return;
    if (!setups.has(setup.setup_id)) setupOrder.push(setup.setup_id);
    setups.set(setup.setup_id, setup);
    chart.setSetup(setup);
    updatedIds.add(setup.setup_id);
    window.setTimeout(function () {
      updatedIds.delete(setup.setup_id);
      const row = signalBody && signalBody.querySelector('tr[data-setup-id="' + setup.setup_id + '"]');
      if (row) row.classList.remove("updated");
    }, 1150);
  }

  function applyStateChanges(changes) {
    (changes || []).forEach(function (change) {
      if (change.setup) touchSetup(change.setup);
    });
  }

  function applyEvent(event) {
    if (!event) return;
    if (event.seq !== undefined) {
      if (Number(event.seq) <= lastSeq) return;
      lastSeq = Number(event.seq);
    }
    if (event.type === "candle") {
      chart.setCandle(Number(event.index), event.candle);
      applyStateChanges(event.state_changes);
      (event.warnings || []).forEach(function (text) {
        warnings.unshift({ index: event.index, text: text });
      });
      if (warnings.length > 500) warnings = warnings.slice(0, 500);
      setCurrentCandle(event);
      setProgress(event.progress);
      renderMetrics(event.metrics);
      renderWarnings();
      renderSignals();
      chart.draw();
    } else if (event.type === "done") {
      sawDone = true;
      finished = true;
      lastActiveCount = Number((event.metrics || {}).still_active_at_end || lastActiveCount);
      renderMetrics(event.metrics);
      setStatus("finished");
      setProgress(event.progress);
      closeStream();
      loadFullResult();
    } else if (event.type === "error") {
      showError(event.message || "Replay failed.");
      setStatus("failed");
      closeStream();
    }
  }

  function applyState(state) {
    if (!state) return;
    mode = state.mode || mode;
    currentSpeed = Number(state.speed || currentSpeed);
    const speedRange = $("speed-range");
    const speedValue = $("speed-value");
    if (speedRange) speedRange.value = String(Math.round(currentSpeed));
    if (speedValue) speedValue.textContent = String(Math.round(currentSpeed));
    setHeader(state.dataset, state.params, state.progress && state.progress.total);
    setProgress(state.progress);
    if (state.error) showError(state.error);
    const alreadyDone = finished || sawDone;
    (state.events || []).forEach(applyEvent);
    if (state.status === "finished" || state.status === "failed") {
      finished = true;
      setStatus(state.status);
      if (mode === "backtest" || sawDone) {
        loadFullResult();
      } else if (!alreadyDone) {
        // A stopped replay has no final result; keep the partial metrics visible.
        showError("Replay stopped before completion. Partial metrics are shown; artifacts are unavailable.");
        setStatus("finished");
      }
    } else {
      setStatus(state.status || (sawDone ? "finished" : "paused"));
    }
    updateControls();
  }

  async function loadFullResult() {
    if (resultLoaded || resultLoading) return;
    resultLoading = true;
    try {
      const data = await TB.fetchJSON("/api/runs/" + encodeURIComponent(runId));
      resultLoaded = true;
      hydrateFromResult(data);
    } catch (error) {
      if (error.status === 409) {
        showError("Run has not produced a final result yet.");
      } else {
        showError(error.message);
      }
    } finally {
      resultLoading = false;
    }
  }

  function hydrateFromResult(data) {
    finished = true;
    sawDone = true;
    mode = data.mode || mode;
    setups.clear();
    setupOrder.length = 0;
    (data.setup_results || []).forEach(function (setup) {
      setups.set(setup.setup_id, setup);
      setupOrder.push(setup.setup_id);
      chart.setSetup(setup);
    });
    if (data.candles && data.candles.length) chart.setCandles(data.candles);
    warnings = (data.warnings || []).map(function (text) {
      const match = /^Candle (\d+):/.exec(text);
      return { index: match ? match[1] : "final", text: text };
    }).reverse();
    if (data.dataset) {
      const strategy = (data.config || {}).strategy || {};
      const params = Object.assign({}, data.config || {}, strategy.detector || {});
      setHeader(data.dataset.name, params, data.dataset.candle_count);
      setProgress({ index: data.dataset.candle_count, total: data.dataset.candle_count });
      const current = $("current-candle");
      if (current) {
        current.textContent = "candle " + data.dataset.candle_count + " · " + TB.fmtTime(data.dataset.last_timestamp);
      }
    } else {
      setProgress({ index: progressTotal, total: progressTotal });
    }
    renderMetrics(data.metrics);
    renderWarnings();
    renderSignals();
    renderAssumptions(data.assumptions);
    renderDirections(data.metrics);
    setStatus("finished");
    enableDownloads();
    chart.draw();
  }

  function enableDownloads() {
    const links = [
      ["download-png", "/api/runs/" + encodeURIComponent(runId) + "/chart.png"],
      ["download-json", "/api/runs/" + encodeURIComponent(runId) + "/report.json"],
      ["download-csv", "/api/runs/" + encodeURIComponent(runId) + "/report.csv"],
      ["download-md", "/api/runs/" + encodeURIComponent(runId) + "/report.md"],
    ];
    links.forEach(function ([id, href]) {
      const link = $(id);
      if (!link) return;
      link.href = href;
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
    });
  }

  // --- signal detail dialog ---------------------------------------------
  function openDetail(setupId) {
    const setup = setups.get(Number(setupId));
    if (!setup || !detailDialog) return;
    $("detail-title").textContent = "Signal #" + setup.setup_id + " · " + setup.direction;
    const meta = setup.setup_metadata || {};
    const transitions = (setup.state_transitions || []).map(function (t) {
      return "<li><strong>" + TB.escapeHTML(String(t.previous_state).replace(/_/g, " ")) +
        " → " + TB.escapeHTML(String(t.new_state).replace(/_/g, " ")) + "</strong>" +
        '<span class="sub">' + TB.fmtTime(t.timestamp) + " · candle " +
        TB.escapeHTML(t.candle_index ?? "—") + "</span>" +
        '<span class="reason">' + TB.escapeHTML(t.reason || "") + "</span></li>";
    }).join("");
    const arithmetic =
      "TARGET = (B + C) / A\n" +
      "       = (" + setup.b.value + " + " + setup.c.value + ") / " + setup.a.value + "\n" +
      "       = " + setup.target;
    $("detail-body").innerHTML =
      '<div class="detail-grid">' +
        '<div class="detail-block"><h3>Mathematical target</h3>' +
          '<pre class="arithmetic">' + TB.escapeHTML(arithmetic) + "</pre>" +
          "<p>Projected price target (interpretation): <strong>" +
          TB.escapeHTML(meta.price_target ?? "—") + "</strong></p></div>" +
        '<div class="detail-block"><h3>Points</h3><ul class="transition-list">' +
          ["a", "b", "c"].map(function (key) {
            const point = setup[key] || {};
            return "<li><strong>" + key.toUpperCase() + " = " + TB.escapeHTML(point.value ?? "—") +
              '</strong><span class="sub">' + TB.fmtTime(point.timestamp) + " · candle " +
              TB.escapeHTML(point.candle_index ?? "—") + "</span></li>";
          }).join("") + "</ul></div>" +
        '<div class="detail-block"><h3>Outcome</h3><ul class="transition-list">' +
          "<li><strong>Status</strong>" + TB.statusHTML(setup.final_status) + "</li>" +
          '<li><strong>Activated</strong><span class="sub">' + TB.fmtTime(setup.activated_at) + "</span></li>" +
          '<li><strong>Completed</strong><span class="sub">' + TB.fmtTime(setup.completed_at) + "</span></li>" +
          '<li><strong>Monitored</strong><span class="sub">' + TB.escapeHTML(setup.candles_monitored) + " candles</span></li>" +
          '<li><strong>MFE / MAE</strong><span class="sub">' +
          (Number(setup.max_favorable_excursion || 0) * 100).toFixed(2) + "% / " +
          (Number(setup.max_adverse_excursion || 0) * 100).toFixed(2) + "%</span></li>" +
          '<li><strong>Cost impact</strong><span class="sub">' + TB.escapeHTML(setup.cost_impact) + "</span></li>" +
        "</ul></div>" +
        '<div class="detail-block"><h3>State transitions</h3>' +
          (transitions ? '<ul class="transition-list">' + transitions + "</ul>" : '<p class="muted">None recorded.</p>') +
        "</div>" +
      "</div>";
    detailDialog.showModal();
  }

  if (signalBody) {
    signalBody.addEventListener("click", function (event) {
      const row = event.target.closest("tr[data-setup-id]");
      if (row) openDetail(row.getAttribute("data-setup-id"));
    });
    signalBody.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      const row = event.target.closest("tr[data-setup-id]");
      if (!row) return;
      event.preventDefault();
      openDetail(row.getAttribute("data-setup-id"));
    });
  }

  // --- table controls ----------------------------------------------------
  ["filter-direction", "filter-status"].forEach(function (id) {
    const el = $(id);
    if (el) el.addEventListener("change", renderSignals);
  });
  document.querySelectorAll("[data-sort]").forEach(function (button) {
    button.addEventListener("click", function () {
      const key = button.getAttribute("data-sort");
      if (sort.key === key) sort.dir *= -1;
      else sort = { key: key, dir: 1 };
      renderSignals();
    });
  });

  // --- replay controls ---------------------------------------------------
  async function control(action, extra) {
    const body = Object.assign({ action: action }, extra || {});
    try {
      const state = await TB.fetchJSON("/api/runs/" + encodeURIComponent(runId) + "/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      applyState(state);
      if (action === "start") openStream();
      if (action === "stop") closeStream();
    } catch (error) {
      showError(error.message);
    }
  }

  const startButton = $("start-btn");
  const pauseButton = $("pause-btn");
  const stepButton = $("step-btn");
  const stopButton = $("stop-btn");
  if (startButton) startButton.addEventListener("click", function () { showError(""); control("start"); });
  if (pauseButton) pauseButton.addEventListener("click", function () { control("pause"); });
  if (stepButton) stepButton.addEventListener("click", function () { control("step"); });
  if (stopButton) stopButton.addEventListener("click", function () { control("stop"); });

  const speedRange = $("speed-range");
  if (speedRange) {
    speedRange.addEventListener("input", function () {
      const label = $("speed-value");
      if (label) label.textContent = speedRange.value;
    });
    speedRange.addEventListener("change", function () {
      control("speed", { speed: Number(speedRange.value) });
    });
  }

  // --- SSE with polling fallback ----------------------------------------
  function openStream() {
    if (stream || finished || typeof window.EventSource === "undefined") {
      if (!finished) startPolling();
      return;
    }
    stream = new EventSource("/api/runs/" + encodeURIComponent(runId) + "/stream");
    stream.addEventListener("candle", function (event) {
      try { applyEvent(JSON.parse(event.data)); } catch (_) { /* ignore malformed frame */ }
    });
    stream.addEventListener("done", function (event) {
      try { applyEvent(JSON.parse(event.data)); } catch (_) { /* ignore */ }
    });
    stream.addEventListener("error", function () {
      // EventSource retries automatically; if the run is still active, poll as a
      // deterministic fallback so a proxy that buffers SSE cannot stall the UI.
      if (!finished) startPolling();
    });
  }

  function closeStream() {
    if (stream) {
      stream.close();
      stream = null;
    }
    if (pollHandle) {
      window.clearTimeout(pollHandle);
      pollHandle = null;
    }
  }

  function startPolling() {
    if (pollHandle || finished) return;
    pollHandle = window.setTimeout(async function () {
      pollHandle = null;
      try {
        const state = await TB.fetchJSON(
          "/api/runs/" + encodeURIComponent(runId) + "/state?since=" + (lastSeq + 1)
        );
        applyState(state);
      } catch (error) {
        showError(error.message);
      }
      if (!finished) startPolling();
    }, 650);
  }

  // --- run comparison ----------------------------------------------------
  let compareRuns = [];
  function metric(run, key) {
    return ((run && run.metrics) || {})[key];
  }
  function compareRow(label, accessor) {
    const a = $("compare-a").value;
    const b = $("compare-b").value;
    const runA = compareRuns.find(function (run) { return run.run_id === a; });
    const runB = compareRuns.find(function (run) { return run.run_id === b; });
    return "<tr><td>" + label + "</td><td>" +
      TB.escapeHTML(accessor(runA) ?? "—") + "</td><td>" +
      TB.escapeHTML(accessor(runB) ?? "—") + "</td></tr>";
  }
  function renderCompare() {
    const body = $("compare-body");
    const a = $("compare-a").value;
    const b = $("compare-b").value;
    if (!body) return;
    if (!a || !b) {
      body.innerHTML = '<tr><td colspan="3" class="empty">Choose two runs to compare.</td></tr>';
      return;
    }
    body.innerHTML = [
      compareRow("Dataset", function (r) { return r && r.dataset; }),
      compareRow("Mode", function (r) { return r && r.mode; }),
      compareRow("Status", function (r) { return r && r.status; }),
      compareRow("Total setups", function (r) { return TB.fmtNumber(metric(r, "total_setups"), 0); }),
      compareRow("Target hit rate", function (r) { return TB.fmtPct(metric(r, "target_hit_rate_pct")); }),
      compareRow("Invalidation rate", function (r) { return TB.fmtPct(metric(r, "invalidation_rate_pct")); }),
      compareRow("Completion rate", function (r) { return TB.fmtPct(metric(r, "completion_rate_pct")); }),
      compareRow("Still active at end", function (r) { return TB.fmtNumber(metric(r, "still_active_at_end"), 0); }),
      compareRow("Avg duration", function (r) {
        return TB.fmtDuration(((metric(r, "duration") || {}).avg_ms));
      }),
      compareRow("Setups / 100 candles", function (r) {
        return TB.fmtNumber(metric(r, "setup_frequency_per_100_candles"), 2);
      }),
    ].join("");
  }
  async function loadCompareRuns() {
    try {
      const data = await TB.fetchJSON("/api/runs");
      compareRuns = data.runs || [];
      const a = $("compare-a");
      const b = $("compare-b");
      if (!a || !b) return;
      const currentA = a.value;
      const currentB = b.value;
      const options = compareRuns.map(function (run) {
        return '<option value="' + TB.escapeHTML(run.run_id) + '">' +
          TB.escapeHTML(run.run_id) + " · " + TB.escapeHTML(run.dataset) +
          " · " + TB.escapeHTML(run.mode) + "</option>";
      }).join("");
      a.innerHTML = '<option value="">Select a run…</option>' + options;
      b.innerHTML = '<option value="">Select a run…</option>' + options;
      a.value = currentA || runId;
      b.value = currentB || (compareRuns.length > 1 ? compareRuns.find(function (r) { return r.run_id !== runId; })?.run_id || "" : "");
      renderCompare();
    } catch (_) { /* comparison is optional */ }
  }

  ["compare-a", "compare-b"].forEach(function (id) {
    const el = $(id);
    if (el) el.addEventListener("change", renderCompare);
  });

  // --- boot --------------------------------------------------------------
  (async function boot() {
    try {
      const state = await TB.fetchJSON("/api/runs/" + encodeURIComponent(runId) + "/state?since=0");
      applyState(state);
      updateControls();
      if (state.status !== "finished" && state.status !== "failed") {
        if (state.status === "replaying") openStream();
      }
    } catch (error) {
      showError(error.message);
      setStatus("failed");
    }
    loadCompareRuns();
  })();
})();
