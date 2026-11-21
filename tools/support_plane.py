"""Measure the main horizontal support plane of Category 2 assets and store it in provenance.

Usage: python -P -E tools/support_plane.py ASSET_ID [ASSET_ID ...]

Upward-facing faces (normal z > 0.99) are grouped by height (2 mm bins). The support plane is
the group with the largest area; groups within 5% of that area are tie-broken by height (so a
shelf reports its top board and a rimmed tray reports its floor, not the thin rim).
"""
import json
import pathlib
import sys

import numpy as np
import trimesh

LIB = pathlib.Path(__file__).resolve().parents[1] / "vla_library"


def support_plane(m):
    up = m.face_normals[:, 2] > 0.99
    z = m.triangles_center[up, 2]
    area = m.area_faces[up]
    bins = np.round(z / 0.002).astype(int)
    groups = {b: area[bins == b].sum() for b in np.unique(bins)}
    best = max(groups.values())
    b = max(k for k, v in groups.items() if v >= 0.95 * best)
    sel = np.where(up)[0][bins == b]
    pts = m.triangles[sel].reshape(-1, 3)
    ext = pts.max(axis=0) - pts.min(axis=0)
    return dict(height_m=round(float(pts[:, 2].mean()), 4), extent_xy_m=[round(float(ext[0]), 4), round(float(ext[1]), 4)],
                area_m2=round(float(m.area_faces[sel].sum()), 4))


def main():
    for aid in sys.argv[1:]:
        p = LIB / "provenance" / f"{aid}.json"
        rec = json.loads(p.read_text(encoding="utf-8"))
        m = trimesh.load(LIB / rec["category_folder"] / f"{aid}.stl", force="mesh")
        rec["support_plane"] = support_plane(m)
        p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(aid, rec["support_plane"], "bbox", [round(float(x), 3) for x in m.extents])


if __name__ == "__main__":
    main()
