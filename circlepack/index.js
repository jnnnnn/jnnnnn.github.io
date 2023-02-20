import * as d3 from "https://cdn.skypack.dev/d3@7";

const domains_config = {
    category: { s: "ordinal" },
    maturity: { s: "ordinal" },
    riskcategory: { s: "ordinal" },
    when: { s: "ordinal" },
    none: { s: "linear" },
    costbenefit: { s: "linear" },
    effort: { s: "linear" },
    upskilleffort: { s: "linear" },
    setupeffort: { s: "linear" },
    risk: { s: "linear" },
    created: { s: "time" },
    updated: { s: "time" },
};

var data = [];

// set the dimensions and margins of the graph
// include the dumb thing to make correct on mobiles
var width = (window.innerWidth / 2) * window.devicePixelRatio;
var height = window.innerHeight * window.devicePixelRatio;

var simulation = d3.forceSimulation();

// append the svg object to the body of the page
var svg = d3
    .select("#polygonchart")
    .append("svg")
    .attr("width", width)
    .attr("height", height);

// Initialize the polygon: all located at the center of the svg area
var gs = svg.append("g");

// d3 load data.csv
d3.csv("data.csv", (d) => {
    return {
        ...d,
        effort: +d.effort,
        upskilleffort: +d.upskilleffort,
        setupeffort: +d.setupeffort,
        risk: +d.risk,
        costbenefit: +d.risk / +d.effort,
        created: Date.parse(d.created),
        updated: Date.parse(d.updated),
        none: 0.5,
    };
}).then(function (ds) {
    data = ds;
    compute_domains();
    prepare_options();
    draw(ds);
    restyle();
});

var domains = {};
function compute_domains() {
    let minmax = (field) => [
        Math.min(...data.map((d) => d[field])),
        Math.max(...data.map((d) => d[field])),
    ];
    let sortedcategory = (field) =>
        [...new Set(data.map((d) => d[field]))].sort();
    domains = {
        none: [0, 1],
        effort: minmax("effort"),
        upskilleffort: minmax("upskilleffort"),
        setupeffort: minmax("setupeffort"),
        risk: minmax("risk"),
        updated: minmax("updated"),
        created: minmax("created"),
        costbenefit: minmax("costbenefit"),
        category: sortedcategory("category"),
        maturity: sortedcategory("maturity"),
        riskcategory: sortedcategory("riskcategory"),
        when: sortedcategory("when"),
    };
}
let ranges = {
    size: d3.interpolate(20, 50),
    posx: d3.interpolate(0.2 * width, width * 0.7),
    posy: d3.interpolate(0.8 * height, height * 0.3),
    colour: d3.interpolateSinebow,
    saturation: d3.interpolate(0.1, 1),
    strokewidth: d3.interpolate(1, 5),
    strokelength: d3.interpolate(0.1, 1),
    sides: d3.interpolate(3, 10),
};

// copy the options from the first select to the others
function prepare_options() {
    let selects = document.querySelectorAll("select");
    let first = selects[0];
    for (let i = 1; i < selects.length; i++) {
        let select = selects[i];
        for (let j = 0; j < first.options.length; j++) {
            let option = first.options[j];
            select.options[j] = new Option(option.text, option.value);
        }
    }
}

function polygon_points(radius, sides) {
    const N = Math.ceil(sides);
    return d3.range(N).map((i) => {
        let angle = (i / N) * 2 * Math.PI + (3 * Math.PI) / 2;
        return [radius * Math.cos(angle), radius * Math.sin(angle)];
    });
}

function draw(data) {
    gs = gs.selectAll("polygon").data(data).enter().append("g");

    gs.attr("translate", `transform(${width / 2}, ${height / 2})`)
        .on("click", clicked)
        .call(
            d3
                .drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended)
        )
        .on("mouseover", function (event, d) {
            const text = JSON.stringify(d, null, 2);
            d3.select("#hint").node().innerHTML = `<pre>${text}</pre>`;
        });

    gs.append("polygon");

    gs.append("text")
        .attr("dominant-baseline", "middle")
        .attr("text-anchor", "middle")
        .text((d) => d.code);

    // Apply these forces to the nodes and update their positions.
    // Once the force algorithm is happy with positions ('alpha' value is low enough), simulations will stop.
    simulation.nodes(data).on("tick", (d) => {
        gs.attr("transform", (d) => `translate(${d.x}, ${d.y})`);
    });
}

function clicked(event, d) {
    if (event.defaultPrevented) return; // dragged

    restyle();

    updateInfoCard(d);
}

function dragstarted() {
    simulation.alpha(0.1).restart();
}

function dragged(event, d) {
    d3.select(this)
        .raise()
        .attr("cx", (d.x = event.x))
        .attr("cy", (d.y = event.y));
}

function dragended() {
    simulation.alpha(0.1).restart();
}

function getScale(range) {
    const selectedDomain = getSelection(range);
    const domain_values = domains[selectedDomain]; // keys in d: effort, risk, etc
    console.assert(domain_values, `domain ${selectedDomain} not found`);
    const range_values = ranges[range]; // selection possibilites: size, posx, etc
    if (domains_config[selectedDomain].s == "ordinal") {
        const scale = d3
            .scaleOrdinal()
            .domain(domain_values)
            .range([range_values(0), range_values(1)]);
        return (d) => scale(d[selectedDomain]);
    } else {
        const scale = d3
            .scaleSequential()
            .domain(domain_values)
            .interpolator(range_values);
        return (d) => scale(d[selectedDomain]);
    }
}

// find the currently selected domain for a given range
function getSelection(range) {
    return d3.select(`#${range}`).property("value");
}

function distance(point0, point1) {
    const dx = point0[0] - point1[0];
    const dy = point0[1] - point1[1];
    return Math.sqrt(dx * dx + dy * dy);
}

function restyle() {
    // strokelength: scale from 0 to pi*size^2 based on the selected strokelength param
    const dashscale = (d) => {
        const size = getScale("size")(d);
        const sides = getScale("sides")(d);
        const points = polygon_points(size, sides);
        const circumference = sides * distance(points[0], points[1]);
        const domain = domains[getSelection("strokelength")];
        const range = d3.interpolate(0, circumference);
        const dashlen = d3.scaleSequential().domain(domain).interpolator(range)(
            d[getSelection("strokelength")]
        );
        return `${dashlen}, 10000`;
    };

    gs.select("polygon")
        .attr("points", (d) => {
            const sides = getScale("sides")(d);
            const radius = getScale("size")(d);
            const str = polygon_points(radius, sides).join(" ");
            return str;
        })
        .transition()
        .duration(1000)
        .style("fill", getScale("colour"))
        .style("fill-opacity", getScale("saturation"))
        .attr("stroke", "black")
        .attr("stroke-width", getScale("strokewidth"))
        .attr("stroke-dasharray", dashscale);

    simulation
        .force("x", d3.forceX().strength(0.5).x(getScale("posx")))
        .force("y", d3.forceY().strength(0.5).y(getScale("posy")))
        .force(
            "collide",
            d3
                .forceCollide()
                .strength(0.5)
                .radius((d) => 10 + getScale("size")(d))
                .iterations(1)
        )
        //.force("charge", d3.forceManyBody().strength(1))
        .alphaTarget(0)
        .alphaDecay(0.02);

    simulation.alpha(0.3).restart();
}

function updateInfoCard(d) {
    document.getElementById("detail").innerHTML = `
        <div class="card">
            <h1>${d.name}</h1>
            <h2>What is the purpose?</h2>
            <p class="note">What is this and why is it important?</p>
            <h2>Does this apply to us?</h2>
            <p class="note">How can a team determine that this tools is important/required for their product?  At what point(s) in the product's lifecycle should it be used and how often?  examples: in all CI/CD pipelines, for all cloud software, if your software is hosted on VMs, if you are using docker containers, before delivering new software to customer facing environments, when making significant software changes
            </p>
            <h2>What's the risk if we don't use it?</h2>
            <p class="note">Consider the risk and who is impacted.  The team, our customers, Iress?</p>
            <h2>How long will it take us?</h2>
            <p class="note">Consider setup / first time use, including any knowledge aquisition, as well as ongoing or regular use.</p>
            <div class="links">
                <a href="">User Guide</a>
                <a href="">Get Help</a>
                <a href="">Provide Feedback</a>
            </div>
        </div>
    `;
}

function randomize() {
    const params = Object.keys(ranges);
    params.forEach((param) => {
        const options = document.getElementById(param).options;
        const index = Math.floor(Math.random() * options.length);
        document.getElementById(param).selectedIndex = index;
    });
    restyle();
}

d3.select("form").node().onchange = () => restyle();
d3.select("#randomize").on("click", () => randomize());