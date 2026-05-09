from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from imagetopixel.config.settings import APP_NAME, ORG_NAME
from imagetopixel.core.exporter import save_outputs
from imagetopixel.core.image_loader import SUPPORTED_IMAGE_FILTER
from imagetopixel.core.models import PaletteEntry, ProcessingOptions, ProcessingResult, VariantResult
from imagetopixel.core.pixelizer import rerender_variant_palette
from imagetopixel.core.preprocess import (
    algorithm_label,
    contour_label,
    list_algorithms,
    list_contours,
)
from imagetopixel.gui.preview_panel import PreviewPanel
from imagetopixel.gui.workers import ImageProcessWorker


PADDING_LABELS = {
    "edge": "边缘延展",
    "mirror": "镜像补边",
    "solid": "纯色补边",
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1480, 940)
        self.setAcceptDrops(True)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_image_path: Path | None = None
        self.current_result: ProcessingResult | None = None
        self.current_thread: QThread | None = None
        self.current_worker: ImageProcessWorker | None = None
        self.pending_reprocess = False
        self._palette_updating = False
        self._palette_checkboxes: dict[int, QCheckBox] = {}

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

        self.contour_combo = QComboBox()
        for value in list_contours():
            self.contour_combo.addItem(contour_label(value), value)
        self.contour_combo.currentIndexChanged.connect(self.on_variant_selection_changed)

        self.algorithm_combo = QComboBox()
        for value in list_algorithms():
            self.algorithm_combo.addItem(algorithm_label(value), value)
        self.algorithm_combo.currentIndexChanged.connect(self.on_variant_selection_changed)

        self.output_size_combo = QComboBox()
        for size in (16, 32, 64):
            self.output_size_combo.addItem(f"{size} x {size}", size)
        self.output_size_combo.currentIndexChanged.connect(self.on_variant_selection_changed)

        self.mask_tolerance_spin = QSpinBox()
        self.mask_tolerance_spin.setRange(1, 80)
        self.mask_tolerance_spin.setValue(18)
        self.mask_tolerance_spin.valueChanged.connect(self.on_settings_changed)

        self.strict_coverage_spin = self._build_threshold_spin(0.50)
        self.strict_coverage_spin.valueChanged.connect(self.on_settings_changed)

        self.loose_coverage_spin = self._build_threshold_spin(0.35)
        self.loose_coverage_spin.valueChanged.connect(self.on_settings_changed)

        self.hybrid_threshold_spin = self._build_threshold_spin(0.30)
        self.hybrid_threshold_spin.valueChanged.connect(self.on_settings_changed)

        self.preserve_outline_checkbox = QCheckBox("保留边框")
        self.preserve_outline_checkbox.setChecked(True)
        self.preserve_outline_checkbox.stateChanged.connect(self.on_settings_changed)

        self.outline_strength_spin = self._build_threshold_spin(0.75)
        self.outline_strength_spin.valueChanged.connect(self.on_settings_changed)

        self.palette_size_spin = QSpinBox()
        self.palette_size_spin.setRange(10, 20)
        self.palette_size_spin.setValue(16)
        self.palette_size_spin.valueChanged.connect(self.on_settings_changed)

        self.preview_checkbox = QCheckBox("同时保存放大预览图")

        self.hint_label = QLabel(
            "系统会先自动把颜色归并到 10 到 20 个色块，再允许你手动启用或停用单个色块。参数变化后会自动重渲染。"
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("hintLabel")

        self.original_panel = PreviewPanel("原图", "等待载入图片", image_min_size=120)
        self.mask_panel = PreviewPanel("Mask", "导入图片后自动显示", image_min_size=120)
        self.square_panel = PreviewPanel("工作图", "导入图片后自动显示", image_min_size=120)

        self.source_tabs = QTabWidget()
        self.source_tabs.addTab(self.original_panel, "原图")
        self.source_tabs.addTab(self.mask_panel, "Mask")
        self.source_tabs.addTab(self.square_panel, "工作图")

        self.palette_scroll = QScrollArea()
        self.palette_scroll.setWidgetResizable(True)
        self.palette_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.palette_container = QWidget()
        self.palette_layout = QVBoxLayout(self.palette_container)
        self.palette_layout.setContentsMargins(8, 8, 8, 8)
        self.palette_layout.setSpacing(6)
        self.palette_layout.addStretch(1)
        self.palette_scroll.setWidget(self.palette_container)

        self.contour_panels: dict[str, PreviewPanel] = {}
        for value in list_contours():
            self.contour_panels[value] = PreviewPanel(
                f"16 x 16 · {contour_label(value)}",
                "生成后显示",
                image_min_size=90,
            )

        self.output_panel = PreviewPanel("当前输出", "生成后显示", image_min_size=160)

        controls_layout = QGridLayout()
        controls_layout.addWidget(self.import_button, 0, 0)
        controls_layout.addWidget(self.process_button, 0, 1)
        controls_layout.addWidget(self.save_button, 0, 2)
        controls_layout.addWidget(QLabel("输出目录"), 1, 0)
        controls_layout.addWidget(self.output_dir_edit, 1, 1, 1, 2)
        controls_layout.addWidget(self.output_button, 1, 3)
        controls_layout.addWidget(QLabel("补边模式"), 2, 0)
        controls_layout.addWidget(self.padding_combo, 2, 1)
        controls_layout.addWidget(QLabel("轮廓方案"), 2, 2)
        controls_layout.addWidget(self.contour_combo, 2, 3)
        controls_layout.addWidget(QLabel("颜色算法"), 3, 0)
        controls_layout.addWidget(self.algorithm_combo, 3, 1)
        controls_layout.addWidget(QLabel("调色板大小"), 3, 2)
        controls_layout.addWidget(self.palette_size_spin, 3, 3)
        controls_layout.addWidget(self.preview_checkbox, 4, 0, 1, 2)

        params_layout = QGridLayout()
        params_layout.addWidget(QLabel("背景容差"), 0, 0)
        params_layout.addWidget(self.mask_tolerance_spin, 0, 1)
        params_layout.addWidget(QLabel("Coverage 50%"), 0, 2)
        params_layout.addWidget(self.strict_coverage_spin, 0, 3)
        params_layout.addWidget(QLabel("Coverage 35%"), 1, 0)
        params_layout.addWidget(self.loose_coverage_spin, 1, 1)
        params_layout.addWidget(QLabel("Hybrid 阈值"), 1, 2)
        params_layout.addWidget(self.hybrid_threshold_spin, 1, 3)
        params_layout.addWidget(self.preserve_outline_checkbox, 2, 0, 1, 2)
        params_layout.addWidget(QLabel("边框强度"), 2, 2)
        params_layout.addWidget(self.outline_strength_spin, 2, 3)

        left_top = QWidget()
        left_top_layout = QVBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.addWidget(self.source_tabs)

        palette_group = QWidget()
        palette_group_layout = QVBoxLayout(palette_group)
        palette_group_layout.setContentsMargins(0, 0, 0, 0)
        palette_title = QLabel("调色板色块")
        palette_title.setObjectName("previewTitle")
        palette_group_layout.addWidget(palette_title)
        palette_group_layout.addWidget(self.palette_scroll)

        left_splitter = QSplitter()
        left_splitter.setOrientation(Qt.Orientation.Vertical)
        left_splitter.addWidget(left_top)
        left_splitter.addWidget(palette_group)
        left_splitter.setStretchFactor(0, 5)
        left_splitter.setStretchFactor(1, 3)

        contour_container = QWidget()
        contour_layout = QVBoxLayout(contour_container)
        contour_layout.setContentsMargins(0, 0, 0, 0)
        contour_title = QLabel("16x16 轮廓候选")
        contour_title.setObjectName("previewTitle")
        contour_layout.addWidget(contour_title)
        contour_grid = QGridLayout()
        for index, value in enumerate(list_contours()):
            contour_grid.addWidget(self.contour_panels[value], index // 2, index % 2)
        contour_layout.addLayout(contour_grid)

        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_header = QHBoxLayout()
        output_header.addWidget(QLabel("主预览"))
        output_header.addStretch(1)
        output_header.addWidget(QLabel("尺寸"))
        output_header.addWidget(self.output_size_combo)
        output_layout.addLayout(output_header)
        output_layout.addWidget(self.output_panel)

        right_splitter = QSplitter()
        right_splitter.setOrientation(Qt.Orientation.Vertical)
        right_splitter.addWidget(contour_container)
        right_splitter.addWidget(output_container)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 4)

        main_splitter = QSplitter()
        main_splitter.setOrientation(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 7)

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.addLayout(controls_layout)
        root_layout.addLayout(params_layout)
        root_layout.addWidget(self.hint_label)
        root_layout.addWidget(main_splitter, stretch=1)
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
                padding: 12px;
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
            QLineEdit, QComboBox, QTabWidget::pane, QSpinBox, QDoubleSpinBox, QScrollArea {
                border: 1px solid #d9cfc2;
                border-radius: 8px;
                background: white;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 34px;
                padding: 0 10px;
            }
            QTabBar::tab {
                padding: 8px 12px;
                margin-right: 4px;
                background: #efe6d8;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #fffaf2;
            }
            QSplitter::handle {
                background: #e3d8c7;
            }
            """
        )

        self.restore_preferences()

    def _build_threshold_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def restore_preferences(self) -> None:
        output_dir = self.settings.value("output_dir", "", str)
        if output_dir:
            self.output_dir_edit.setText(output_dir)

        padding_mode = self.settings.value("padding_mode", "edge", str)
        contour = self.settings.value("contour", "hybrid", str)
        algorithm = self.settings.value("algorithm", "", str) or self.settings.value("preset", "majority", str)
        output_size = self.settings.value("output_size", 64, int)
        save_preview = self.settings.value("save_previews", False, bool)

        self.set_combo_by_value(self.padding_combo, padding_mode)
        self.set_combo_by_value(self.contour_combo, contour)
        self.set_combo_by_value(self.algorithm_combo, algorithm)
        self.set_combo_by_value(self.output_size_combo, output_size)
        self.preview_checkbox.setChecked(bool(save_preview))

        self.mask_tolerance_spin.setValue(self.settings.value("mask_tolerance", 18, int))
        self.strict_coverage_spin.setValue(self.settings.value("coverage_strict", 0.50, float))
        self.loose_coverage_spin.setValue(self.settings.value("coverage_loose", 0.35, float))
        self.hybrid_threshold_spin.setValue(self.settings.value("hybrid_threshold", 0.30, float))
        self.preserve_outline_checkbox.setChecked(self.settings.value("preserve_outline", True, bool))
        self.outline_strength_spin.setValue(self.settings.value("outline_strength", 0.75, float))
        self.palette_size_spin.setValue(self.settings.value("palette_size", 16, int))

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        self.settings.setValue("output_dir", self.output_dir_edit.text())
        self.settings.setValue("padding_mode", self.padding_combo.currentData())
        self.settings.setValue("contour", self.contour_combo.currentData())
        self.settings.setValue("algorithm", self.algorithm_combo.currentData())
        self.settings.setValue("output_size", self.output_size_combo.currentData())
        self.settings.setValue("save_previews", self.preview_checkbox.isChecked())
        self.settings.setValue("mask_tolerance", self.mask_tolerance_spin.value())
        self.settings.setValue("coverage_strict", self.strict_coverage_spin.value())
        self.settings.setValue("coverage_loose", self.loose_coverage_spin.value())
        self.settings.setValue("hybrid_threshold", self.hybrid_threshold_spin.value())
        self.settings.setValue("preserve_outline", self.preserve_outline_checkbox.isChecked())
        self.settings.setValue("outline_strength", self.outline_strength_spin.value())
        self.settings.setValue("palette_size", self.palette_size_spin.value())
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def set_combo_by_value(self, combo: QComboBox, value: str | int) -> None:
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
            f"已载入：{path.name}。你现在可以调参数、查看自动归并后的调色板，并手动停用或启用色块。"
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
            contour=self.contour_combo.currentData(),
            algorithm=self.algorithm_combo.currentData(),
            mask_tolerance=self.mask_tolerance_spin.value(),
            coverage_strict=self.strict_coverage_spin.value(),
            coverage_loose=self.loose_coverage_spin.value(),
            hybrid_threshold=self.hybrid_threshold_spin.value(),
            preserve_outline=self.preserve_outline_checkbox.isChecked(),
            outline_strength=self.outline_strength_spin.value(),
            palette_size=self.palette_size_spin.value(),
        )

    def selected_variant(self) -> VariantResult | None:
        if self.current_result is None:
            return None

        contour = self.contour_combo.currentData() or self.current_result.selected_contour
        algorithm = self.algorithm_combo.currentData() or self.current_result.selected_algorithm
        contour_result = self.current_result.contours.get(contour)
        if contour_result is None:
            return None
        return contour_result.variants.get(algorithm)

    def rebuild_palette_controls(self, variant: VariantResult) -> None:
        self._palette_updating = True
        self._palette_checkboxes.clear()

        while self.palette_layout.count():
            item = self.palette_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for entry in variant.palette_entries:
            self.palette_layout.addWidget(self.build_palette_row(entry))

        self.palette_layout.addStretch(1)
        self._palette_updating = False

    def build_palette_row(self, entry: PaletteEntry) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        swatch = QFrame()
        swatch.setFixedSize(18, 18)
        swatch.setStyleSheet(
            "background: rgba({r}, {g}, {b}, {a}); border: 1px solid #b5a998; border-radius: 4px;".format(
                r=entry.rgba[0],
                g=entry.rgba[1],
                b=entry.rgba[2],
                a=entry.rgba[3],
            )
        )

        checkbox = QCheckBox(f"#{entry.rgba[0]:02X}{entry.rgba[1]:02X}{entry.rgba[2]:02X} · {entry.pixel_count}px")
        checkbox.setChecked(entry.enabled)
        checkbox.stateChanged.connect(lambda _, palette_index=entry.index: self.on_palette_toggle(palette_index))
        self._palette_checkboxes[entry.index] = checkbox

        layout.addWidget(swatch)
        layout.addWidget(checkbox, stretch=1)
        return row

    @Slot()
    def on_settings_changed(self) -> None:
        if self.current_image_path is not None:
            self.start_processing()

    @Slot()
    def on_variant_selection_changed(self) -> None:
        if self.current_result is not None and self.current_result.contours:
            self.apply_selected_variant(refresh_palette=True)

    def on_palette_toggle(self, palette_index: int) -> None:
        if self._palette_updating:
            return

        variant = self.selected_variant()
        if variant is None:
            return

        checkbox = self._palette_checkboxes.get(palette_index)
        if checkbox is None:
            return

        for entry in variant.palette_entries:
            if entry.index == palette_index:
                entry.enabled = checkbox.isChecked()
                break

        rerender_variant_palette(variant, tuple(sorted(variant.outputs)))
        self.apply_selected_variant(refresh_palette=False)

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

        worker = ImageProcessWorker(
            str(self.current_image_path),
            self.current_options(),
            include_all_algorithms=True,
        )
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
        self.mask_panel.set_image(result.foreground_mask)
        self.square_panel.set_image(result.focused_square)

        for contour, panel in self.contour_panels.items():
            contour_result = result.contours.get(contour)
            if contour_result is None:
                panel.clear("当前批次未生成")
                continue
            panel.set_image(contour_result.mask, pixelated=True)

        self.apply_selected_variant(refresh_palette=True)
        self.save_button.setEnabled(True)

        left, top, right, bottom = result.padding
        padding_text = (
            f"补边：左 {left}px / 上 {top}px / 右 {right}px / 下 {bottom}px"
            if any(result.padding)
            else "原图已是 1:1"
        )
        self.statusBar().showMessage(
            f"生成完成。前景识别模式：{result.background_mode}；{padding_text}",
            6000,
        )

    def apply_selected_variant(self, refresh_palette: bool) -> None:
        if self.current_result is None:
            return

        contour = self.contour_combo.currentData() or self.current_result.selected_contour
        algorithm = self.algorithm_combo.currentData() or self.current_result.selected_algorithm
        preview_size = self.output_size_combo.currentData() or 64
        contour_result = self.current_result.contours.get(contour)
        if contour_result is None:
            return

        variant = contour_result.variants.get(algorithm)
        if variant is None:
            return

        self.current_result.selected_contour = contour
        self.current_result.selected_algorithm = algorithm
        self.current_result.variants = dict(contour_result.variants)
        self.current_result.outputs = dict(variant.outputs)

        if refresh_palette:
            self.rebuild_palette_controls(variant)

        image = variant.outputs.get(preview_size)
        if image is None:
            preview_size = sorted(variant.outputs)[0]
            image = variant.outputs[preview_size]

        self.output_panel.title_label.setText(
            f"{preview_size} x {preview_size} · {contour_label(contour)} · {algorithm_label(algorithm)}"
        )
        self.output_panel.set_image(image, pixelated=True)

        for key, panel in self.contour_panels.items():
            title = f"16 x 16 · {contour_label(key)}"
            if key == contour:
                title = f"{title} · 当前"
            panel.title_label.setText(title)

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
