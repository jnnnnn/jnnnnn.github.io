"use strict";
import { dragstarted, dragged, dragended, dragsubject } from "./drag.js";
import { draw } from "./draw.js";
import {
  keydown,
  click,
  mousemove,
  dropFile,
  resetSimulation
} from "./commands.js";
import { size, load } from "./model.js";

const canvas = document.querySelector("div#graphDiv > canvas");

const distance = edge => {
  return 10 * (size(edge.source) + size(edge.target));
};

// Because this makes size 12 nodes have a reasonable amount of charge strength
// (~1000) for a linkdistance of 100
const chargeStrength = node => -200 * size(node);

const simulation = d3
  .forceSimulation()
  .force("charge", d3.forceManyBody().strength(chargeStrength))
  .force(
    "link",
    d3
      .forceLink()
      .id(d => d.id)
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
    ctx: canvas.getContext("2d"),
    width: 100,
    height: 100,
    mouse: { x: 0, y: 0 }
  }
};

const resize = () => {
  state.mutables.width = canvas.clientWidth;
  state.mutables.height = canvas.clientHeight;

  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;

  simulation
    .force("x", d3.forceX((state.mutables.width || 100) / 2).strength(0.1))
    .force("y", d3.forceY((state.mutables.height || 100) / 2).strength(0.1))
    .alpha(0.3)
    .restart();

  console.log(`resize to ${state.mutables.width} x ${state.mutables.height}`);
  state.mutables.ctx = canvas.getContext("2d");
};

window.addEventListener("resize", resize);

d3.select("body").on("keydown", () => {
  keydown(state)(d3.event.key);
  draw(state)();
});

const dz = document.getElementById("graphDiv");
dz.addEventListener("dragover", e => e.preventDefault(), true);
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

  canvasS.call(
    d3
      .zoom(canvasS)
      .scaleExtent([0.1, 8])
      .on("zoom", () => {
        state.transform = d3.event.transform;
        draw(state)();
      })
  );

  resize();
  simulation.on("tick", draw(state));
  load(state);
  resetSimulation(state)();
};

createGraph();
