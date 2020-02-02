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
};

// Not quite properly implemented but good enough. Ideally it would not be
// possible to touch things that are conceptually immutable but that would
// result in more levels of indirection so nah.
export const mutate = state => mutation => {
  const oldState = { ...state };
  stateHistory.push(oldState);
  switch (typeof mutation) {
    case "function":
      Object.assign(state, mutation(oldState));
      break;
    case "object":
      Object.assign(state, mutation);
      break;
    default:
      throw "Invalid state assignment";
  }
};

export const addNode = state => (values, parent) => {
  const newNode = createNode(state)(values, parent);
  mutate(state)({
    nodes: [...state.nodes, newNode],
    edges: parent
      ? [...state.edges, { source: parent, target: newNode }]
      : state.edges
  });
};

export const mutateNode = state => (node, mutation) => {
  const node2 = { ...node, ...mutation };
  const nodes = [...state.nodes];
  const i = nodes.indexOf(node);
  if (i < 0) throw "node to update not found";
  nodes[i] = node2;

  mutate(state)({
    nodes,
    edges: replaceNodeInEdges(state.edges, node, node2),
    selected: state.selected === node ? node2 : state.selected
  });
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

let largestId = 0;
export const createNode = state => (values, parent) => {
  // avoid collisions between node IDs by keeping track of the largest ID we've seen
  largestId = 1 + Math.max(largestId, ...state.nodes.map(n => n.id));

  return {
    id: largestId,
    level: parent ? parent.level + 1 : 1,
    ...values
  };
};

export const addEdge = state => (source, target) => {
  // don't add duplicate edges, it makes the simulation wonky
  if (
    state.edges.find(
      e =>
        (e.source === source && e.target === target) ||
        (e.target === source && e.source == target)
    )
  ) {
    return;
  }

  mutate(state)({ edges: [...state.edges, { source, target }] });
};

export const removeEdge = state => (source, target) => {
  const edges = state.edges.filter(
    e =>
      !(
        (e.source === source && e.target === target) ||
        (e.target === source && e.source == target)
      )
  );
  mutate(state)({ edges });
};

export const removeNode = state => node => {
  const edges = state.edges.filter(
    e => !(e.source === node || e.target === node)
  );
  const nodes = state.nodes.filter(n => n !== node);
  mutate(state)({ nodes, edges });
};
