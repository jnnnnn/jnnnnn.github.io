
var margin = { top: 20, right: 90, bottom: 30, left: 90 },
    width = 960 - margin.left - margin.right,
    height = 500 - margin.top - margin.bottom;

var duration = 750;

function load_text_data() {
    var raw = document.getElementById("textdata").value;
    if (!raw)
        return;
    var csv_rows = d3.tsvParse(raw);

    var root = d3.stratify()
        .id(d => d.Index)
        .parentId(d => d.Parent)
        (csv_rows);
    root.x0 = height / 2;
    root.y0 = 0;
    update(root);
}

function update(root) {

    // We need to compute positions for all the nodes...
    var treeData = d3.tree().nodeSize([20, 100])(root);
    var nodes = treeData.descendants();
    var links = treeData.descendants().slice(1);

    let height = d3.max(nodes.map(d => d.x))*2.2;
    let width = d3.max(nodes.map(d => d.y));

    d3.select('svg#chart')
        .attr('width', width*2+100)
        .attr('height', height);
    d3.select('svg#chart g')
        .attr("transform", "translate(" + 100 + "," + height/2 + ")");
    root.x0 = height;

    // Now that we know where they should be, add or update the nodes of the graph in the svg chart
    var node = d3.select('svg#chart g').selectAll('g.node')
        .data(nodes, d => d.id);

    var nodeEnterList = node.enter();

    var nodeEnter = nodeEnterList.append('g')
        .attr('class', 'node')
        .attr("transform", d => "translate(" + root.y0 + "," + root.x0 + ")");
    nodeEnter.append('circle')
        .attr('class', 'node')
        .attr('r', 1e-6)
        .style("fill", d => d._children ? "lightsteelblue" : "#fff");

    nodeEnter.append('text')
        .attr("dy", ".35em")
        .attr("x", d => d.children || d._children ? -13 : 13)
        .attr("text-anchor", d => d.children || d._children ? "end" : "start")
        .text(d => d.data.Description);

    var nodeUpdate = nodeEnter.merge(node);

    nodeUpdate.transition()
        .duration(duration)
        .attr("transform", d => "translate(" + d.y + "," + d.x + ")");

    nodeUpdate.select('circle.node')
        .attr('r', 10)
        .style("fill", d => d._children ? "lightsteelblue" : "#fff")
        .attr('cursor', 'pointer');

    var nodeExit = node.exit().transition()
        .duration(duration)
        .attr("transform", d => "translate(" + root.y + "," + root.x + ")")
        .remove();

    nodeExit.select('circle')
        .attr('r', 1e-6);

    nodeExit.select('text')
        .style('fill-opacity', 1e-6);

    // Update the links...
    var link = d3.select('svg#chart g').selectAll('path.link')
        .data(links, d => d.id);

    var linkEnter = link.enter().insert('path', "g")
        .attr("class", "link")
        .attr('d', function (d) {
            var o = { x: root.x0, y: root.y0 }
            return diagonal(o, o)
        });

    var linkUpdate = linkEnter.merge(link);
    linkUpdate.transition()
        .duration(duration)
        .attr('d', d => diagonal(d, d.parent));

    var linkExit = link.exit().transition()
        .duration(duration)
        .attr('d', function (d) {
            var o = { x: root.x, y: root.y }
            return diagonal(o, o)
        })
        .remove();

    // Store the old positions for transition.
    nodes.forEach(function (d) {
        d.x0 = d.x;
        d.y0 = d.y;
    });

    // Creates a curved (diagonal) path from parent to the child nodes
    function diagonal(s, d) {
        return `M ${s.y} ${s.x}
          C ${(s.y + d.y) / 2} ${s.x},
            ${(s.y + d.y) / 2} ${d.x},
            ${d.y} ${d.x}`
    }
}