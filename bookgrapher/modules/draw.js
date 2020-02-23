import { size } from "./model.js";

const drawNodeCircle = (ctx, n) => {
  ctx.beginPath();
  const radius = size(n);
  ctx.fillStyle = n.col || "#aaa";
  ctx.strokeStyle = n.col || "#aaa";
  ctx.lineWidth = radius / 10;
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);

  n.fixed ? ctx.fill() : ctx.stroke();
};

const drawNode = state => n => {
  const ctx = state.mutables.ctx;

  if (!state.mutables.cmd.present) {
    drawNodeCircle(ctx, n);
  }

  drawText(state)(n, size(n) * 2);

  if (state.mutables.cmd.on) {
    ctx.fillText(n.id, n.x, n.y - size(n) * 2);
  }
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

const drawEdgeArrow = state => e => {
  const ctx = state.mutables.ctx;

  ctx.beginPath();

  const x1 = e.target.x;
  const y1 = e.target.y;
  const x2 = e.source.x;
  const y2 = e.source.y;

  const r1 = size(e.target);
  const r2 = size(e.source);

  const dx = x2 - x1;
  const dy = y2 - y1;
  const mag = Math.sqrt(dx * dx + dy * dy);
  const sthatx = dx / mag;
  const sthaty = dy / mag;
  const ex = x1 + 3 * r1 * sthatx;
  const ey = y1 + 3 * r1 * sthaty;
  const ux = x1 + 4 * r1 * sthatx;
  const uy = y1 + 4 * r1 * sthaty;
  const ax = ux - r1 * sthaty;
  const ay = uy + r1 * sthatx;
  const bx = ux + r1 * sthaty;
  const by = uy - r1 * sthatx;
  const cx = x2 - 3 * r2 * sthatx;
  const cy = y2 - 3 * r2 * sthaty;

  ctx.moveTo(ex, ey);
  ctx.lineTo(ax, ay);
  ctx.moveTo(ex, ey);
  ctx.lineTo(bx, by);
  ctx.moveTo(ex, ey);
  ctx.lineTo(cx, cy);
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#0008";
  ctx.stroke();

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
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  if (!state.mutables.cmd.present) {
    drawOrigin(state)(ctx);
  }

  state.edges.forEach(drawEdgeArrow(state));
  state.nodes.forEach(drawNode(state));

  drawSelection(state)(ctx);

  ctx.restore();

  drawOverlay(state)(ctx);
};

const defaultFont = Number(
  getComputedStyle(document.body, null).fontSize.replace(/[^\d]/g, "")
);

const drawOverlay = state => ctx => {
  ctx.fillStyle = state.mutables.cmd.on ? "red" : "black";
  ctx.font = defaultFont + "px Arial";
  ctx.textAlign = "left";
  ctx.fillText("For help, press /", 0, defaultFont);

  if (state.mutables.cmd.on) {
    let i = 2;
    for (const [key, value] of Object.entries(state.mutables.cmd)) {
      ctx.fillText(`${key}: ${JSON.stringify(value)}`, 0, defaultFont * i++);
    }
  }
};

const drawOrigin = state => ctx => {
  ctx.beginPath();
  ctx.moveTo(-100, 0);
  ctx.lineTo(100, 0);
  ctx.moveTo(0, -100);
  ctx.lineTo(0, 100);
  ctx.strokeStyle = "#0088";
  ctx.lineWidth = 1 / state.transform.k;
  ctx.stroke();
};
