import { size } from "./model.js";

const drawNode = state => n => {
  const ctx = state.mutables.ctx;

  if (!n.fixed) {
    ctx.beginPath();
    const radius = size(n);
    ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
    ctx.fillStyle = n.col || "#ddd";
    ctx.fill();
  }
  ctx.fillStyle = "black";
  ctx.font = size(n) * 2 + "px Arial";
  ctx.textAlign = "center";
  ctx.fillText(n.text, n.x, n.y);
};

const drawEdge = ctx => e => {
  ctx.beginPath();
  ctx.moveTo(e.source.x, e.source.y);
  ctx.lineTo(e.target.x, e.target.y);
  ctx.strokeStyle = "#ddd";
  ctx.stroke();
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

  state.edges.forEach(drawEdge(ctx));
  state.nodes.forEach(drawNode(state));
  drawSelection(state)(ctx);

  ctx.restore();
};
