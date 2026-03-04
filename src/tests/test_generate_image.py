'''
Author: tfj
Date: 2026-03-03 22:10:55
LastEditors: tfj
LastEditTime: 2026-03-03 22:28:38
Description: 
Version: Alpha
'''
"""
直接调用 GenerateImageTools.generate_image 的测试脚本（不使用 Agent）
运行方式：在项目根目录下执行
    python tests/test_dashscope_image.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.tools.generate_image_tools import GenerateImageTools

# ──────────────────────────────────────────────────────────
# 配置（按需修改）
# ──────────────────────────────────────────────────────────

# 图像生成模型
MODEL = "z-image-turbo"

# 图像尺寸
SIZE = "1120*1440"

# 测试提示词
PROMPT = (
    "film grain, analog film texture, soft film lighting, Kodak Portra 400 style, "
    "cinematic grainy texture, photorealistic details, subtle noise, (film grain:1.2)。"
    "采用近景特写镜头拍摄的东亚年轻女性，呈现户外雪地场景。她体型纤瘦，呈站立姿势，"
    "身体微微向右侧倾斜，头部抬起看向画面上方，姿态自然放松。她的面部是典型东亚长相，"
    "肤色白皙，脸颊带有自然的红润感，五官清秀：眼睛是深棕色，眼型偏圆，眼神略带惊讶地望向上方，"
    "眼白部分可见；眉毛是深黑色，形状自然弯长；鼻子小巧挺直，嘴唇涂有红色口红，唇瓣微张，"
    "表情带着轻微的惊讶或好奇。她的头发是深黑色长直发，发丝被风吹得略显凌乱，"
    "部分垂在脸颊两侧，头顶佩戴一顶深灰色的头盔，头盔边缘露出少量发丝。"
    "服装是蓝白拼接的厚重外套，外套材质看起来是毛绒与布料结合，显得温暖厚实，适合雪地环境。"
    "背景是被白雪覆盖的户外场景，远处可见模糊的树木轮廓，天空是明亮的浅蓝色，带有少量白云，"
    "光线是强烈的自然日光，照亮人物面部与头发，形成清晰的光影，色调以蓝、白、黑为主，"
    "整体风格清新自然。"
)

# ──────────────────────────────────────────────────────────
# 初始化工具类（API Key 从 .env 中的 DASHSCOPE_API_KEY 自动读取）
# ──────────────────────────────────────────────────────────
tools = GenerateImageTools(
    model=MODEL,
    default_size=SIZE,
    prompt_extend=False,
)


def main():
    print("=" * 55)
    print("  阿里云 DashScope 图像生成 直连测试")
    print("=" * 55)

    # ── Step 1：检查 API Key ──────────────────────────────
    print("\n[Step 1] 检查 API Key...")
    if not tools.api_key:
        print("❌ 未配置 IMAGE_API_KEY，请在 .env 文件中添加：")
        print("   IMAGE_API_KEY=your-api-key")
        return
    print(f"  ✅ API Key 已加载（前8位：{tools.api_key[:8]}...）")

    # ── Step 2：发送生图请求 ──────────────────────────────
    print(f"\n[Step 2] 正在请求生图...")
    print(f"  模型  ：{tools.model}")
    print(f"  尺寸  ：{SIZE}")
    print(f"  提示词：{PROMPT[:60]}...")

    result = tools.generate_image(prompt=PROMPT, size=SIZE)

    print(f"\n  结果：{result}")

    # ── Step 3：判断结果 ──────────────────────────────────
    if result.startswith("error:"):
        print("\n❌ 生图失败，请查看上方错误信息。")
    else:
        print(f"\n✅ 生图成功！图像已缓存到本地：{result}")


if __name__ == "__main__":
    main()
