import { findNodeAtCoords } from "./model.js";

export const dragstarted = state => () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0.3).restart();
  }
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

export const dragged = state => () => {
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

export const dragended = state => () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0);
  }
  d3.event.subject.fx = null;
  d3.event.subject.fy = null;
};

export const dragsubject = state => () => {
  const { transform } = state;

  // The tricky part is the need to distinguish between two coordinate spaces:
  // the world coordinates used to position the nodes, and the pointer
  // coordinates representing the mouse or touches. The drag behavior doesn’t
  // know the view is being transformed by the zoom behavior, so we must convert
  // between the two coordinate spaces.
  // https://bl.ocks.org/mbostock/2b534b091d80a8de39219dd076b316cd
  const x = transform.invertX(d3.event.x);
  const y = transform.invertY(d3.event.y);

  const node = findNodeAtCoords(state)({ x, y });

  // the node must move under the mouse in screen space, so we have to transform
  // its position back to screen space (?)
  if (node) {
    node.x = transform.applyX(node.x);
    node.y = transform.applyY(node.y);

    return node;
  }
};
