"""
Weighted Graph + Dijkstra's shortest path
-----------------------------------------
Used for: finding the NEAREST MEDICAL STORES.

The city is modelled as a graph:
  * vertices = places (localities / junctions / stores)
  * edges    = roads, weighted by distance in km
Dijkstra's algorithm (using our own MinHeap) finds the shortest road
distance from the patient's location to every store, and we can rebuild
the exact route using the `previous` map.

  Dijkstra with a binary heap : O((V + E) log V)
"""

from .heap import MinHeap


class Graph:
    def __init__(self):
        self.adj = {}        # vertex -> list of (neighbour, weight)   (adjacency list)
        self.pos = {}        # vertex -> (x, y) only used to draw the map

    def add_vertex(self, v, x=0, y=0):
        self.adj.setdefault(v, [])
        self.pos[v] = (x, y)

    def add_edge(self, u, v, w):
        """Undirected road of length w km."""
        self.adj.setdefault(u, []).append((v, w))
        self.adj.setdefault(v, []).append((u, w))

    def edges(self):
        seen, out = set(), []
        for u, nbrs in self.adj.items():
            for v, w in nbrs:
                key = (u, v) if u < v else (v, u)     # same road seen from both ends
                if key not in seen:
                    seen.add(key)
                    out.append((u, v, w))
        return out

    def dijkstra(self, source):
        dist = {v: float("inf") for v in self.adj}
        prev = {v: None for v in self.adj}
        dist[source] = 0
        pq = MinHeap()
        pq.push(0, source)
        visited = set()
        while len(pq):
            u = pq.pop()
            if u in visited:
                continue
            visited.add(u)
            for v, w in self.adj[u]:
                nd = dist[u] + w
                if nd < dist[v]:          # relaxation step
                    dist[v] = nd
                    prev[v] = u
                    pq.push(nd, v)
        return dist, prev

    @staticmethod
    def build_path(prev, target):
        path = []
        while target is not None:
            path.append(target)
            target = prev[target]
        return path[::-1]
