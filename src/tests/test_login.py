"""
测试登录工具
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_login():
    """测试闲鱼登录功能"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    result = tools.login(timeout_seconds=180)
    print(f"\n登录结果：\n{result}")

    # 清理
    tools._close_browser()


if __name__ == "__main__":
    test_login()
