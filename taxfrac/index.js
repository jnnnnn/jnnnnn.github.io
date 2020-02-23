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
  const xmax = 300000;
  const ymax = xmax;

  const points = [{ income: 0, tax: 0 }];
  for (const bracket of brackets) {
    const start = points[points.length - 1];
    const thisBracketTax = (bracket.end - start.income) * bracket.taxRate;
    points.push({ income: bracket.end, tax: start.tax + thisBracketTax });
  }
  const taxpoints = points.map(p => ({ x: p.income, y: p.tax }));
  const incomepoints = points.map(p => ({ x: p.income, y: p.income }));

  const xScale = d3
    .scaleLinear()
    .domain([0, xmax])
    .range([0, width]);
  const yScale = d3
    .scaleLinear()
    .domain([0, ymax])
    .range([height, 0]);

  const incomeToTax = d3
    .scaleLinear()
    .domain(taxpoints.map(d => d.x))
    .range(taxpoints.map(d => d.y));

  const line = d3
    .line()
    .x(d => xScale(d.x))
    .y(d => yScale(d.y));

  const mousemove = () => {
    const income = xScale.invert(d3.event.clientX - margin.left);
    const tax = incomeToTax(income);
    const percentage = Math.round((100 * tax) / income);
    const bracket = brackets.filter(b => b.end > income)[0];
    const text = `
          <p>
            at an income of $${Math.round(income)},
            you pay $${Math.round(tax)} tax (${percentage}%)
          </p>
          <p>
            You are in the ${(bracket ? bracket.taxRate : 0) * 100}% bracket.
          </p>
          `;

    document.querySelector("div#description").innerHTML = text;

    d3.select("#taxi").remove();
    const hover = d3.select("#hover");
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

    d3.select("#taxt").remove();
    hover
      .append("text")
      .attr("id", "taxt")
      .attr("class", "tax")
      .attr("x", xScale(income))
      .attr("y", yScale(tax / 2))
      .text(`Tax: $${Math.round(tax)}`);

    d3.select("#incomet").remove();
    hover
      .append("text")
      .attr("id", "incomet")
      .attr("class", "income")
      .attr("x", xScale(income))
      .attr("y", yScale(tax + (income - tax) / 2))
      .text(`You keep: $${Math.round(income - tax)}`);

    d3.select("#effec").remove();
    hover
      .append("text")
      .attr("id", "effec")
      .attr("x", xScale(income))
      .attr("y", yScale(tax))
      .text(`You pay ${percentage}% tax`);
  };
  d3.select("svg").remove();
  d3.select("#graph").append("svg");
  const svg = d3
    .select("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
    .on(supportsTouch ? "touchmove" : "mousemove", mousemove)
    .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
    .attr("id", "graph");

  svg.append("rect").attr({ x: 0, y: 0, width, height, fill: "#fff" });

  svg
    .append("g")
    .attr("transform", "translate(0," + height + ")")
    .call(d3.axisBottom(xScale));

  svg.append("g").call(d3.axisLeft(yScale));

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
    .attr("cx", d => xScale(d.x))
    .attr("cy", d => yScale(d.y))
    .attr("r", 3);
  svg
    .selectAll(".dot2")
    .data(incomepoints)
    .enter()
    .append("circle")
    .attr("class", "income dot")
    .attr("cx", d => xScale(d.x))
    .attr("cy", d => yScale(d.y))
    .attr("r", 3);

  svg.append("g").attr("id", "hover");
};

createGraph(bracketsAU, document.querySelector("#maxincomev").value);
