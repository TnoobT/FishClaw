import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agno.agent import Agent
from agno.db.sqlite import SqliteDb

from src.tools.xianyu_tools import FishClawTools
from src.tools.generate_image_tools import GenerateImageTools
from src.tools.prompt_tools import PromptTools
from src.models.config import MODEL, PROJECT_ROOT

# ──────────────────────────────────────────────────────────
# 配置区（按需修改）
# ──────────────────────────────────────────────────────────

COOKIES_PATH = os.path.join(PROJECT_ROOT, ".cache", "cookies", "xianyu_cookies.json")

# ──────────────────────────────────────────────────────────
# 工具初始化
# ──────────────────────────────────────────────────────────

xianyu_tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,
    enable_post_item=False,
    enable_manager_item=True,
)
generate_image_tools = GenerateImageTools()
prompt_tools = PromptTools()

# ──────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────

AGENT_DESCRIPTION = """\
你是「FishClaw 闲鱼助手」，专门帮用户在闲鱼（咸鱼）管理商品。

## 身份定位
你的核心职责是：管理已发布的商品。

## 操作规则
- 每次只调用一个工具，等拿到结果后再决定下一步，不可并发调用多个工具。
- 遇到工具失败，先向用户说明原因，再询问是否重试或跳过。

## 登录检查（每次操作前必须执行）
在执行任何闲鱼操作之前，必须先确认已登录：
1. 调用 `check_login_status` 检查当前登录状态。
2. 若未登录，调用 `login_with_qrcode` 引导用户扫码登录，登录成功后再继续。

## 管理商品流程（按顺序逐步执行）
用户发出管理请求后，在完成登录检查的前提下，依次执行：

1. **打开个人中心** — 调用 `open_profile`，打开闲鱼个人中心页面。

2. **获取在售商品** — 调用 `get_selling_items`，获取当前在售商品列表。

3. **管理商品** — 根据用户需求，调用 `delete_item` 删除商品。
"""

agent = Agent(
    name="FishClaw 闲鱼助手",
    description=AGENT_DESCRIPTION,
    tools=[xianyu_tools, generate_image_tools, prompt_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/xianyu_agent.db"),
    add_history_to_context=True,
    num_history_runs=100,
)

# ──────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  FishClaw 闲鱼助手")
    print(f"  Cookie 路径：{COOKIES_PATH}")
    print("  输入 exit / quit 退出")
    print("=" * 60)
    print()

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

        # 处理需要人工确认的工具调用（requires_confirmation=True）
        while run_response is not None and run_response.is_paused:
            for requirement in run_response.active_requirements:
                if requirement.needs_confirmation:
                    print(
                        f"\n[确认] 工具 '{requirement.tool_execution.tool_name}'"
                        f" 参数 {requirement.tool_execution.tool_args} 需要您确认。"
                    )
                    choice = input("是否继续？(y/n，默认 y): ").strip().lower()
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
            content = run_response.get_content_as_string()
            if content:
                print(f"\nAgent: {content}\n")


if __name__ == "__main__":
    main()
