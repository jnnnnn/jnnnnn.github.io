import * as d3 from "https://cdn.skypack.dev/d3@7";

const domains_config = {
    Category: { s: d3.scaleOrdinal },
    Maturity: { s: d3.scaleOrdinal },
    "Risk Category": { s: d3.scaleOrdinal },
    When: { s: d3.scaleOrdinal },
    nonemin: { s: d3.scaleSequential },
    nonemed: { s: d3.scaleSequential },
    nonemax: { s: d3.scaleSequential },
    "Cost/Benefit": { s: d3.scaleSequential },
    Effort: { s: d3.scaleSequential },
    "Upskill Effort": { s: d3.scaleSequential },
    "Setup Effort": { s: d3.scaleSequential },
    Risk: { s: d3.scaleSequential },
    Created: { s: d3.scaleSequential, time: true },
    Updated: { s: d3.scaleSequential, time: true },
    "Team Size": { s: d3.scaleSequential },
};

const default_ranges = {
    size: "nonemed",
    posx: "When",
    posy: "Risk Category",
    colour: "Risk Category",
    saturation: "nonemed",
    strokewidth: "nonemin",
    strokelength: "nonemin",
    sides: "When",
};

prepare_options();

var data = [];

// set the dimensions and margins of the graph
var width = window.innerWidth;
var height = window.innerHeight;

var simulation = d3.forceSimulation();

// append the svg object to the body of the page
let svg = d3.select("#polygonchart").append("svg");

// Initialize the polygon: all located at the center of the svg area
let gs = svg.append("g");

svg.append("g").attr("id", "y-axis").attr("transform", `translate(${40}, 0)`);
svg.append("g").attr("id", "x-axis");

let domains = {};
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
        nonemed: [0, 1],
        nonemax: [0, 1],
    };
}

const EDGEPAD = 100 * window.devicePixelRatio;

let ranges = {
    size: d3.interpolate(20, 50),
    posx: d3.interpolate(0, width),
    posy: d3.interpolate(height, 0),
    // red at both ends doesn't make sense, skip the end
    colour: (i) => d3.interpolateSinebow(i * 0.7),
    saturation: d3.interpolate(0.1, 1),
    strokewidth: d3.interpolate(1, 5),
    strokelength: d3.interpolate(0.1, 1),
    sides: (f) => Math.round(d3.interpolate(3, 10)(f)),
    identity: (i) => i,
};

const resize = () => {
    width = (window.innerWidth - 10) * window.devicePixelRatio;
    height = (window.innerHeight - 10) * window.devicePixelRatio;

    d3.select("svg").attr("width", width).attr("height", height);
    d3.select("#x-axis").attr(
        "transform",
        `translate(0, ${height - 40 * window.devicePixelRatio})`
    );
    ranges.posx = d3.interpolate(EDGEPAD * 1.5, width - EDGEPAD);
    ranges.posy = d3.interpolate(height - EDGEPAD * 1.5, EDGEPAD);
    restyle();
};

// attach to window resize event
window.addEventListener("resize", resize);

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
    // set defaults
    for (let select of selects) {
        select.value = default_ranges[select.id];
    }
}

function polygon_points(radius, sides) {
    const N = Math.ceil(sides);
    return d3.range(N).map((i) => {
        let angle = (i / N) * 2 * Math.PI - Math.PI / 2;
        return [radius * Math.cos(angle), radius * Math.sin(angle)];
    });
}

const EXTRA_HINT_FIELDS = ["Effort", "Maturity", "When", "Risk Category"];

const title = (d) =>
    d.Name + "\n\n" + EXTRA_HINT_FIELDS.map((f) => `${f}: ${d[f]}`).join("\n");

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
        .on("mouseover", function (_event, d) {
            const text = JSON.stringify(d, null, 2);
            //console.log(text);
            //d3.select("#hint").node().innerHTML = `<pre>${text}</pre>`;
        });

    gs.append("polygon").append("title").text(title);

    gs.append("text")
        .attr("dominant-baseline", "middle")
        .attr("text-anchor", "middle")
        .text((d) => d.Code)
        .append("title")
        .text(title);

    // Apply these forces to the nodes and update their positions.
    // Once the force algorithm is happy with positions ('alpha' value is low enough), simulations will stop.
    simulation.nodes(data).on("tick", () => {
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
        .transition()
        .duration(1000)
        .attr("points", (d) => {
            const sides = getScale("sides")(d);
            const radius = getScale("size")(d);
            const str = polygon_points(radius, sides).join(" ");
            return str;
        })
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

// load data
const map_csv_row = (d) => ({
    ...d,
    Effort: +d["Effort"],
    "Upskill Effort": +d["Upskill Effort"],
    "Setup Effort": +d["Setup Effort"],
    Risk: +d["Risk"],
    Created: new Date(d["Created"]),
    Updated: new Date(d["Updated"]),
    "Team Size": +d["Team Size"],
    "Cost/Benefit": +d["Cost/Benefit"],
    nonemin: 0,
    nonemed: 0.5,
    nonemax: 1,
});

// try this next https://stackoverflow.com/questions/74464800/download-google-sheet-as-csv-from-url-using-javascript
// https://docs.google.com/spreadsheets/d/1PCaXLQFyUbgdJLoVp0LbQ6g4We6SuCAyhJHf694Ocp4/gviz/tq?tqx=out:csv&sheet=Sheet1
try {
    // couldn't figure out CORS with the IRESS sheet (can't share publically, requires IRESS credentials). Error was
    // Cross-Origin Request Blocked: The Same Origin Policy disallows reading the remote resource at https://docs.google.com/spreadsheets/d/1PCaXLQFyUbgdJLoVp0LbQ6g4We6SuCAyhJHf694Ocp4/gviz/tq?tqx=out:csv&sheet=Sheet1. (Reason: expected ‘true’ in CORS header ‘Access-Control-Allow-Credentials’).
    // or (credentials: "omit"): HTTP 401.
    // Fixed by using a public sheet from my personal account.
    const LIVE_DATA_URL =
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ6CsJDV3HRTgoRzKxQeNvF7bB3hoC-zFU5mhHazv5iBpVIOi6oqdwCok4DVeGR1ft4rdihlxGK4wSE/pub?gid=0&single=true&output=csv";
    data = await d3.csv(LIVE_DATA_URL, map_csv_row);
} catch (e) {
    console.log("Failed to load live data, falling back to local data", e);
    data = await d3.csv("data.csv", map_csv_row);
}

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

compute_domains();
resize();
draw(data);
restyle();
