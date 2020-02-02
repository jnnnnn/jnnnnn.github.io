import {
  findNodeAtCoords,
  mutate,
  mutateNode,
  undo,
  addNode,
  removeEdge,
  addEdge
} from "./model.js";

export const keydown = state => key => {
  const target = findNodeAtCoords(state)(state.mouse); // maybe null
  const source = state.selected;
  switch (key) {
    case "s":
      select(state)(source, target);
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
    case "Delete":
    case "Backspace":
      remove(state)(source, target);
      break;
    default:
      console.log("No command for ", key, d3.event);
  }
};

const select = state => (source, target) => {
  mutate(state)({ selected: target });
};

const link = state => (source, target) => {
  if (target && source && target !== source) {
    addEdge(state)(source, target);
  }
};

const unlink = state => (source, target) => {
  if (target && source && target !== source) {
    removeEdge(state)(source, target);
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
  };
  textarea.onblur = finishEditing;

  textarea.onkeydown = keyEvent => {
    if (keyEvent.key === "Escape") textarea.remove();
    if (keyEvent.key === "Enter" && keyEvent.ctrlKey) finishEditing();
    // stop key presses from triggering other commands by bubbling up to the body
    keyEvent.stopPropagation();
  };
};

const remove = state => (source, target) => {};
