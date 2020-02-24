N = 1000

import random
import json

nodes = [{"id": n, "x": n, "y": n, "text": str(n), "level": 3} for n in range(N)]
edges = [{"source": n, "target": (n + 1) % N} for n in range(N)]

for n in range(N // 10):
    edges.append(
        {"source": random.randint(0, N - 1), "target": random.randint(0, N - 1)}
    )

with open("testgraph.json", "w") as f:
    f.write(json.dumps({"nodes": nodes, "edges": edges}))
