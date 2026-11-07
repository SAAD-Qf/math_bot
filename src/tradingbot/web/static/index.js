/* Control panel: parameters, replay/backtest launch, calculator, validation, history. */
(function () {
  "use strict";

  const datasets = window.__TB_DATASETS__ || [];
  const form = document.getElementById("run-form");
  const formError = document.getElementById("form-error");
  const datasetSelect = document.getElementById("dataset");
  const datasetHint = document.getElementById("dataset-hint");

  function showError(message) {
    if (!formError) return;
    formError.textContent = message;
    formError.hidden = false;
  }

  function clearError() {
    if (formError) formError.hidden = true;
  }

  function numberValue(id) {
    const el = document.getElementById(id);
    return el ? Number(el.value) : 0;
  }

  function textValue(id, fallback) {
    const el = document.getElementById(id);
    return el ? el.value : fallback;
  }

  function checked(id) {
    const el = document.getElementById(id);
    return Boolean(el && el.checked);
  }

  function collectParams() {
    return {
      dataset: datasetSelect.value,
      left_window: numberValue("left_window"),
      right_window: numberValue("right_window"),
      min_separation: numberValue("min_separation"),
      min_distance: textValue("min_distance", "0"),
      direction: textValue("direction", "both"),
      target_mode: textValue("target_mode", "high_low_reach"),
      target_projection: textValue("target_projection", "c_anchored_ratio"),
      invalidation_rule: textValue("invalidation_rule", "reference"),
      max_candles_active: numberValue("max_candles_active"),
      allow_overlapping: checked("allow_overlapping"),
      allow_same_candle_activation: checked("allow_same_candle_activation"),
      max_active_setups: numberValue("max_active_setups"),
      fee: textValue("fee", "0"),
      slippage: textValue("slippage", "0"),
      spread: textValue("spread", "0"),
      speed: numberValue("speed"),
    };
  }

  function updateDatasetHint() {
    if (!datasetHint || !datasetSelect || !datasetSelect.value) return;
    const item = datasets.find(function (d) { return d.name === datasetSelect.value; });
    if (!item) { datasetHint.textContent = ""; return; }
    const first = item.first_timestamp ? TB.fmtTime(item.first_timestamp) : "—";
    const last = item.last_timestamp ? TB.fmtTime(item.last_timestamp) : "—";
    datasetHint.textContent = item.candle_count + " candles · " + first + " → " + last;
  }

  if (datasetSelect) {
    datasetSelect.addEventListener("change", updateDatasetHint);
    updateDatasetHint();
  }

  if (form) {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearError();
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      try {
        const payload = collectParams();
        const response = await TB.fetchJSON("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        window.location.href = "/runs/" + encodeURIComponent(response.run_id);
      } catch (error) {
        showError(error.message);
        if (button) button.disabled = false;
      }
    });
  }

  const instantButton = document.getElementById("instant-btn");
  if (instantButton) {
    instantButton.addEventListener("click", async function () {
      clearError();
      instantButton.disabled = true;
      try {
        const payload = collectParams();
        delete payload.speed;
        const response = await TB.fetchJSON("/api/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        window.location.href = "/runs/" + encodeURIComponent(response.run_id);
      } catch (error) {
        showError(error.message);
        instantButton.disabled = false;
      }
    });
  }

  // --- target calculator -------------------------------------------------
  const calcForm = document.getElementById("calc-form");
  const calcOutput = document.getElementById("calc-output");
  if (calcForm) {
    calcForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      try {
        const data = await TB.fetchJSON("/api/calculate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            a: document.getElementById("calc-a").value,
            b: document.getElementById("calc-b").value,
            c: document.getElementById("calc-c").value,
          }),
        });
        calcOutput.textContent = data.lines.join("\n");
      } catch (error) {
        calcOutput.textContent = "Error: " + error.message;
      }
    });
  }

  // --- upload validation --------------------------------------------------
  const validateForm = document.getElementById("validate-form");
  const validateResult = document.getElementById("validate-result");
  if (validateForm) {
    validateForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const fileInput = document.getElementById("validate-file");
      if (!fileInput.files || !fileInput.files.length) {
        validateResult.hidden = false;
        validateResult.textContent = "Choose a CSV file first.";
        return;
      }
      validateResult.hidden = false;
      validateResult.textContent = "Validating…";
      const body = new FormData();
      body.append("file", fileInput.files[0]);
      try {
        const report = await TB.fetchJSON("/api/validate", { method: "POST", body: body });
        const lines = [
          (report.is_valid ? "PASSED" : "INVALID") + " · " + report.name,
          "Rows: " + report.row_count + " · Candles: " + report.candle_count,
          "Chronologically sorted: " + report.sorted,
        ];
        if (report.duplicates_removed) lines.push("Duplicates removed: " + report.duplicates_removed);
        if (report.first_timestamp) {
          lines.push("Range: " + TB.fmtTime(report.first_timestamp) + " → " + TB.fmtTime(report.last_timestamp));
        }
        (report.warnings || []).forEach(function (warning) { lines.push("Warning: " + warning); });
        (report.errors || []).forEach(function (error) { lines.push("Error: " + error); });
        validateResult.textContent = lines.join("\n");
      } catch (error) {
        validateResult.textContent = "Error: " + error.message;
      }
    });
  }

  // --- run history --------------------------------------------------------
  const historyBody = document.getElementById("run-history-body");
  async function loadHistory() {
    if (!historyBody) return;
    try {
      const data = await TB.fetchJSON("/api/runs");
      if (!data.runs.length) {
        historyBody.innerHTML = '<tr><td colspan="7" class="empty">No runs yet.</td></tr>';
        return;
      }
      historyBody.innerHTML = data.runs.map(function (run) {
        const metrics = run.metrics || {};
        return "<tr>" +
          '<td><a href="/runs/' + encodeURIComponent(run.run_id) + '">' + TB.escapeHTML(run.run_id) + "</a></td>" +
          "<td>" + TB.escapeHTML(run.dataset) + "</td>" +
          "<td>" + TB.escapeHTML(run.mode) + "</td>" +
          '<td><span class="status status-' + TB.statusSafe(run.status) + '">' + TB.escapeHTML(run.status) + "</span></td>" +
          '<td class="num">' + TB.fmtNumber(metrics.total_setups, 0) + "</td>" +
          '<td class="num">' + TB.fmtPct(metrics.target_hit_rate_pct) + "</td>" +
          '<td class="muted">' + TB.fmtDate(run.created_at) + "</td>" +
          "</tr>";
      }).join("");
    } catch (error) {
      historyBody.innerHTML = '<tr><td colspan="7" class="empty">Could not load history: ' + TB.escapeHTML(error.message) + "</td></tr>";
    }
  }
  const refreshHistory = document.getElementById("refresh-history");
  if (refreshHistory) refreshHistory.addEventListener("click", loadHistory);
  loadHistory();
})();
