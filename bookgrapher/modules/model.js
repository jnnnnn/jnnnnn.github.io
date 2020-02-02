export const findNodeAtCoords = state => ({ x, y }) => {
  for (let node of state.nodes) {
    const radius = size(node);
    const dx = x - node.x;
    const dy = y - node.y;
    if (dx * dx + dy * dy < radius * radius) {
      return node;
    }
  }
};

const stateHistory = [];

export const undo = state => {
  const restoredState = stateHistory.pop();
  Object.assign(state, restoredState);
  resetSimulation(state);
};

// Not quite properly implemented but good enough. Ideally it would not be
// possible to touch things that are conceptually immutable but that would
// result in more levels of indirection so nah.
export const mutate = state => stateMapper => {
  const oldState = { ...state };
  stateHistory.push(oldState);
  switch (typeof stateMapper) {
    case "function":
      Object.assign(state, stateMapper(oldState));
      break;
    case "object":
      Object.assign(state, stateMapper);
      break;
    default:
      throw "Invalid state assignment";
  }
};

export const mutateNode = state => (node, values) => {
  const node2 = { ...node, ...values };
  const nodes = [...state.nodes];
  const i = nodes.indexOf(node);
  if (i < 0) throw "node to update not found";
  nodes[i] = node2;

  mutate(state)({
    nodes,
    edges: replaceNodeInEdges(state.edges, node, node2),
    selected: state.selected === node ? node2 : state.selected
  });

  resetSimulation(state);
};

const resetSimulation = state => {
  state.simulation.nodes(state.nodes);
  state.simulation.force("link").links(state.edges);
  state.simulation.alpha(0.3).restart();
};

const replaceNodeInEdges = (edges, oldNode, newNode) => {
  return edges.map(edge => {
    if (edge.source === oldNode)
      return { source: newNode, target: edge.target };
    else if (edge.target === oldNode)
      return { source: edge.source, target: newNode };
    else return edge;
  });
};

export const size = node => 40 / Math.pow(2, node.level || 12);
