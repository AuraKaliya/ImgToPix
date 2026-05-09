# CLI 说明

## 入口

推荐通过自举入口调用：

```bash
python bootstrap.py <command>
```

也可以在依赖安装后直接调用：

```bash
python -m imagetopixel <command>
imagetopixel <command>
```

## 命令

### 启动 GUI

```bash
python bootstrap.py gui
```

### 单图转换

```bash
python bootstrap.py convert input.png --output output
```

带参数示例：

```bash
python bootstrap.py convert input.png --output output --padding-mode mirror --preset sharper --save-previews
```

### 批量转换

```bash
python bootstrap.py batch ./images --output ./output
python bootstrap.py batch ./images --output ./output --recursive
```

### 环境检查

```bash
python bootstrap.py doctor
```

### 文档入口

```bash
python bootstrap.py docs
python bootstrap.py docs cli
python bootstrap.py docs usage --open
```

## 参数

- `--sizes 16 32 64`：自定义输出尺寸列表
- `--padding-mode edge|mirror|solid`：指定补边策略
- `--preset standard|sharper|smoother`：指定处理预设
- `--save-previews`：同时保存放大预览图
