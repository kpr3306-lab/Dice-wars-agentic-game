"""
Map Generator for Dice Wars Clone
-----------------------------------
Generates organic, hand-drawn-looking territory maps (NOT node graphs) by:
  1. Building an irregular island silhouette (randomized radial polygon, smoothed)
  2. Scattering seed points inside it (rejection-sampled for even spacing)
  3. Computing a Voronoi diagram over the seeds
  4. Clipping each Voronoi cell to the island silhouette with Shapely
  5. Deriving adjacency directly from Voronoi ridge pairs

Output: JSON files in game/data/ consumed by the Flask backend and the
Canvas renderer on the frontend. Each map is generated with a fixed seed
so it is stable across runs (deterministic + reproducible for grading).
"""
import json
import math
import random
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

def make_island_silhouette(cx, cy, base_radius, n_points=24, jitter=0.35, seed=0):
    rnd = random.Random(seed)
    # Randomized radii per angle, then smoothed with a moving average so the
    # coastline looks hand-drawn rather than spiky/noisy.
    raw_radii = [base_radius * (1 + rnd.uniform(-jitter, jitter)) for _ in range(n_points)]
    smoothed = []
    for i in range(n_points):
        window = [raw_radii[(i + k) % n_points] for k in (-1, 0, 1)]
        smoothed.append(sum(window) / len(window))
    pts = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        r = smoothed[i]
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return Polygon(pts)

def poisson_ish_points(poly, n_target, min_dist, seed=0, max_attempts=8000):
    rnd = random.Random(seed)
    minx, miny, maxx, maxy = poly.bounds
    pts = []
    attempts = 0
    while len(pts) < n_target and attempts < max_attempts:
        attempts += 1
        x = rnd.uniform(minx, maxx)
        y = rnd.uniform(miny, maxy)
        p = Point(x, y)
        if not poly.contains(p):
            continue
        if all((x - qx) ** 2 + (y - qy) ** 2 >= min_dist ** 2 for qx, qy in pts):
            pts.append((x, y))
    return pts

def bounded_voronoi_regions(points, bounding_box):
    # Add far-away "ghost" points so every real cell is a closed, finite polygon.
    minx, miny, maxx, maxy = bounding_box
    span = max(maxx - minx, maxy - miny) * 10
    ghosts = [
        (minx - span, miny - span), (maxx + span, miny - span),
        (minx - span, maxy + span), (maxx + span, maxy + span),
        ((minx + maxx) / 2, miny - span), ((minx + maxx) / 2, maxy + span),
        (minx - span, (miny + maxy) / 2), (maxx + span, (miny + maxy) / 2),
    ]
    all_points = np.array(list(points) + ghosts)
    vor = Voronoi(all_points)
    return vor, len(points)

def build_map(name, cx, cy, base_radius, n_territories, seed, min_dist_factor=0.22):
    island = make_island_silhouette(cx, cy, base_radius, seed=seed)
    min_dist = base_radius * min_dist_factor / math.sqrt(n_territories / 20)
    seeds = poisson_ish_points(island, n_territories, min_dist, seed=seed)
    vor, n_real = bounded_voronoi_regions(seeds, island.bounds)

    territories = []
    valid_index_map = {}  # original point index -> territory id (only for those that survive clipping)
    for i in range(n_real):
        region_index = vor.point_region[i]
        region = vor.regions[region_index]
        if -1 in region or len(region) == 0:
            continue
        cell_pts = [tuple(vor.vertices[v]) for v in region]
        try:
            cell_poly = Polygon(cell_pts)
            clipped = cell_poly.intersection(island)
        except Exception:
            continue
        if clipped.is_empty or clipped.area < 5:
            continue
        # Some clips can produce MultiPolygon slivers; keep the largest piece.
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda g: g.area)
        coords = list(clipped.exterior.coords)
        # simplify slightly for cleaner rendering / smaller payload
        clipped_simplified = clipped.simplify(1.5, preserve_topology=True)
        coords = list(clipped_simplified.exterior.coords)
        tid = len(territories)
        valid_index_map[i] = tid
        centroid = clipped.centroid
        territories.append({
            "id": tid,
            "polygon": [[round(x, 1), round(y, 1)] for x, y in coords],
            "centroid": [round(centroid.x, 1), round(centroid.y, 1)],
            "neighbors": set(),
        })

    # Adjacency straight from Voronoi ridge pairs (cells that share an edge)
    for (p1, p2) in vor.ridge_points:
        if p1 in valid_index_map and p2 in valid_index_map:
            a, b = valid_index_map[p1], valid_index_map[p2]
            territories[a]["neighbors"].add(b)
            territories[b]["neighbors"].add(a)

    for t in territories:
        t["neighbors"] = sorted(t["neighbors"])

    # drop any isolated territory (no neighbors) - rare edge artifact
    territories = [t for t in territories if t["neighbors"]]
    # re-index cleanly
    old_to_new = {t["id"]: i for i, t in enumerate(territories)}
    for t in territories:
        t["neighbors"] = sorted(old_to_new[n] for n in t["neighbors"] if n in old_to_new)
    for i, t in enumerate(territories):
        t["id"] = i

    minx, miny, maxx, maxy = island.bounds
    return {
        "name": name,
        "width": round(maxx - minx + 40, 1),
        "height": round(maxy - miny + 40, 1),
        "offset": [round(-minx + 20, 1), round(-miny + 20, 1)],
        "island_outline": [[round(x, 1), round(y, 1)] for x, y in island.exterior.coords],
        "territories": territories,
        "count": len(territories),
    }

def offset_map(m):
    ox, oy = m["offset"]
    for t in m["territories"]:
        t["polygon"] = [[x + ox, y + oy] for x, y in t["polygon"]]
        t["centroid"] = [t["centroid"][0] + ox, t["centroid"][1] + oy]
    m["island_outline"] = [[x + ox, y + oy] for x, y in m["island_outline"]]
    return m

if __name__ == "__main__":
    maps = [
        ("skirmish_isle", 400, 300, 260, 18, 7),
        ("twin_peninsulas", 450, 320, 300, 28, 21),
        ("grand_continent", 500, 360, 340, 40, 99),
    ]
    for name, cx, cy, r, n, seed in maps:
        m = build_map(name, cx, cy, r, n, seed)
        m = offset_map(m)
        path = f"/home/claude/dicewars/game/data/{name}.json"
        with open(path, "w") as f:
            json.dump(m, f)
        print(f"{name}: {m['count']} territories -> {path}")
