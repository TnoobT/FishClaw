'''
Author: tfj
Date: 2026-03-03 21:49:34
LastEditors: tfj
LastEditTime: 2026-03-03 23:07:43
Description: 
Version: Alpha
'''
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
from src.tools.generate_image_tools import GenerateImageTools
from src.tools.prompt_tools import PromptTools
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
generate_image_tools = GenerateImageTools()
prompt_tools = PromptTools()


agent = Agent(
    name="闲鱼助手",
    description=(
        "你是一个闲鱼账号助手。"
        "你的职责是：登录闲鱼账号并发布商品。"
        "发布商品时，严格按以下顺序逐步执行：\n"
        "1. 调用 generate_image_prompt，传入用户提到的技术主题，获取英文生图提示词。\n"
        "2. 把上一步返回的提示词传给 generate_image，生成商品图片，获取本地图片路径。\n"
        "3. 调用 generate_product_description，传入用户提到的技术主题，获取约500字的商品描述文案。\n"
        "4. 把图片路径和商品描述传给 fill_item_info，填写商品信息。\n"
        "5. 调用 post_item 发布商品。\n"
        "做任何闲鱼操作前，先检查登录状态：\n"
        "- 先调用 check_login_status，如果已登录则继续任务。\n"
        "- 如果未登录，调用 login_with_qrcode 扫码登录后再继续。\n"
        "注意：每次只调用一个工具，根据上一步的返回结果再决定下一步。"
    ),
    tools=[xianyu_tools, generate_image_tools, prompt_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/xianyu_agent.db"),
    add_history_to_context=True,
    num_history_runs=100
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

    # 自定义 CLI 循环，正确处理 requires_confirmation=True 的暂停流程
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("再见！")
            break

        run_response = agent.run(user_input)

        # 处理暂停确认（requires_confirmation=True）
        while run_response is not None and run_response.is_paused:
            for requirement in run_response.active_requirements:
                if requirement.needs_confirmation:
                    print(
                        f"\n[确认] 工具 '{requirement.tool_execution.tool_name}'"
                        f" 参数 {requirement.tool_execution.tool_args} 需要您的确认。"
                    )
                    choice = input("是否继续执行？(y/n，默认 y): ").strip().lower()
                    if choice == "n":
                        requirement.reject()
                        print("已取消。")
                    else:
                        requirement.confirm()

            run_response = agent.continue_run(
                run_id=run_response.run_id,
                requirements=run_response.requirements,
            )

        if run_response is not None:
            # 打印 Agent 回复
            content = run_response.get_content_as_string()
            if content:
                print(f"\nAgent: {content}\n")
