import {
  findNodeAtCoords,
  mutate,
  mutateNode,
  undo,
  addNode
} from "./model.js";

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
    case "z":
      undo(state);
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
  // we might create it here but it is not added to the model until finishEditing
  const textarea = document.createElement("textarea");
  textarea.className = "centered";
  textarea.value = target ? target.text : "";
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  // stop this keyDown generating a keyPress and overwriting the value with "e"
  d3.event.preventDefault();

  const finishEditing = () => {
    if (target) mutateNode(state)(target, { text: textarea.value });
    else addNode(state)({ text: textarea.value }, source);
    textarea.remove();
  };
  textarea.onblur = finishEditing;

  textarea.onkeydown = keyEvent => {
    if (keyEvent.key === "Escape") textarea.remove();
    if (keyEvent.key === "Enter" && keyEvent.ctrlKey) finishEditing();
    // stop key presses from triggering other commands by bubbling up to the body
    keyEvent.stopPropagation();
  };
};
