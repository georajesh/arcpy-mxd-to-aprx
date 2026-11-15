# arcpy-mxd-to-aprx

Bulk-convert ArcMap `.mxd` documents to ArcGIS Pro `.aprx` projects with ArcPy, then automatically repair broken data sources. Tested on ArcGIS Pro 3.x.

📝 **Background and walkthrough:** [read the blog post on LinkedIn](https://www.linkedin.com/pulse/bulk-converting-mxd-aprx-arcgis-3x-workflow-actually-works-dulal-5g9tc/)

---

## Why this exists

ArcMap is retired, and many organizations still have folders full of `.mxd` files. Opening and importing them into ArcGIS Pro one at a time is slow. Scripting it naively also runs into problems:

- Maps imported from an MXD don't always behave like native Pro maps, so later scripted edits can fail.
- Data paths in old MXDs often point to drives and folders that no longer exist, so layers come in **broken**.

This tool runs the whole batch in one pass. It creates a clean, writable map in every project and tries to reconnect broken layers for you.

## How it works

For each `.mxd` in a folder:

1. **Copy a blank template project.** Your `base.aprx` is copied to `<output>/<name>.aprx`.
2. **Import the MXD** with `ArcGISProject.importDocument()`.
3. **Create a writable native map** (`FinalMap` by default) and copy the imported layers into it, keeping their order.
4. **Repair broken layers** (optional). Each broken layer is matched by name against datasets in a data folder (e.g. `Roads` → `Roads.shp`) and reconnected with `updateConnectionProperties()`.

If one MXD fails, the error is logged and the batch carries on. A summary is printed at the end.

## Requirements

- ArcGIS Pro 3.x (licensed), which includes ArcPy
- Run it with ArcGIS Pro's Python environment (`arcgispro-py3`), from the Python Command Prompt, a Pro notebook, or the full path to its `python.exe`
- A blank `.aprx` to use as a template. Create a new empty project in ArcGIS Pro and save it, e.g. as `base.aprx`

## Usage

### Option 1: Command-line script

```bat
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" mxd_to_aprx.py ^
    --mxd-folder  "D:\GIS\legacy_mxds" ^
    --output      "D:\GIS\converted" ^
    --template    "D:\GIS\base.aprx" ^
    --data-folder "D:\GIS\data"
```

| Option | Required | Description |
|---|---|---|
| `--mxd-folder` | ✅ | Folder containing `.mxd` files |
| `--output` | ✅ | Where the `.aprx` files are written (created if missing). Existing files with the same name are replaced |
| `--template` | ✅ | Blank `.aprx` used as the base for every project |
| `--data-folder` | | Folder searched when repairing broken layers. Repair is skipped if omitted |
| `--map-name` | | Name of the writable map to create (default `FinalMap`) |
| `--recursive` | | Also convert `.mxd` files in subfolders |
| `--extensions` | | Extensions tried when matching layers by name (default `.shp .tif .lyrx` and no extension, which covers rasters and folder datasets) |

Example output:

```
Found 3 MXD file(s)

[OK] parcels_2012.mxd -> parcels_2012.aprx
[OK] zoning.mxd -> zoning.aprx
[X] Failed to convert corrupt_old.mxd: ...

Repairing broken layers...
  parcels_2012.aprx
    [+] Repaired: Roads -> D:\GIS\data\Roads.shp
    [!] Still broken: Contours

Summary
  Converted: 2
  Failed:    1
  Layers repaired:     1
  Layers still broken: 1
```

### Option 2: Jupyter notebook

Open [`notebooks/BulkConversion_mxd_to_aprx.ipynb`](notebooks/BulkConversion_mxd_to_aprx.ipynb) in ArcGIS Pro (Insert → Notebook) or Jupyter running on `arcgispro-py3`. Edit the folder paths at the top of each cell and run them in order:

1. **Convert MXD files to APRX projects**
2. **Repair broken layer connections**

## Limitations

- Only the **first** map (data frame) in each MXD is copied into the writable map. The other imported maps and layouts are still in the `.aprx`.
- Layer repair matches on **layer name = dataset name**. Layers that were renamed in the MXD, or that point to enterprise geodatabases or services, need manual repair (or extend `repair_layers()`).
- Layouts are imported as-is. Their map frames still reference the imported maps, not `FinalMap`.

## Contributing

Issues and pull requests are welcome, especially new repair strategies (e.g. geodatabase feature classes or path remapping).

## License

[MIT](LICENSE) © 2025 Rajesh Dulal
