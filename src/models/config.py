from __future__ import annotations

import os

from dotenv import load_dotenv
from agno.models.dashscope import DashScope

# 加载项目根目录下的 .env 文件
load_dotenv()

# ──────────────────────────────────────────────────────────────
# 智能体用 LLM 配置（从 .env 读取 AGENT_LLM_* 前缀变量）
# ──────────────────────────────────────────────────────────────
MODEL = DashScope(
    id=os.environ.get("AGENT_LLM_MODEL", "qwen-max"),
    api_key=os.environ.get("AGENT_LLM_API_KEY"),
    base_url=os.environ.get("AGENT_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    temperature=float(os.environ.get("AGENT_LLM_TEMPERATURE", "0.5")),
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))