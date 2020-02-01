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

export const size = node => 40 / Math.pow(2, node.level || 12);
