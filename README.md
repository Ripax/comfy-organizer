# ComfyUI Model Organizer

A small PySide6 desktop app for browsing a ComfyUI `models` directory, inspecting model files, and staging file moves.

The left panel is the source folder tree and the right panel is the destination/browsing grid. Configure them independently in the root `.config` file:

```ini
[folders]
left = D:\ComfyUI\models
right = D:\ComfyUI\organized-models
```

Leave either value blank to fall back to `COMFYUI_MODELS_PATH` or the built-in default. Both folders must exist. Restart the app after editing `.config`.

The `[filter]` section controls file types shown in the left tree:

```ini
[filter]
filter = ['.safetensors', '.json', '.yaml', '.yml']
only_show = TRUE
```

With `only_show = TRUE`, only listed extensions are shown; with `FALSE`, listed extensions are hidden and other files are shown. Folders remain visible in either mode.

## Features

- Browse the left source tree and right destination grid independently. Double-click folders in the right grid to navigate within the configured right-side folder.
- The left tree keeps folders visible and applies the configurable extension include/exclude list; the right grid keeps the full folder contents visible.
- See recursive folder sizes with color cues.
- Recognize common model, config, and source-file extensions with distinct icons.
- Use neighboring images as `.safetensors` previews when available.
- Select a model to view its file details. For `.safetensors`, the app reads the header to show metadata and tensor names, data types, and shapes; it does not load model weights.
- Stage drag-and-drop moves and review them before committing.
- See startup status and progress on the branded splash screen.

> **Moving files:** Dragging only stages operations. **Commit Moves** performs the actual moves in the filesystem.

## Requirements

- Python 3.10 or newer
- PySide6

## Setup on Windows

From the project directory, create and activate a virtual environment, then install the dependency:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you leave both `.config` values blank, set the shared fallback directory for the current PowerShell session:

```powershell
$env:COMFYUI_MODELS_PATH = "D:\ComfyUI\models"
```

Run the app:

```powershell
python .\organizer.py
```

You can also launch it as a package:

```powershell
python -m comfy_organizer
```

The app also supports setting `COMFYUI_MODELS_PATH` as a persistent Windows environment variable.

## Development

Check Python syntax with:

```powershell
python -m compileall -q .\organizer.py .\comfy_organizer
```

The application is split into `comfy_organizer\core.py` (Qt UI and startup), `utils.py` (filesystem and metadata helpers), `icons.py` (app and file icons), and `qss.py` / `theme.qss` (stylesheet loading and styles). The root `organizer.py` remains a compatibility launcher. There is currently no automated test suite or packaged executable.
