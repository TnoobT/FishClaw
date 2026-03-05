"""
测试市场搜索工具
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools
cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")


def test_search_market():
    """测试闲鱼市场搜索功能"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    # 搜索关键词
    keyword = "Python编程"
    max_results = 10

    result = tools.search_market(keyword=keyword, max_results=max_results)
    print(f"\n搜索结果：\n{result}")

    # 清理
    tools._close_browser()


if __name__ == "__main__":
    test_search_market()
