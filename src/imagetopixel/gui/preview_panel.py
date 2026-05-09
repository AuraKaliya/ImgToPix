from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from imagetopixel.core.pixelizer import build_preview


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


class PreviewPanel(QFrame):
    def __init__(self, title: str, placeholder: str, parent=None, image_min_size: int = 220) -> None:
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._base_pixmap = QPixmap()
        self._transformation_mode = Qt.TransformationMode.SmoothTransformation

        self.title_label = QLabel(title)
        self.title_label.setObjectName("previewTitle")
        self.info_label = QLabel("")
        self.info_label.setObjectName("previewInfo")

        self.image_label = QLabel(placeholder)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(image_min_size, image_min_size)
        self.image_label.setWordWrap(True)
        self.image_label.setObjectName("previewImage")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.image_label, stretch=1)

    def clear(self, placeholder: str) -> None:
        self.info_label.clear()
        self._base_pixmap = QPixmap()
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(placeholder)

    def set_image(self, image: Image.Image, pixelated: bool = False) -> None:
        display_image = build_preview(image, scale=10) if pixelated else image
        self._base_pixmap = pil_to_qpixmap(display_image)
        self._transformation_mode = (
            Qt.TransformationMode.FastTransformation
            if pixelated
            else Qt.TransformationMode.SmoothTransformation
        )
        scaled = self._base_pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            self._transformation_mode,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")
        self.info_label.setText(f"{image.width} x {image.height}")

    def resizeEvent(self, event) -> None:
        if not self._base_pixmap.isNull():
            scaled = self._base_pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                self._transformation_mode,
            )
            self.image_label.setPixmap(scaled)
        super().resizeEvent(event)
