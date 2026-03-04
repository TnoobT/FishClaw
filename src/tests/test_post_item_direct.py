'''
Author: tfj
Date: 2026-03-03 21:49:34
LastEditors: tfj
LastEditTime: 2026-03-03 22:53:56
Description: 
Version: Alpha
'''
"""
直接调用 FishClawTools.post_item 的测试脚本（不使用 Agent）
运行方式：在项目根目录下执行
    python tests/test_post_item_direct.py
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

# 测试图片路径（相对于项目根目录的 tmp/test.png）
IMAGE_PATH = os.path.join(PROJECT_ROOT, ".cache", "cache_img", "test.png")

# 宝贝描述
DESCRIPTION = "aigc 虚拟服务，全新未拆封，支持7天无理由退换。"

# 分类（默认「其他技能服务」）
CATEGORY = "其他技能服务"

# 价格（元）
PRICE = 100.0

# ──────────────────────────────────────────────────────────
# 初始化工具类
# ──────────────────────────────────────────────────────────
tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    enable_login=True,
    enable_post_item=True,
    headless=False,  # 有头模式，方便观察操作过程
)


def main():
    print("=" * 55)
    print("  闲鱼「发布闲置商品」直连测试")
    print("=" * 55)

    # ── Step 1：检查登录状态 ──────────────────────────────
    print("\n[Step 1] 检查登录状态...")
    status = tools.check_login_status()
    print(f"  结果：{status}")

    if "未登录" in status or "出错" in status:
        # ── Step 1.1：未登录则先扫码登录 ────────────────
        print("\n[Step 1.1] 检测到未登录，打开浏览器等待扫码登录...")
        login_result = tools.login_with_qrcode(timeout_seconds=180)
        print(f"  结果：{login_result}")

        if "出错" in login_result or "失败" in login_result or "超时" in login_result:
            print("\n❌ 登录失败，请检查上方错误信息，流程终止。")
            return

    print("\n✅ 已登录，开始填写商品信息...")

    # ── Step 2：检查图片文件是否存在 ─────────────────────
    abs_image = os.path.abspath(IMAGE_PATH)
    print(f"\n[Step 2] 图片路径：{abs_image}")
    if not os.path.exists(abs_image):
        print(f"❌ 图片文件不存在：{abs_image}，请先将测试图片放到 tmp/test.png")
        return
    print("  ✅ 图片文件存在")

    # ── Step 3：填写商品信息 ──────────────────────────────────
    print(f"\n[Step 3] 正在填写商品信息...")
    print(f"  图片  ：{abs_image}")
    print(f"  描述  ：{DESCRIPTION}")
    print(f"  分类  ：{CATEGORY}")
    print(f"  价格  ：¥{PRICE:.2f}")

    fill_result = tools.fill_item_info(
        image=abs_image,
        description=DESCRIPTION,
        price=PRICE,
    )
    print(f"\n  填写结果：{fill_result}")

    if "成功" not in fill_result:
        print("\n❌ 填写商品信息失败，请查看上方错误信息。")
        return

    print("\n" + "=" * 55)
    print("  [Step 4] 请打开 .cache/screenshot 目录查看截图，")
    print("  确认商品信息填写无误后按 Enter 继续发布；")
    print("  若有问题请按 Ctrl+C 取消。")
    print("=" * 55)
    input("\n  >> 按 Enter 确认并发布...")

    # ── Step 4：截图确认后发布商品 ───────────────────────
    print(f"\n[Step 4] 正在发布商品...")
    post_result = tools.post_item()
    print(f"\n  发布结果：{post_result}")

    if "成功" in post_result:
        print("\n✅ 商品发布成功！")
    elif "出错" in post_result or "失败" in post_result:
        print("\n❌ 发布失败，请查看上方错误信息。")
    else:
        print("\n⚠️  发布操作已执行，请在浏览器中确认结果。")


if __name__ == "__main__":
    main()
