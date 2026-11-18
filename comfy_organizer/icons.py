"""Application and file-type icon helpers."""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap, QColor


FILE_ICON_STYLES = {
    ".bat": ("#dc2626", "BAT"),
    ".bin": ("#64748b", "BIN"),
    ".ckpt": ("#f97316", "CKPT"),
    ".cfg": ("#0f766e", "CFG"),
    ".conf": ("#14b8a6", "CONF"),
    ".csv": ("#10b981", "CSV"),
    ".env": ("#d97706", "ENV"),
    ".gguf": ("#a855f7", "GGUF"),
    ".ini": ("#475569", "INI"),
    ".json": ("#f59e0b", "JSON"),
    ".md": ("#0ea5e9", "MD"),
    ".model": ("#06b6d4", "MOD"),
    ".onnx": ("#22c55e", "ONNX"),
    ".properties": ("#a16207", "PROP"),
    ".ps1": ("#2563eb", "PS1"),
    ".py": ("#3776ab", "PY"),
    ".pt": ("#ef4444", "PT"),
    ".pth": ("#eab308", "PTH"),
    ".safetensors": ("#3b82f6", "SAFE"),
    ".sh": ("#16a34a", "SH"),
    ".tflite": ("#ec4899", "TFL"),
    ".toml": ("#7c3aed", "TOML"),
    ".txt": ("#6b7280", "TXT"),
    ".xml": ("#fb923c", "XML"),
    ".yaml": ("#cb171e", "YAML"),
    ".yml": ("#be123c", "YML"),
}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def app_icon_path():
    return Path(__file__).parent / "assets" / "comfy-organizer.svg"


def app_icon():
    return QIcon(str(app_icon_path()))


class FileIconProvider:

    def __init__(self):
        self._preview_icon_cache = {}
        self._file_icon_cache = {}

    def clear_preview_cache(self):
        self._preview_icon_cache.clear()

    def icon_for_file(self, file_path):
        icon = self._preview_icon(file_path)
        if icon is not None:
            return icon
        return self._file_type_icon(file_path)

    def _preview_icon(self, file_path):
        if file_path in self._preview_icon_cache:
            return self._preview_icon_cache[file_path]

        base_path, extension = os.path.splitext(file_path)
        if extension.lower() != ".safetensors":
            return None

        candidates = [
            file_path + image_extension
            for image_extension in IMAGE_EXTENSIONS
        ]
        candidates.extend(
            base_path + image_extension
            for image_extension in IMAGE_EXTENSIONS
        )

        for image_path in candidates:
            if not os.path.isfile(image_path):
                continue

            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                continue

            icon = QIcon(
                pixmap.scaled(
                    128,
                    128,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
            self._preview_icon_cache[file_path] = icon
            return icon

        self._preview_icon_cache[file_path] = None
        return None

    def _file_type_icon(self, file_path):
        filename = os.path.basename(file_path).lower()
        extension = os.path.splitext(filename)[1]
        if not extension and filename in FILE_ICON_STYLES:
            extension = filename

        style = FILE_ICON_STYLES.get(extension)
        if style is None:
            return None

        if extension not in self._file_icon_cache:
            color, label = style
            pixmap = QPixmap(128, 128)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(8, 8, 112, 112, 22, 22)
            painter.setBrush(QColor("#f5f7fa"))
            painter.drawRoundedRect(29, 20, 70, 88, 8, 8)

            font = QFont()
            font.setBold(True)
            font.setPixelSize(18)
            painter.setFont(font)
            painter.setPen(QColor("#17191d"))
            painter.drawText(
                29,
                20,
                70,
                88,
                Qt.AlignCenter,
                label
            )
            painter.end()

            self._file_icon_cache[extension] = QIcon(pixmap)

        return self._file_icon_cache[extension]
