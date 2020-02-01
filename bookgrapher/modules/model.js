export const findNodeAtCoords = state => ({ x, y }) => {
  for (let node of state.nodes) {
    const radius = node.radius || 5;
    const dx = x - node.x;
    const dy = y - node.y;
    if (dx * dx + dy * dy < radius * radius) {
      return node;
    }
  }
};
