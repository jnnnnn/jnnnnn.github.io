export const save = state => {
  const object = exportState(state);
  const blob = new Blob([JSON.stringify(object)], {
    type: "application/json"
  });
  console.log("saving", blob);
  saveFile(blob, "bookchart.json");
};

const saveFile = (blob, name) => {
  const a = document.createElement("a");
  a.href = window.URL.createObjectURL(blob);
  a.download = name;
  a.rel = "x";
  document.body.append(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => window.URL.revokeObjectURL(a.href), 1000);
};

// convert the internal state representation into something that serializes neatly
export const exportState = state => ({
  nodes: state.nodes.map(n => ({
    id: n.id,
    text: n.text,
    level: n.level,
    x: n.x,
    y: n.y
  })),
  edges: state.edges.map(e => ({ source: e.source.id, target: e.target.id }))
});

// convert an exported object into the internal state representation
export const importState = exportedObj => {
  const nodemap = new Map(exportedObj.nodes.map(n => [n.id, n]));
  return {
    nodes: exportedObj.nodes,
    edges: exportedObj.edges.map(e => {
      return {
        source: nodemap.get(e.source),
        target: nodemap.get(e.target)
      };
    })
  };
};

export const dropFile = state => async dropEvent => {
  // don't want to load a json file as a document :/
  dropEvent.preventDefault();
  const json = await dropEvent.dataTransfer.files[0].text();

  JSON.parse(json);

  console.log(json);
};
