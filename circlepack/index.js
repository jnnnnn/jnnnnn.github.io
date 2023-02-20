import * as d3 from "https://cdn.skypack.dev/d3@7";
import { axisBottom, axisLeft } from "https://cdn.skypack.dev/d3-axis@3";

const domains_config = {
    category: { s: d3.scaleOrdinal },
    maturity: { s: d3.scaleOrdinal },
    riskcategory: { s: d3.scaleOrdinal },
    when: { s: d3.scaleOrdinal },
    nonemin: { s: d3.scaleSequential },
    nonemax: { s: d3.scaleSequential },
    costbenefit: { s: d3.scaleSequential },
    effort: { s: d3.scaleSequential },
    upskilleffort: { s: d3.scaleSequential },
    setupeffort: { s: d3.scaleSequential },
    risk: { s: d3.scaleSequential },
    created: { s: d3.scaleSequential, time: true },
    updated: { s: d3.scaleSequential, time: true },
    teamsize: { s: d3.scaleSequential },
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

svg.append("g").attr("id", "y-axis").attr("transform", `translate(${40}, 0)`);
svg.append("g")
    .attr("id", "x-axis")
    .attr("transform", `translate(0, ${height - 40})`);

// d3 load data.csv
d3.csv("data.csv", (d) => {
    return {
        ...d,
        effort: +d.effort,
        upskilleffort: +d.upskilleffort,
        setupeffort: +d.setupeffort,
        risk: +d.risk,
        costbenefit: +d.risk / +d.effort,
        created: new Date(d.created),
        updated: new Date(d.updated),
        teamsize: +d.teamsize,
        nonemin: 0,
        nonemax: 1,
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
    let sortedcategory = (field) =>
        [...new Set(data.map((d) => d[field]))].sort();
    domains = {
        ...Object.fromEntries(
            Object.entries(domains_config).map(([key, value]) => [
                key,
                value.s.name === "ordinal"
                    ? sortedcategory(key)
                    : d3.extent(data, (d) => d[key]),
            ])
        ),
        nonemin: [0, 1],
        nonemax: [0, 1],
    };
}
let ranges = {
    size: d3.interpolate(20, 50),
    posx: d3.interpolate(0.2 * width, width * 0.7),
    posy: d3.interpolate(0.8 * height, height * 0.3),
    // red at both ends doesn't make sense, skip the end
    colour: (i) => d3.interpolateSinebow(i * 0.7),
    saturation: d3.interpolate(0.1, 1),
    strokewidth: d3.interpolate(1, 5),
    strokelength: d3.interpolate(0.1, 1),
    sides: (f) => Math.round(d3.interpolate(3, 10)(f)),
    identity: (i) => i,
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
        let angle = (i / N) * 2 * Math.PI - Math.PI / 2;
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

function getRawScale(range_key, optional_domain_key) {
    const domain_key = optional_domain_key || getDomainKey(range_key);
    const domain_values = domains[domain_key]; // keys in d: effort, risk, etc
    console.assert(domain_values, `domain ${domain_key} not found`);
    const interpolator = ranges[range_key]; // selection possibilites: size, posx, etc
    console.assert(interpolator, `range ${range_key} not found`);
    const scale = domains_config[domain_key].s();
    scale.domain(domain_values);
    if (domains_config[domain_key].s.name === "ordinal") {
        const N = domain_values.length;
        scale.range(d3.range(N).map((n) => interpolator(n / (N - 1))));
    } else {
        scale.interpolator(interpolator);
    }
    return scale;
}

function getScale(range_key, optional_domain_key) {
    const domain_key = optional_domain_key || getDomainKey(range_key);
    return (d) => getRawScale(range_key, domain_key)(d[domain_key]);
}

// find the key of the currently selected domain for a given range
function getDomainKey(range_key) {
    return d3.select(`#${range_key}`).property("value");
}

function distance(point0, point1) {
    const dx = point0[0] - point1[0];
    const dy = point0[1] - point1[1];
    return Math.sqrt(dx * dx + dy * dy);
}

const dashscale = () => (d) => {
    const size = getScale("size")(d);
    const sides = getScale("sides")(d);
    const points = polygon_points(size, sides);
    const circumference = sides * distance(points[0], points[1]);
    const dashlen =
        getScale("identity", getDomainKey("strokelength"))(d) * circumference;
    return `${dashlen}, 10000`;
};

function restyle() {
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
        .attr("stroke-dasharray", dashscale());

    const makeAxis = (d3axis, nodeid, range_key) => {
        const axis = d3axis(getRawScale(range_key));
        if (domains_config[getDomainKey(range_key)].time) {
            axis.tickFormat(d3.timeFormat("%Y-%m"));
        }
        d3.select(nodeid).transition().call(axis);
    };
    makeAxis(d3.axisTop, "#x-axis", "posx");
    makeAxis(d3.axisRight, "#y-axis", "posy");

    simulation
        .force("x", d3.forceX().strength(0.5).x(getScale("posx")))
        .force("y", d3.forceY().strength(0.5).y(getScale("posy")))
        .force(
            "collide",
            d3
                .forceCollide()
                .strength(0.5)
                .radius((d) => getScale("size")(d))
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
    d3.selectAll("select")
        .nodes()
        .forEach((s) => {
            const options = d3.select(s).selectAll("option");
            s.selectedIndex = Math.floor(Math.random() * options.size());
        });
    restyle();
}

d3.select("form").node().onchange = () => restyle();
d3.select("#randomize").on("click", () => randomize());

// for console debugging
window.j = {
    domains,
    d3,
    data,
    domains_config,
    ranges,
    simulation,
    polygon_points,
    distance,
};
