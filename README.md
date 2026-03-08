# HTML To Mobile Images

把 `HTML + CSS` 自动渲染并切分为适合手机阅读的固定尺寸图片（默认 `1400x2400`）。

项目包含一条完整流水线：

1. 自动把 CSS `<link>` 注入 HTML（幂等，不会重复插入）
2. 读取页面并渲染
3. 智能切分（优先找空白行）或硬切分
4. 输出固定尺寸图片到 `images_<帖子标题>`

## 项目结构

```text
html_to_image.py          # 渲染+切分主脚本
insert_css_into_html.py   # 注入 CSS link
run_html_pipeline.sh      # 一键流水线（推荐）
my.css                    # 默认样式模板
```

## 依赖

- Python 3.9+
- Playwright
- Pillow
- Chromium（Playwright 浏览器内核）

安装：

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## 快速开始

在项目目录运行：

```bash
./run_html_pipeline.sh 121/备用安卓机的好去处😄.html
```

可选：指定 CSS 文件路径

```bash
./run_html_pipeline.sh 121/备用安卓机的好去处😄.html /Users/tim/Downloads/my.css
```

输出目录默认：

```text
<html所在目录>/images_<title标签内容>
```

例如：

```text
121/images_备用安卓机的好去处😄
```

## 单独使用脚本

### 1) 只注入 CSS

```bash
python3 insert_css_into_html.py 121/备用安卓机的好去处😄.html --css-href ../my.css
```

### 2) 只导图

```bash
python3 html_to_image.py 121/备用安卓机的好去处😄.html
```

## 常用参数（`html_to_image.py`）

- `--width` / `--height`: 输出尺寸（默认 `1400x2400`）
- `--supersample`: 超采样倍率（默认 `4.0`，更清晰）
- `--side-padding`: 页面左右内边距
- `--top-padding` / `--bottom-padding`: 页面上下内边距（作用在页面样式层）
- `--slice-padding`: 每张切片上下留白（作用在切图层，默认 `80`）
- `--cut-mode smart|hard`: 智能切分/硬切分
- `--search-range`: 智能切分搜索范围
- `--white-threshold`: 空白像素阈值
- `--white-row-ratio`: 判定“空白行”的比例阈值
- `--sharpen`: 输出锐化强度

## 说明

- `insert_css_into_html.py` 是幂等的：如果已经插入相同 `<link>`，会自动跳过。
- 切图始终输出固定尺寸（默认每张 `1400x2400`）。
- 智能切分只影响纵向切点，横向排版由 CSS + 注入参数控制。
