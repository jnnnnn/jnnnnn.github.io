const drawNode = state => n => {
  const { ctx } = state;
  ctx.beginPath();
  const radius = n.radius || 5;
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = n.col || "#ddd";
  ctx.fill();

  ctx.fillStyle = "black";
  ctx.font = 40 / Math.pow(2, n.level) + "px Arial";
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

const drawOverlay = state => ctx => {};
const drawSelection = state => ctx => {
  const n = state.selected;
  if (!n) return;
  ctx.beginPath();
  const radius = (n.radius || 5) * 2;
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = "rgba(255, 0, 0, 0.2)";
  ctx.fill();
};

export const draw = state => () => {
  const { transform, ctx, width, height } = state;

  ctx.save();

  ctx.clearRect(0, 0, width, height);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  state.edges.forEach(drawEdge(ctx));
  state.nodes.forEach(drawNode(state));
  drawSelection(state)(ctx);

  ctx.restore();

  ctx.save();
  drawOverlay(ctx, state);
  ctx.restore();
};
