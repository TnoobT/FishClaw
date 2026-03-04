import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.tools.prompt_tools import PromptTools


if __name__ == "__main__":
    prompt_tools = PromptTools()
    res = prompt_tools.generate_product_description("YOLO")
    print(res)
