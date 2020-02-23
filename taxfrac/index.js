// todo: fix this
const supportsTouch = "ontouchstart" in window || navigator.msMaxTouchPoints;

const graphdiv = document.querySelector("div#graph");
const margin = { top: 50, right: 50, bottom: 50, left: 50 },
  width = graphdiv.clientWidth - margin.left - margin.right,
  height = graphdiv.clientHeight - margin.top - margin.bottom;

const bracketsAU = [
  { end: 18200, taxRate: 0.0 },
  { end: 37000, taxRate: 0.19 },
  { end: 90000, taxRate: 0.325 },
  { end: 180000, taxRate: 0.37 },
  { end: 300000, taxRate: 0.45 }
];

const bracketsUS = [
  { end: 9700, taxRate: 0.1 },
  { end: 39475, taxRate: 0.12 },
  { end: 84200, taxRate: 0.22 },
  { end: 160725, taxRate: 0.24 },
  { end: 204100, taxRate: 0.32 },
  { end: 510300, taxRate: 0.35 },
  { end: 1000000, taxRate: 0.37 }
];

const createGraph = (brackets, maxincome) => {
  const xmax = maxincome;
  const ymax = xmax;

  const points = [{ income: 0, tax: 0 }];
  for (const bracket of brackets) {
    const start = points[points.length - 1];
    const thisBracketTax = (bracket.end - start.income) * bracket.taxRate;
    points.push({ income: bracket.end, tax: start.tax + thisBracketTax });
  }
  const taxpoints = points.map(p => ({ x: p.income, y: p.tax }));
  const incomepoints = points.map(p => ({ x: p.income, y: p.income }));

  const x = d3
    .scaleLinear()
    .domain([0, xmax])
    .range([0, width]);
  const y = d3
    .scaleLinear()
    .domain([0, ymax])
    .range([height, 0]);

  const line = d3
    .line()
    .x(d => x(d.x))
    .y(d => y(d.y));

  const mousemove = () => {
    const incomeToTax = d3
      .scaleLinear()
      .domain(taxpoints.map(d => d.x))
      .range(taxpoints.map(d => d.y));
    const income = x.invert(d3.event.clientX - margin.left);
    const tax = incomeToTax(income);
    const percentage = Math.round((100 * tax) / income);
    const bracket = brackets.filter(b => b.end > income)[0];
    const taxBracketRate = (bracket ? bracket.taxRate : 0) * 100;
    updateDescription(income, tax, percentage, taxBracketRate);
    updateHoverLines(line, income, tax);
    updateHoverTexts(income, tax, percentage, x, y);
  };
  d3.select("svg").remove();
  d3.select("div#graph").append("svg");
  const svg = d3
    .select("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .on(supportsTouch ? "touchmove" : "mousemove", mousemove)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
    .attr("id", "chart");

  svg.append("rect").attr({ x: 0, y: 0, width, height, fill: "#fff" });

  svg
    .append("g")
    .attr("transform", "translate(0," + height + ")")
    .call(d3.axisBottom(x));

  svg.append("g").call(d3.axisLeft(y));

  updateLines(svg, line, taxpoints, incomepoints, x, y);

  svg.append("g").attr("id", "hover");
};

const updateLines = (svg, line, taxpoints, incomepoints, x, y) => {
  svg
    .append("path")
    .attr("class", "tax line")
    .attr("d", line(taxpoints));

  svg
    .append("path")
    .attr("class", "income line")
    .attr("d", line(incomepoints));

  svg
    .selectAll(".dot")
    .data(taxpoints)
    .enter()
    .append("circle")
    .attr("class", "tax dot")
    .attr("cx", d => x(d.x))
    .attr("cy", d => y(d.y))
    .attr("r", 3);
  svg
    .selectAll(".dot2")
    .data(incomepoints)
    .enter()
    .append("circle")
    .attr("class", "income dot")
    .attr("cx", d => x(d.x))
    .attr("cy", d => y(d.y))
    .attr("r", 3);
};

const updateHoverTexts = (income, tax, percentage, x, y) => {
  const hover = d3.select("#hover");
  d3.select("#taxt").remove();
  hover
    .append("text")
    .attr("id", "taxt")
    .attr("class", "tax")
    .attr("x", x(income))
    .attr("y", y(tax / 2))
    .text(`Tax: $${Math.round(tax)}`);

  d3.select("#incomet").remove();
  hover
    .append("text")
    .attr("id", "incomet")
    .attr("class", "income")
    .attr("x", x(income))
    .attr("y", y(tax + (income - tax) / 2))
    .text(`You keep: $${Math.round(income - tax)}`);

  d3.select("#effec").remove();
  hover
    .append("text")
    .attr("id", "effec")
    .attr("x", x(income))
    .attr("y", y(tax))
    .text(`You pay ${percentage}% tax`);
};

const updateHoverLines = (line, income, tax) => {
  const hover = d3.select("#hover");
  d3.select("#taxi").remove();
  hover
    .append("path")
    .attr("id", "taxi")
    .attr("class", "tax line")
    .attr(
      "d",
      line([
        { x: income, y: 0 },
        { x: income, y: tax }
      ])
    );
  d3.select("#incomei").remove();
  hover
    .append("path")
    .attr("id", "incomei")
    .attr("class", "income line")
    .attr(
      "d",
      line([
        { x: income, y: tax },
        { x: income, y: income }
      ])
    );
};

const updateDescription = (income, tax, percentage, taxBracketRate) => {
  document.querySelector("div#description").innerHTML = `
  <p>
    at an income of $${Math.round(income)},
    you pay $${Math.round(tax)} tax (${percentage}%)
  </p>
  <p>
    You are in the ${taxBracketRate}% bracket.
  </p>
  `;
};

createGraph(bracketsAU, document.querySelector("#maxincomev").value);
