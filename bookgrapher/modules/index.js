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

const ctx = graphCanvas.getContext("2d");

const size = node => 12 - node.level;

const chargeStrength = node => -1 * Math.pow(size(node), 3);
const simulation = d3
  .forceSimulation()
  //.force("center", d3.forceCenter(graphWidth / 2, height / 2))
  .force("x", d3.forceX(graphWidth / 2).strength(0.1))
  .force("y", d3.forceY(height / 2).strength(0.1))
  .force("charge", d3.forceManyBody().strength(chargeStrength))
  .force(
    "link",
    d3
      .forceLink()
      .id(d => d.id)
      .distance(100)
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
  ctx.beginPath();
  const radius = d.radius || 5;
  ctx.arc(d.x, d.y, radius, 0, 2 * Math.PI, true);
  ctx.fillStyle = d.col || "#ddd";
  ctx.fill();

  ctx.fillStyle = "black";
  ctx.font = 24 / d.level + "px Arial";
  ctx.textAlign = "center";
  ctx.fillText(d.text, d.x, d.y);
};

const drawEdge = d => {
  ctx.beginPath();
  ctx.moveTo(d.source.x, d.source.y);
  ctx.lineTo(d.target.x, d.target.y);
  ctx.strokeStyle = "#ddd";
  ctx.stroke();
};

const simulationUpdate = state => () => {
  ctx.save();
  const { transform } = state;

  ctx.clearRect(0, 0, graphWidth, height);
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  state.edges.forEach(drawEdge);
  state.nodes.forEach(drawNode);

  ctx.restore();
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
