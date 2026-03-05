"""
测试商品发布工具
注意：此测试需要先运行 test_draft_item.py 填写草稿
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools
cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")

def test_publish_item():
    """测试发布商品功能（需要先填写草稿）"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    # 先填写草稿
    image = "assets\default_agent.png"  # 替换为实际图片URL或本地路径
    description = "这是一个测试商品，用于测试发布功能。"
    price = 88.88

    draft_result = tools.draft_item(
        image=image,
        description=description,
        price=price
    )
    print(f"\n草稿填写结果：\n{draft_result}")

    # 等待用户确认
    confirm = input("\n草稿已填写完成，是否继续发布？(y/n): ")

    if confirm.lower() == 'y':
        # 发布商品
        publish_result = tools.publish_item()
        print(f"\n发布结果：\n{publish_result}")
    else:
        print("已取消发布")

    # 清理
    input("按回车键关闭浏览器...")
    tools._close_browser()


if __name__ == "__main__":
    test_publish_item()
