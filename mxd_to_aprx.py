"""
Bulk-convert ArcMap .mxd documents to ArcGIS Pro .aprx projects, then repair broken layers.

Run with the Python that ships with ArcGIS Pro (arcgispro-py3), for example:

    "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" mxd_to_aprx.py ^
        --mxd-folder  "D:\\GIS\\legacy_mxds" ^
        --output      "D:\\GIS\\converted" ^
        --template    "D:\\GIS\\base.aprx" ^
        --data-folder "D:\\GIS\\data"

Workflow (per MXD):
  1. Copy a blank template .aprx to <output>/<name>.aprx
  2. Import the MXD into it (importDocument)
  3. Create a new, writable native map ("FinalMap" by default) and copy the imported layers into it
  4. Optionally repair broken layers by looking for a dataset with the layer's name in --data-folder
"""

import argparse
import os
import sys

import arcpy


def find_mxds(folder, recursive):
    if not recursive:
        return sorted(
            os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".mxd")
        )
    found = []
    for root, _dirs, files in os.walk(folder):
        found.extend(os.path.join(root, f) for f in files if f.lower().endswith(".mxd"))
    return sorted(found)


def top_level_layers(map_obj):
    # listLayers() also returns layers nested in group layers; adding a group layer already
    # brings its children, so only copy top-level layers to avoid duplicates.
    return [lyr for lyr in map_obj.listLayers() if "\\" not in lyr.longName]


def convert_mxd(mxd_path, output_folder, template_aprx, map_name):
    aprx_name = os.path.splitext(os.path.basename(mxd_path))[0] + ".aprx"
    aprx_path = os.path.join(output_folder, aprx_name)

    if os.path.exists(aprx_path):
        os.remove(aprx_path)
        print(f"[~] Replacing existing: {aprx_name}")

    # 1. Copy the blank base project
    arcpy.mp.ArcGISProject(template_aprx).saveACopy(aprx_path)

    # 2. Import the MXD, tracking which maps the import added (ignores any maps in the template)
    aprx = arcpy.mp.ArcGISProject(aprx_path)
    before = {m.name for m in aprx.listMaps()}
    aprx.importDocument(mxd_path)
    imported = [m for m in aprx.listMaps() if m.name not in before]
    if not imported:
        raise RuntimeError("import produced no maps")

    # 3. Create a writable native map and copy the imported layers into it, preserving order
    final_map = aprx.createMap(map_name)
    for lyr in top_level_layers(imported[0]):
        final_map.addLayer(lyr, "BOTTOM")

    aprx.save()
    del aprx
    return aprx_path


def repair_layers(aprx_path, data_folder, map_name, extensions):
    aprx = arcpy.mp.ArcGISProject(aprx_path)
    maps = aprx.listMaps(map_name)
    if not maps:
        print(f"    [!] No map named '{map_name}' found, skipping repair")
        return 0, 0

    repaired = still_broken = 0
    for lyr in maps[0].listLayers():
        if lyr.isGroupLayer or not lyr.supports("DATASOURCE") or not lyr.isBroken:
            continue
        for ext in extensions:
            guess_path = os.path.join(data_folder, lyr.name + ext)
            if arcpy.Exists(guess_path):
                try:
                    lyr.updateConnectionProperties(None, guess_path)
                    print(f"    [+] Repaired: {lyr.name} -> {guess_path}")
                    repaired += 1
                except Exception as e:  # noqa: BLE001 - report and keep going
                    print(f"    [!] Error repairing {lyr.name}: {e}")
                    still_broken += 1
                break
        else:
            print(f"    [!] Still broken: {lyr.name}")
            still_broken += 1

    aprx.save()
    del aprx
    return repaired, still_broken


def main():
    p = argparse.ArgumentParser(description="Bulk-convert ArcMap .mxd files to ArcGIS Pro .aprx projects.")
    p.add_argument("--mxd-folder", required=True, help="Folder containing .mxd files")
    p.add_argument("--output", required=True, help="Folder to write .aprx files to (created if missing)")
    p.add_argument("--template", required=True, help="Blank .aprx used as the base for every new project")
    p.add_argument("--data-folder", help="Folder to search when repairing broken layers (skip repair if omitted)")
    p.add_argument("--map-name", default="FinalMap", help="Name of the writable map to create (default: FinalMap)")
    p.add_argument("--recursive", action="store_true", help="Also look for .mxd files in subfolders")
    p.add_argument(
        "--extensions",
        nargs="*",
        default=[".shp", ".tif", ".lyrx", ""],
        help="File extensions to try when matching a broken layer by name (default: .shp .tif .lyrx and no extension)",
    )
    args = p.parse_args()

    for path, label in [(args.mxd_folder, "--mxd-folder"), (args.template, "--template")]:
        if not os.path.exists(path):
            sys.exit(f"{label} not found: {path}")
    os.makedirs(args.output, exist_ok=True)

    mxds = find_mxds(args.mxd_folder, args.recursive)
    print(f"Found {len(mxds)} MXD file(s)\n")

    converted, failed = [], []
    for mxd in mxds:
        try:
            aprx_path = convert_mxd(mxd, args.output, args.template, args.map_name)
            print(f"[OK] {os.path.basename(mxd)} -> {os.path.basename(aprx_path)}")
            converted.append(aprx_path)
        except Exception as e:  # noqa: BLE001 - one bad MXD shouldn't stop the batch
            print(f"[X] Failed to convert {os.path.basename(mxd)}: {e}")
            failed.append(mxd)

    total_repaired = total_broken = 0
    if args.data_folder:
        print("\nRepairing broken layers...")
        for aprx_path in converted:
            print(f"  {os.path.basename(aprx_path)}")
            try:
                r, b = repair_layers(aprx_path, args.data_folder, args.map_name, args.extensions)
                total_repaired += r
                total_broken += b
            except Exception as e:  # noqa: BLE001
                print(f"    [X] Repair failed: {e}")

    print("\nSummary")
    print(f"  Converted: {len(converted)}")
    print(f"  Failed:    {len(failed)}")
    if args.data_folder:
        print(f"  Layers repaired:     {total_repaired}")
        print(f"  Layers still broken: {total_broken}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
