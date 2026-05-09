# CLI 说明

## 入口

推荐通过 bootstrap 调用：

```bash
python bootstrap.py <command>
```

也可以在依赖安装完成后直接运行：

```bash
python -m imagetopixel <command>
imagetopixel <command>
```

## 常用命令

### 启动 GUI

```bash
python bootstrap.py gui
```

### 单图转换

```bash
python bootstrap.py convert input.png --output output
python bootstrap.py convert input.png --output output --contour hybrid --algorithm majority
python bootstrap.py convert input.png --output output --stdout-report full
```

### 批量转换

```bash
python bootstrap.py batch ./images --output ./output
python bootstrap.py batch ./images --output ./output --recursive
python bootstrap.py batch ./images --output ./output --recursive --contour coverage-35 --algorithm median
python bootstrap.py batch ./images --output ./output --recursive --report-file reports/batch.json --summary-file reports/batch.md
```

### 环境自检

```bash
python bootstrap.py doctor
```

### 文档入口

```bash
python bootstrap.py docs
python bootstrap.py docs cli
python bootstrap.py docs usage --open
```

## 通用参数

- `--sizes 16 32 64`：指定导出尺寸列表
- `--padding-mode edge|mirror|solid`：指定补边模式
- `--contour coverage-50|coverage-35|center-hit|hybrid`：选择 `16x16` 轮廓方案
- `--algorithm majority|median|center`：选择轮廓内的颜色采样算法
- `--preset ...`：兼容旧参数，等同于 `--algorithm`
- `--save-previews`：同时保存放大预览图

说明：当前实现中，所有尺寸都从 `16x16` 主结果生成；默认的 `32x32` 和 `64x64` 是它的最近邻放大结果。

## 结构化输出

- `--stdout-report compact`：输出精简 JSON
- `--stdout-report full`：输出完整 JSON
- `--json`：兼容旧参数，等同于 `--stdout-report full`
- `--report-file path/to/report.json`：保存完整 JSON 报告
- `--summary-file path/to/summary.csv`
- `--summary-file path/to/summary.md`

## 覆盖策略

- 默认行为：覆盖已有输出
- `--overwrite`：显式声明覆盖
- `--skip-existing`：若目标文件已存在则跳过，并在报告中标记为 `skipped`

## 失败处理

- `batch` 默认遇错继续
- 全部成功返回 `0`
- 全部失败返回 `1`
- 部分成功且部分失败返回 `2`
- `--stop-on-error`：遇到首个失败立即停止

## 命名策略

- `--name-mode flat`：输出如 `hero_16.png`
- `--name-mode parent`：输出如 `icons__hero_16.png`
- `--name-mode mirror`：输出如 `chars/hero_16.png`
