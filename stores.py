"""
Medical stores: find the nearest store that has all of a patient's medicines.

Data structure used here:
    Graph -> places around VIIT are vertices, roads are edges with a distance in km
"""

from sorting_searching import merge_sort, quick_sort


# =====================================================================
# Graph: places are vertices, roads are edges with a distance in km.
# Stored as an adjacency list: place -> list of (neighbour, km).
# =====================================================================
class Graph:
    def __init__(self):
        self.adj = {}
        self.pos = {}                  # (x, y) of each place, only for drawing the map

    def add_vertex(self, place, x=0, y=0):
        self.adj.setdefault(place, [])
        self.pos[place] = (x, y)

    def add_edge(self, a, b, km):
        """A two-way road between a and b."""
        self.adj.setdefault(a, []).append((b, km))
        self.adj.setdefault(b, []).append((a, km))

    def edges(self):
        """Each road once (it is stored from both ends)."""
        seen, roads = set(), []
        for a in self.adj:
            for b, km in self.adj[a]:
                pair = (a, b) if a < b else (b, a)
                if pair not in seen:
                    seen.add(pair)
                    roads.append((a, b, km))
        return roads

    def shortest_distances(self, start):
        """Shortest road distance from start to every place.
        Repeatedly pick the closest place not visited yet, then check whether
        going through it gives a shorter way to its neighbours.
        Returns (distance, previous): previous[p] is the place before p on the best route."""
        distance = {p: float("inf") for p in self.adj}
        previous = {p: None for p in self.adj}
        distance[start] = 0
        visited = set()
        while len(visited) < len(self.adj):
            closest = None
            for p in self.adj:
                if p not in visited and (closest is None or distance[p] < distance[closest]):
                    closest = p
            if distance[closest] == float("inf"):
                break                  # the rest can't be reached
            visited.add(closest)
            for neighbour, km in self.adj[closest]:
                if distance[closest] + km < distance[neighbour]:
                    distance[neighbour] = distance[closest] + km
                    previous[neighbour] = closest
        return distance, previous

    @staticmethod
    def route(previous, end):
        path = []
        while end is not None:
            path.append(end)
            end = previous[end]
        return path[::-1]


# =====================================================================
# The medical stores part of CareMate
# =====================================================================
class Stores:
    def add_place(self, name, x, y):
        self.city.add_vertex(name, x, y)
        self._save("places", name=name, x=x, y=y)

    def add_road(self, a, b, km):
        self.city.add_edge(a, b, km)
        self._save("roads", place_a=a, place_b=b, km=km)

    def add_store(self, name, node, hours, phone, stock, sid=None):
        sid = sid or self._next_id("S")
        self.stores[sid] = dict(id=sid, name=name, node=node, hours=hours, phone=phone,
                                stock=set(m.lower() for m in stock))
        self._save("stores", id=sid, name=name, node=node, hours=hours, phone=phone)
        for m in set(stock):
            self._save("store_stock", ignore=True, store_id=sid, medicine=m)
        return sid

    def nearest_stores(self, from_place, needed=None):
        dist, prev = self.city.shortest_distances(from_place)
        needed = [m.lower() for m in (needed or [])]
        results = []
        for s in self.stores.values():
            d = dist.get(s["node"], float("inf"))
            have = [m for m in needed if m in s["stock"]]
            results.append(dict(store=s, distance=round(d, 1),
                                path=Graph.route(prev, s["node"]),
                                has_all=len(have) == len(needed), available=len(have),
                                missing=[m for m in needed if m not in s["stock"]]))
        # stores that stock everything first, then by distance (quick sort)
        return quick_sort(results, key=lambda r: (not r["has_all"], r["distance"]))

    def places(self):
        return merge_sort([v for v in self.city.adj if not v.startswith("store:")])
