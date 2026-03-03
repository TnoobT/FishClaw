"""
闲鱼登录工具 Agent 测试
运行方式：在项目根目录执行
    python FishClaw/tests/test_xianyu_login.py

Agent 会自动调用 FishClawTools 中的三个工具方法完成登录流程：
  1. check_login_status  → 检查是否有已保存的 Cookie
  2. send_sms_code       → 向手机发送验证码（浏览器会自动弹出）
  3. login_with_sms      → 提交验证码，完成登录，保存 Cookie
"""

import sys
import os

# 让脚本在任意目录运行都能找到 FishClaw 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from src.tools.xianyu_tools import FishClawTools
from src.models.config import MODEL
# ──────────────────────────────────────────────────────────
# 配置区（按需修改）
# ──────────────────────────────────────────────────────────

# Cookie 保存路径（相对当前脚本）
COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..", ".cache", "cookies", "xianyu_cookies.json")

# 模型配置（DashScope / 通义千问）

# ──────────────────────────────────────────────────────────
# 构建工具 & Agent
# ──────────────────────────────────────────────────────────

xianyu_tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,   # 必须有头，方便人工处理滑块验证码
    enable_post_item=True,
)

agent = Agent(
    name="闲鱼助手",
    description=(
        "你是一个闲鱼账号助手。"
        "你的职责是：登录闲鱼账号并发布商品。"
        "你拥有以下工具：check_login_status、login_with_qrcode、post_item。"
        "请做与闲鱼相关的事情之前要检查登录状态，如果未登录则先扫码登录，以下是流程：\n"
        "1. 先调用 check_login_status 检查是否已登录，如果已登录则任务完成。\n"
        "2. 如果未登录，调用 login_with_qrcode 扫码登录。\n"
    ),
    tools=[xianyu_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/xianyu_agent.db"),
    add_history_to_context=True,
)

# ──────────────────────────────────────────────────────────
# 运行测试
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  闲鱼登录 Agent 测试")
    print(f"  Cookie 路径：{COOKIES_PATH}")
    print("=" * 60)
    print()

    # 使用 cli 交互模式，Agent 可以多轮对话向用户索要验证码
    agent.cli_app()
