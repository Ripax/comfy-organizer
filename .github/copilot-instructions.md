# Copilot instructions

## Project shape

This repository contains one PySide6/Qt desktop application for organizing files under a ComfyUI `models` directory. The root `organizer.py` is a compatibility launcher; implementation lives in the `comfy_organizer` package.

The project includes `README.md`, `requirements.txt`, and `.gitignore`. There is no automated test suite, linter configuration, or packaged executable.

## Running and validation

- Run the GUI:

  ```powershell
  python .\organizer.py
  ```

- Or launch the package:

  ```powershell
  python -m comfy_organizer
  ```

- There is no separate build command.
- The app targets Python with PySide6 installed. Its only third-party runtime dependency is `PySide6`.
- `main()` reads separate `left` and `right` folder paths from the project-root `.config`. Blank entries use `COMFYUI_MODELS_PATH` when set, otherwise the built-in ComfyUI models path:

  ```text
  C:\Users\Rion\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models
  ```

  For local testing under another installation or user account, set the environment variable before launching.

- At minimum, validate syntax with:

  ```powershell
  python -m compileall -q .\organizer.py .\comfy_organizer
  ```

- For GUI changes, start the app after compilation and exercise the relevant drag/drop and commit flow. There is no single-test runner or test selector.

## Architecture

The application is split across a small package:

- `comfy_organizer/core.py` contains `StagedTreeView`, `StagedGridView`, `FolderSizeFileSystemModel`, `ComfyUIModelOrganizer`, and `main()`.
- `comfy_organizer/utils.py` contains filesystem, size-formatting, and safetensors-header helpers.
- `comfy_organizer/icons.py` provides app and extension/preview icons; the app SVG is in `comfy_organizer/assets/`.
- `comfy_organizer/splash.py` builds the startup splash screen; version and creator metadata are in `comfy_organizer/__init__.py`.
- `comfy_organizer/qss.py` loads the stylesheet from `comfy_organizer/theme.qss`.
- `organizer.py` and `comfy_organizer/__main__.py` are launchers.
- `StagedTreeView` accepts dropped file URLs and emits `move_queued(source, destination)`.
- `StagedGridView` has the same staged drag/drop contract, but resolves drops on items or the grid root differently.
- `ComfyUIModelOrganizer` owns the shared `QFileSystemModel`, builds the split tree/grid/table UI, and processes the pending move queue.
- Source and destination paths are configured in `.config`; they are not editable or displayed as path fields in the UI. Navigate the right grid with double-click and Parent Folder.
- The left tree root and right grid root are configured independently. The left panel is the source tree; the right panel is the destination/browsing grid.
- The left tree uses `LeftPanelFilterModel`: retain directories and apply the `.config` extension include/exclude list. The default list is supported model formats plus `.json`, `.yaml`, and `.yml`; the right grid remains unfiltered.
- The `.config` `[filter]` section supplies the extension list and `only_show` mode for the left tree; keep directories visible in either mode.
- The pending operations table is the in-memory staging layer: it stores source file paths and destination folders, not the Qt model indexes or actual files.
- `commit_moves()` performs the filesystem moves with `shutil.move()`. The queue is cleared and the views are refreshed after an attempt, even when individual operations failed.

The application is not a live file manager. Dragging a file only queues it; `Commit Moves` performs the actual filesystem changes.

## Code conventions

- Preserve the existing Qt signal pattern: drag/drop views emit `move_queued = Signal(str, str)` and the main window receives it through `add_to_queue()`.
- Source and destination paths should be absolute. `add_to_queue()` normalizes both paths and prevents duplicate sources in the pending table.
- Destination validation in both view classes rejects the source itself and drops inside a source directory. Keep this guard when changing drag/drop behavior.
- Before `commit_moves()` calls `shutil.move()`, preserve checks for:
  - missing source,
  - missing destination folder,
  - source already at the intended destination,
  - an existing destination file.
- The queue table has exactly two columns: source file and destination folder. Errors should continue to be summarized in `QMessageBox` rather than interrupting the whole commit loop.
- Application styles live in `comfy_organizer/theme.qss`; `apply_dark_theme()` loads them through `qss.py`. Update object names and matching `setObjectName()` values together when restyling controls.
- `refresh_views()` resets the shared `QFileSystemModel` root and recursively re-expands the left hierarchy.
