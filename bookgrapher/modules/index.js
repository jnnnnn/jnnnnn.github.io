"use strict";
import { dragstarted, dragged, dragended, dragsubject } from "./drag.js";

const height = window.innerHeight;
const graphWidth = window.innerWidth;

const graphCanvas = d3
  .select("#graphDiv")
  .append("canvas")
  .attr("width", graphWidth + "px")
  .attr("height", height + "px")
  .node();

const context = graphCanvas.getContext("2d");

const simulation = d3
  .forceSimulation()
  .force("center", d3.forceCenter(graphWidth / 2, height / 2))
  .force("x", d3.forceX(graphWidth / 2).strength(0.1))
  .force("y", d3.forceY(height / 2).strength(0.1))
  .force(
    "charge",
    d3.forceManyBody().strength(d => -10 * (d.radius || 5))
  )
  .force(
    "link",
    d3
      .forceLink()
      .strength(1)
      .id(d => d.id)
  )
  .alphaTarget(0)
  .alphaDecay(0.05);

let state = {
  transform: d3.zoomIdentity,
  nodes: [],
  edges: [],
  simulation: simulation
};

const drawNode = d => {
  context.beginPath();
  const radius = d.radius || 5;
  context.arc(d.x, d.y, radius, 0, 2 * Math.PI, true);
  context.fillStyle = d.col || "black";
  context.fill();
};

const simulationUpdate = state => () => {
  context.save();
  const { transform } = state;

  context.clearRect(0, 0, graphWidth, height);
  context.translate(transform.x, transform.y);
  context.scale(transform.k, transform.k);

  state.edges.forEach(d => {
    context.beginPath();
    context.moveTo(d.source.x, d.source.y);
    context.lineTo(d.target.x, d.target.y);
    context.stroke();
  });

  state.nodes.forEach(drawNode);

  context.restore();
};

const createGraph = async () => {
  const data = await d3.json("data.json");
  state.nodes = data.nodes;
  state.edges = data.edges;

  d3.select(graphCanvas)
    .call(
      d3
        .drag()
        .subject(dragsubject(state))
        .on("start", dragstarted(state))
        .on("drag", dragged(state))
        .on("end", dragended(state))
    )
    .call(
      d3
        .zoom()
        .scaleExtent([1 / 10, 8])
        .on("zoom", () => {
          state.transform = d3.event.transform;
          simulationUpdate(state);
        })
    );

  simulation.nodes(data.nodes).on("tick", simulationUpdate(state));

  simulation.force("link").links(state.edges);
};

createGraph();
