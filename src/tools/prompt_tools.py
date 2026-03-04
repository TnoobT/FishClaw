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
            "你是一名在闲鱼上长期接单的程序员，现在要写一段自己服务的商品描述。\n\n"
            "根据给定的技术主题，写一段第一人称的描述正文，严格遵守以下规则：\n\n"
            "必须做到：\n"
            "- 开篇直接列出自己掌握的具体工具和技术（按主题自动扩展，例如 AIGC 要覆盖 SD、Flux、ComfyUI、LoRA、ControlNet 等）\n"
            "- 列举 2~3 个接单时真实遇到的买家问题，例如：环境装不上、模型跑不动、出图效果不稳定、脚本报错等——必须是具体的技术问题，不是泛化的业务场景\n"
            "- 说清楚我怎么解决这些问题（具体操作层面，不要只说能解决）\n"
            "- 语气平实，像在和人说话\n"
            "- 字数 300~450 字\n"
            "- 只输出正文，不加标题、不加分段标签\n\n"
            "- 罗列出所有相关的核心技术要点\n"
            "严格禁止：\n"
            "- 禁止编造设计师、艺术家、企业主等虚构用户场景\n"
            "- 禁止使用节省时间、提升效率、激发创意、赋能、解决方案等空洞词汇\n"
            "- 禁止介绍这个技术领域是什么或有什么意义\n"
            "- 禁止堆砌形容词和感叹词"
        )
        log_info(f"[PromptTools] 生成商品描述，主题：{topic}")
        result = self._call_llm(system, f"技术主题：{topic}")
        log_info(f"[PromptTools] 商品描述（前100字）：{result[:100]}")
        return result
