"""Process a batch spec (JSON list of assets) into library STLs + provenance records.

Usage: python -P -E tools/ingest.py tools/specs/<batch>.json [--only ID ...]

Each spec entry: asset_id, family, category_folder (relative to vla_library/), categories,
origin, source, source_url, license, source_units, input (path to raw mesh), and optional
scale, up, fit_longest, candidate_regions, ambiguous, notes, size_limit_m.
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB = ROOT / "vla_library"
PROV = LIB / "provenance"
PROCESS = ROOT / "tools" / "process_mesh.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    specs = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    PROV.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in specs:
        if a.only and s["asset_id"] not in a.only:
            continue
        out = LIB / s["category_folder"] / f"{s['asset_id']}.stl"
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-P", "-E", str(PROCESS), str(ROOT / s["input"]), str(out),
               "--scale", str(s.get("scale", 1.0)), "--up", s.get("up", "z")]
        if s.get("largest_only"):
            cmd += ["--largest-only"]
        if s.get("fit_longest"):
            cmd += ["--fit-longest", str(s["fit_longest"])]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL {s['asset_id']}: {r.stderr.strip()[-400:]}")
            continue
        stats = json.loads(r.stdout.strip().splitlines()[-1])
        rec = {k: v for k, v in s.items() if k != "input"}
        rec["raw_input"] = s["input"]
        rec["stats"] = stats
        limit = s.get("size_limit_m", 0.3)
        rec["over_size_limit"] = bool(limit and stats["longest_dim_m"] > limit)
        (PROV / f"{s['asset_id']}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        rows.append((s["asset_id"], stats["extents_m"], stats["watertight"], stats["face_count"],
                     stats["holes_filled"], rec["over_size_limit"]))
    print(f"{'asset_id':22} {'extents_m':28} {'wt':5} {'faces':>7} {'holes':>5} over")
    for aid, ext, wt, fc, h, over in rows:
        print(f"{aid:22} {str(ext):28} {str(wt):5} {fc:7d} {h:5d} {'OVER' if over else ''}")


if __name__ == "__main__":
    main()
