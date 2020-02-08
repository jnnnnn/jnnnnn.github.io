import { size } from "./model.js";

const drawNode = state => n => {
  const ctx = state.mutables.ctx;

  ctx.beginPath();
  const radius = size(n);
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = n.col || "#ddd";
  ctx.strokeStyle = n.col || "#ddd";
  ctx.lineWidth = radius / 10;
  n.fixed ? ctx.fill() : ctx.stroke();

  drawText(state)(n, size(n) * 2);
};

const drawText = state => (obj, fontSize) => {
  const ctx = state.mutables.ctx;
  ctx.fillStyle = "black";
  ctx.font = fontSize + "px Arial";
  ctx.textAlign = "center";

  if (!obj.lines) obj.lines = obj.text.split("\n");
  obj.lines.forEach((line, index) => {
    ctx.fillText(line, obj.x, obj.y + index * fontSize);
  });
};

const drawEdge = state => e => {
  const ctx = state.mutables.ctx;

  ctx.beginPath();

  const x1 = e.source.x;
  const y1 = e.source.y;
  const x2 = e.target.x;
  const y2 = e.target.y;

  const r1 = size(e.source);
  const r2 = size(e.target);

  const dx = x2 - x1;
  const dy = y2 - y1;
  const mag = Math.sqrt(dx * dx + dy * dy);
  const sthatx = dx / mag;
  const sthaty = dy / mag;
  const ux = x1 + 3 * r1 * sthatx;
  const uy = y1 + 3 * r1 * sthaty;
  const ax = ux - r1 * sthaty;
  const ay = uy + r1 * sthatx;
  const bx = ux + r1 * sthaty;
  const by = uy - r1 * sthatx;
  const cx = x2 - 3 * r2 * sthatx;
  const cy = y2 - 3 * r2 * sthaty;

  ctx.moveTo(ax, ay);
  ctx.lineTo(bx, by);
  ctx.lineTo(cx, cy);
  ctx.fillStyle = "#0003";
  ctx.fill();

  if (e.text) {
    e.x = 0.5 * (ux + cx);
    e.y = 0.5 * (uy + cy);
    const fontSize = 2 * Math.min(size(e.source), size(e.target));
    drawText(state)(e, fontSize);
  }
};

const drawSelection = state => ctx => {
  const n = state.selected;
  if (!n) return;
  ctx.beginPath();
  const radius = size(n);
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = "rgba(255, 0, 0, 0.2)";
  ctx.fill();
};

export const draw = state => () => {
  const { transform, mutables } = state;
  const { ctx, width, height } = mutables;

  ctx.save();

  ctx.clearRect(0, 0, width, height);
  drawOverlay(ctx);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  state.edges.forEach(drawEdge(state));
  state.nodes.forEach(drawNode(state));
  drawSelection(state)(ctx);

  ctx.restore();
};

const defaultFont = Number(
  getComputedStyle(document.body, null).fontSize.replace(/[^\d]/g, "")
);

const drawOverlay = ctx => {
  ctx.fillStyle = "black";
  ctx.font = defaultFont + "px Arial";
  ctx.textAlign = "left";
  ctx.fillText("For help, press /", 0, defaultFont);
};
