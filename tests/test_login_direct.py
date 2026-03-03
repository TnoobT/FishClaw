"""
直接调用 FishClawTools 函数的测试脚本（不使用 Agent）
    python tests/test_login_direct.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.xianyu_tools import FishClawTools

# ──────────────────────────────────────────────────────────
# 配置（改这里）
# ──────────────────────────────────────────────────────────
COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..",".cache", "cookies", "xianyu_cookies.json")

# ──────────────────────────────────────────────────────────
# 初始化工具类
# ──────────────────────────────────────────────────────────
tools = FishClawTools(
    cookies_path=COOKIES_PATH,
    headless=False,  # 有头模式，方便查看和手动处理滑块
)


def main():
    print("=" * 55)
    print("  闲鱼登录直连测试")
    print("=" * 55)

    # ── Step 1：检查登录状态 ──────────────────────────────
    print("\n[Step 1] 检查登录状态...")
    status = tools.check_login_status()
    print(f"  结果：{status}")

    if "已登录" in status or "可能已登录" in status:
        print("\n✅ Cookie 有效，无需重新登录，流程结束。")
        return

    # ── Step 2：扫码登录 ──────────────────────────────────
    print("\n[Step 2] 打开闲鱼首页，等待用户手动扫码登录...")
    login_result = tools.login_with_qrcode()
    print(f"  结果：{login_result}")

    if "出错" in login_result or "失败" in login_result or "错误" in login_result:
        print("\n❌ 扫码登录失败，请检查上方错误信息。")
        return



if __name__ == "__main__":
    main()
