"use strict";
import { dragstarted, dragged, dragended, dragsubject } from "./drag.js";
import { draw } from "./draw.js";

const height = window.innerHeight;
const width = window.innerWidth;

const graphCanvas = d3
  .select("#graphDiv")
  .append("canvas")
  .attr("width", width + "px")
  .attr("height", height + "px")
  .node();

const ctx = graphCanvas.getContext("2d");

const size = node => 12 - node.level;
const distance = edge => {
  const sum = Math.pow(2, size(edge.source)) + Math.pow(2, size(edge.target));
  return sum / 3000;
};

// Because this makes size 12 nodes have a reasonable amount of charge strength
// (~1000) for a linkdistance of 100
const chargeStrength = node => -4 * Math.pow(size(node) * 3, 2);

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
  selection: undefined,
  ctx,
  width,
  height,
  mouse: { x: 0, y: 0 }
};

const click = state => () => {
  const subject = dragsubject(state)();
  console.log(subject);
};

const mousemove = state => () => {
  const [screenX, screenY] = d3.mouse(d3.event.currentTarget);
  state.mouse = {
    x: state.transform.invertX(screenX),
    y: state.transform.invertY(screenY)
  };
};

const keydown = state => () => {
  console.log(d3.event);
  console.log();
};
d3.select("body").on("keydown", keydown(state));

const createGraph = async () => {
  const data = await d3.json("data.json");
  state.nodes = data.nodes;
  state.edges = data.edges;

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

  simulation.nodes(data.nodes).on("tick", draw(state));

  simulation.force("link").links(state.edges);
};

createGraph();
