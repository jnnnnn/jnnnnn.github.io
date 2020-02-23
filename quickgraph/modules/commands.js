import {
  findNodeAtCoords,
  mutate,
  mutateNode,
  undo,
  redo,
  removeEdge,
  addEdge,
  removeNode,
  findEdge,
  mutateEdge,
  createNode
} from "./model.js.js";
import { draw } from "./draw.js.js";
import { save, importState } from "./save.js.js";

export const keydown = state => key => {
  if (state.mutables.cmd.on && commandMode(state)(key)) {
    return;
  }
  const target = findNodeAtCoords(state)(state.mutables.mouse); // maybe null
  const source = state.selected;
  switch (key) {
    case "F":
      state.mutables.cmd.arrowsForward = !state.mutables.cmd.arrowsForward;
      break;
    case "c":
      state.mutables.cmd.on = !state.mutables.cmd.on;
      break;
    case "s":
      if (d3.event.ctrlKey) {
        event.preventDefault();
        save(state);
      } else select(state)(source, target);
      break;
    case "L":
      editEdge(state)(source, target);
      break;
    case "l":
      link(state)(source, target, "");
      break;
    case "u":
      unlink(state)(source, target);
      break;
    case "e":
      editNode(state)(source, target);
      break;
    case "n":
      addNode(state)(source, target);
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
    case "R":
      resetSimulation(state)(1);
      break;
    case "p":
      state.mutables.cmd.present = !state.mutables.cmd.present;
      break;
    case "g":
      state.mutables.cmd.gravity = !state.mutables.cmd.gravity;
      resetSimulation(state)();
      break;
    case "/":
      showHelp();
      break;
    default:
      console.log(`No action for ${key} defined.`, d3.event);
  }
};

const commandMode = state => key => {
  const startCommand = state => command => {
    state.mutables.cmd.action = command;
    state.mutables.cmd.source = state.selected;
    state.mutables.cmd.lookup = "";
  };
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
      state.mutables.cmd.lookup = (state.mutables.cmd.lookup || "") + key;
      searchSelect(state);
      break;
    case "Escape":
      clearCommand(state);
      break;
    case "l":
      startCommand(state)("link");
      break;
    case "L":
      startCommand(state)("Link");
      break;
    case "u":
      startCommand(state)("unlink");
      break;
    case "Enter":
      completeCommand(state);
      clearCommand(state);
      break;
    default:
      return false;
  }
  draw(state)();
  return true;
};

const completeCommand = state => {
  const source = state.mutables.cmd.source;
  const target = state.selected;
  switch (state.mutables.cmd.action) {
    case "link":
      link(state)(source, target, "");
      break;
    case "Link":
      editEdge(state)(source, target);
      break;
    case "unlink":
      unlink(state)(source, target);
      break;
  }
};

const clearCommand = state => {
  state.mutables.cmd.lookup = "";
  state.mutables.cmd.source = undefined;
  state.mutables.cmd.action = "";
};

const searchSelect = state => {
  const keystr = state.mutables.cmd.lookup;
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

export const resetZoom = state => {
  const canvas = state.mutables.canvas;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  let transform = d3.zoomIdentity.translate(width / 2, height / 2);
  if (state.nodes.length) {
    const xs = state.nodes.map(n => n.x);
    const ys = state.nodes.map(n => n.y);
    const x0 = Math.min(...xs);
    const x1 = Math.max(...xs);
    const y0 = Math.min(...ys);
    const y1 = Math.max(...ys);
    transform = d3.zoomIdentity
      .translate(width / 2, height / 2)
      .scale(Math.min(8, 0.9 / Math.max((x1 - x0) / width, (y1 - y0) / height)))
      .translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
  }

  d3.select(canvas)
    .transition()
    .duration(750)
    .call(state.mutables.zoom.transform, transform);

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

const differentNodes = (source, target) => {
  return target && source && target !== source;
};

const editEdge = state => (source, target) => {
  if (!differentNodes(source, target)) return;
  const existing = findEdge(state)(source, target);
  promptText({
    placeholder: "Edge label",
    startText: existing ? existing.text : "",
    confirm: text => link(state)(source, target, text)
  });
};

const link = state => (source, target, text) => {
  if (!differentNodes(source, target)) return;
  const existing = findEdge(state)(source, target);
  if (existing) {
    mutateEdge(state)(existing, { source, target, text });
  } else {
    addEdge(state)(source, target, { text });
  }
  resetSimulation(state)();
};

const unlink = state => (source, target) => {
  if (differentNodes(source, target)) {
    removeEdge(state)(source, target);
    resetSimulation(state)();
  }
};

const addNodeModel = state => (source, target, text) => {
  const { x, y } = state.mutables.mouse;
  const current = source;
  // if we have a currently selected node, make the new one the same size.
  const newNode = createNode(state)({ text, x, y }, current);

  // As a user, I like for new nodes to automatically link the new node to the
  // current one
  const newEdge = !source
    ? undefined
    : state.mutables.cmd.arrowsForward
    ? { source: source, target: newNode }
    : { source: newNode, target: source };

  mutate(state)({
    nodes: [...state.nodes, newNode],
    edges: newEdge ? [...state.edges, newEdge] : state.edges
  });
};

const addNode = state => (source, target) => {
  promptText({
    placeholder: "Node label",
    startText: "",
    confirm: text => {
      addNodeModel(state)(source, target, text);
      resetSimulation(state)();
    }
  });
};

const editNode = state => (source, target) => {
  if (!source) return;
  promptText({
    placeholder: "Node label",
    startText: source.text,
    confirm: value => {
      mutateNode(state)(source, { text: value });
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

const forceGravity = state => alpha => {
  for (const n of state.nodes) {
    n.vy += 10 * alpha;
  }
};

export const resetSimulation = state => (energy = 0.3) => {
  const sim = state.simulation;
  const g = state.mutables.cmd.gravity;
  sim.nodes(state.nodes);
  sim.force("link").links(state.edges);
  sim.force("x", g ? null : d3.forceX(0).strength(0.03));
  sim.force("y", g ? null : d3.forceY(0).strength(0.03));
  sim.force("gravity", g ? forceGravity(state) : null);

  if (energy > 0) sim.alpha(energy).restart();
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
