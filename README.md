# Notion自动转小红书图片

把 Notion 文章导出成 `HTML` 后，自动转换为适合手机阅读与发布的小红书图片（默认 `1400x2400`）。

核心目标：

- 固定图片尺寸，保证发帖排版稳定
- 智能切分，尽量避免切断正文
- 自动套用自定义 CSS，统一字体、边距和标题样式

## 整套 Pipeline

1. 在 Notion 写好帖子  
2. 从 Notion 导出为 HTML（会得到一个 `.html` 文件 + 同名资源文件夹）  
3. 运行本项目的一键脚本  
4. 自动完成：
   - 注入 CSS 链接（幂等，不重复插）
   - 渲染 HTML
   - 智能切图（或硬切）
   - 输出 `images_<帖子标题>/page_001.png ...`

## 从 Notion 到图片：详细步骤

### 1) 在 Notion 导出 HTML

- 在 Notion 页面右上角点击 `...`
- 选择 `Export`
- 导出格式选 `HTML`
- 解压后你会得到：
  - `帖子标题.html`
  - `帖子标题/`（图片资源目录）

### 2) 准备样式

- 在项目根目录编辑 `my.css`
- 重点可调：
  - 字体和字号
  - 左右边距
  - 标题样式（如 `.page-title`）

### 3) 一键执行

在项目目录执行：

```bash
./run_html_pipeline.sh 121/备用安卓机的好去处😄.html
```

Windows（`cmd`）：

```bat
run_html_pipeline.bat 121\备用安卓机的好去处😄.html
```

如果要指定 CSS 文件：

```bash
./run_html_pipeline.sh 121/备用安卓机的好去处😄.html /Users/tim/Downloads/my.css
```

Windows（`cmd`）：

```bat
run_html_pipeline.bat 121\备用安卓机的好去处😄.html D:\path\to\my.css
```

### 4) 查看输出

输出目录默认为：

```text
<html所在目录>/images_<title标签内容>
```

例如：

```text
121/images_备用安卓机的好去处😄
```

## 项目结构

```text
html_to_image.py          # 渲染+切分主脚本
insert_css_into_html.py   # 往 HTML 注入 CSS link
run_html_pipeline.py      # 跨平台一键流水线主入口
run_html_pipeline.sh      # macOS/Linux 启动器
run_html_pipeline.bat     # Windows 启动器
my.css                    # 默认样式模板
requirements.txt
```

## 安装依赖

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## 常用参数（`html_to_image.py`）

- `--width` / `--height`：输出尺寸（默认 `1400x2400`）
- `--supersample`：超采样倍率（默认 `5.0`）
- `--side-padding`：页面左右内边距（样式层）
- `--top-padding` / `--bottom-padding`：页面上下内边距（样式层）
- `--slice-padding`：每张切图上下留白（切图层，默认 `80`）
- `--cut-mode smart|hard`：智能切分/硬切分
- `--search-range`：智能切分搜索范围
- `--white-threshold`：空白像素阈值
- `--white-row-ratio`：空白行比例阈值
- `--sharpen`：导出锐化强度

## 说明

- `insert_css_into_html.py` 是幂等的：相同 CSS link 已存在时会自动跳过。
- `run_html_pipeline.py` 会自动计算 CSS 相对路径；`sh/bat` 只是平台启动器。
- 输出图片始终固定尺寸（默认每张 `1400x2400`）。
- 智能切分主要优化纵向切点；横向观感主要由 CSS 控制。
