import random
import json

nodes = []

n = 0

edges = []


def gen_node(level):
    global n
    node = {"id": n, "x": n, "y": n + n % 2, "text": str(n), "level": level}
    nodes.append(node)
    n += 1
    if level < 3:
        children = [gen_node(level + 1) for _ in range(4)]
        for c in children:
            edge = {"source": node["id"], "target": c["id"]}
            edges.append(edge)
    return node


gen_node(-2)
N = len(nodes)

for n in range(0):
    edges.append(
        {"source": random.randint(0, N - 1), "target": random.randint(0, N - 1)}
    )

with open("testgraphtree.json", "w") as f:
    f.write(json.dumps({"nodes": nodes, "edges": edges}))
