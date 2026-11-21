"""Convert a source mesh into a library STL (meters, outward normals, not mirrored).

Usage:
    python -P -E tools/process_mesh.py IN OUT_STL --scale 1.0 [--up z|y] [--max-faces 100000]
        [--max-hole-edges 40] [--fit-longest METERS]

Prints a JSON dict of stats on stdout. Never rescales to fit a size limit unless
--fit-longest is given explicitly (used only for unitless sources such as Objaverse).
"""
import argparse
import json
import sys

import numpy as np
import trimesh


def load_mesh(path):
    # skip_materials drops UVs so texture seams do not split vertices
    m = trimesh.load(path, force="mesh", skip_materials=True, process=False)
    m = trimesh.Trimesh(vertices=np.asarray(m.vertices, dtype=np.float64),
                        faces=np.asarray(m.faces), process=True)
    m.merge_vertices(merge_tex=True, merge_norm=True)
    return m


def clean(m):
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()
    return m


def boundary_loops(m):
    edges = m.edges_sorted
    uniq, counts = np.unique(edges, axis=0, return_counts=True)
    bnd = uniq[counts == 1]
    if len(bnd) == 0:
        return []
    g = {}
    for a, b in bnd:
        g.setdefault(a, []).append(b)
        g.setdefault(b, []).append(a)
    seen, loops = set(), []
    for start in g:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        ok = True
        while True:
            nbrs = [n for n in g[cur] if n != prev]
            if len(g[cur]) != 2 or not nbrs:
                ok = False
                break
            nxt = nbrs[0]
            if nxt == start:
                break
            if nxt in seen:
                ok = False
                break
            loop.append(nxt)
            seen.add(nxt)
            prev, cur = cur, nxt
        if ok and len(loop) >= 3:
            loops.append(loop)
    return loops


def fill_small_holes(m, max_edges):
    """Fan-fill boundary loops with <= max_edges edges. Returns number of holes filled."""
    trimesh.repair.fill_holes(m)
    loops = [l for l in boundary_loops(m) if len(l) <= max_edges]
    if not loops:
        return 0
    verts = [m.vertices]
    faces = [m.faces]
    n = len(m.vertices)
    for loop in loops:
        c = m.vertices[loop].mean(axis=0)
        verts.append(c[None])
        for i in range(len(loop)):
            faces.append(np.array([[loop[i], loop[(i + 1) % len(loop)], n]]))
        n += 1
    m2 = trimesh.Trimesh(np.vstack(verts), np.vstack(faces), process=True)
    m.vertices, m.faces = m2.vertices, m2.faces
    return len(loops)


def decimate(m, max_faces):
    import fast_simplification
    if len(m.faces) <= max_faces:
        return m, False
    reduction = 1.0 - (max_faces * 0.95) / len(m.faces)
    v, f = fast_simplification.simplify(m.vertices.astype(np.float32), m.faces.astype(np.int32),
                                        target_reduction=reduction)
    return trimesh.Trimesh(v.astype(np.float64), f, process=True), True


def meshfix(m, max_extent_change=0.02):
    """Fallback for non-manifold pinches / larger cracks. Returns a repaired mesh only if it is
    watertight and its extents stay within max_extent_change of the input; otherwise None."""
    import pymeshfix
    v, f = pymeshfix.clean_from_arrays(np.ascontiguousarray(m.vertices, dtype=np.float64),
                                          np.ascontiguousarray(m.faces, dtype=np.int32))
    if len(f) == 0:
        return None
    r = trimesh.Trimesh(v, f, process=True)
    rel = np.abs(r.extents - m.extents) / np.maximum(m.extents, 1e-9)
    if r.is_watertight and rel.max() <= max_extent_change:
        return r
    return None


def stl_roundtrip_watertight(m):
    import io
    buf = io.BytesIO(m.export(file_type="stl"))
    return trimesh.load(buf, file_type="stl", force="mesh").is_watertight


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply source coords to get meters")
    ap.add_argument("--up", choices=["z", "y"], default="z", help="source up axis")
    ap.add_argument("--fit-longest", type=float, default=None,
                    help="unitless sources only: scale so longest extent equals this (m)")
    ap.add_argument("--max-faces", type=int, default=100_000)
    ap.add_argument("--max-hole-edges", type=int, default=40)
    ap.add_argument("--largest-only", action="store_true",
                    help="keep the largest component and parts touching its bbox (drops loose extras)")
    a = ap.parse_args()

    m = clean(load_mesh(a.inp))
    if a.largest_only:
        # drop loose extra objects shipped in the same file (e.g. a lid lying beside a pan)
        # keep the largest part plus every part whose bounding box touches it (attached handles)
        parts = m.split(only_watertight=False)
        main = max(parts, key=lambda p: p.area)
        lo, hi = main.bounds[0] - 1e-6, main.bounds[1] + 1e-6
        keep = [p for p in parts if np.all(p.bounds[0] <= hi) and np.all(p.bounds[1] >= lo)]
        m = trimesh.util.concatenate(keep)
    if a.up == "y":
        # proper rotation (+90 deg about X): Y-up -> Z-up, determinant +1, no mirroring
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    scale = a.scale
    if a.fit_longest:
        scale = a.fit_longest / float(m.extents.max())
    m.apply_scale(scale)

    holes = fill_small_holes(m, a.max_hole_edges)
    m, decimated = decimate(m, a.max_faces)
    if decimated and not m.is_watertight:
        holes += fill_small_holes(m, a.max_hole_edges)
    clean(m)
    repair = "none"
    if not m.is_watertight:
        repair = "native_failed"
        fixed = meshfix(m)
        if fixed is not None:
            m, repair = fixed, "meshfix"
    trimesh.repair.fix_normals(m, multibody=True)
    if m.is_watertight and m.body_count > 1:
        # intersecting closed parts (e.g. handle pushed into body) leave internal surfaces;
        # a boolean union removes them while keeping genuinely separate parts separate
        try:
            u = trimesh.boolean.union(m.split(only_watertight=False), engine="manifold")
            if u.is_watertight and len(u.faces) and stl_roundtrip_watertight(u):
                m, repair = u, (repair + "+union" if repair != "none" else "union")
        except Exception:
            pass
    inverted = False
    if m.is_watertight and m.volume < 0:
        m.invert()
        inverted = True
    # rest on z=0, centered in xy (translation only)
    b = m.bounds
    m.apply_translation([-(b[0, 0] + b[1, 0]) / 2, -(b[0, 1] + b[1, 1]) / 2, -b[0, 2]])

    m.export(a.out, file_type="stl")
    chk = trimesh.load(a.out, force="mesh")
    stats = {
        "extents_m": [round(float(x), 4) for x in chk.extents],
        "longest_dim_m": round(float(chk.extents.max()), 4),
        "watertight": bool(chk.is_watertight),
        "volume_m3": round(float(chk.volume), 7) if chk.is_watertight else None,
        "face_count": int(len(chk.faces)),
        "bodies": int(chk.body_count),
        "holes_filled": holes,
        "decimated": decimated,
        "normals_inverted": inverted,
        "repair": repair,
        "assigned_scale_m": scale,
    }
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
