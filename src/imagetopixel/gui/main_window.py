from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from imagetopixel.config.settings import APP_NAME, ORG_NAME
from imagetopixel.core.exporter import save_outputs
from imagetopixel.core.image_loader import SUPPORTED_IMAGE_FILTER
from imagetopixel.core.models import ProcessingOptions, ProcessingResult
from imagetopixel.core.preprocess import list_presets
from imagetopixel.gui.preview_panel import PreviewPanel
from imagetopixel.gui.workers import ImageProcessWorker


PADDING_LABELS = {
    "edge": "边缘延展",
    "mirror": "镜像补边",
    "solid": "纯色补边",
}

PRESET_LABELS = {
    "standard": "标准",
    "sharper": "更锐利",
    "smoother": "更平滑",
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1380, 860)
        self.setAcceptDrops(True)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_image_path: Path | None = None
        self.current_result: ProcessingResult | None = None
        self.current_thread: QThread | None = None
        self.current_worker: ImageProcessWorker | None = None
        self.pending_reprocess = False

        self.import_button = QPushButton("导入图片")
        self.import_button.clicked.connect(self.open_image)

        self.process_button = QPushButton("重新生成")
        self.process_button.clicked.connect(self.start_processing)
        self.process_button.setEnabled(False)

        self.save_button = QPushButton("保存全部")
        self.save_button.clicked.connect(self.save_all)
        self.save_button.setEnabled(False)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("未选择输出目录")

        self.output_button = QPushButton("选择输出目录")
        self.output_button.clicked.connect(self.pick_output_dir)

        self.padding_combo = QComboBox()
        for value, label in PADDING_LABELS.items():
            self.padding_combo.addItem(label, value)
        self.padding_combo.currentIndexChanged.connect(self.on_settings_changed)

        self.preset_combo = QComboBox()
        for value in list_presets():
            self.preset_combo.addItem(PRESET_LABELS[value], value)
        self.preset_combo.currentIndexChanged.connect(self.on_settings_changed)

        self.preview_checkbox = QCheckBox("同时保存放大预览图")

        self.hint_label = QLabel(
            "拖拽图片到窗口任意位置，或点击“导入图片”开始。默认一次生成 16 / 32 / 64 三种真像素图。"
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("hintLabel")

        self.original_panel = PreviewPanel("原图", "等待载入图片")
        self.square_panel = PreviewPanel("补成正方形", "导入图片后自动显示")
        self.output_16_panel = PreviewPanel("16 x 16", "生成后显示")
        self.output_32_panel = PreviewPanel("32 x 32", "生成后显示")
        self.output_64_panel = PreviewPanel("64 x 64", "生成后显示")

        controls_layout = QGridLayout()
        controls_layout.addWidget(self.import_button, 0, 0)
        controls_layout.addWidget(self.process_button, 0, 1)
        controls_layout.addWidget(self.save_button, 0, 2)
        controls_layout.addWidget(QLabel("输出目录"), 1, 0)
        controls_layout.addWidget(self.output_dir_edit, 1, 1, 1, 2)
        controls_layout.addWidget(self.output_button, 1, 3)
        controls_layout.addWidget(QLabel("补边模式"), 2, 0)
        controls_layout.addWidget(self.padding_combo, 2, 1)
        controls_layout.addWidget(QLabel("处理预设"), 2, 2)
        controls_layout.addWidget(self.preset_combo, 2, 3)
        controls_layout.addWidget(self.preview_checkbox, 3, 0, 1, 2)

        left_column = QVBoxLayout()
        left_column.addWidget(self.original_panel, stretch=1)
        left_column.addWidget(self.square_panel, stretch=1)

        right_grid = QGridLayout()
        right_grid.addWidget(self.output_16_panel, 0, 0)
        right_grid.addWidget(self.output_32_panel, 0, 1)
        right_grid.addWidget(self.output_64_panel, 1, 0, 1, 2)

        preview_layout = QHBoxLayout()
        preview_layout.addLayout(left_column, stretch=4)
        preview_layout.addLayout(right_grid, stretch=5)

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self.hint_label)
        root_layout.addLayout(preview_layout, stretch=1)
        self.setCentralWidget(central)

        status_bar = QStatusBar()
        status_bar.showMessage("准备就绪")
        self.setStatusBar(status_bar)

        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4efe7;
            }
            QLabel#hintLabel {
                color: #5b5248;
                font-size: 13px;
                padding: 4px 0 10px 0;
            }
            QFrame#previewPanel {
                border: 1px solid #d9cfc2;
                border-radius: 12px;
                background: #fffaf2;
            }
            QLabel#previewTitle {
                font-size: 16px;
                font-weight: 700;
                color: #322b23;
            }
            QLabel#previewInfo {
                color: #8a7e72;
                min-height: 20px;
            }
            QLabel#previewImage {
                border: 1px dashed #d9cfc2;
                border-radius: 10px;
                background: #fcf8f0;
                color: #8a7e72;
                padding: 18px;
            }
            QPushButton {
                background: #2f6f66;
                color: white;
                border: none;
                border-radius: 8px;
                min-height: 36px;
                padding: 0 14px;
            }
            QPushButton:disabled {
                background: #8cb5af;
                color: #e7f1ef;
            }
            QLineEdit, QComboBox {
                min-height: 34px;
                border: 1px solid #d9cfc2;
                border-radius: 8px;
                background: white;
                padding: 0 10px;
            }
            """
        )

        self.restore_preferences()

    def restore_preferences(self) -> None:
        output_dir = self.settings.value("output_dir", "", str)
        if output_dir:
            self.output_dir_edit.setText(output_dir)

        padding_mode = self.settings.value("padding_mode", "edge", str)
        preset = self.settings.value("preset", "standard", str)
        save_preview = self.settings.value("save_previews", False, bool)

        self.set_combo_by_value(self.padding_combo, padding_mode)
        self.set_combo_by_value(self.preset_combo, preset)
        self.preview_checkbox.setChecked(bool(save_preview))

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        self.settings.setValue("output_dir", self.output_dir_edit.text())
        self.settings.setValue("padding_mode", self.padding_combo.currentData())
        self.settings.setValue("preset", self.preset_combo.currentData())
        self.settings.setValue("save_previews", self.preview_checkbox.isChecked())
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def set_combo_by_value(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return

        path = Path(urls[0].toLocalFile())
        if path.is_file():
            self.load_image(path)
            event.acceptProposedAction()

    @Slot()
    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", SUPPORTED_IMAGE_FILTER)
        if path:
            self.load_image(Path(path))

    def load_image(self, path: Path) -> None:
        self.current_image_path = path
        if not self.output_dir_edit.text():
            self.output_dir_edit.setText(str(path.parent / "output"))

        self.process_button.setEnabled(True)
        self.hint_label.setText(
            f"已载入：{path.name}。你可以调整补边模式和处理预设，结果会自动刷新。"
        )
        self.start_processing()

    @Slot()
    def pick_output_dir(self) -> None:
        current = self.output_dir_edit.text() or str(Path.cwd())
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", current)
        if directory:
            self.output_dir_edit.setText(directory)
            self.statusBar().showMessage(f"输出目录已更新：{directory}", 3000)

    def current_options(self) -> ProcessingOptions:
        return ProcessingOptions(
            padding_mode=self.padding_combo.currentData(),
            preset=self.preset_combo.currentData(),
        )

    @Slot()
    def on_settings_changed(self) -> None:
        if self.current_image_path is not None:
            self.start_processing()

    @Slot()
    def start_processing(self) -> None:
        if self.current_image_path is None:
            return

        if self.current_thread is not None:
            self.pending_reprocess = True
            return

        self.process_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.statusBar().showMessage("处理中，请稍候...")

        worker = ImageProcessWorker(str(self.current_image_path), self.current_options())
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_processing_finished)
        worker.failed.connect(self.on_processing_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_thread_finished)

        self.current_worker = worker
        self.current_thread = thread
        thread.start()

    @Slot(object)
    def on_processing_finished(self, result: ProcessingResult) -> None:
        self.current_result = result
        self.original_panel.set_image(result.original)
        self.square_panel.set_image(result.squared)
        self.output_16_panel.set_image(result.outputs[16], pixelated=True)
        self.output_32_panel.set_image(result.outputs[32], pixelated=True)
        self.output_64_panel.set_image(result.outputs[64], pixelated=True)
        self.save_button.setEnabled(True)

        left, top, right, bottom = result.padding
        if any(result.padding):
            self.statusBar().showMessage(
                f"生成完成。补边：左 {left}px / 上 {top}px / 右 {right}px / 下 {bottom}px",
                6000,
            )
        else:
            self.statusBar().showMessage("生成完成。原图已是 1:1。", 6000)

    @Slot(str)
    def on_processing_failed(self, message: str) -> None:
        self.statusBar().showMessage("处理失败", 4000)
        QMessageBox.critical(self, "处理失败", f"图片处理失败：\n{message}")

    @Slot()
    def on_thread_finished(self) -> None:
        self.current_worker = None
        self.current_thread = None
        self.process_button.setEnabled(self.current_image_path is not None)

        if self.pending_reprocess:
            self.pending_reprocess = False
            self.start_processing()

    @Slot()
    def save_all(self) -> None:
        if self.current_result is None:
            return

        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.information(self, "缺少输出目录", "请先选择输出目录。")
            return

        try:
            saved = save_outputs(
                self.current_result,
                output_dir=output_dir,
                options=self.current_options(),
                save_previews=self.preview_checkbox.isChecked(),
            )
        except Exception as exc:  # pragma: no cover - GUI path
            QMessageBox.critical(self, "保存失败", f"文件保存失败：\n{exc}")
            return

        self.statusBar().showMessage(f"已保存 {len(saved)} 个文件到 {output_dir}", 6000)
        QMessageBox.information(self, "保存成功", f"已导出到：\n{output_dir}")


def run() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    window = MainWindow()
    window.show()
    app.exec()
