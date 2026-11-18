"""Filesystem and model-metadata helpers."""

import configparser
import ast
import json
import os
from pathlib import Path


MODEL_EXTENSIONS = frozenset(
    {
        ".bin",
        ".ckpt",
        ".gguf",
        ".model",
        ".onnx",
        ".pt",
        ".pth",
        ".safetensors",
        ".tflite",
    }
)

DEFAULT_FILTER_EXTENSIONS = frozenset(
    {
        ".safetensors",
        ".json",
        ".yaml",
        ".yml",
    }
)

DEFAULT_MODELS_PATH = (
    r"C:\Users\Rion\AppData\Local"
    r"\Comfy-Desktop\ComfyUI-Installs"
    r"\ComfyUI\ComfyUI\models"
)


def _read_config(config_path=None):
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / ".config"
    else:
        config_path = Path(config_path)

    config = configparser.ConfigParser(interpolation=None)
    if config_path.is_file():
        config.read(config_path, encoding="utf-8")
    return config


def configured_models_path():
    return os.environ.get(
        "COMFYUI_MODELS_PATH",
        DEFAULT_MODELS_PATH
    )


def load_panel_paths(config_path=None):
    config = _read_config(config_path)
    fallback_path = configured_models_path()

    def configured_path(option):
        path = config.get(
            "folders",
            option,
            fallback=""
        ).strip()
        if not path:
            path = fallback_path
        path = os.path.expandvars(
            os.path.expanduser(path)
        )
        return os.path.abspath(path)

    return configured_path("left"), configured_path("right")


def load_panel_filter(config_path=None):
    config = _read_config(config_path)
    filter_value = config.get(
        "filter",
        "filter",
        fallback=repr(sorted(DEFAULT_FILTER_EXTENSIONS))
    )

    try:
        extensions = ast.literal_eval(filter_value)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(
            "The [filter] filter setting must be a list of extensions."
        ) from exc

    if not isinstance(extensions, list) or not all(
        isinstance(extension, str) and extension.strip()
        for extension in extensions
    ):
        raise ValueError(
            "The [filter] filter setting must be a list of non-empty strings."
        )

    normalized_extensions = set()
    for extension in extensions:
        extension = extension.strip().lower()
        if not extension.startswith("."):
            extension = f".{extension}"
        normalized_extensions.add(extension)

    only_show = config.getboolean(
        "filter",
        "only_show",
        fallback=True
    )
    return frozenset(normalized_extensions), only_show


def format_size(size):
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)

    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0


def folder_size(folder_path):
    total = 0

    try:
        for directory, _, filenames in os.walk(folder_path):
            for filename in filenames:
                file_path = os.path.join(directory, filename)
                try:
                    total += os.path.getsize(file_path)
                except OSError:
                    continue
    except OSError:
        pass

    return total


def read_safetensors_details(file_path):
    max_header_size = 16 * 1024 * 1024

    try:
        with open(file_path, "rb") as model_file:
            header_length_bytes = model_file.read(8)
            if len(header_length_bytes) != 8:
                return ["", "Safetensors header is incomplete."]

            header_length = int.from_bytes(
                header_length_bytes,
                byteorder="little"
            )
            if header_length > max_header_size:
                return [
                    "",
                    "Safetensors header is too large to inspect safely."
                ]

            header_bytes = model_file.read(header_length)
            if len(header_bytes) != header_length:
                return ["", "Safetensors header is incomplete."]

        header = json.loads(header_bytes)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return ["", f"Safetensors metadata could not be read: {exc}"]

    if not isinstance(header, dict):
        return ["", "Safetensors header has an invalid structure."]

    details = ["", "Safetensors Details"]
    metadata = header.get("__metadata__", {})
    if isinstance(metadata, dict) and metadata:
        details.append("Metadata:")
        details.extend(
            f"  {key}: {value}"
            for key, value in metadata.items()
        )
    else:
        details.append("Metadata: none")

    tensors = [
        (name, tensor)
        for name, tensor in header.items()
        if name != "__metadata__" and isinstance(tensor, dict)
    ]
    details.append(f"Tensor count: {len(tensors):,}")
    if tensors:
        details.append("Tensors:")
        details.extend(
            f"  {name}: {tensor.get('dtype', 'unknown')}, "
            f"shape={tensor.get('shape', 'unknown')}"
            for name, tensor in tensors
        )

    return details
