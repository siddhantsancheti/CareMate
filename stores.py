import data
from sorting_searching import merge_sort, quick_sort


class Graph:
    def __init__(self):
        self.roads = {}
        self.pos = {}

    def add_place(self, place, x, y):
        self.roads[place] = []
        self.pos[place] = (x, y)

    def add_road(self, a, b, km):
        self.roads[a].append((b, km))
        self.roads[b].append((a, km))

    def all_roads(self):
        return [(a, b, km) for a in self.roads for b, km in self.roads[a] if a < b]

    def shortest_distances(self, start):
        distance = {p: float("inf") for p in self.roads}
        previous = {p: None for p in self.roads}
        distance[start] = 0
        visited = set()
        while len(visited) < len(self.roads):
            closest = None
            for p in self.roads:
                if p not in visited and (closest is None or distance[p] < distance[closest]):
                    closest = p
            visited.add(closest)
            for neighbour, km in self.roads[closest]:
                if distance[closest] + km < distance[neighbour]:
                    distance[neighbour] = distance[closest] + km
                    previous[neighbour] = closest
        return distance, previous


city = Graph()


def route(previous, end):
    path = []
    while end is not None:
        path.append(end)
        end = previous[end]
    return path[::-1]


def add_store(name, near, x, y, km, hours, phone, stock):
    node = "store:" + name
    city.add_place(node, x, y)
    city.add_road(near, node, km)
    sid = data.new_id("S")
    data.stores[sid] = dict(id=sid, name=name, node=node, hours=hours, phone=phone,
                            stock=[m.lower() for m in stock])


def nearest_stores(from_place, needed):
    distance, previous = city.shortest_distances(from_place)
    results = []
    for s in data.stores.values():
        missing = [m for m in needed if m.lower() not in s["stock"]]
        results.append(dict(store=s, distance=round(distance[s["node"]], 1), path=route(previous, s["node"]),
                            has_all=not missing, available=len(needed) - len(missing), missing=missing))
    return quick_sort(results, key=lambda r: (not r["has_all"], r["distance"]))


def places():
    return merge_sort([p for p in city.roads if not p.startswith("store:")])
