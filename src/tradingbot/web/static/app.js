/* Shared formatters/helpers for the local research dashboard. */
(function () {
  "use strict";

  const TB = {};

  TB.fetchJSON = async function (url, options) {
    const response = await fetch(url, options);
    const text = await response.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = { error: text }; }
    }
    if (!response.ok) {
      const message = (data && (data.error || data.detail)) || response.statusText;
      const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
      error.status = response.status;
      throw error;
    }
    return data;
  };

  TB.escapeHTML = function (value) {
    return String(value ?? "").replace(/[&<>"']/g, function (ch) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
    });
  };

  TB.fmtNumber = function (value, digits) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    const places = digits === undefined ? 4 : digits;
    return number.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: places,
    });
  };

  TB.fmtPct = function (value) {
    if (value === null || value === undefined) return "0%";
    const number = Number(value);
    if (!Number.isFinite(number)) return "0%";
    return number.toFixed(number % 1 === 0 ? 0 : 2) + "%";
  };

  TB.fmtDuration = function (ms) {
    if (ms === null || ms === undefined || !Number.isFinite(Number(ms))) return "—";
    let value = Number(ms);
    if (value < 1000) return Math.round(value) + " ms";
    value /= 1000;
    if (value < 120) return value.toFixed(1) + " s";
    value /= 60;
    if (value < 120) return value.toFixed(1) + " min";
    value /= 60;
    if (value < 72) return value.toFixed(1) + " h";
    return (value / 24).toFixed(1) + " d";
  };

  TB.fmtTime = function (timestamp) {
    if (timestamp === null || timestamp === undefined) return "—";
    const date = new Date(Number(timestamp));
    if (Number.isNaN(date.getTime())) return String(timestamp);
    return date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
  };

  TB.shortTime = function (timestamp) {
    if (timestamp === null || timestamp === undefined) return "—";
    const date = new Date(Number(timestamp));
    if (Number.isNaN(date.getTime())) return String(timestamp);
    return date.toISOString().slice(5, 16).replace("T", " ");
  };

  TB.fmtDate = function (iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString();
  };

  TB.statusSafe = function (status) {
    return String(status || "pending").replace(/[^a-z_]/gi, "").toLowerCase();
  };

  TB.statusHTML = function (status) {
    const safe = TB.statusSafe(status);
    return '<span class="status status-' + safe + '">' + TB.escapeHTML(String(status).replace(/_/g, " ")) + "</span>";
  };

  TB.directionHTML = function (direction) {
    const safe = String(direction || "").toLowerCase() === "short" ? "short" : "long";
    return '<span class="status status-' + safe + '">' + safe + "</span>";
  };

  TB.paramSummary = function (params) {
    if (!params) return "";
    const parts = [];
    if (params.left_window !== undefined) {
      parts.push("L" + params.left_window + "/R" + params.right_window + "/S" + params.min_separation);
    }
    if (params.target_mode) parts.push(params.target_mode);
    if (params.target_projection) parts.push(params.target_projection);
    return parts.join(" · ");
  };

  TB.setVisible = function (el, visible) {
    if (el) el.hidden = !visible;
  };

  window.TB = TB;
})();
