"""Generate parametric Category 2 support objects (CC0, origin=cad) as raw meshes in meters.

Usage: python -P -E tools/make_supports.py OUT_DIR
Writes one .stl per design into OUT_DIR (a raw-input dir; tools/ingest.py then processes them).
All parts are unioned with manifold3d so the output is a single watertight body.
"""
import pathlib
import sys

import trimesh
from trimesh.creation import box


def union(parts):
    return trimesh.boolean.union(parts, engine="manifold")


def slab(w, d, t):
    return box([w, d, t], trimesh.transformations.translation_matrix([0, 0, t / 2]))


def legged_table(w, d, h, top_t, leg, inset):
    parts = [box([w, d, top_t], trimesh.transformations.translation_matrix([0, 0, h - top_t / 2]))]
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - inset - leg / 2), sy * (d / 2 - inset - leg / 2)
            parts.append(box([leg, leg, h - top_t + 1e-3],
                             trimesh.transformations.translation_matrix([x, y, (h - top_t) / 2])))
    return union(parts)


def rimmed_tray(w, d, base_t, rim_h, wall):
    outer = box([w, d, base_t + rim_h], trimesh.transformations.translation_matrix([0, 0, (base_t + rim_h) / 2]))
    pocket = box([w - 2 * wall, d - 2 * wall, rim_h + 1e-3],
                 trimesh.transformations.translation_matrix([0, 0, base_t + rim_h / 2 + 5e-4]))
    return trimesh.boolean.difference([outer, pocket], engine="manifold")


def shelf_unit(w, d, h, board_t, n_shelves, side_t):
    parts = []
    for sx in (-1, 1):
        parts.append(box([side_t, d, h], trimesh.transformations.translation_matrix([sx * (w / 2 - side_t / 2), 0, h / 2])))
    for k in range(n_shelves):
        z = board_t / 2 + k * (h - board_t) / (n_shelves - 1)
        parts.append(box([w - 2 * side_t + 2e-3, d, board_t], trimesh.transformations.translation_matrix([0, 0, z])))
    return union(parts)


def pedestal_table(r_top, h, top_t, r_col, r_base, base_t):
    top = trimesh.creation.cylinder(r_top, top_t, sections=96)
    top.apply_translation([0, 0, h - top_t / 2])
    col = trimesh.creation.cylinder(r_col, h - top_t - base_t + 2e-3, sections=48)
    col.apply_translation([0, 0, base_t + (h - top_t - base_t) / 2])
    base = trimesh.creation.cylinder(r_base, base_t, sections=96)
    base.apply_translation([0, 0, base_t / 2])
    return union([top, col, base])


DESIGNS = {
    "gen_slab_600x400x30": lambda: slab(0.60, 0.40, 0.03),
    "gen_table_700x500x450": lambda: legged_table(0.70, 0.50, 0.45, 0.025, 0.04, 0.02),
    "gen_tray_450x320_rim30": lambda: rimmed_tray(0.45, 0.32, 0.008, 0.03, 0.012),
    "gen_shelf_600x300x500": lambda: shelf_unit(0.60, 0.30, 0.50, 0.018, 3, 0.018),
    "gen_pedestal_r250_h400": lambda: pedestal_table(0.25, 0.40, 0.025, 0.03, 0.17, 0.02),
}


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in DESIGNS.items():
        m = fn()
        m.export(out / f"{name}.stl")
        print(name, [round(x, 3) for x in m.extents], m.is_watertight)


if __name__ == "__main__":
    main()
