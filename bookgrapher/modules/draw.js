const drawNode = state => n => {
  const { ctx } = state;
  ctx.beginPath();
  const radius = n.radius || 5;
  ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = n === state.selected ? "red" : n.col || "#ddd";
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

const drawOverlay = (ctx, state) => {};
const drawSelection = (ctx, state) => {
  ctx.fillText("mouse", state.mouse.x, state.mouse.y);
};

export const draw = state => () => {
  const { transform, ctx, width, height } = state;

  ctx.save();

  ctx.clearRect(0, 0, width, height);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  state.edges.forEach(drawEdge(ctx));
  state.nodes.forEach(drawNode(state));
  drawSelection(ctx, state);

  ctx.restore();

  ctx.save();
  drawOverlay(ctx, state);
  ctx.restore();
};
