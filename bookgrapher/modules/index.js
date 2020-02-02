"use strict";
import { dragstarted, dragged, dragended, dragsubject } from "./drag.js";
import { draw } from "./draw.js";
import { keydown, click, mousemove, resetSimulation } from "./commands.js";
import { size, load } from "./model.js";
import { dropFile } from "./save.js";

const height = window.innerHeight;
const width = window.innerWidth;

const graphCanvas = d3
  .select("#graphDiv")
  .append("canvas")
  .attr("width", width + "px")
  .attr("height", height + "px")
  .node();

const ctx = graphCanvas.getContext("2d");

const distance = edge => {
  return 10 * (size(edge.source) + size(edge.target));
};

// Because this makes size 12 nodes have a reasonable amount of charge strength
// (~1000) for a linkdistance of 100
const chargeStrength = node => -200 * size(node);

const simulation = d3
  .forceSimulation()
  //.force("center", d3.forceCenter(graphWidth / 2, height / 2))
  .force("x", d3.forceX(width / 2).strength(0.1))
  .force("y", d3.forceY(height / 2).strength(0.1))
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
  ctx,
  width,
  height,
  mouse: { x: 0, y: 0 }
};

d3.select("body").on("keydown", () => {
  keydown(state)(d3.event.key);
  draw(state)();
});

const dz = document.getElementById("graphDiv");
dz.addEventListener("dragover", e => e.preventDefault(), true);
dz.addEventListener("drop", dropFile(state), true);

const createGraph = () => {
  const canvas = d3.select(graphCanvas);

  canvas.on("click", click(state));

  canvas.on("mousemove", mousemove(state));

  canvas.call(
    d3
      .drag(canvas)
      .subject(dragsubject(state))
      .on("start", dragstarted(state))
      .on("drag", dragged(state))
      .on("end", dragended(state))
  );

  canvas.call(
    d3
      .zoom(canvas)
      .scaleExtent([0.1, 8])
      .on("zoom", () => {
        state.transform = d3.event.transform;
        draw(state)();
      })
  );

  simulation.on("tick", draw(state));
  load(state);
};

createGraph();
