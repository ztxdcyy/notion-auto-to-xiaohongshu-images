# Notion自动转小红书图片

把 Notion 导出的帖子，快速转成适合手机阅读的高清分页图片。

## 你能做什么

- 上传 Notion 导出的 `zip` 或 `html`
- 导出前先看全文预览
- 一键导出高清图片
- 支持两种常用尺寸：
  - `1200 x 1600`（3:4 常规图文）
  - `1440 x 2400`（满屏打开）

## 3 分钟跑起来

### 1) 安装依赖

```bash
cd /Users/tim/code/Personal_Project/html-to-mobile-images
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run playwright install chromium
```

> 如果你还没装 `uv`：
>
> `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2) 启动

```bash
python web_app.py
```

浏览器打开：

```text
http://127.0.0.1:8123
```

## 使用步骤

1. 上传源文件
- 推荐上传 Notion 导出的 `zip`
- 也支持上传单个 `html`（若依赖外部资源，可能缺图）

2. 选参数
- 在“导出图片选项”里选择尺寸和清晰度
- 在“切分策略选项”里按需微调

3. 生成预览
- 点击 `生成全文预览`
- 中间区域上下滚动查看分页效果

4. 高清导出
- 点击 `开始高清导出`
- 右侧看任务状态和页数

## Notion 导出建议

在 Notion 中：

1. 打开页面右上角 `...`
2. 选择 `Export`
3. 格式选 `HTML`
4. 将导出的 `html + 同名资源目录` 一起打包成 `zip` 上传（最稳）

## 常见问题

### 1) 启动后打不开页面

请用：

- `http://127.0.0.1:8123`
- 或 `http://localhost:8123`

不要直接访问 `0.0.0.0`。

### 2) 页面显示不全或图片不清晰

- 提高“导出清晰度(倍率)”
- 适当提高“导出锐化强度”
- 优先上传 Notion 原始 zip，避免资源缺失

### 3) 智能切分效果不理想

在“切分策略选项”里微调：

- 搜索范围
- 最小分段高度
- 空白阈值 / 空白行比例

---

如果你只想最省心：

- 上传 zip
- 尺寸选 `1440 x 2400`
- 直接“生成预览” -> “开始高清导出”
