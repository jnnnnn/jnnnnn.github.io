import {
  findNodeAtCoords,
  mutate,
  mutateNode,
  undo,
  addNode,
  removeEdge,
  addEdge,
  removeNode
} from "./model.js";
import { draw } from "./draw.js";
import { save } from "./save.js";

export const keydown = state => key => {
  const target = findNodeAtCoords(state)(state.mouse); // maybe null
  const source = state.selected;
  switch (key) {
    case "s":
      if (d3.event.ctrlKey) {
        event.preventDefault();
        save(state);
      } else select(state)(source, target);
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
      resetSimulation(state)();
      break;
    case "Delete":
    case "Backspace":
    case "d":
      remove(state)(source, target);
      break;
    case "+":
      resize(state)(-1)(source, target);
      break;
    case "-":
      resize(state)(+1)(source, target);
      break;
    default:
      console.log("No command for ", key, d3.event);
  }
};

export const click = state => () => {
  const modelCoords = {
    x: state.transform.invertX(d3.event.x),
    y: state.transform.invertY(d3.event.y)
  };
  const target = state.simulation.find(modelCoords.x, modelCoords.y);
  if (target) select(state)(null, target);
};

const resize = state => delta => (source, target) => {
  const node = target || source;
  if (!node) return;
  mutateNode(state)(node, {
    ...node,
    level: Math.min(Math.max(node.level + delta, 1), 10)
  });
  resetSimulation(state)(0);
};

const select = state => (source, target) => {
  mutate(state)({ selected: target });
  resetSimulation(state)(0);
};

const remove = state => (source, target) => {
  if (target) {
    removeNode(state)(target);
    resetSimulation(state)();
  }
};

const link = state => (source, target) => {
  if (target && source && target !== source) {
    addEdge(state)(source, target);
    resetSimulation(state)();
  }
};

const unlink = state => (source, target) => {
  if (target && source && target !== source) {
    removeEdge(state)(source, target);
    resetSimulation(state)();
  }
};

const edit = state => (source, target) => {
  // we might create it here but it is not added to the model until finishEditing
  const textarea = document.createElement("textarea");
  // save mouse coords for create later
  const coords = state.mouse;
  textarea.className = "centered";
  textarea.value = target ? target.text : "";
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  // stop this keyDown generating a keyPress and overwriting the value with "e"
  d3.event.preventDefault();

  const finishEditing = () => {
    if (target) mutateNode(state)(target, { text: textarea.value });
    else addNode(state)({ text: textarea.value, ...coords }, source);
    textarea.remove();
    resetSimulation(state)();
  };
  textarea.onblur = finishEditing;

  textarea.onkeydown = keyEvent => {
    if (keyEvent.key === "Escape") textarea.remove();
    if (keyEvent.key === "Enter" && keyEvent.ctrlKey) finishEditing();
    // stop key presses from triggering other commands by bubbling up to the body
    keyEvent.stopPropagation();
  };
};

const resetSimulation = state => (energy = 0.3) => {
  state.simulation.nodes(state.nodes);
  state.simulation.force("link").links(state.edges);
  if (energy > 0) state.simulation.alpha(energy).restart();
  else draw(state)();
};
