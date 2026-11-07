/* Client-side canvas candlestick chart. Server PNG remains the downloadable artifact. */
(function () {
  "use strict";

  const MAX_VISIBLE = 500;
  const COLORS = {
    up: "#3fb950",
    down: "#ff6b6b",
    grid: "rgba(142, 162, 186, 0.14)",
    text: "#8ea2ba",
    target: "#ff6b6b",
    a: "#b48cff",
    b: "#ff9f43",
    c: "#c8a27a",
    reached: "#3fb950",
    invalidated: "#8ea2ba",
    expired: "#e3b341",
  };

  function num(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function PriceChart(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.candles = [];
    this.lastIndex = -1;
    this.setups = new Map();
    this.tsIndex = new Map();
    this.empty = document.getElementById("chart-empty");
    this._resize = this.resize.bind(this);
    window.addEventListener("resize", this._resize);
    if (window.ResizeObserver) {
      this._observer = new ResizeObserver(this._resize);
      this._observer.observe(canvas.parentElement || canvas);
    }
    this.resize();
  }

  PriceChart.prototype.resize = function () {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(200, rect.width || 800);
    const height = Math.max(200, rect.height || 380);
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.width = width;
    this.height = height;
    this.draw();
  };

  PriceChart.prototype.setCandle = function (index, candle) {
    const parsed = {
      timestamp: Number(candle.timestamp),
      open: num(candle.open),
      high: num(candle.high),
      low: num(candle.low),
      close: num(candle.close),
      volume: num(candle.volume),
    };
    if (parsed.open === null || parsed.high === null || parsed.low === null || parsed.close === null) return;
    this.candles[index] = parsed;
    this.lastIndex = Math.max(this.lastIndex, index);
    this.tsIndex.set(parsed.timestamp, index);
  };

  PriceChart.prototype.setCandles = function (candles) {
    candles.forEach(function (candle, index) { this.setCandle(index, candle); }, this);
    this.draw();
  };

  PriceChart.prototype.setSetup = function (setup) {
    if (!setup || setup.setup_id === null || setup.setup_id === undefined) return;
    this.setups.set(setup.setup_id, setup);
    this.draw();
  };

  PriceChart.prototype.draw = function () {
    const ctx = this.ctx;
    if (!ctx) return;
    ctx.clearRect(0, 0, this.width, this.height);
    if (this.lastIndex < 0) {
      if (this.empty) this.empty.hidden = false;
      return;
    }
    if (this.empty) this.empty.hidden = true;

    const pad = { left: 54, right: 16, top: 16, bottom: 28 };
    const plotW = this.width - pad.left - pad.right;
    const plotH = this.height - pad.top - pad.bottom;
    if (plotW <= 10 || plotH <= 10) return;

    const start = Math.max(0, this.lastIndex - MAX_VISIBLE + 1);
    const end = this.lastIndex;
    let min = Infinity;
    let max = -Infinity;
    for (let i = start; i <= end; i += 1) {
      const candle = this.candles[i];
      if (!candle) continue;
      if (candle.low < min) min = candle.low;
      if (candle.high > max) max = candle.high;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return;
    const range = Math.max(max - min, Math.abs(max) * 0.001, 1e-9);
    const padding = range * 0.08;
    min -= padding;
    max += padding;
    const priceToY = (price) => pad.top + ((max - price) / (max - min)) * plotH;
    const indexToX = (index) => pad.left + ((index - start + 0.5) / (end - start + 1)) * plotW;
    const candleWidth = Math.max(1, Math.min(12, (plotW / (end - start + 1)) * 0.62));

    // Horizontal grid + price labels.
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillStyle = COLORS.text;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let g = 0; g <= 4; g += 1) {
      const price = min + ((max - min) * g) / 4;
      const y = priceToY(price);
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(this.width - pad.right, y);
      ctx.stroke();
      ctx.fillText(price.toFixed(price >= 100 ? 1 : 4), pad.left - 7, y);
    }

    // Candles.
    for (let i = start; i <= end; i += 1) {
      const candle = this.candles[i];
      if (!candle) continue;
      const x = indexToX(i);
      const color = candle.close >= candle.open ? COLORS.up : COLORS.down;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, priceToY(candle.high));
      ctx.lineTo(x, priceToY(candle.low));
      ctx.stroke();
      const openY = priceToY(candle.open);
      const closeY = priceToY(candle.close);
      const top = Math.min(openY, closeY);
      const bodyHeight = Math.max(1, Math.abs(closeY - openY));
      ctx.fillRect(x - candleWidth / 2, top, candleWidth, bodyHeight);
    }

    // Target levels (dashed) and outcome markers, drawn under the A/B/C labels.
    ctx.setLineDash([5, 4]);
    this.setups.forEach((setup) => {
      const meta = setup.setup_metadata || {};
      const target = num(meta.price_target);
      if (target === null) return;
      const startIndex = setup.a && setup.a.candle_index !== null
        ? Number(setup.a.candle_index) : Math.max(0, start);
      if (startIndex > end) return;
      let endIndex = end;
      const terminalTs = setup.completed_at || setup.reached_at || setup.invalidated_at || setup.expiry_at;
      if (terminalTs) {
        const mapped = this.tsIndex.get(Number(terminalTs));
        if (mapped !== undefined) endIndex = mapped;
      }
      if (endIndex < start) return;
      const visible = target >= min && target <= max;
      if (visible) {
        const y = priceToY(target);
        ctx.strokeStyle = COLORS.target;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(indexToX(Math.max(start, startIndex)), y);
        ctx.lineTo(indexToX(Math.min(end, endIndex)), y);
        ctx.stroke();
      } else if (target > max) {
        ctx.strokeStyle = "rgba(255,107,107,0.5)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(indexToX(Math.max(start, startIndex)), pad.top + 1);
        ctx.lineTo(indexToX(Math.min(end, endIndex)), pad.top + 1);
        ctx.stroke();
      }
    });
    ctx.setLineDash([]);

    // A/B/C markers.
    const markerSpecs = [
      ["a", COLORS.a, "^", "A"],
      ["b", COLORS.b, "v", "B"],
      ["c", COLORS.c, "o", "C"],
    ];
    this.setups.forEach((setup) => {
      markerSpecs.forEach(([key, color, shape, label]) => {
        const point = setup[key];
        if (!point || point.candle_index === null || point.candle_index === undefined) return;
        const index = Number(point.candle_index);
        if (index < start || index > end) return;
        const value = num(point.value);
        if (value === null) return;
        const x = indexToX(index);
        const y = priceToY(value);
        ctx.fillStyle = color;
        ctx.strokeStyle = "#0a1018";
        ctx.lineWidth = 1;
        ctx.beginPath();
        if (shape === "^") {
          ctx.moveTo(x, y - 7);
          ctx.lineTo(x - 5, y + 3);
          ctx.lineTo(x + 5, y + 3);
          ctx.closePath();
        } else if (shape === "v") {
          ctx.moveTo(x, y + 7);
          ctx.lineTo(x - 5, y - 3);
          ctx.lineTo(x + 5, y - 3);
          ctx.closePath();
        } else {
          ctx.arc(x, y, 4.5, 0, Math.PI * 2);
        }
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.font = "700 9px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = shape === "^" ? "bottom" : "top";
        ctx.fillText(label, x, shape === "^" ? y - 9 : y + 9);
      });

      const outcomes = [
        [setup.reached_at, "★", COLORS.reached],
        [setup.invalidated_at, "✕", COLORS.invalidated],
        [setup.expiry_at, "◼", COLORS.expired],
      ];
      outcomes.forEach(([timestamp, glyph, color]) => {
        if (!timestamp) return;
        const index = this.tsIndex.get(Number(timestamp));
        if (index === undefined || index < start || index > end) return;
        const candle = this.candles[index];
        if (!candle) return;
        ctx.fillStyle = color;
        ctx.font = "700 13px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(glyph, indexToX(index), priceToY(candle.close) - 14);
      });
    });

    // X-axis range labels (left/right aligned so long ranges never clip).
    ctx.fillStyle = COLORS.text;
    ctx.font = "10px ui-monospace, monospace";
    ctx.textBaseline = "top";
    const first = this.candles[start];
    const last = this.candles[end];
    if (first && last) {
      const y = this.height - pad.bottom + 7;
      ctx.textAlign = "left";
      ctx.fillText(window.TB.shortTime(first.timestamp), pad.left, y);
      ctx.textAlign = "right";
      ctx.fillText(
        window.TB.shortTime(last.timestamp) +
          (start > 0 ? "  (last " + (end - start + 1) + ")" : ""),
        this.width - pad.right,
        y
      );
    }
  };

  window.PriceChart = PriceChart;
})();
