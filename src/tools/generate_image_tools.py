'''
Author: tfj
Date: 2026-03-03 22:06:15
LastEditors: tfj
LastEditTime: 2026-03-03 23:27:59
Description: 
Version: Alpha
'''
import json
import os
import datetime
import dotenv

dotenv.load_dotenv()

from typing import Optional

import requests

from agno.tools import Toolkit
from agno.utils.log import log_info, log_warning


class GenerateImageTools(Toolkit):
    """图像生成工具。

    使用阿里云调用图像生成模型，
    根据给定的文本提示词生成图像，将图像缓存到本地后返回本地文件路径。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "z-image-turbo",
        default_size: str = "1024*1024",
        prompt_extend: bool = False,
        cache_path: Optional[str] = None,
        enable_generate_image: bool = True,
        all: bool = False,
        **kwargs,
    ):
        """初始化 GenerateImageTools。

        :param api_key: 阿里云 DashScope API Key。若未提供，则从环境变量
                        DASHSCOPE_API_KEY 读取。
        :param model: 使用的图像生成模型名称，默认为 "z-image-turbo"。
        :param default_size: 默认图像尺寸，格式为 "宽*高"，默认为 "1024*1024"。
        :param prompt_extend: 是否开启提示词扩展，默认为 False。
        :param cache_path: 图像缓存目录。若不提供，默认为项目根目录下的
                          .cache/cache_img。目录不存在时自动创建。
        :param enable_generate_image: 是否注册 generate_image 工具，默认为 True。
        :param all: 为 True 时注册所有工具，优先级高于各 enable_* 参数。
        """
        self.api_key: str = api_key or os.environ.get("IMAGE_API_KEY", "")
        self.model: str = model
        self.default_size: str = default_size
        self.prompt_extend: bool = prompt_extend

        # 确定缓存目录并创建
        if cache_path:
            self.cache_path: str = os.path.abspath(cache_path)
        else:
            # 默认：本文件 -> src/tools -> src -> 项目根 -> .cache/cache_img
            _project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            self.cache_path = os.path.join(_project_root, ".cache", "cache_img")

        os.makedirs(self.cache_path, exist_ok=True)

        self._api_url: str = (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
            "multimodal-generation/generation"
        )

        tools = []
        if all or enable_generate_image:
            tools.append(self.generate_image)

        super().__init__(name="dashscope_image_tools", tools=tools, **kwargs)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_image(self, image_url: str) -> str:
        """下载远程图像并保存到 cache_path，返回本地绝对路径。

        :param image_url: 远程图像 URL。
        :return: 本地文件绝对路径；下载失败时返回 "error: ..."。
        """
        try:
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            log_warning(f"[GenerateImageTools] 图像下载失败: {e}")
            return f"error: 图像下载失败 - {e}"

        # 从 Content-Type 推断扩展名，默认 .png
        content_type = resp.headers.get("Content-Type", "image/png")
        ext = ".jpg" if "jpeg" in content_type else ".png"

        filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ext
        local_path = os.path.join(self.cache_path, filename)

        with open(local_path, "wb") as f:
            f.write(resp.content)

        log_info(f"[GenerateImageTools] 图像已缓存到本地: {local_path}")
        return local_path

    def generate_image(
        self,
        prompt: str,
        size: Optional[str] = None,
        **kwargs,
    ) -> str:
        """根据文本提示词调用阿里云 DashScope 接口生成图像并缓存到本地。

        :param prompt: 图像生成的文本描述（支持中英文混合）。
        :param size: 图像尺寸，格式为 "宽*高"，例如 "1120*1440"。
                     若不提供则使用初始化时设定的 default_size。
        :return: 成功时返回缓存图像的本地绝对路径（字符串）；
                 失败时返回 "error: <错误信息>" 格式的字符串。
        """
        if not self.api_key:
            return "error: 未提供 DASHSCOPE_API_KEY，请通过构造参数或环境变量设置"

        image_size = size or self.default_size

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": {
                "prompt_extend": self.prompt_extend,
                "size": image_size,
            },
        }

        log_info(f"[GenerateImageTools] 请求生图，模型={self.model}，尺寸={image_size}")

        try:
            response = requests.post(
                self._api_url,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=120,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            log_warning("[GenerateImageTools] 请求超时")
            return "error: 请求超时，请稍后重试"
        except requests.exceptions.HTTPError as e:
            log_warning(f"[GenerateImageTools] HTTP 错误: {e}")
            return f"error: HTTP 错误 {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            log_warning(f"[GenerateImageTools] 网络请求错误: {e}")
            return f"error: 网络请求错误 - {e}"

        try:
            result = response.json()
        except ValueError:
            log_warning("[GenerateImageTools] 响应体无法解析为 JSON")
            return f"error: 响应解析失败 - {response.text}"

        # 提取图像 URL
        # 响应结构: output.choices[0].message.content[0].image_url
        # 或        output.results[0].url（不同模型可能结构有所不同）
        try:
            output = result.get("output", {})

            # 尝试 multimodal-generation 标准响应结构
            choices = output.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", [])
                for item in content:
                    if "image" in item:
                        image_url = item["image"]
                        if not image_url:  # API 返回 image 字段但值为空时跳过
                            continue
                        log_info(f"[GenerateImageTools] 生图成功，准备下载缓存: {image_url}")
                        return self._download_image(image_url)

            # 尝试备用结构 results[0].url
            results = output.get("results", [])
            if results:
                image_url = results[0].get("url") or ""
                if image_url:
                    log_info(f"[GenerateImageTools] 生图成功，准备下载缓存: {image_url}")
                    return self._download_image(image_url)

            # 未能提取到 URL，返回完整响应供调试
            log_warning(f"[GenerateImageTools] 未能从响应中提取图像 URL: {result}")
            return f"error: 未能提取图像 URL，完整响应: {json.dumps(result, ensure_ascii=False)}"

        except (KeyError, IndexError, TypeError) as e:
            log_warning(f"[GenerateImageTools] 解析响应结构时出错: {e}")
            return f"error: 解析响应失败 - {e}，完整响应: {json.dumps(result, ensure_ascii=False)}"
