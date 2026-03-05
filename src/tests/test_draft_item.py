"""
测试商品草稿填写工具
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_draft_item():
    """测试填写商品草稿功能"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    # 商品信息
    image = "assets\default_agent.png"  # 替换为实际图片URL或本地路径
    description = "这是一个测试商品描述，包含详细的商品信息。"
    price = 99.99

    result = tools.draft_item(
        image=image,
        description=description,
        price=price
    )
    print(f"\n草稿填写结果：\n{result}")

    # 注意：不要自动关闭浏览器，以便查看截图和确认草稿
    print("\n请查看浏览器中的草稿内容，确认无误后可调用 publish_item 发布")
    input("按回车键关闭浏览器...")

    # 清理
    tools._close_browser()


if __name__ == "__main__":
    test_draft_item()
