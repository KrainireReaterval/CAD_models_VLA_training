"""Render STL files to a contact sheet (two shaded views each) for visual QA.

Usage: python -P -E tools/render_sheet.py OUT.png STL [STL ...]
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

MAX_FACES = 6000
LIGHT = np.array([0.4, -0.6, 0.7]) / np.linalg.norm([0.4, -0.6, 0.7])


def draw(ax, m, elev, azim):
    if len(m.faces) > MAX_FACES:
        idx = np.random.default_rng(0).choice(len(m.faces), MAX_FACES, replace=False)
        faces, normals = m.faces[idx], m.face_normals[idx]
    else:
        faces, normals = m.faces, m.face_normals
    shade = 0.35 + 0.65 * np.clip(normals @ LIGHT, 0, 1)
    pc = Poly3DCollection(m.vertices[faces], facecolors=np.c_[shade * 0.55, shade * 0.7, shade * 0.9],
                          edgecolor="none")
    ax.add_collection3d(pc)
    c, r = m.bounds.mean(axis=0), m.extents.max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    cols = 4
    rows = (len(paths) + cols - 1) // cols
    fig = plt.figure(figsize=(cols * 4.4, rows * 2.4))
    for i, p in enumerate(paths):
        m = trimesh.load(p, force="mesh")
        name = p.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
        for j, (elev, azim) in enumerate([(35, -60), (60, 120)]):
            ax = fig.add_subplot(rows, cols * 2, i * 2 + j + 1, projection="3d")
            draw(ax, m, elev, azim)
            if j == 0:
                ax.set_title(f"{name[:26]}\n{max(m.extents):.3f} m wt={m.is_watertight}", fontsize=7)
    plt.tight_layout()
    fig.savefig(out, dpi=80)


if __name__ == "__main__":
    main()
