"use strict";
import { dragstarted, dragged, dragended, dragsubject } from "./drag.js";
import { draw } from "./draw.js";
import {
  keydown,
  click,
  mousemove,
  dropFile,
  resetSimulation,
  resetZoom,
} from "./commands.js";
import { size, load } from "./model.js";

const canvas = document.querySelector("div#graphDiv > canvas");

const distance = (edge) => {
  return 10 * (size(edge.source) + size(edge.target));
};

// Because this makes size 12 nodes have a reasonable amount of charge strength
// (~1000) for a linkdistance of 100
const chargeStrength = (node) => -200 * size(node);

const simulation = d3
  .forceSimulation()
  .force("charge", d3.forceManyBody().strength(chargeStrength))
  .force(
    "link",
    d3
      .forceLink()
      .id((d) => d.id)
      .distance(distance)
  )
  .alphaTarget(0)
  .alphaDecay(0.05);

let state = {
  transform: d3.zoomIdentity,
  nodes: [],
  edges: [],
  simulation: simulation,
  // these values are shared by all state objects
  mutables: {
    canvas,
    ctx: canvas.getContext("2d"),
    width: 100,
    height: 100,
    mouse: { x: 0, y: 0 },
    cmd: {},
  },
};

state.mutables.zoom = d3
  .zoom(canvas)
  .scaleExtent([0.1, 8])
  .on("zoom", () => {
    state.transform = d3.event.transform;
    draw(state)();
  });

const resize = () => {
  state.mutables.width = canvas.clientWidth;
  state.mutables.height = canvas.clientHeight;

  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;

  simulation
    .force("x", d3.forceX(0).strength(0.03))
    .force("y", d3.forceY(0).strength(0.03))
    .alpha(0.3)
    .restart();

  state.mutables.ctx = canvas.getContext("2d");
};

window.addEventListener("resize", resize);

d3.select("body").on("keydown", () => {
  keydown(state)(d3.event.key);
  draw(state)();
});

const dz = document.getElementById("graphDiv");
dz.addEventListener("dragover", (e) => e.preventDefault(), true);
dz.addEventListener("drop", dropFile(state), true);

const createGraph = () => {
  const canvasS = d3.select(canvas);

  canvasS.on("click", click(state));

  canvasS.on("mousemove", mousemove(state));

  canvasS.call(
    d3
      .drag(canvasS)
      .subject(dragsubject(state))
      .on("start", dragstarted(state))
      .on("drag", dragged(state))
      .on("end", dragended(state))
  );

  canvasS.call(state.mutables.zoom);

  resize();
  simulation.on("tick", draw(state));
  load(state);
  resetSimulation(state)();
  resetZoom(state);
};

createGraph();
