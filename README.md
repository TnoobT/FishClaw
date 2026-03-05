# FishClaw — 闲鱼AI助手
<p align="center">
    <img src="assets/logo.png" alt="FishClaw Logo" width="150" height="150">
</p>

基于 LLM + Playwright 的闲鱼自动化助手，用自然语言发布商品、管理在售列表，持续开发中~

---

## 免责声明

> [警告]
> 请勿用于非法用途，否则后果自负。

<details>
<summary>▶ 点击展开完整免责声明</summary>

**1. 使用目的**

本项目仅供学习交流使用，请勿用于任何商业或非法用途。用户理解并同意，任何违反法律法规、侵犯他人合法权益的行为，均与本项目及其开发者无关，后果由用户自行承担。

**2. 使用期限**

您应在下载或保存本项目源代码后 **24 小时内**删除相关文件；超出此期限的任何使用行为，一概与本项目及其开发者无关。

**3. 操作规范**

- 本项目严禁用于窃取他人隐私或进行非法测试、渗透攻击。
- 严禁利用本项目相关技术从事任何非法工作，如因此产生的一切不良后果与本项目及开发者无关。
- 本项目仅允许在授权情况下使用数据，用户如因违反此规定而引发任何法律责任，由用户自行承担。

**4. 免责声明接受**

下载、保存、浏览源代码或安装编译使用本程序，即表示您已阅读并同意本声明，并承诺遵守全部条款。

**5. 免责声明修改**

本声明可能随项目运营情况及法律法规变化进行调整，用户应定期查阅本页面以获取最新版本，并在使用本项目时遵守最新版本的免责声明。

> 请用户慎重阅读并理解本免责声明的所有内容，确保在使用本项目时严格遵守相关规定。

</details>

---

## 功能

### ✅ 发布商品
对话式发布闲鱼商品，全流程自动化：
- 根据技术主题自动生成科技感封面图（调用阿里云 DashScope 图像生成模型）
- 自动生成第一人称口语化商品描述文案（约 500 字，由 LLM 生成）
- 自动填写发布表单（图片上传、描述、分类选择、价格）
- 发布前截图供用户确认，点击确认后提交

### ✅ 管理商品
- 打开个人中心，获取所有在售商品列表（标题、价格、链接）
- 指定商品 URL 后一键 **下架**（草稿状态，可重新上架）或 **删除**（含二次确认）
- 一键 **刷新/置顶** 商品，提升搜索排名（每件每天可刷新一次）
- 查看商品 **浏览量、收藏数、成交数** 等数据，评估商品表现

### ✅ 市场调研
- 关键词搜索闲鱼商品，采集标题、价格、链接，用于竞品调研和定价参考

### ✅ 通用工具
- `goto`：跳转到任意 URL，配合其他工具灵活使用
- `get_page_content`：读取当前页面可见文字，让 AI 感知浏览器状态

### ✅ 登录管理
- 扫码登录（自动检测二维码弹窗，引导用户扫码）
- Cookie 本地持久化，重启后免重复登录
- 每次操作前自动检查登录状态

---

## 技术栈

| 层次 | 技术 |
|------|------|
| **AI 框架** | [Agno](https://github.com/agno-agi/agno) — Agent 编排、工具调用、对话历史 |
| **LLM** | 阿里云 DashScope（`qwen-max` 等，OpenAI 兼容接口） |
| **图像生成** | 阿里云 DashScope `z-image-turbo` |
| **浏览器自动化** | [Playwright](https://playwright.dev/python/) — 有头 Chromium，模拟真实用户操作 |

---

## 项目结构

```
FishClaw/
├── main.py                        # 入口，单 Agent CLI
├── src/
│   ├── models/
│   │   └── config.py              # LLM 配置（从 .env 读取）
│   ├── tools/
│   │   ├── xianyu_tools.py        # Playwright 闲鱼自动化工具集
│   │   ├── generate_image_tools.py # 图像生成工具（DashScope）
│   │   └── prompt_tools.py        # 提示词生成工具（生图词 + 商品文案）
│   └── cookbook/
│       ├── post_item_agent.py     # 单功能发布 Agent 示例
│       └── manager_item_agent.py  # 单功能管理 Agent 示例
├── assets/
│   ├── logo.png
│   └── default_agent.png          # 无 API Key 时的封面图兜底
├── .cache/
│   ├── cookies/xianyu_cookies.json # Cookie 持久化
│   ├── cache_img/                  # 生成图片缓存
│   └── screenshot/                 # 发布前截图
├── .env                            # 环境变量（不提交）
├── .env.example                    # 环境变量模板
└── pyproject.toml
```

---

## 快速开始

### 1. 安装依赖

```bash
uv venv
venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
uv sync
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填写以下必填项：

```env
# Agent 推理 + 文案生成用的 LLM
AGENT_LLM_MODEL=qwen-max
AGENT_LLM_API_KEY=your-dashscope-api-key
AGENT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 封面图生成（可选，未配置时使用默认图片）
IMAGE_API_KEY=your-dashscope-api-key
```

### 3. 运行

```bash
python main.py
```

### 4. 对话示例

```
You: 帮我发布一个 Python 爬虫技术服务的商品，价格 99 元
# → 自动生成封面图、文案，填写表单，截图确认后发布

You: 查看我现在在售的商品
# → 打开个人中心，列出所有在售商品

You: 把第二个商品下架
# → 进入商品详情，点击「下架」按钮并确认

You: 删除第三个商品
# → 进入商品详情，点击「删除」并处理二次确认弹窗

You: 帮我把第一个商品刷新一下
# → 进入商品详情，点击「刷新」按钮提升排名

You: 查看第一个商品的浏览量和收藏数
# → 打开商品详情页，采集并展示数据

You: 搜索一下 Python 教程，看看竞品价格
# → 在闲鱼搜索，采集前 20 条结果的标题和价格
```

---

## 工具速查

### 始终可用

| 工具 | 说明 |
|------|------|
| `check_login_status` | 检查当前账号登录状态 |
| `take_screenshot` | 截图当前页面 |
| `goto(url)` | 在浏览器中打开指定 URL |
| `get_page_content()` | 读取当前页面可见文字（供 AI 分析页面状态） |
| `search_market(keyword)` | 搜索闲鱼商品，采集标题、价格、链接 |

### enable_login=True

| 工具 | 说明 |
|------|------|
| `login_with_qrcode()` | 打开扫码登录弹窗，引导用户扫码 |

### enable_post_item=True

| 工具 | 说明 |
|------|------|
| `fill_item_info(...)` | 在发布页填写图片、描述、分类、价格 |
| `post_item()` ⚠️ | 提交发布（需用户确认） |

### enable_manager_item=True

| 工具 | 说明 |
|------|------|
| `open_profile()` | 打开个人中心 |
| `get_selling_items()` | 采集所有在售商品列表 |
| `bump_item(item_url)` | 刷新/置顶商品（每天一次） |
| `delist_item(item_url)` ⚠️ | 下架商品（变草稿，可重新上架） |
| `delete_item(item_url)` ⚠️ | 永久删除商品 |
| `get_item_stats(item_url)` | 查看商品浏览量、收藏数、成交数 |

> ⚠️ 标注的工具 `requires_confirmation=True`，执行前会暂停等待用户确认。

---

## 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `AGENT_LLM_MODEL` | Agent 推理模型 | `qwen-max` |
| `AGENT_LLM_API_KEY` | DashScope API Key | — |
| `AGENT_LLM_BASE_URL` | LLM 接口地址 | DashScope 兼容模式 |
| `AGENT_LLM_TEMPERATURE` | 推理温度 | `0.5` |
| `IMAGE_API_KEY` | 图像生成 API Key | — |
| `XIANYU_HOME_URL` | 闲鱼首页地址 | `https://www.goofish.com` |
| `PLAYWRIGHT_HEADLESS` | 是否无头模式 | `false`（有头，降低风控） |
| `BROWSE_COMMENT_TEXT` | 浏览评论内容 | 预设养号文案 |

---

## 测试

```bash
# 参数验证 + 工具注册测试（无需浏览器，秒级完成）
python tests/test_tools.py

# 含浏览器集成测试（启动无头 Chromium，约 15-30 秒）
RUN_BROWSER_TESTS=true python tests/test_tools.py
```

测试覆盖：

| 分类 | 内容 |
|------|------|
| 初始化 | 各 `enable_*` 开关的工具注册正确性 |
| 参数验证 | 空参数提前返回错误提示 |
| 浏览器集成 | `goto` / `get_page_content` / `search_market` 真实调用（可选） |
