import { findNodeAtCoords, mutate, mutateNode } from "./model.js";

export const keydown = state => key => {
  const target = findNodeAtCoords(state)(state.mouse); // maybe null
  const source = state.selected;
  switch (key) {
    case "s":
      select(state)(target);
      break;
    case "l":
      link(state)(source, target);
      break;
    case "u":
      unlink(state)(source, target);
      break;
    case "e":
      edit(state)(source, target);
      break;
  }
};

const select = state => target => {
  mutate(state)({ selected: target });
};

const link = state => (source, target) => {
  if (target && source && target !== source) {
    addEdge(state)(source, target);
  }
};

const addEdge = state => (source, target) => {
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

  updateEdges(state)([...state.edges, { source, target }]);
};

const updateEdges = state => edges => {
  mutate(state)({ edges });
  state.simulation.force("link").links(state.edges);
  state.simulation.alpha(0.3).restart();
};

const unlink = state => (source, target) => {
  if (target && source && target !== source) {
    removeEdge(state)(source, target);
  }
};

const removeEdge = state => (source, target) => {
  const fewerEdges = state.edges.filter(
    e =>
      !(
        (e.source === source && e.target === target) ||
        (e.target === source && e.source == target)
      )
  );
  updateEdges(state)(fewerEdges);
};

const edit = state => (source, target) => {
  const node = target || source;
  if (!node) return;

  const textarea = document.createElement("textarea");
  textarea.className = "centered";
  textarea.value = node.text;
  d3.event.stopPropagation(); // we don't need this but here for reference
  d3.event.preventDefault(); // this stops the "keypress" event getting triggered and adding an e to the value
  document.body.append(textarea);
  textarea.focus();
  textarea.select();

  textarea.onblur = focusEvent => {
    mutateNode(state)(node, { text: textarea.value });
    textarea.remove();
  };
};
