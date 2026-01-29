/**
 * Stock Monitor Dashboard - Charts Module
 * Canvas-based sparkline rendering for performance
 */

const Charts = (() => {
  // Get CSS variable value
  function getCSSVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // Colors
  const COLORS = {
    gain: null,
    loss: null,
    neutral: null
  };

  // Initialize colors after DOM loads
  function initColors() {
    COLORS.gain = getCSSVar('--gain') || '#00C853';
    COLORS.loss = getCSSVar('--loss') || '#FF1744';
    COLORS.neutral = getCSSVar('--neutral') || '#9E9E9E';
  }

  /**
   * Draw a sparkline on a canvas element
   * @param {HTMLCanvasElement} canvas - Canvas element to draw on
   * @param {number[]} data - Array of values
   * @param {number} change - Net change (determines color)
   * @param {Object} options - Optional configuration
   */
  function drawSparkline(canvas, data, change = 0, options = {}) {
    if (!canvas || !data || data.length < 2) {
      return;
    }

    // Ensure colors are initialized
    if (!COLORS.gain) {
      initColors();
    }

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    // Get dimensions from CSS or defaults
    const width = options.width || canvas.clientWidth || 80;
    const height = options.height || canvas.clientHeight || 24;

    // Set canvas size with DPR for sharp rendering
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    ctx.scale(dpr, dpr);

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Calculate data range
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1; // Avoid division by zero

    // Normalize data to 0-1
    const normalized = data.map(v => (v - min) / range);

    // Padding
    const padding = options.padding || 2;
    const drawWidth = width - padding * 2;
    const drawHeight = height - padding * 2;

    // Determine color based on change
    let strokeColor;
    if (change > 0) {
      strokeColor = COLORS.gain;
    } else if (change < 0) {
      strokeColor = COLORS.loss;
    } else {
      strokeColor = COLORS.neutral;
    }

    // Draw filled area under line (optional)
    if (options.fill !== false) {
      ctx.beginPath();
      ctx.moveTo(padding, height - padding);

      normalized.forEach((y, i) => {
        const x = padding + (i / (data.length - 1)) * drawWidth;
        const py = padding + (1 - y) * drawHeight;
        ctx.lineTo(x, py);
      });

      ctx.lineTo(padding + drawWidth, height - padding);
      ctx.closePath();

      ctx.fillStyle = strokeColor;
      ctx.globalAlpha = 0.1;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // Draw line
    ctx.beginPath();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = options.lineWidth || 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    normalized.forEach((y, i) => {
      const x = padding + (i / (data.length - 1)) * drawWidth;
      const py = padding + (1 - y) * drawHeight;

      if (i === 0) {
        ctx.moveTo(x, py);
      } else {
        ctx.lineTo(x, py);
      }
    });

    ctx.stroke();

    // Draw end point dot (optional)
    if (options.showEndPoint) {
      const lastY = normalized[normalized.length - 1];
      const endX = padding + drawWidth;
      const endY = padding + (1 - lastY) * drawHeight;

      ctx.beginPath();
      ctx.arc(endX, endY, 2, 0, Math.PI * 2);
      ctx.fillStyle = strokeColor;
      ctx.fill();
    }
  }

  /**
   * Draw a horizontal bar chart for sector performance
   * @param {HTMLElement} container - Container element
   * @param {Array} sectors - Array of sector data
   */
  function drawSectorChart(container, sectors) {
    if (!container || !sectors || sectors.length === 0) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state__message">No sector data available</p></div>';
      return;
    }

    // Sort sectors by change (descending)
    const sorted = [...sectors].sort((a, b) => b.change - a.change);

    // Find max absolute change for scaling
    const maxAbs = Math.max(...sorted.map(s => Math.abs(s.change)), 5);
    const scale = 50 / maxAbs; // 50% max width each direction

    // Build HTML
    const html = sorted.map(sector => {
      const isPositive = sector.change >= 0;
      const barWidth = Math.min(Math.abs(sector.change) * scale, 50);
      const barClass = isPositive ? 'sector-row__bar--positive' : 'sector-row__bar--negative';
      const valueClass = isPositive ? 'sector-row__value--positive' : 'sector-row__value--negative';
      const sign = isPositive ? '+' : '';

      return `
        <div class="sector-row">
          <span class="sector-row__name">${sector.name}</span>
          <div class="sector-row__bar-container">
            <div class="sector-row__bar-center"></div>
            <div class="sector-row__bar ${barClass}" style="width: ${barWidth}%;"></div>
          </div>
          <span class="sector-row__value ${valueClass}">${sign}${sector.change.toFixed(2)}%</span>
        </div>
      `;
    }).join('');

    container.innerHTML = html;
  }

  /**
   * Create a canvas element for sparklines
   */
  function createSparklineCanvas(width = 80, height = 24) {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    return canvas;
  }

  return {
    initColors,
    drawSparkline,
    drawSectorChart,
    createSparklineCanvas
  };
})();

// Initialize colors when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  Charts.initColors();
});
