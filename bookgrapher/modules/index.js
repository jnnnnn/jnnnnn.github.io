"use strict";
import {} from "./drag.js";

const radius = 5;

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
  .force("charge", d3.forceManyBody().strength(-50))
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

const dragstarted = () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0.3).restart();
  }
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

const dragged = () => {
  d3.event.subject.fx = state.transform.invertX(d3.event.x);
  d3.event.subject.fy = state.transform.invertY(d3.event.y);
};

const dragended = () => {
  if (!d3.event.active) {
    state.simulation.alphaTarget(0);
  }
  d3.event.subject.fx = null;
  d3.event.subject.fy = null;
};

const drawNode = d => {
  context.beginPath();
  context.arc(d.x, d.y, radius, 0, 2 * Math.PI, true);
  context.fillStyle = d.col || "black";
  context.fill();
};

const simulationUpdate = state => () => {
  context.save();

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

const dragsubject = state => () => {
  for (let node of state.nodes) {
    const dx = transform.invertX(d3.event.x) - node.x;
    const dy = transform.invertY(d3.event.y) - node.y;

    if (dx * dx + dy * dy < radius * radius) {
      node.x = transform.applyX(node.x);
      node.y = transform.applyY(node.y);

      return node;
    }
  }
};

const createGraph = async () => {
  const data = await d3.json("data.json");

  d3.select(graphCanvas)
    .call(
      d3
        .drag()
        .subject(dragsubject(data))
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended)
    )
    .call(
      d3
        .zoom()
        .scaleExtent([1 / 10, 8])
        .on("zoom", () => {
          transform = d3.event.transform;
          console.log(transform);
          simulationUpdate(data);
        })
    );

  simulation.nodes(data.nodes).on("tick", simulationUpdate(data));

  simulation.force("link").links(data.edges);
};

createGraph();
