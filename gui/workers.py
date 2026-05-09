from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from core.models import ProcessingOptions, ProcessingResult
from core.pixelizer import process_image


class ImageProcessWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, image_path: str, options: ProcessingOptions) -> None:
        super().__init__()
        self.image_path = image_path
        self.options = options

    @Slot()
    def run(self) -> None:
        try:
            result: ProcessingResult = process_image(self.image_path, self.options)
        except Exception as exc:  # pragma: no cover - GUI signal path
            self.failed.emit(str(exc))
            return

        self.finished.emit(result)
