"""
闲鱼（咸鱼）工具类 v2 — 重构版
基于 Playwright 实现，核心设计原则：
  - 只暴露"意图"给模型，所有底层步骤私有化
  - 最小工具集（7个），消除冗余和微操工具
  - 所有业务工具内置登录检查拦截器
  - 删除失效工具（SMS登录、评论）
"""

import json
import os
import random
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

from agno.tools import Toolkit, tool
from agno.utils.log import log_info, log_warning

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError:
    raise ImportError("`playwright` not installed. Please install using `pip install playwright && playwright install chromium`")

try:
    from playwright_stealth import stealth_sync  # type: ignore
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    log_warning("`playwright-stealth` not installed. Stealth mode disabled.")

# ── 常量 ──────────────────────────────────────────────────
XIANYU_HOME_URL = os.environ.get("XIANYU_HOME_URL", "https://www.goofish.com")
_PLAYWRIGHT_HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "false").strip().lower() == "true"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _random_delay(min_s: float = 0.5, max_s: float = 2.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


class FishClawTools(Toolkit):
    """
    闲鱼自动化工具类 v2。

    暴露给 Agent 的工具（7个）：
      login                  — 检查登录状态，未登录则拉起二维码等待扫码
      search_market          — 搜索市场商品，用于竞品调研和定价参考
      draft_item             — 填写商品草稿并截图，供用户确认
      publish_item           — 确认并发布商品（需用户二次确认）
      get_selling_items      — 获取当前在售商品列表
      manage_item            — 对指定商品执行下架或删除
      simulate_farming       — 模拟真人浏览养号

    Args:
        cookies_path (str): Cookies 本地保存路径，默认 './xianyu_cookies.json'
        headless (bool): 是否无头模式，默认 False
        proxy (Optional[str]): 代理地址，如 'http://127.0.0.1:7890'
    """

    def __init__(
        self,
        cookies_path: str = "./xianyu_cookies.json",
        headless: bool = _PLAYWRIGHT_HEADLESS,
        proxy: Optional[str] = None,
        enable_farming: bool = False,
        **kwargs,
    ):
        self.cookies_path = Path(cookies_path)
        self.headless = headless
        self.proxy = proxy

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        tools: List[Any] = [
            self.login,
            self.search_market,
            self.draft_item,
            self.publish_item,
            self.get_selling_items,
            self.manage_item,
            self.get_page_content,
        ]
        if enable_farming:
            tools.append(self.simulate_farming)

        super().__init__(
            name="xianyu_tools",
            tools=tools,
            external_execution_required_tools=["get_selling_items", "search_market"],
            **kwargs,
        )

    # ══════════════════════════════════════════════════════
    # 私有：浏览器生命周期
    # ══════════════════════════════════════════════════════

    def _ensure_browser(self) -> None:
        if self._browser is not None and self._browser.is_connected():
            return

        log_info("FishClaw: 启动浏览器...")
        self._playwright = sync_playwright().start()

        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-extensions",
                "--window-position=200,50",
                "--window-size=1100,860",
            ],
        }
        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}

        self._browser = self._playwright.chromium.launch(**launch_args)

        context_args = {
            "viewport": {"width": 1100, "height": 860},
            "user_agent": DEFAULT_UA,
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "java_script_enabled": True,
        }
        if self.proxy:
            context_args["proxy"] = {"server": self.proxy}

        self._context = self._browser.new_context(**context_args)
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        self._page = self._context.new_page()
        if HAS_STEALTH:
            stealth_sync(self._page)
            log_info("FishClaw: Stealth 模式已启用")

    def _get_page(self) -> Page:
        self._ensure_browser()
        return self._page  # type: ignore

    def _save_cookies(self) -> None:
        if self._context is None:
            return
        cookies = self._context.cookies()
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        log_info(f"FishClaw: Cookies 已保存到 {self.cookies_path}")

    def _load_cookies(self) -> bool:
        if not self.cookies_path.exists():
            return False
        try:
            cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
            if self._context is None:
                self._ensure_browser()
            self._context.add_cookies(cookies)  # type: ignore
            log_info(f"FishClaw: 已从 {self.cookies_path} 加载 Cookies")
            return True
        except Exception as e:
            log_warning(f"FishClaw: 加载 Cookies 失败 - {e}")
            return False

    def _close_browser(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    # ══════════════════════════════════════════════════════
    # 私有：登录状态检测（拦截器）
    # ══════════════════════════════════════════════════════

    _NOT_LOGGED_IN_SELECTORS = [
        'button:has-text("登录")',
        'a:has-text("登录")',
        'span:has-text("登录")',
        '[class*="login-btn"]',
        '[class*="loginBtn"]',
        '[class*="sign-in"]',
        '[data-testid*="login"]',
        '[class*="login-modal"]',
        '[class*="loginModal"]',
        '[class*="login-dialog"]',
    ]

    def _is_logged_in(self, page: Optional[Page] = None) -> bool:
        """检测当前页面是否处于已登录状态（反向逻辑：找不到未登录特征 → 已登录）"""
        p = page or self._page
        if p is None:
            return False
        if "login.taobao.com" in p.url or "login.xianyu" in p.url:
            return False
        for sel in self._NOT_LOGGED_IN_SELECTORS:
            try:
                if p.locator(sel).first.is_visible(timeout=500):
                    return False
            except Exception:
                pass
        return True

    def _ensure_logged_in(self) -> Optional[str]:
        """
        登录状态拦截器。所有业务工具调用前执行。
        已登录返回 None；未登录则触发二维码登录流程，返回结果字符串。
        """
        page = self._get_page()
        self._load_cookies()
        page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
        _random_delay(1.0, 2.0)

        if self._is_logged_in(page):
            return None  # 已登录，放行

        # 未登录：拉起扫码流程
        log_info("FishClaw: 未登录，自动触发二维码登录流程...")
        return self._do_qrcode_login(page, timeout_seconds=180)

    def _do_qrcode_login(self, page: Page, timeout_seconds: int = 180) -> str:
        """内部二维码登录流程，阻塞直到扫码成功或超时"""
        print(
            f"\n{'='*60}\n"
            f"请在弹出的浏览器窗口中手动扫码登录闲鱼。\n"
            f"登录成功后将自动继续，等待最多 {timeout_seconds} 秒...\n"
            f"{'='*60}\n"
        )
        for elapsed in range(timeout_seconds):
            time.sleep(1.0)
            try:
                if self._is_logged_in(page):
                    self._save_cookies()
                    title = page.title()
                    log_info(f"FishClaw: 扫码登录成功，用时 {elapsed + 1} 秒")
                    return f"登录成功！当前页面：{title}。Cookies 已保存到 {self.cookies_path}。"
            except Exception:
                pass
        return f"等待扫码超时（{timeout_seconds} 秒），请重新调用 login 再次尝试。"

    # ══════════════════════════════════════════════════════
    # 私有：截图
    # ══════════════════════════════════════════════════════

    def _take_screenshot(self, page: Optional[Page] = None, label: str = "screenshot") -> str:
        """保存截图到 .cache/screenshot 目录，返回绝对路径或错误信息"""
        p = page or self._page
        if p is None:
            return "无可用页面，无法截图。"
        try:
            screenshot_dir = Path(".cache") / "screenshot"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = screenshot_dir / f"{label}_{ts}.png"
            p.screenshot(path=str(path), full_page=True)
            log_info(f"FishClaw: 截图已保存到 {path}")
            return str(path.resolve())
        except Exception as e:
            return f"截图失败：{e}"

    # ══════════════════════════════════════════════════════
    # 私有：跨 frame 元素查找
    # ══════════════════════════════════════════════════════

    def _find_element(self, page: Page, selector: str, timeout: int = 3000):
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=timeout):
                return el
        except Exception:
            pass
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                el = frame.locator(selector).first
                if el.is_visible(timeout=1000):
                    return el
            except Exception:
                continue
        return None

    # ══════════════════════════════════════════════════════
    # 私有：商品发布子步骤
    # ══════════════════════════════════════════════════════

    def _prepare_image(self, image: str) -> Tuple[bool, str, Optional[str]]:
        image = image.strip()
        if image.startswith("http://") or image.startswith("https://"):
            try:
                suffix = Path(image.split("?")[0]).suffix or ".jpg"
                fd, tmp_file = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                urllib.request.urlretrieve(image, tmp_file)
                return True, str(Path(tmp_file).resolve()), tmp_file
            except Exception as e:
                return False, f"下载图片失败：{e}", None
        else:
            local_path = str(Path(image).resolve())
            if not Path(local_path).exists():
                return False, f"图片文件不存在：{local_path}", None
            return True, local_path, None

    def _navigate_to_publish(self, page: Page) -> Tuple[bool, str, Optional[Any]]:
        for sel in ['div.sidebar-item-text-container--KNEB4FFf', ':text("发闲置")']:
            try:
                el = page.locator(sel).first
                if not el.is_visible(timeout=3000):
                    continue
                _random_delay(0.5, 1.0)
                with self._context.expect_page(timeout=8000) as new_page_info:
                    el.click()
                publish_page = new_page_info.value
                publish_page.wait_for_load_state("networkidle", timeout=15000)
                return True, f"已进入发布页面：{publish_page.url[:80]}", publish_page
            except Exception as e:
                log_warning(f"FishClaw: 点击「发闲置」失败（{sel}）: {e}")
        return False, "未能找到「发闲置」按钮，请确认已登录，或页面结构已更新。", None

    def _upload_image(self, page: Any, local_image_path: str) -> Tuple[bool, str]:
        all_frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
        for frame in all_frames:
            for css in ['input[name="file"][type="file"]', 'input[type="file"][accept*="image"]', 'input[type="file"]']:
                try:
                    el = frame.query_selector(css)
                    if el is None:
                        continue
                    el.set_input_files(local_image_path)
                    _random_delay(2.0, 4.0)
                    return True, f"图片已上传"
                except Exception:
                    continue
        for sel in [':text("添加首图")', ':text("添加图片")', 'div[class*="addPic"]']:
            trigger = self._find_element(page, sel, timeout=2000)
            if trigger is None:
                continue
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    trigger.click()
                fc_info.value.set_files(local_image_path)
                _random_delay(2.0, 4.0)
                return True, "图片已上传（file_chooser）"
            except Exception:
                continue
        return False, "未能上传图片，请手动上传。"

    def _fill_text_field(self, page: Any, text: str, mode: str = "replace") -> Tuple[bool, str]:
        """填写或追加描述文字"""
        desc_selectors = [
            'div[contenteditable="true"][class*="editor"]',
            'div[contenteditable="true"][data-placeholder*="描述"]',
            'div[contenteditable="true"][class*="desc"]',
            'textarea[placeholder*="描述"]',
            'textarea',
        ]
        for sel in desc_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    _random_delay(0.3, 0.6)
                    if mode == "replace":
                        page.keyboard.press("Control+A")
                    else:
                        page.keyboard.press("Control+End")
                        page.keyboard.press("Enter")
                    _random_delay(0.2, 0.4)
                    for char in text:
                        page.keyboard.type(char)
                        time.sleep(random.uniform(0.03, 0.12))
                    _random_delay(0.5, 1.0)
                    return True, f"描述已{'填写' if mode == 'replace' else '追加'}"
            except Exception:
                continue
        return False, "未能找到描述输入框。"

    def _select_category(self, page: Any, category: str = "其他技能服务") -> Tuple[bool, str]:
        trigger_selectors = [
            'div[class*="categorySelect"]', 'div[class*="category-select"]',
            '.ant-select', 'div:has-text("选择分类")',
        ]
        def _click_option(cat: str) -> bool:
            for loc_str in [f'li:text-is("{cat}")', f'div[class*="option"]:text-is("{cat}")', f'span:text-is("{cat}")']:
                try:
                    el = page.locator(loc_str).first
                    el.scroll_into_view_if_needed(timeout=1500)
                    if el.is_visible(timeout=800):
                        el.click()
                        _random_delay(0.4, 0.8)
                        return True
                except Exception:
                    pass
            return False

        if _click_option(category):
            return True, f"已选择分类「{category}」"

        for sel in trigger_selectors:
            try:
                trigger = page.locator(sel).first
                if trigger.is_visible(timeout=1000):
                    trigger.click()
                    _random_delay(0.6, 1.2)
                    break
            except Exception:
                continue

        if _click_option(category):
            return True, f"已选择分类「{category}」"

        return False, "未能选择分类，请检查分类名称。"

    def _fill_price(self, page: Any, price: float) -> Tuple[bool, str]:
        price_str = f"{price:.2f}"
        for sel in ['input[placeholder="0.00"]', 'input[placeholder*="价格"]', 'input[type="number"]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    _random_delay(0.2, 0.5)
                    el.click(click_count=3)
                    for char in price_str:
                        page.keyboard.type(char)
                        time.sleep(random.uniform(0.05, 0.15))
                    _random_delay(0.5, 1.2)
                    return True, f"价格已填写：¥{price_str}"
            except Exception:
                continue
        return False, "未能找到价格输入框。"

    def _click_publish_button(self, page: Any) -> Tuple[bool, str]:
        for sel in ['button:has-text("发布")', 'a:has-text("立即发布")', '[type="submit"]:has-text("发布")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    _random_delay(0.5, 1.0)
                    el.click()
                    log_info(f"FishClaw: 已点击发布按钮（{sel}）")
                    break
            except Exception:
                continue
        else:
            return False, "未能找到「发布」按钮，请在浏览器中手动点击。"

        _random_delay(2.0, 3.5)
        for sel in [':text("发布成功")', ':text("成功发布")',
                    'div[class*="sellerButton"]:has-text("下架")']:
            try:
                if page.locator(sel).first.is_visible(timeout=4000):
                    return True, "商品发布成功！"
            except Exception:
                continue

        return True, f"发布操作已完成，当前页面：{page.title()}（{page.url[:80]}）"

    # ══════════════════════════════════════════════════════
    # 私有：个人中心跳转
    # ══════════════════════════════════════════════════════

    def _ensure_profile_page(self) -> Tuple[bool, str]:
        """确保当前页面在个人中心，自动跳转。"""
        page = self._get_page()
        try:
            page.goto("https://www.goofish.com/personal", wait_until="domcontentloaded", timeout=15000)
            _random_delay(1.5, 2.5)
            current = page.url
            if "login" not in current and "error" not in current:
                self._page = page
                return True, f"已打开个人中心：{current}"
        except Exception as e:
            return False, f"跳转个人中心失败：{e}"
        return False, "未能跳转到个人中心，请确认已登录。"

    # ══════════════════════════════════════════════════════
    # 工具 1：登录
    # ══════════════════════════════════════════════════════

    def login(self, timeout_seconds: int = 180) -> str:
        """
        检查闲鱼登录状态。已登录则直接返回状态；未登录则打开浏览器展示二维码，
        等待用户手动扫码，登录成功后自动保存 Cookies。

        Args:
            timeout_seconds (int): 等待扫码的最大秒数，默认 180 秒。

        Returns:
            str: 登录状态描述。
        """
        try:
            page = self._get_page()
            self._load_cookies()
            page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 2.5)

            if self._is_logged_in(page):
                self._save_cookies()
                title = page.title()
                return f"已登录（Cookie 有效）：{title}。Cookies 已刷新保存到 {self.cookies_path}。"

            return self._do_qrcode_login(page, timeout_seconds=timeout_seconds)

        except Exception as e:
            return f"登录时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 2：搜索市场
    # ══════════════════════════════════════════════════════

    def search_market(self, keyword: str, max_results: int = 20) -> str:
        """
        在闲鱼搜索指定关键词，采集结果列表（标题、价格、链接），用于竞品调研和定价参考。

        Args:
            keyword (str): 搜索关键词。
            max_results (int): 最多返回结果数量，默认 20。

        Returns:
            str: 搜索结果列表。
        """
        if not keyword.strip():
            return "keyword 不能为空。"

        auth_result = self._ensure_logged_in()
        if auth_result is not None:
            return auth_result

        try:
            page = self._get_page()
            log_info(f"FishClaw [search_market]: 搜索关键词「{keyword}」")

            # 找搜索框
            typed = False
            for sel in ['input[placeholder*="搜索"]', 'input[type="search"]', 'input[class*="search"]']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        _random_delay(0.3, 0.6)
                        el.fill(keyword)
                        _random_delay(0.3, 0.6)
                        page.keyboard.press("Enter")
                        typed = True
                        break
                except Exception:
                    continue

            if not typed:
                search_url = f"{XIANYU_HOME_URL}/search?q={urllib.parse.quote(keyword)}"
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            _random_delay(2.0, 3.0)
            try:
                page.wait_for_selector('a:has(img[class*="feeds-image"])', timeout=8000)
            except Exception:
                pass

            results = page.evaluate(f"""() => {{
                const items = [];
                const links = document.querySelectorAll('a:has(img[class*="feeds-image"])');
                for (const a of links) {{
                    if (items.length >= {max_results}) break;
                    const href = a.getAttribute('href') || a.href || '';
                    if (!href) continue;
                    const allText = Array.from(a.querySelectorAll('*'))
                        .flatMap(el => Array.from(el.childNodes)
                            .filter(n => n.nodeType === 3)
                            .map(n => n.textContent.trim()))
                        .filter(t => t && !t.startsWith('¥') && !/^[\\d.,]+$/.test(t));
                    const title = (allText[0] || a.getAttribute('title') || '').slice(0, 80);
                    const priceEl = a.querySelector('[class*="price"]') ||
                                    Array.from(a.querySelectorAll('*')).find(el => el.textContent.trim().startsWith('¥'));
                    const price = priceEl ? priceEl.textContent.trim().slice(0, 20) : '';
                    if (title && href) items.push({{ title, price, href }});
                }}
                return items;
            }}""")

            if not results:
                return f"未找到关键词「{keyword}」的搜索结果，当前页面：{page.url}"

            lines = [f"关键词「{keyword}」共找到 {len(results)} 条结果："]
            for i, item in enumerate(results, 1):
                price_str = f"  价格：{item['price']}" if item['price'] else ""
                href_str = f"\n   链接：{item['href'][:80]}" if item['href'] else ""
                lines.append(f"【第{i}个：{item['title']}{price_str}{href_str}】")

            return "\n".join(lines)

        except Exception as e:
            return f"搜索市场商品时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 3：填写商品草稿
    # ══════════════════════════════════════════════════════

    def draft_item(
        self,
        image: str,
        description: str,
        price: float = 100.0,
    ) -> str:
        """
        在闲鱼发布页面填写商品草稿（图片、描述、分类、价格），完成后截图供用户确认。
        填写成功后请展示截图给用户，确认无误后调用 publish_item 完成发布。

        Args:
            image (str): 宝贝图片，支持本地路径或网络 URL。
            description (str): 宝贝描述文字。
            price (float): 商品售价（元），默认 100.0。

        Returns:
            str: 填写结果汇总，成功则提示调用 publish_item 发布。
        """
        auth_result = self._ensure_logged_in()
        if auth_result is not None:
            return auth_result

        _tmp_file: Optional[str] = None
        step_results: List[str] = []

        def _record(step: str, ok: bool, msg: str) -> None:
            icon = "✓" if ok else "✗"
            step_results.append(f"[{icon}] {step}: {msg}")
            log_info(f"FishClaw [draft_item] {'OK' if ok else 'FAIL'} {step}: {msg}")

        try:
            page = self._get_page()

            # Step 1: 处理图片
            ok, img_result, _tmp_file = self._prepare_image(image)
            _record("处理图片", ok, img_result)
            if not ok:
                return f"草稿填写失败：{img_result}"
            local_image_path = img_result

            # Step 2: 进入发布页
            ok, msg, publish_page = self._navigate_to_publish(page)
            _record("进入发布页", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}"
            page = publish_page
            self._page = publish_page

            # Step 3: 上传图片
            ok, msg = self._upload_image(page, local_image_path)
            _record("上传图片", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}\n\n" + "\n".join(step_results)

            # Step 4: 填写触发描述（让系统自动定位类目）
            TRIGGER_TEXT = "技术服务~技术服务~技术服务~"
            ok, msg = self._fill_text_field(page, TRIGGER_TEXT, mode="replace")
            _record("填写触发描述", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}\n\n" + "\n".join(step_results)

            # Step 5: 选择分类
            ok, msg = self._select_category(page, "其他技能服务")
            _record("选择分类", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}\n\n" + "\n".join(step_results)

            # Step 6: 追加实际描述
            ok, msg = self._fill_text_field(page, description, mode="append")
            _record("追加实际描述", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}\n\n" + "\n".join(step_results)

            # Step 7: 填写价格
            ok, msg = self._fill_price(page, price)
            _record("填写价格", ok, msg)
            if not ok:
                return f"草稿填写失败：{msg}\n\n" + "\n".join(step_results)

            # Step 8: 截图
            screenshot_path = self._take_screenshot(page, label="draft_item")
            _record("截图", True, screenshot_path)

            return (
                "草稿填写完成！请用户查看截图确认商品信息无误，\n"
                "，接下来调用 publish_item 完成发布。\n\n"
            )

        except Exception as e:
            return f"填写草稿时出错：{e}"
        finally:
            if _tmp_file and Path(_tmp_file).exists():
                try:
                    os.remove(_tmp_file)
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════
    # 工具 4：确认发布商品
    # ══════════════════════════════════════════════════════

    @tool(requires_confirmation=True)
    def publish_item(self) -> str:
        """
        在用户确认草稿无误后，点击发布按钮完成商品发布。

        Returns:
            str: 发布结果描述。
        """
        try:
            if self._page is None:
                return "没有已打开的发布页面，请先调用 draft_item 填写草稿。"

            page = self._page
            ok, msg = self._click_publish_button(page)
            if not ok:
                return f"发布失败：{msg}"
            return msg

        except Exception as e:
            return f"发布时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 5：获取在售商品列表
    # ══════════════════════════════════════════════════════

    def get_selling_items(self) -> str:
        """
        获取当前账号所有在售商品列表（标题、价格、链接）。
        内部自动跳转到个人中心页面，无需手动导航。

        Returns:
            str: 在售商品汇总文本。
        """
        auth_result = self._ensure_logged_in()
        if auth_result is not None:
            return auth_result

        try:
            ok, msg = self._ensure_profile_page()
            if not ok:
                return msg

            page = self._page

            # 点击「在售」Tab
            for sel in [':text("在售")', 'span:text-is("在售")', 'div[class*="tab"]:has-text("在售")']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        _random_delay(1.0, 2.0)
                        break
                except Exception:
                    continue

            # JS 滚动采集商品卡片
            COLLECT_JS = """
() => {
    const results = [];
    const links = document.querySelectorAll('a:has(img[class*="feeds-image"])');
    links.forEach(a => {
        const href = a.getAttribute('href') || '';
        if (!href) return;
        const allText = Array.from(a.querySelectorAll('*'))
            .flatMap(el => Array.from(el.childNodes)
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim()))
            .filter(t => t && !t.startsWith('¥') && !/^[\d.,]+$/.test(t));
        const title = (allText[0] || a.getAttribute('title') || '(无标题)').slice(0, 60);
        const priceEl = a.querySelector('[class*="price"]') ||
                        Array.from(a.querySelectorAll('*')).find(el => el.textContent.trim().startsWith('¥'));
        const price = priceEl ? priceEl.textContent.trim().slice(0, 20) : '';
        results.push({ href, title, price });
    });
    return results;
}
"""
            seen_hrefs: set = set()
            items: List[Dict[str, str]] = []
            no_new_count = 0

            for _ in range(30):
                try:
                    card_list = page.evaluate(COLLECT_JS)
                    for card in card_list:
                        href = card.get("href", "")
                        if not href or href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)
                        full_href = href if href.startswith("http") else f"https://www.goofish.com{href}"
                        items.append({
                            "title": card.get("title", "(无标题)") or "(无标题)",
                            "price": card.get("price", ""),
                            "href": full_href,
                        })
                except Exception as e:
                    log_warning(f"FishClaw [get_selling_items] JS 异常: {e}")

                prev_count = len(items)
                page.mouse.wheel(0, 900)
                _random_delay(1.2, 2.0)

                if len(items) == prev_count:
                    no_new_count += 1
                    if no_new_count >= 2:
                        break
                else:
                    no_new_count = 0

            if not items:
                return "未找到任何在售商品。请确认账号有在售商品，或当前页面不是个人中心。"

            lines = [f"共找到 {len(items)} 件在售商品："]
            for i, item in enumerate(items, 1):
                price_str = f"  价格：{item['price']}" if item['price'] else ""
                lines.append(f"{i}. 【{item['title']}】{price_str}\n   链接：{item['href']}")
            return "\n".join(lines)

        except Exception as e:
            return f"获取在售商品时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 6：管理指定商品（下架/删除）
    # ══════════════════════════════════════════════════════

    @tool(requires_confirmation=True)
    def manage_item(self, item_url: str, action: str) -> str:
        """
        对指定商品执行下架或删除操作。内部自动跳转到商品详情页并处理确认弹窗。
        请先调用 get_selling_items 获取商品链接，再调用此工具。

        Args:
            item_url (str): 商品详情页 URL（从 get_selling_items 返回结果中获取）。
            action (str): 操作类型，枚举值："delist"（下架）或 "delete"（删除）。
                         下架：商品转为草稿状态，可重新上架。
                         删除：永久删除商品数据，不可恢复。

        Returns:
            str: 操作结果描述。
        """
        if not item_url.strip():
            return "item_url 不能为空，请从 get_selling_items 获取商品链接。"
        if action not in ("delist", "delete"):
            return "action 参数错误，请传入 'delist'（下架）或 'delete'（删除）。"

        try:
            page = self._get_page()

            # 跳转到商品详情页
            log_info(f"FishClaw [manage_item]: 前往 {item_url[:80]}...")
            page.goto(item_url, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 2.5)

            action_text = "下架" if action == "delist" else "删除"

            # 点击操作按钮
            btn_selectors = [
                f'div[class*="sellerButton"]:text-is("{action_text}")',
                f'div[class*="sellerButton"]:has-text("{action_text}")',
                f'button:text-is("{action_text}")',
                f'span:text-is("{action_text}")',
                f'a:text-is("{action_text}")',
            ]
            clicked = False
            for sel in btn_selectors:
                try:
                    el = page.locator(sel).first
                    el.scroll_into_view_if_needed(timeout=2000)
                    if el.is_visible(timeout=3000):
                        _random_delay(0.5, 1.0)
                        el.click()
                        _random_delay(1.0, 2.0)
                        log_info(f"FishClaw [manage_item]: 已点击「{action_text}」按钮（{sel}）")
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                return (
                    f"未能在商品详情页找到「{action_text}」按钮。\n"
                    f"当前 URL：{page.url}\n"
                    f"请确认商品链接正确，或该商品已被{action_text}。"
                )

            # 处理确认弹窗
            for sel in [
                'div[class*="btnChildren"]:has-text("确定")',
                'div[class*="btnChildren"]:has-text("确认")',
                'button:has-text("确定")',
                'button:has-text("确认")',
            ]:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        _random_delay(0.3, 0.8)
                        el.click()
                        _random_delay(1.0, 2.0)
                        log_info(f"FishClaw [manage_item]: 已点击确认弹窗（{sel}）")
                        break
                except Exception:
                    continue

            # 确认操作结果
            _random_delay(2.0, 3.0)
            current_url = page.url
            current_title = page.title()

            if item_url.rstrip("/") not in current_url.rstrip("/"):
                return f"商品已成功{action_text}！当前页面：{current_title}（{current_url[:80]}）"

            success_kws = ["下架成功", "已下架", "宝贝被删掉了", "已删除", "操作成功"]
            for kw in success_kws:
                try:
                    if page.locator(f':text("{kw}")').first.is_visible(timeout=2000):
                        return f"商品已成功{action_text}！（检测到提示：{kw}）"
                except Exception:
                    continue

            return (
                f"已点击「{action_text}」按钮，但未检测到明确的成功提示。\n"
                f"当前页面：{current_title}（{current_url[:80]}）\n"
                f"请在浏览器中确认商品是否已{action_text}。"
            )

        except Exception as e:
            return f"{action_text}商品时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 7：读取当前页面内容
    # ══════════════════════════════════════════════════════

    def get_page_content(self) -> str:
        """
        读取当前浏览器页面的可见文字内容，供分析页面状态或提取信息。
        可配合其他工具使用：例如导航到某个页面后调用此工具读取内容。

        Returns:
            str: 当前页面的标题、URL 和主要文字内容（最多 3000 字符）。
        """
        try:
            import re
            page = self._get_page()
            title = page.title()
            url = page.url

            content = page.evaluate("""() => {
                function getVisibleText(el) {
                    if (!el) return '';
                    if (el.nodeType === Node.TEXT_NODE) return el.textContent.trim();
                    if (el.nodeType !== Node.ELEMENT_NODE) return '';
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return '';
                    return Array.from(el.childNodes).map(getVisibleText).join(' ');
                }
                return getVisibleText(document.body);
            }""")

            content = re.sub(r'\s+', ' ', content).strip()
            truncated = ""
            if len(content) > 3000:
                content = content[:3000]
                truncated = "\n...(内容过长，已截断至 3000 字符)"

            return f"【页面标题】{title}\n【当前 URL】{url}\n【页面内容】\n{content}{truncated}"

        except Exception as e:
            return f"读取页面内容时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具 8：模拟真人浏览养号（可选）
    # ══════════════════════════════════════════════════════

    def simulate_farming(self, duration_minutes: int = 5) -> str:
        """
        模拟真人在闲鱼首页随机浏览，包含随机滚动和点击进入帖子，用于账号养号。
        浏览期间不做任何交易操作，仅模拟正常用户行为。

        Args:
            duration_minutes (int): 模拟浏览持续时长（分钟），默认 5 分钟。

        Returns:
            str: 养号操作摘要，包含浏览次数和总用时。
        """
        auth_result = self._ensure_logged_in()
        if auth_result is not None:
            return auth_result

        try:
            page = self._get_page()
            end_time = time.time() + duration_minutes * 60
            scroll_count = 0
            post_count = 0

            log_info(f"FishClaw [simulate_farming]: 开始养号，预计 {duration_minutes} 分钟...")

            while time.time() < end_time:
                # 随机滚动 3~6 次
                rounds = random.randint(3, 6)
                for _ in range(rounds):
                    direction = "down" if random.random() < 0.7 else "up"
                    distance = random.randint(300, 800)
                    delta = distance if direction == "down" else -distance
                    page.mouse.wheel(0, delta)
                    _random_delay(0.8, 2.5)
                    scroll_count += 1

                # 随机点进一个帖子
                card_selectors = [
                    'a[href*="/item/"]', 'a[href*="/detail/"]',
                    'div[class*="card"] a', 'div[class*="feed"] a',
                ]
                candidates = []
                for sel in card_selectors:
                    try:
                        els = page.locator(sel).all()
                        for el in els:
                            try:
                                if el.is_visible(timeout=500):
                                    candidates.append(el)
                            except Exception:
                                continue
                        if candidates:
                            break
                    except Exception:
                        continue

                if candidates:
                    target = random.choice(candidates)
                    try:
                        target.scroll_into_view_if_needed(timeout=2000)
                        _random_delay(0.5, 1.2)
                        target.click()
                        _random_delay(3.0, 6.0)
                        post_count += 1
                        page.go_back(wait_until="domcontentloaded", timeout=10000)
                        _random_delay(1.0, 2.5)
                    except Exception:
                        pass

                if time.time() >= end_time:
                    break

                # 偶尔回到首页（每 3~5 个循环一次）
                if random.random() < 0.3:
                    page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=15000)
                    _random_delay(2.0, 3.5)

            return (
                f"养号完成！持续 {duration_minutes} 分钟，"
                f"共滚动 {scroll_count} 次，进入帖子 {post_count} 次。"
            )

        except Exception as e:
            return f"养号时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 析构
    # ══════════════════════════════════════════════════════

    def __del__(self):
        try:
            self._close_browser()
        except Exception:
            pass