"""
测试模拟养号工具
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.tools.xianyu_tools import FishClawTools

cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "cookies", "xianyu_cookies.json")
def test_simulate_farming():
    """测试模拟养号功能"""
    # 注意：需要启用 enable_farming=True
    tools = FishClawTools(
        cookies_path=cookies_path,
        headless=False,
        enable_farming=True
    )

    # 设置养号时长（分钟）
    duration = 1  # 测试时使用较短时间，实际使用可设置为 5-10 分钟

    print(f"开始模拟养号，预计持续 {duration} 分钟...")
    result = tools.simulate_farming(duration_minutes=duration)
    print(f"\n养号结果：\n{result}")

    # 清理
    input("按回车键关闭浏览器...")
    tools._close_browser()


if __name__ == "__main__":
    test_simulate_farming()
