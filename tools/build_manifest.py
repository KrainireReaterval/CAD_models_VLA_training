"""Rebuild vla_library/manifest.csv from vla_library/provenance/*.json (one row per asset)."""
import csv
import json
import pathlib
import sys

LIB = pathlib.Path(__file__).resolve().parents[1] / "vla_library"
COLS = ["asset_id", "family", "category_folder", "categories", "origin", "source", "source_url",
        "license", "source_units", "assigned_scale_m", "longest_dim_m", "watertight", "face_count",
        "candidate_regions", "ambiguous", "notes"]


def main():
    # optional args: category_folder prefixes to include (e.g. category1) so each commit's manifest
    # only lists assets committed so far
    prefixes = tuple(sys.argv[1:]) or ("",)
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((LIB / "provenance").glob("*.json"))]
    recs = [r for r in recs if r["category_folder"].startswith(prefixes)]
    with open(LIB / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in sorted(recs, key=lambda r: (r["category_folder"], r["asset_id"])):
            st = r["stats"]
            notes = list(filter(None, [r.get("notes", "")]))
            if r.get("over_size_limit"):
                notes.append(f"OVER_SIZE_LIMIT ({st['longest_dim_m']} m)")
            if st.get("repair") == "meshfix":
                notes.append("repair=meshfix")
            if not st["watertight"]:
                notes.append("not_watertight")
            if st["holes_filled"]:
                notes.append(f"holes_filled={st['holes_filled']}")
            if st["decimated"]:
                notes.append("decimated")
            notes.append("extents_m=" + "x".join(str(x) for x in st["extents_m"]))
            w.writerow([
                r["asset_id"], r["family"], "vla_library/" + r["category_folder"],
                "[" + ", ".join(r["categories"]) + "]", r["origin"], r["source"], r["source_url"],
                r["license"], r["source_units"], f"{st['assigned_scale_m']:.6g}", st["longest_dim_m"],
                st["watertight"], st["face_count"], ";".join(r.get("candidate_regions", [])),
                r.get("ambiguous", False), "; ".join(notes),
            ])
    print(f"manifest.csv: {len(recs)} rows")


if __name__ == "__main__":
    main()
