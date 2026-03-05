'''
Author: tfj
Date: 2026-03-04
LastEditors: tfj
Description: 提示词生成工具（生图提示词 & 商品描述文案）
Version: Alpha
'''
import os
import re

import dotenv

dotenv.load_dotenv()

from openai import OpenAI

from agno.tools import Toolkit
from agno.utils.log import log_info, log_warning


class PromptTools(Toolkit):
    """提示词生成工具。

    提供两个工具：
    - generate_image_prompt：为图像生成工具生成科技感英文提示词
    - generate_product_description：为闲鱼商品生成结构化技术服务描述文案
    """

    _DEFAULT_IMAGE_SYSTEM = (
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

    _DEFAULT_DESCRIPTION_SYSTEM = (
        "你是一名在闲鱼长期接单的程序员，现在要写一段闲鱼服务商品描述。\n\n"
        "根据给定的技术主题，严格按照以下结构和格式输出，不要修改格式骨架\n\n"
        "注意：\n"
        "1. 语气要客观描述，不要迎合客户，不要迎合客户，不要迎合客户\n"
        "2. 禁止使用emoji表情\n"    
        
        "【第一段，1~2行】\n"
        "简短自我介绍，点明专注方向，末尾说「帮你快速脱坑」。\n"
        "格式参考：本人 (互联网一线从业者)，专注 XX 方向，帮你快速脱坑，把时间花在更重要的事情上。\n\n"
        "【第二段，用下面的分隔线括起来】\n"
        "-----------------------------------------------------\n"
        "我能帮你解决这些事儿 (主打一个专注):\n"
        "【分类名】：用口语写，说清楚能做什么、具体怎么操作，不要泛泛而谈。\n"
        "（根据主题选 3~5 个最合适的分类，常见分类：环境配置、代码调试、模型训练、模型使用、参数调优、部署上线、数据处理、效果优化等）\n"
        "-----------------------------------------------------\n\n"
        "【第三段，用下面的分隔线括起来】\n"
        "-----------------------------------------------------\n"
        "主攻技术 (为了让你能搜到我):\n"
        "按 2~4 个维度分组，尽量多列相关的技术/框架/工具/模型名，用逗号分隔。\n"
        "格式参考：AIGC 生成框架： Stable Diffusion, Flux, ComfyUI\n"
        "-----------------------------------------------------\n\n"
        "严格禁止：\n"
        "- 禁止编造虚构用户场景（设计师、艺术家、老板、企业主等）\n"
        "- 禁止使用效率、赋能、解决方案、激发创意、节省时间等空洞词汇\n"
        "- 禁止介绍这个技术是什么或有什么意义\n"
        "- 禁止加多余的标题行、前言、结束语\n"
        "- 只输出正文，不加任何说明"
    )

    _EMOJI_RE = re.compile(
        r'[^\x09\x0A\x0D\x20-\x7E'           # ASCII 可打印字符 + 常用空白
        r'\u2014\u2018\u2019\u201C\u201D'      # 破折号、弯引号
        r'\u300A-\u300F\u3010\u3011\uFF08\uFF09'  # 书名号、方括号、全角括号
        r'\u3000-\u303F'                        # CJK 符号与标点
        r'\u4E00-\u9FFF'                        # CJK 统一汉字
        r'\uFF00-\uFFEF]+'                      # 全角字母数字及半角片假名
    )

    @classmethod
    def _strip_emoji(cls, text: str) -> str:
        """移除 emoji 及不可见字符，保留中英文、数字和常用标点。"""
        return cls._EMOJI_RE.sub('', text)

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
        图片中不含中文。优先读取环境变量 PROMPT_IMAGE_SYSTEM，未设置则使用内置默认值。

        Args:
            topic: 技术主题，例如 "AIGC"、"区块链"、"机器学习" 等。

        Returns:
            str: 适合直接传入图像生成工具的英文提示词。
        """
        system = os.environ.get("PROMPT_IMAGE_SYSTEM", "").strip() or self._DEFAULT_IMAGE_SYSTEM
        log_info(f"[PromptTools] 生成生图提示词，主题：{topic}")
        result = self._call_llm(system, f"Technology topic: {topic}")
        result = self._strip_emoji(result)
        log_info(f"[PromptTools] 生图提示词：{result}")
        return result

    def generate_product_description(self, topic: str) -> str:
        """根据技术主题生成闲鱼商品描述文案。

        文案结构化分段，包含自我介绍、服务分类、技术关键词三部分，
        适合在闲鱼平台出售技术服务。优先读取环境变量 PROMPT_DESCRIPTION_SYSTEM，
        未设置则使用内置默认值。

        Args:
            topic: 技术主题或服务内容，例如 "AIGC绘画" 、"Python爬虫" 等。

        Returns:
            str: 结构化商品描述文案。
        """
        system = os.environ.get("PROMPT_DESCRIPTION_SYSTEM", "").strip() or self._DEFAULT_DESCRIPTION_SYSTEM
        log_info(f"[PromptTools] 生成商品描述，主题：{topic}")
        result = self._call_llm(system, f"技术主题：{topic}")
        result = self._strip_emoji(result)
        log_info(f"[PromptTools] 商品描述（前100字）：{result[:100]}")
        return result
