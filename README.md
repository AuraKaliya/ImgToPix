# ImageToPixel

将高分辨率“伪像素”图片压缩为真正的像素图，并固定输出 `16x16`、`32x32`、`64x64` 三种规格。

## 当前能力

- GUI 导入、拖拽、预览、导出
- 自动把非 `1:1` 图片补成正方形
- 支持边缘延展、镜像补边、纯色补边
- 支持 `standard`、`sharper`、`smoother` 三种预设
- CLI 单图转换、批量转换、环境自检、文档入口
- 启动时自动创建 `.venv` 并安装依赖
- 预留独立 skill 骨架，便于后续迁移

## 推荐启动方式

GUI：

```bash
start.bat
```

CLI：

```bash
python bootstrap.py doctor
python bootstrap.py convert input.png --output output
```

## 开发安装

```bash
pip install -r requirements.txt
```

或：

```bash
pip install -e .[dev,build]
```

## 直接运行

```bash
python app.py
python -m imagetopixel gui
python -m imagetopixel doctor
```

## 测试

```bash
pytest
```

## 文档

- [docs/usage.md](docs/usage.md)
- [docs/gui.md](docs/gui.md)
- [docs/cli.md](docs/cli.md)
