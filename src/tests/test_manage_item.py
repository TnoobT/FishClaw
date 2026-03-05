"""
测试商品管理工具（下架/删除）
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_manage_item():
    """测试商品管理功能（下架或删除）"""
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False
    )

    # 先获取在售商品列表
    print("正在获取在售商品列表...")
    items_result = tools.get_selling_items()
    print(f"\n{items_result}")

    # 手动输入要管理的商品URL
    item_url = input("\n请输入要管理的商品URL（从上面列表中复制）: ").strip()

    if not item_url:
        print("未输入商品URL，测试结束")
        tools._close_browser()
        return

    # 选择操作类型
    print("\n请选择操作类型：")
    print("1. delist - 下架（商品转为草稿状态，可重新上架）")
    print("2. delete - 删除（永久删除商品数据，不可恢复）")
    action_choice = input("请输入选项 (1/2): ").strip()

    action = "delist" if action_choice == "1" else "delete"
    action_text = "下架" if action == "delist" else "删除"

    # 二次确认
    confirm = input(f"\n确认要{action_text}该商品吗？(y/n): ")

    if confirm.lower() == 'y':
        result = tools.manage_item(item_url=item_url, action=action)
        print(f"\n管理结果：\n{result}")
    else:
        print("已取消操作")

    # 清理
    input("按回车键关闭浏览器...")
    tools._close_browser()


if __name__ == "__main__":
    test_manage_item()
