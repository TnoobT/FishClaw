"""
测试获取页面内容工具
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_get_page_content():
    """测试读取页面内容功能"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    # 先登录并导航到首页
    print("正在登录...")
    login_result = tools.login(timeout_seconds=180)
    print(f"\n{login_result}")

    # 读取当前页面内容
    print("\n正在读取页面内容...")
    result = tools.get_page_content()
    print(f"\n页面内容：\n{result}")

    # 清理
    input("按回车键关闭浏览器...")
    tools._close_browser()


if __name__ == "__main__":
    test_get_page_content()
