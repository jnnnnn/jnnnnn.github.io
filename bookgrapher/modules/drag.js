export const dragstarted = state => () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0.3).restart();
  }
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

export const dragged = state => () => {
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

export const dragended = state => () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0);
  }
  d3.event.subject.fx = null;
  d3.event.subject.fy = null;
};

export const dragsubject = state => () => {
  const { transform } = state;
  for (let node of state.nodes) {
    const dx = transform.invertX(d3.event.x) - node.x;
    const dy = transform.invertY(d3.event.y) - node.y;
    const radius = node.radius || 5;

    if (dx * dx + dy * dy < radius * radius) {
      node.x = transform.applyX(node.x);
      node.y = transform.applyY(node.y);

      return node;
    }
  }
};
