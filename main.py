import os

from agno.agent import Agent
from agno.db.sqlite import SqliteDb

from src.tools.xianyu_tools import FishClawTools
from src.tools.generate_image_tools import GenerateImageTools
from src.tools.prompt_tools import PromptTools
from src.models.config import MODEL, PROJECT_ROOT

# ──────────────────────────────────────────────────────────
# 配置区
# ──────────────────────────────────────────────────────────

COOKIES_PATH = os.path.join(PROJECT_ROOT, ".cache", "cookies", "xianyu_cookies.json")

# ──────────────────────────────────────────────────────────
# 工具初始化
# ──────────────────────────────────────────────────────────

xianyu_tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,
    enable_farming=False,   # 需要养号时改为 True
)

generate_image_tools = GenerateImageTools()
prompt_tools = PromptTools()

# ──────────────────────────────────────────────────────────
# Agent 定义
# ──────────────────────────────────────────────────────────

AGENT_DESCRIPTION = """\
你是「FishClaw 闲鱼助手」，帮助用户在闲鱼（咸鱼）平台发布和管理技术类商品。

## 基本规则
- 每次只调用一个工具，等拿到结果后再决定下一步，不可并发调用多个工具。
- 遇到工具失败，先向用户说明原因，再询问是否重试或跳过。
- 所有闲鱼工具内部已自动处理登录检查，无需手动调用登录工具，除非用户明确要求登录。

## 发布商品流程
用户想要【发布/上架/新建】商品时，依次执行：
1. 调用 `generate_image_prompt`，传入技术主题，生成科技感英文图片提示词。
2. 调用 `generate_image`，传入提示词，获取本地图片路径。
3. 调用 `generate_product_description`，传入技术主题，生成约 500 字商品描述。
4. 调用 `draft_item`，传入图片路径、描述和价格，完成草稿填写并截图。
5. 将截图展示给用户确认，若有修改需求，重新调用 `draft_item`。
6. 用户确认无误后，调用 `publish_item` 完成发布（需用户二次确认）。

## 管理商品流程
用户想要【管理/查看/删除/下架】商品时，依次执行：
1. 调用 `get_selling_items`，获取在售商品列表，等待系统打印给用户后，询问用户要操作哪件商品。
2. 根据用户指令，调用 `manage_item`，传入商品链接和操作类型（delist 下架 / delete 删除）。

## 市场调研流程
用户想要【搜索/调研/定价参考】时：
1. 调用 `search_market`，传入关键词，等待系统打印搜索结果给用户。
2. 根据结果向用户提供定价或竞品分析建议。
"""

agent = Agent(
    name="FishClaw 闲鱼助手",
    description=AGENT_DESCRIPTION,
    tools=[xianyu_tools, generate_image_tools, prompt_tools],
    model=MODEL,
    markdown=True,
    db=SqliteDb(db_file=".cache/tmp/xianyu_agent.db"),
    add_history_to_context=True,
    num_history_runs=50,
)

# ──────────────────────────────────────────────────────────
# external_execution 工具名 → 处理函数映射
# ──────────────────────────────────────────────────────────

def _handle_external_tool(requirement) -> str:
    """统一处理 external_execution_required 工具，执行并返回给 LLM 的摘要。"""
    tool_name = requirement.tool_execution.tool_name
    tool_args = requirement.tool_execution.tool_args or {}

    if tool_name == "get_selling_items":
        result = xianyu_tools.get_selling_items()
    elif tool_name == "search_market":
        result = xianyu_tools.search_market(**tool_args)
    else:
        result = f"[未知 external tool: {tool_name}]"

    # 完整列表直接打印给用户
    print(f"\n{result}\n")

    # 给 LLM 的精简摘要，避免重复输出长列表
    return (
        f"{result}\n"
        "以上列表已直接打印给用户，不要再打印这些列表，不要重复输出列表\n"
        "用户问题分成两种情况:\n"
        "1. 用户只要看有哪些商品，你就固定回复“请问您接下来想对哪件商品操作”\n"
        "2. 如果是其它问题，你就正常回答问题\n"
        
    )

# ──────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  FishClaw 闲鱼助手 Beta")
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

        # ── 处理暂停（external_execution / requires_confirmation）──
        while run_response is not None and run_response.is_paused:
            has_external = False

            for requirement in run_response.active_requirements:

                if requirement.needs_external_execution:
                    llm_summary = _handle_external_tool(requirement)
                    requirement.set_external_execution_result(llm_summary)
                    has_external = True

                elif requirement.needs_confirmation:
                    tool_name = requirement.tool_execution.tool_name
                    tool_args = requirement.tool_execution.tool_args
                    print(f"\n[需要确认] 即将执行「{tool_name}」，参数：{tool_args}")
                    choice = input("是否继续？(y/n，默认 y): ").strip().lower()
                    if choice == "n":
                        requirement.reject()
                        print("已取消。")
                    else:
                        requirement.confirm()

            if has_external:
                print("AI 理解中，请稍等...\n")

            run_response = agent.continue_run(
                run_id=run_response.run_id,
                requirements=run_response.requirements,
            )

        if run_response is not None:
            content = run_response.get_content_as_string()
            if content:
                print(f"\nAssistant: {content}\n")


if __name__ == "__main__":
    main()