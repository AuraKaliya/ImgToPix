# ImageToPixel

将高分辨率的“伪像素图”压缩为真正可用的小尺寸像素图，并默认导出 `16x16`、`32x32`、`64x64` 三种规格。

当前版本采用“`16x16` 母版优先”流程：

- 核心算法只为 `16x16` 服务
- `32x32` 与 `64x64` 由 `16x16` 使用最近邻等比放大生成
- GUI 会同时预览多种 `16x16` 候选算法，便于对比选择

## 当前能力

- GUI 导入、拖拽、预览、导出
- 自动补成正方形，并聚焦有效主体区域
- 支持 `edge`、`mirror`、`solid` 三种补边方式
- 支持 `majority`、`median`、`center` 三种 `16x16` 母版算法
- CLI 单图转换、批量转换、环境自检、文档入口
- CLI 支持结构化 JSON 报告、CSV/Markdown 摘要
- 启动时可自动准备 `.venv` 环境

## 推荐启动

GUI:

```bash
start.bat
```

CLI:

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
