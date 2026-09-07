/* Renders the campaign map onto the canvas: territory polygons, dice
   badges, selection glow, and valid-attack-target highlighting. */

const COLORS = {
  human: "#8c3a3a",
  humanLight: "#b25050",
  ai: "#3f6b80",
  aiLight: "#5c8ca3",
  ink: "#100d0a",
  water: "#141a26",
  glow: "#e0bb63",
};

class BoardRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.state = null;
    this.selectedId = null;
    this.hoverId = null;
    this.validTargets = new Set();
    this.pulsePhase = 0;
    this._animate = this._animate.bind(this);
    requestAnimationFrame(this._animate);
  }

  setState(state) {
    this.state = state;
    if (state) {
      const w = state.width, h = state.height;
      const scale = Math.min(900 / w, 640 / h);
      this.scale = scale;
      this.canvas.width = w * scale;
      this.canvas.height = h * scale;
    }
  }

  setSelection(id, validTargets) {
    this.selectedId = id;
    this.validTargets = new Set(validTargets || []);
  }

  hitTest(px, py) {
    if (!this.state) return null;
    const { x, y } = this._toWorld(px, py);
    for (const tid in this.state.territories) {
      const t = this.state.territories[tid];
      if (this._pointInPoly(x, y, t.polygon)) return t.id;
    }
    return null;
  }

  _toWorld(px, py) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;
    return { x: ((px - rect.left) * scaleX) / this.scale, y: ((py - rect.top) * scaleY) / this.scale };
  }

  _pointInPoly(x, y, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1];
      const xj = poly[j][0], yj = poly[j][1];
      const intersect = ((yi > y) !== (yj > y)) &&
        (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  _animate(ts) {
    this.pulsePhase = (ts / 500) % (Math.PI * 2);
    this.draw();
    requestAnimationFrame(this._animate);
  }

  draw() {
    const { ctx, canvas, state } = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!state) return;
    ctx.save();
    ctx.scale(this.scale, this.scale);

    // water backdrop
    ctx.fillStyle = COLORS.water;
    ctx.fillRect(0, 0, state.width, state.height);

    // island shadow
    this._drawPolyPath(state.island_outline);
    ctx.fillStyle = "rgba(0,0,0,0.25)";
    ctx.fill();

    const glowAmt = (Math.sin(this.pulsePhase) + 1) / 2;

    for (const tid in state.territories) {
      const t = state.territories[tid];
      this._drawTerritory(t, glowAmt);
    }

    ctx.restore();
  }

  _drawPolyPath(poly) {
    const ctx = this.ctx;
    ctx.beginPath();
    poly.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
    ctx.closePath();
  }

  _drawTerritory(t, glowAmt) {
    const ctx = this.ctx;
    const isSelected = t.id === this.selectedId;
    const isTarget = this.validTargets.has(t.id);
    const isHover = t.id === this.hoverId;

    const baseColor = t.owner === "human" ? COLORS.human : COLORS.ai;
    const lightColor = t.owner === "human" ? COLORS.humanLight : COLORS.aiLight;

    this._drawPolyPath(t.polygon);

    // subtle radial shading per territory for a hand-painted feel
    const grad = ctx.createRadialGradient(
      t.centroid[0], t.centroid[1], 4,
      t.centroid[0], t.centroid[1], 60
    );
    grad.addColorStop(0, isHover ? lightColor : baseColor);
    grad.addColorStop(1, baseColor);
    ctx.fillStyle = grad;
    ctx.fill();

    if (isTarget) {
      ctx.save();
      ctx.strokeStyle = COLORS.glow;
      ctx.lineWidth = 2 + glowAmt * 1.5;
      ctx.shadowColor = COLORS.glow;
      ctx.shadowBlur = 8 + glowAmt * 10;
      ctx.stroke();
      ctx.restore();
    }
    if (isSelected) {
      ctx.save();
      ctx.strokeStyle = "#fff6e0";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "#fff6e0";
      ctx.shadowBlur = 10;
      ctx.stroke();
      ctx.restore();
    }

    ctx.lineWidth = 1.1;
    ctx.strokeStyle = COLORS.ink;
    ctx.stroke();

    // dice badge
    const [cx, cy] = t.centroid;
    ctx.save();
    ctx.fillStyle = "rgba(20,15,10,0.82)";
    this._roundRect(cx - 15, cy - 11, 30, 22, 4);
    ctx.fill();
    ctx.strokeStyle = "rgba(224,187,99,0.7)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#f3e6c8";
    ctx.font = "600 13px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(t.dice, cx, cy + 1);
    ctx.restore();
  }

  _roundRect(x, y, w, h, r) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
}
