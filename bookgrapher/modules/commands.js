import {
  findNodeAtCoords,
  mutate,
  mutateNode,
  undo,
  redo,
  addNode,
  removeEdge,
  addEdge,
  removeNode,
  findEdge,
  mutateEdge
} from "./model.js";
import { draw } from "./draw.js";
import { save, importState } from "./save.js";

export const keydown = state => key => {
  const target = findNodeAtCoords(state)(state.mutables.mouse); // maybe null
  const source = state.selected;
  switch (key) {
    case "c":
      state.command = !state.command;
    case "s":
      if (d3.event.ctrlKey) {
        event.preventDefault();
        save(state);
      } else select(state)(source, target);
      break;
    case "l":
      editEdge(state)(source, target);
      break;
    case "u":
      unlink(state)(source, target);
      break;
    case "e":
      editNode(state)(source, target);
      break;
    case "z":
    case "Z":
      if (d3.event.ctrlKey && d3.event.shiftKey) redo(state);
      else if (d3.event.ctrlKey) undo(state);
      resetSimulation(state)();
      break;
    case "Delete":
    case "Backspace":
    case "D":
    case "d":
      d3.event.preventDefault();
      if (d3.event.shiftKey) deleteAll(state);
      else remove(state)(source, target);
      break;
    case "+":
      resize(state)(-1)(source, target);
      break;
    case "-":
      resize(state)(+1)(source, target);
      break;
    case "f":
      fix(state)(source, target);
      break;
    case "r":
      resetZoom(state);
      break;
    case "/":
      showHelp();
      break;
    default:
      numberAction(state)(key);
  }
};

const numberAction = state => key => {
  switch (key) {
    case "0":
    case "1":
    case "2":
    case "3":
    case "4":
    case "5":
    case "6":
    case "7":
    case "8":
    case "9":
      const newval = (state.mutables.settings.commandstr || "") + key;
      state.mutables.settings.commandstr = newval;
      if (searchSelect(state)(newval)) {
        state.mutables.settings.commandstr = "";
      }
      break;
    case "Escape":
      state.mutables.settings.commandstr = "";
      break;
  }
  console.log("No command for ", key, d3.event);
};

const searchSelect = state => keystr => {
  const target = state.nodes.find(n => n.id == keystr);
  if (target) {
    select(state)(null, target);
  }
  return !!target;
};

const showHelp = () => {
  window.location =
    "https://github.com/jnnnnn/jnnnnn.github.io/tree/master/bookgrapher";
};

const deleteAll = state => {
  mutate(state)({ nodes: [], edges: [] });
  resetSimulation(state)();
};

const resetZoom = state => {
  d3.select(state.mutables.canvas).call(
    state.mutables.zoom.transform,
    d3.zoomIdentity
  );
  draw(state)();
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
    level: Math.min(Math.max(node.level + delta, -3), 10)
  });
  resetSimulation(state)(0);
};

const select = state => (source, target) => {
  mutate(state)({ selected: target });
  resetSimulation(state)(0);
};

const remove = state => (source, target) => {
  const node = target || source;
  if (node) {
    removeNode(state)(node);
    resetSimulation(state)();
  }
};

const editEdge = state => (source, target) => {
  if (!(target && source && target !== source)) return;

  const existing = findEdge(state)(source, target);

  promptText({
    placeholder: "Edge label",
    startText: existing ? existing.text : "",
    confirm: value => {
      if (existing)
        mutateEdge(state)(existing, { source, target, text: value });
      else addEdge(state)(source, target, { text: value });
      resetSimulation(state)();
    }
  });
};

const unlink = state => (source, target) => {
  if (target && source && target !== source) {
    removeEdge(state)(source, target);
    resetSimulation(state)();
  }
};

const editNode = state => (source, target) => {
  // save mouse coords for create later
  const coords = state.mutables.mouse;

  promptText({
    placeholder: "Node label",
    startText: target ? target.text : "",
    confirm: value => {
      if (target) mutateNode(state)(target, { text: value });
      else addNode(state)({ text: value, ...coords }, source);
      resetSimulation(state)();
    }
  });
};

const promptText = ({ startText, confirm, cancel, placeholder }) => {
  // we might create it here but it is not added to the model until confirm
  const textarea = document.createElement("textarea");
  textarea.className = "centered";
  textarea.value = startText;
  document.getElementById("graphDiv").append(textarea);
  textarea.focus();
  textarea.select();
  textarea.placeholder = placeholder;
  // stop this keyDown generating a keyPress and overwriting the value with "e"
  d3.event.preventDefault();

  const abort = () => {
    textarea.remove();
    if (cancel) cancel();
  };
  textarea.onblur = abort;

  textarea.onkeydown = keyEvent => {
    if (keyEvent.key === "Escape") abort();
    if (keyEvent.key === "Enter" && !keyEvent.shiftKey) {
      confirm(textarea.value);
      textarea.remove();
    }
    // stop key presses from triggering other commands by bubbling up to the body
    keyEvent.stopPropagation();
  };
};

export const resetSimulation = state => (energy = 0.3) => {
  state.simulation.nodes(state.nodes);
  state.simulation.force("link").links(state.edges);
  if (energy > 0) state.simulation.alpha(energy).restart();
  else draw(state)();
};

export const mousemove = state => () => {
  const [screenX, screenY] = d3.mouse(d3.event.currentTarget);
  state.mutables.mouse = {
    x: state.transform.invertX(screenX),
    y: state.transform.invertY(screenY)
  };
};

export const dropFile = state => async dropEvent => {
  // don't want to load a json file as a document. I almost feel like this is
  // something the browser should do.
  dropEvent.preventDefault();

  const json = await dropEvent.dataTransfer.files[0].text();
  const importedState = importState(JSON.parse(json));
  mutate(state)(importedState);
  resetSimulation(state)();
};

const fix = state => (source, target) => {
  const node = target || source;
  if (!node) return;
  const fixed = !node.fixed;
  mutateNode(state)(node, {
    fixed,
    fx: fixed ? node.x : null,
    fy: fixed ? node.y : null
  });
  resetSimulation(state)(0);
};
