'''
Author: tfj
Date: 2026-03-04
LastEditors: tfj
Description: FishClaw 闲鱼助手入口（Team 版）
Version: Alpha
'''
import os

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.team import Team

from src.tools.xianyu_tools import FishClawTools
from src.tools.generate_image_tools import GenerateImageTools
from src.tools.prompt_tools import PromptTools
from src.models.config import MODEL, PROJECT_ROOT

# ──────────────────────────────────────────────────────────
# 配置区（按需修改）
# ──────────────────────────────────────────────────────────

COOKIES_PATH = os.path.join(PROJECT_ROOT, ".cache", "cookies", "xianyu_cookies.json")

# ──────────────────────────────────────────────────────────
# 工具初始化（两个 agent 使用不同的工具权限）
# ──────────────────────────────────────────────────────────

post_tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,
    enable_post_item=True,
    enable_manager_item=False,
)

manager_tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,
    enable_post_item=False,
    enable_manager_item=True,
)

generate_image_tools = GenerateImageTools()
prompt_tools = PromptTools()

# ──────────────────────────────────────────────────────────
# 子 Agent 定义
# ──────────────────────────────────────────────────────────

POST_ITEM_DESCRIPTION = """\
你是「FishClaw 发布助手」，专门帮用户在闲鱼（咸鱼）平台上发布技术类商品。

## 身份定位
你服务的用户是技术卖家，主要出售 AI / 编程等技术服务或知识付费商品。
你的核心职责是：自动生成商品素材（封面图 + 描述文案），并完成闲鱼发布全流程。

## 操作规则
- 每次只调用一个工具，等拿到结果后再决定下一步，不可并发调用多个工具。
- 遇到工具失败，先向用户说明原因，再询问是否重试或跳过。

## 登录检查（每次操作前必须执行）
在执行任何闲鱼操作之前，必须先确认已登录：
1. 调用 `check_login_status` 检查当前登录状态。
2. 若未登录，调用 `login_with_qrcode` 引导用户扫码登录，登录成功后再继续。

## 发布商品流程（按顺序逐步执行）
用户发出发布请求后，在完成登录检查的前提下，依次执行：

1. **生成生图提示词** — 调用 `generate_image_prompt`，传入用户提供的技术主题，
   获得一段科技感英文提示词（含相关专业术语，无中文）。

2. **生成封面图** — 将上一步的提示词传给 `generate_image`，
   调用图像生成服务，获取本地图片路径。

3. **生成商品描述** — 调用 `generate_product_description`，传入技术主题，
   获得约 500 字的口语化中文文案，突出技术价值与应用场景。

4. **填写商品信息** — 将图片路径与描述文案传给 `fill_item_info`，完成表单填写。

5. **发布商品** — 调用 `post_item`，提交发布。
"""

MANAGER_ITEM_DESCRIPTION = """\
你是「FishClaw 管理助手」，专门帮用户在闲鱼（咸鱼）管理已发布的商品。

## 身份定位
你的核心职责是：管理已发布的商品（查看、删除等）。

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

post_item_agent = Agent(
    name="FishClaw 发布助手",
    role="负责在闲鱼平台发布新商品，包括生成封面图、商品描述，并完成发布流程。",
    description=POST_ITEM_DESCRIPTION,
    tools=[post_tools, generate_image_tools, prompt_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/post_item_agent.db"),
    add_history_to_context=True,
    num_history_runs=20,
)

manager_item_agent = Agent(
    name="FishClaw 管理助手",
    role="负责管理闲鱼上已发布的商品，包括查看在售商品列表、删除商品等操作。",
    description=MANAGER_ITEM_DESCRIPTION,
    tools=[manager_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/manager_item_agent.db"),
    add_history_to_context=True,
    num_history_runs=20,
)

# ──────────────────────────────────────────────────────────
# Team 定义
# ──────────────────────────────────────────────────────────

team = Team(
    name="FishClaw 闲鱼助手",
    model=MODEL,
    members=[post_item_agent, manager_item_agent],
    instructions=[
        "你是「FishClaw 闲鱼助手」团队的协调者，负责根据用户意图将任务分发给合适的子助手。",
        "若用户想要【发布/上架/新建】商品，将任务委托给「FishClaw 发布助手」。",
        "若用户想要【管理/查看/删除/下架】已有商品，将任务委托给「FishClaw 管理助手」。",
        "每次只委托一个助手，等待结果后再决定下一步。",
        "若意图不明确，直接询问用户是想发布新商品还是管理已有商品。",
    ],
    db=SqliteDb(db_file=".cache/tmp/xianyu_team.db"),
    add_history_to_context=True,
    num_history_runs=20,
    markdown=True,
)

# ──────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────

def run_response_loop(run_response, entity):
    """
    统一处理 run_response，包括需要人工确认的工具暂停场景。
    entity 可以是 Team 或 Agent 实例（需要有 continue_run 方法）。
    """
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

        run_response = entity.continue_run(
            run_id=run_response.run_id,
            requirements=run_response.requirements,
        )

    if run_response is not None:
        content = run_response.get_content_as_string()
        if content:
            print(f"\nAssistant: {content}\n")


def main():
    print("=" * 60)
    print("  FishClaw 闲鱼助手（Team 版）")
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

        run_response = team.run(user_input)
        run_response_loop(run_response, team)


if __name__ == "__main__":
    main()
