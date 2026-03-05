"""
直接调用以下工具的测试脚本（不使用 Agent）：
  - take_screenshot    : 对当前页面截图
  - random_scroll      : 随机上下滑动，模拟浏览
  - open_random_post   : 随机点进一个帖子
  - comment_on_post    : 在当前帖子发表评论
  - open_profile       : 打开个人中心（我的闲鱼）
  - get_selling_items  : 获取所有在售商品列表
  - delete_item        : 删除指定商品

运行方式：在项目根目录下执行
    python src/tests/test_browse_tools_direct.py [test_name]

可用的 test_name：
    screenshot     - 仅测试截图
    scroll         - 仅测试随机滚动
    open_post      - 仅测试随机点进帖子
    comment        - 仅测试评论（需先进入某个帖子）
    profile        - 仅测试打开个人中心
    selling        - 仅测试获取在售商品
    delete         - 仅测试删除商品（交互输入 URL）
    all            - 按顺序执行全部测试（默认）
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.tools.xianyu_tools import FishClawTools
from src.models.config import PROJECT_ROOT

# ──────────────────────────────────────────────────────────
# 配置（按需修改）
# ──────────────────────────────────────────────────────────
COOKIES_PATH = os.path.join(PROJECT_ROOT, ".cache", "cookies", "xianyu_cookies.json")

# random_scroll 的默认滚动轮次
SCROLL_ROUNDS = 5

# ──────────────────────────────────────────────────────────
# 初始化工具
# ──────────────────────────────────────────────────────────
tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    enable_login=True,
    enable_post_item=False,   # 本次测试不需要发布功能
    enable_browse=True,       # 启用浏览/个人中心/商品管理工具
    headless=False,           # 有头模式，可直观看到页面动作
)


# ──────────────────────────────────────────────────────────
# 辅助：打印分隔线
# ──────────────────────────────────────────────────────────
def _sep(title: str = "") -> None:
    line = "=" * 55
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


# ──────────────────────────────────────────────────────────
# 辅助：确保已登录（不重复登录）
# ──────────────────────────────────────────────────────────
def _ensure_login() -> bool:
    print("\n[预检] 检查登录状态...")
    status = tools.check_login_status()
    print(f"  结果：{status}")

    # check_login_status 含"登录"且不含"未登录"即视为已登录
    if "登录" in status and "未登录" not in status:
        print("  登录，无需重新登录。")
        return True

    print("\n  检测到未登录，尝试扫码/Cookie 登录（请在浏览器中完成扫码）...")
    login_result = tools.login_with_qrcode(timeout_seconds=180)
    print(f"  结果：{login_result}")

    # 兼容: 已通过本地 Cookie 自动登录 / 登录成功 / 已登录 等情况
    if "登录" in login_result and "失败" not in login_result and "超时" not in login_result:
        print("  登录成功。")
        return True

    print("  登录失败，测试终止。")
    return False


# ──────────────────────────────────────────────────────────
# 单项测试函数
# ──────────────────────────────────────────────────────────

def test_screenshot():
    """测试 take_screenshot：对当前浏览器页面截图。"""
    _sep("测试 take_screenshot")

    # take_screenshot 需要页面已打开；若 _page 为 None，
    # 先通过 random_scroll 触发首页加载即可。
    if tools._page is None:
        print("  当前无已打开页面，先触发首页加载（random_scroll 1 轮）...")
        pre = tools.random_scroll(rounds=1)
        print(f"  预加载：{pre}")

    result = tools.take_screenshot()
    print(f"\n  结果：{result}")

    if "截图已保存到" in result:
        print("  ✅ 截图成功！")
    else:
        print("  ❌ 截图失败，请检查日志。")

    return result


def test_random_scroll(rounds: int = SCROLL_ROUNDS):
    """测试 random_scroll：随机上下滑动若干轮。"""
    _sep(f"测试 random_scroll（rounds={rounds}）")

    result = tools.random_scroll(rounds=rounds)
    print(f"\n  结果：\n{result}")

    if "随机滑动完成" in result:
        print("  ✅ 随机滑动完成！")
    else:
        print("  ❌ 随机滑动异常，请检查日志。")

    return result


def test_open_random_post():
    """测试 open_random_post：随机点进一个帖子。"""
    _sep("测试 open_random_post")

    # 先滑动，使Feed流中出现帖子链接
    if tools._page is None or "item" not in (tools._page.url if tools._page else ""):
        print("  页面可能没有帖子卡片，先滑动加载内容...")
        tools.random_scroll(rounds=3)

    result = tools.open_random_post()
    print(f"\n  结果：{result}")

    if "已进入帖子" in result:
        print("  ✅ 成功进入一个帖子！")
    elif "未能" in result:
        print("  ⚠️  未找到帖子链接，可能需要更多内容加载（多滑几轮）。")
    else:
        print("  ❌ 进入帖子失败，请检查日志。")

    return result


def test_comment_on_post():
    """测试 comment_on_post：在当前帖子发表评论。"""
    _sep("测试 comment_on_post")

    if tools._page is None:
        print("  ⚠️  当前没有已打开的帖子页面，先执行 open_random_post...")
        post_result = tools.open_random_post()
        print(f"  open_random_post：{post_result}")
        if "已进入帖子" not in post_result:
            print("  ❌ 无法进入帖子，comment_on_post 测试跳过。")
            return "跳过"

    result = tools.comment_on_post()
    print(f"\n  结果：{result}")

    if "评论已发送" in result:
        print("  ✅ 评论发送成功！")
    elif "未能找到评论输入框" in result:
        print("  ⚠️  未找到评论输入框（当前页面可能不支持评论）。")
    elif "评论内容为空" in result:
        print("  ⚠️  请在 .env 中配置 BROWSE_COMMENT_TEXT。")
    else:
        print("  ❌ 评论失败，请检查日志。")

    return result


def test_open_profile():
    """测试 open_profile：打开闲鱼个人中心。"""
    _sep("测试 open_profile")

    result = tools.open_profile()
    print(f"\n  结果：{result}")

    if "已打开个人中心" in result:
        print("  ✅ 成功进入个人中心！")
    elif "未能" in result:
        print("  ⚠️  未找到入口，请确认已登录且页面结构未变更。")
    else:
        print("  ❌ 打开个人中心失败，请检查日志。")

    return result


def test_get_selling_items():
    """测试 get_selling_items：获取所有在售商品列表。"""
    _sep("测试 get_selling_items")

    # 若当前不在个人中心，工具内部会自动调用 open_profile
    result = tools.get_selling_items()
    print(f"\n  结果：\n{result}")

    if "件在售商品" in result:
        print("  ✅ 成功获取在售商品列表！")
    elif "未找到" in result:
        print("  ⚠️  当前账号无在售商品，或未能进入在售 Tab。")
    else:
        print("  ❌ 获取在售商品失败，请检查日志。")

    return result


def test_delete_item(item_url: str = ""):
    """测试 delete_item：删除指定商品。"""
    _sep("测试 delete_item")

    if not item_url:
        item_url = input(
            "  请输入要删除的商品 URL\n"
            "  （可从 get_selling_items 结果中复制，直接回车跳过）：\n  > "
        ).strip()

    if not item_url:
        print("  ⚠️  未提供商品 URL，跳过 delete_item 测试。")
        return "跳过"

    print(f"  将要删除：{item_url}")
    print("  ⚠️  注意：这将永久删除该商品！")
    try:
        confirm = input("  >> 确认删除？输入 y 继续，其他任意键跳过：").strip().lower()
    except KeyboardInterrupt:
        print("\n  已取消。")
        return "取消"

    if confirm != "y":
        print("  已跳过删除测试。")
        return "跳过"

    result = tools.delete_item(item_url)
    print(f"\n  结果：{result}")

    if "成功删除" in result:
        print("  ✅ 商品删除成功！")
    elif "未能" in result:
        print("  ⚠️  未找到「删除」按钮，请确认 URL 和页面结构。")
    else:
        print("  ❓ 请在浏览器中确认删除结果。")

    return result


# ──────────────────────────────────────────────────────────
# 全量测试（顺序执行）
# ──────────────────────────────────────────────────────────

def run_all():
    """按顺序执行所有工具测试。"""
    _sep("浏览模块工具 · 全量测试")

    if not _ensure_login():
        return

    results = {}

    # 1. random_scroll（会自动打开首页）
    results["random_scroll"] = test_random_scroll(rounds=3)

    # 2. take_screenshot（页面已打开）
    results["take_screenshot"] = test_screenshot()

    # 3. open_random_post
    results["open_random_post"] = test_open_random_post()

    # 4. comment_on_post（已在帖子页面）
    print("\n  ⚠️  注意：这将向帖子发送真实评论，如不需要请按 Ctrl+C 取消。")
    try:
        input("  >> 按 Enter 继续，Ctrl+C 跳过评论测试... ")
        results["comment_on_post"] = test_comment_on_post()
    except KeyboardInterrupt:
        print("\n  已跳过评论测试。")
        results["comment_on_post"] = "用户跳过"

    # 5. open_profile
    results["open_profile"] = test_open_profile()

    # 6. get_selling_items
    results["get_selling_items"] = test_get_selling_items()

    # 7. delete_item（交互确认，防误删）
    print("\n  ⚠️  即将测试 delete_item，需手动输入要删除的商品 URL。")
    try:
        results["delete_item"] = test_delete_item()
    except KeyboardInterrupt:
        print("\n  已跳过 delete_item 测试。")
        results["delete_item"] = "用户跳过"

    # 汇总
    _sep("测试汇总")
    for name, res in results.items():
        short = str(res)[:80].replace("\n", " ")
        print(f"  {name}: {short}")
    print()


# ──────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_name = "selling"

    if test_name == "screenshot":
        if not _ensure_login(): sys.exit(1)
        test_screenshot()
    elif test_name == "scroll":
        if not _ensure_login(): sys.exit(1)
        test_random_scroll()
    elif test_name == "open_post":
        if not _ensure_login(): sys.exit(1)
        test_open_random_post()
    elif test_name == "comment":
        if not _ensure_login(): sys.exit(1)
        test_comment_on_post()
    elif test_name == "profile":
        if not _ensure_login(): sys.exit(1)
        test_open_profile()
    elif test_name == "selling":
        if not _ensure_login(): sys.exit(1)
        test_get_selling_items()
    elif test_name == "delete":
        if not _ensure_login(): sys.exit(1)
        test_delete_item()
    elif test_name == "all":
        run_all()
    else:
        print(f"未知测试名称：{test_name}")
        print("可用选项：screenshot | scroll | open_post | comment | profile | selling | delete | all")
        sys.exit(1)
