import { findNodeAtCoords } from "./model.js";

export const keydown = state => key => {
  switch (key) {
    case "s":
      select(state);
      break;
    case "l":
      link(state);
      break;
    case "u":
      unlink(state);
      break;
  }
};

const select = state => {
  state.selected = findNodeAtCoords(state)(state.mouse);
};

const link = state => {
  const target = findNodeAtCoords(state)(state.mouse);
  if (target && state.selected && target !== state.selected) {
    addEdge(state)(state.selected, target);
  }
};

const addEdge = state => (source, target) => {
  // don't add duplicate edges, it makes the simulation wonky
  if (
    state.edges.find(
      e =>
        (e.source === source.id && e.target === target.id) ||
        (e.target === source.id && e.source == target.id)
    )
  ) {
    return;
  }
  state.edges = [...state.edges, { source: source.id, target: target.id }];
  state.simulation.force("link").links(state.edges);
};

const unlink = state => {
  const target = findNodeAtCoords(state)(state.mouse);
  if (target && state.selected && target !== state.selected) {
    removeEdge(state)(state.selected, target);
  }
};

const removeEdge = state => (source, target) => {
  console.log("removing edges", source.id, target.id);
  console.log(state.edges);
  state.edges = state.edges.filter(
    e =>
      !(
        (e.source === source.id && e.target === target.id) ||
        (e.target === source.id && e.source == target.id)
      )
  );
  console.log(state.edges);
  state.simulation.force("link").links(state.edges);
};
