"""
测试获取在售商品列表工具
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_get_selling_items():
    """测试获取在售商品列表功能"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    result = tools.get_selling_items()
    print(f"\n在售商品列表：\n{result}")

    # 清理
    input("按回车键关闭浏览器...")
    tools._close_browser()


if __name__ == "__main__":
    test_get_selling_items()
