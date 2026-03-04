'''
Author: tfj
Date: 2026-03-04
LastEditors: tfj
Description: 提示词生成工具（生图提示词 & 商品描述文案）
Version: Alpha
'''
import os

import dotenv

dotenv.load_dotenv()

from openai import OpenAI

from agno.tools import Toolkit
from agno.utils.log import log_info, log_warning


class PromptTools(Toolkit):
    """提示词生成工具。

    提供两个工具：
    - generate_image_prompt：为图像生成工具生成科技感英文提示词
    - generate_product_description：为闲鱼商品生成口语化技术描述文案（约500字）
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        self.api_key = api_key or os.environ.get("AGENT_LLM_API_KEY", "")
        self.model = model or os.environ.get("AGENT_LLM_MODEL", "qwen-max")
        self.base_url = base_url or os.environ.get(
            "AGENT_LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        if not self.api_key:
            log_warning("[PromptTools] 未提供 AGENT_LLM_API_KEY，工具调用将失败")

        super().__init__(
            name="prompt_tools",
            tools=[self.generate_image_prompt, self.generate_product_description],
            **kwargs,
        )

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content or ""

    def generate_image_prompt(self, topic: str) -> str:
        """根据技术主题生成适合图像生成模型的英文提示词。

        生成的提示词具有科技感视觉风格，包含与主题相关的简短专业英文术语，
        图片中不含中文。

        Args:
            topic: 技术主题，例如 "AIGC"、"区块链"、"机器学习" 等。

        Returns:
            str: 适合直接传入图像生成工具的英文提示词。
        """
        system = (
            "You are a professional image prompt engineer specializing in tech-aesthetic visuals.\n"
            "Generate a concise image generation prompt based on the given technology topic.\n\n"
            "Hard rules:\n"
            "- NO Chinese characters anywhere in the output\n"
            "- Visual style: dark background, neon / holographic / cyberpunk, circuit patterns, glowing code\n"
            "- Naturally embed 3-5 short professional English tech terms as visible text elements in the scene "
            "(e.g., labels, HUDs, floating tags) — keep each term under 3 words\n"
            "- Total prompt length: 60-120 words\n"
            "- Output ONLY the prompt, no explanation, no prefix"
        )
        log_info(f"[PromptTools] 生成生图提示词，主题：{topic}")
        result = self._call_llm(system, f"Technology topic: {topic}")
        log_info(f"[PromptTools] 生图提示词：{result}")
        return result

    def generate_product_description(self, topic: str) -> str:
        """根据技术主题生成闲鱼商品描述文案。

        文案口语化、人性化，约500字，突出技术价值和实际应用场景，
        适合在闲鱼平台出售技术服务或知识付费商品。

        Args:
            topic: 技术主题或服务内容，例如 "AIGC绘画" 、"Python爬虫" 等。

        Returns:
            str: 约500字的商品描述文案。
        """
        system = (
            "你是一名在闲鱼上接单的技术开发者，正在写自己的服务商品描述。\n\n"
            "根据给定的技术主题，生成一段以第一人称（卖家视角）写的商品描述正文，要求：\n"
            "- 字数：450～550字\n"
            "- 核心逻辑：写清楚「我会什么」→「能帮你解决什么问题」，而不是介绍这个技术领域是什么\n"
            "- 技术广度：根据主题，自动扩展到该领域常见的细分技术栈和工具（例如 AIGC 要提到 Stable Diffusion、Flux、ComfyUI、LoRA 训练等具体工具）\n"
            "- 场景具体：列举 2～3 个买家真实遇到的痛点场景，说明我如何用技术帮他解决\n"
            "- 语气：口语化、真诚，像朋友聊天，不堆砌名词，不用'赋能''解决方案'等套话\n"
            "- 可信度细节：可提一句自己踩过的坑或经手过的典型需求，增加真实感\n"
            "- 结尾：自然引导买家留言咨询，不要硬广感\n"
            "- 只输出描述正文，不要标题，不要分段标签"
        )
        log_info(f"[PromptTools] 生成商品描述，主题：{topic}")
        result = self._call_llm(system, f"技术主题：{topic}")
        log_info(f"[PromptTools] 商品描述（前100字）：{result[:100]}")
        return result
