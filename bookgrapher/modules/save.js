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

const exportState = state => ({
  nodes: state.nodes.map(n => ({
    id: n.id,
    text: n.text,
    level: n.level,
    x: n.x,
    y: n.y
  })),
  edges: state.edges.map(e => ({ source: e.source.id, target: e.target.id }))
});
