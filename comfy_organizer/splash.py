"""Startup splash screen for the desktop application."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen

from . import __author__, __version__
from .icons import app_icon


class OrganizerSplashScreen(QSplashScreen):

    def __init__(self):
        pixmap = QPixmap(540, 270)
        pixmap.fill(QColor("#141a24"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1c2635"))
        painter.drawRoundedRect(1, 1, 538, 268, 18, 18)
        app_icon().paint(
            painter,
            QRect(34, 48, 88, 88)
        )

        painter.setPen(QColor("#f8fafc"))
        title_font = QFont("Segoe UI", 21)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            QRect(146, 54, 350, 42),
            Qt.AlignLeft | Qt.AlignVCenter,
            "ComfyUI Model Organizer"
        )

        painter.setPen(QColor("#aab8ca"))
        subtitle_font = QFont("Segoe UI", 10)
        painter.setFont(subtitle_font)
        painter.drawText(
            QRect(148, 97, 340, 28),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Version {__version__}  |  Created by {__author__}"
        )
        painter.end()

        super().__init__(pixmap)
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.status_label = QLabel("Starting...", self)
        self.status_label.setGeometry(34, 180, 472, 24)
        self.status_label.setStyleSheet(
            "color: #cbd5e1; background: transparent; font-size: 9pt;"
        )

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(34, 216, 472, 12)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #111720;
                border: 1px solid #344256;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #4f9cf9;
                border-radius: 5px;
            }
            """
        )

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        QApplication.processEvents()
