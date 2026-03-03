"""
闲鱼（咸鱼）工具类
基于 Playwright 实现：短信验证码登录、发布商品、评论商品等功能。
风控规避策略：有头模式、Stealth 伪装、随机延迟、UA 伪装、清除 webdriver 特征。
"""

import json
import os
import random
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
load_dotenv()

from agno.tools import Toolkit, tool
from agno.utils.log import log_info, log_warning

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError:
    raise ImportError("`playwright` not installed. Please install using `pip install playwright && playwright install chromium`")

# 尝试导入 stealth 包（可选）
try:
    from playwright_stealth import stealth_sync  # type: ignore

    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    log_warning("`playwright-stealth` not installed. Stealth mode disabled. Install with: pip install playwright-stealth")


# ──────────────────────────────────────────────────────────
# 常量（从 .env 读取，保留默认值兜底）
# ──────────────────────────────────────────────────────────
XIANYU_HOME_URL = os.environ.get("XIANYU_HOME_URL", "https://www.goofish.com")

# Playwright 操作层 headless 配置：从 PLAYWRIGHT_HEADLESS 环境变量读取
# 建议保持 false（有头模式），更难被风控识别
_PLAYWRIGHT_HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "false").strip().lower() == "true"

# 真实 Chrome UA
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Viewport 范围（随机选取，模拟真实用户）
VIEWPORT_OPTIONS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]


def _random_delay(min_s: float = 0.5, max_s: float = 2.0) -> None:
    """随机等待，避免操作过快触发风控"""
    time.sleep(random.uniform(min_s, max_s))


def _human_type_el(el: Any, page: Page, text: str) -> None:
    """模拟人工逐字输入（接受 Locator 对象，兼容 iframe 内元素）"""
    el.click()
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.05, 0.2))


class FishClawTools(Toolkit):
    """
    闲鱼（咸鱼）自动化工具类。

    Args:
        cookies_path (str): Cookies 本地保存路径，默认 './xianyu_cookies.json'
        enable_login (bool): 是否注册登录相关工具，默认 True
        enable_post_item (bool): 是否注册发布商品工具（预留）
        enable_comment (bool): 是否注册评论工具（预留）
        headless (bool): 是否无头模式，默认 False（有头更不易被风控）
        proxy (Optional[str]): 代理地址，如 'http://127.0.0.1:7890'，默认 None
    """

    def __init__(
        self,
        cookies_path: str = "./xianyu_cookies.json",
        enable_login: bool = True,
        enable_post_item: bool = False,
        enable_comment: bool = False,
        headless: bool = _PLAYWRIGHT_HEADLESS,  # 从 .env PLAYWRIGHT_HEADLESS 读取
        proxy: Optional[str] = None,
        **kwargs,
    ):
        self.cookies_path = Path(cookies_path)
        self.headless = headless
        self.proxy = proxy

        # Playwright 运行时对象（懒初始化）
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        
        #TODO: send_sms_code 、login_with_sms 有问题，滑块问题待解决

        tools: List[Any] = []
        if enable_login:
            tools.extend([
                self.check_login_status,
                self.login_with_qrcode,
            ])
        if enable_post_item:
            tools.extend([
                self.fill_item_info,
                self.post_item,
            ])
        # 预留：后续实现
        # if enable_comment:
        #     tools.append(self.comment_item)

        super().__init__(name="xianyu_tools", tools=tools, **kwargs)

    # ══════════════════════════════════════════════════════
    # 内部：浏览器生命周期管理
    # ══════════════════════════════════════════════════════

    def _ensure_browser(self) -> None:
        """确保浏览器已启动，懒初始化"""
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
                "--window-position=200,50",   # 固定窗口位置，方便扫码
                "--window-size=1100,860",     # 固定窗口大小，显示完整登录弹框
            ],
        }
        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}

        self._browser = self._playwright.chromium.launch(**launch_args)

        # 固定 viewport 与窗口大小对齐，避免随机大小导致登录弹框被截断
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

        # 注入 stealth 脚本，清除 webdriver 特征
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        self._page = self._context.new_page()

        # 若安装了 playwright-stealth，额外加持
        if HAS_STEALTH:
            stealth_sync(self._page)
            log_info("FishClaw: Stealth 模式已启用")

    def _get_page(self) -> Page:
        self._ensure_browser()
        return self._page  # type: ignore

    def _save_cookies(self) -> None:
        """将当前 Context 的 Cookies 序列化保存到本地 JSON"""
        if self._context is None:
            return
        cookies = self._context.cookies()
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        log_info(f"FishClaw: Cookies 已保存到 {self.cookies_path}")

    def _load_cookies(self) -> bool:
        """从本地加载 Cookies，成功返回 True"""
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

    def _find_element(self, page: Page, selector: str, timeout: int = 3000):
        """
        在主页面及所有 iframe 中查找可见元素。
        返回找到的 Locator 对象；未找到返回 None。
        闲鱼/淘宝登录表单通常嵌套在 iframe 内，需要跨 frame 搜索。
        """
        # 先搜索主页面
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=timeout):
                return el
        except Exception:
            pass

        # 再搜索所有子 iframe
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                el = frame.locator(selector).first
                if el.is_visible(timeout=1000):
                    log_info(f"FishClaw: 在 iframe ({frame.url[:60]}) 中找到元素 {selector}")
                    return el
            except Exception:
                continue

        return None

    def _close_browser(self) -> None:
        """关闭浏览器，释放资源"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    # ══════════════════════════════════════════════════════
    # 工具方法 1：检查登录状态
    # ══════════════════════════════════════════════════════

    def check_login_status(self) -> str:
        """
        检查当前闲鱼账号是否已登录。

        使用 Playwright 访问闲鱼首页，通过 URL 跳转和页面元素判断登录状态。

        Returns:
            str: 登录状态描述。已登录返回页面信息，未登录返回提示。
        """
        try:
            page = self._get_page()

            # 先尝试加载 cookies
            self._load_cookies()

            log_info("FishClaw [Playwright]: 正在访问闲鱼首页验证登录状态...")
            page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 3.0)

            # ── 优先：URL 跳转到登录页 ──
            current_url = page.url
            if "login.taobao.com" in current_url or "login.xianyu.taobao.com" in current_url:
                return "未登录：页面跳转到登录页，请调用 send_sms_code 发送验证码后登录。"

            # ── 检测「未登录」特征元素 ──
            not_logged_in_selectors = [
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

            for sel in not_logged_in_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        log_info(f"FishClaw [Playwright]: 检测到未登录特征元素（{sel}）")
                        return "未登录：检测到登录按钮/弹窗，Cookie 无效或已过期，请重新登录。"
                except Exception:
                    continue

            # ── 未找到未登录特征 → 判定已登录 ──
            log_info("FishClaw [Playwright]: 未发现未登录特征元素，判定为已登录状态。")
            title = page.title()
            return f"已登录：页面正常加载（{title}），Cookie 可正常使用。"

        except Exception as e:
            return f"检查登录状态时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具方法 2：发送短信验证码
    # ══════════════════════════════════════════════════════

    def send_sms_code(self, phone: str) -> str:
        """
        向指定手机号发送闲鱼短信验证码。

        流程：打开闲鱼首页 → 点击登录入口 → 输入手机号 → 勾选同意协议 → 点击获取验证码。
        如遇到滑块验证码，会暂停并提示用户手动处理，处理完成后再继续。

        Args:
            phone (str): 需要登录的手机号码（纯数字，如 '13800138000'）

        Returns:
            str: 操作结果，成功则提示"验证码已发送，请调用 login_with_sms 提交验证码"
        """
        if not phone or not phone.strip().isdigit() or len(phone.strip()) != 11:
            return "手机号格式错误，请传入 11 位纯数字手机号。"

        phone = phone.strip()

        try:
            page = self._get_page()

            # ── Step 0：打开闲鱼首页 ──
            log_info(f"FishClaw: 打开闲鱼首页，手机号 {phone[:3]}****{phone[-4:]}...")
            page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 2.5)
            # ── Step 1：在主页面或 iframe 中填入手机号 ──
            # 阿里系登录表单常被嵌套在 iframe 内，_find_element 会自动跨 frame 搜索
            phone_input_selectors = [
                '#fm-sms-login-id',                          # 闲鱼/淘宝登录弹框精确 ID
                'input[name="fm-sms-login-id"]',             # 闲鱼/淘宝登录弹框精确 name
                'input[placeholder="请输入手机号"]',
                'input[placeholder*="手机号"]',
                'input[type="tel"]',
                'input[name="phone"]',
                'input[name="loginId"]',
                'input[name="TPL_username"]',
            ]
            phone_filled = False
            for sel in phone_input_selectors:
                el = self._find_element(page, sel, timeout=3000)
                if el is not None:
                    try:
                        el.click()                           # 单击聚焦
                        _random_delay(0.3, 0.8)
                        el.click(click_count=3)              # 三连击全选已有内容
                        _random_delay(0.2, 0.5)
                        _human_type_el(el, page, phone)      # 逐字输入，兼容 iframe 内元素
                        phone_filled = True
                        log_info(f"FishClaw: 已填入手机号（selector: {sel}）")
                        break
                    except Exception as e:
                        log_warning(f"FishClaw: 填入手机号时出错（{sel}）: {e}")
                        continue

            if not phone_filled:
                return (
                    "未能找到手机号输入框，可能页面结构已更新或出现验证码拦截。"
                    "请手动查看浏览器窗口并处理后重试。"
                )

            _random_delay(0.5, 1.0)

            # ── Step 2：勾选「同意协议」（跨 iframe 查找）──
            agree_selectors = [
                'span:has-text("您已阅读并同意")',
                'label:has-text("您已阅读并同意")',
                'span:has-text("已阅读并同意")',
                'label:has-text("已阅读并同意")',
                '[class*="agree-check"]',
                '[class*="agreeCheck"]',
                '[class*="protocol-check"]',
                '[class*="protocolCheck"]',
                '[class*="agreement-check"]',
                '[class*="checkBox"]',
            ]
            agreed = False
            for sel in agree_selectors:
                el = self._find_element(page, sel, timeout=2000)
                if el is not None:
                    try:
                        el.click()
                        agreed = True
                        log_info(f"FishClaw: 已勾选同意协议（selector: {sel}）")
                        _random_delay(0.3, 0.8)
                        break
                    except Exception:
                        continue

            if not agreed:
                log_warning("FishClaw: 未找到同意协议元素，继续流程...")

            _random_delay(0.5, 1.0)

            # ── Step 3：点击「获取验证码」（跨 iframe 查找）──
            sms_btn_selectors = [
                'span:has-text("获取验证码")',
                'button:has-text("获取验证码")',
                'a:has-text("获取验证码")',
                'span:has-text("发送验证码")',
                'button:has-text("发送验证码")',
                '[class*="getcode"]',
                '[class*="send-code"]',
            ]
            code_sent = False
            for sel in sms_btn_selectors:
                el = self._find_element(page, sel, timeout=2000)
                if el is not None:
                    try:
                        _random_delay(0.5, 1.0)
                        el.click()
                        code_sent = True
                        log_info(f"FishClaw: 已点击获取验证码（selector: {sel}）")
                        break
                    except Exception:
                        continue

            if not code_sent:
                return (
                    "未能找到「获取验证码」按钮。"
                    "页面可能弹出了滑块验证，请查看浏览器窗口手动完成验证后重试。"
                )

            _random_delay(1.0, 2.0)

            # ── 检测是否出现滑块验证码（跨 iframe 查找）──
            slide_selectors = [
                '.nc-container',
                '#nc_1_wrapper',
                '[class*="slide"]',
                '[class*="captcha"]',
                '[id*="nc_"]',
            ]
            for sel in slide_selectors:
                el = self._find_element(page, sel, timeout=1500)
                if el is not None:
                    log_warning("FishClaw: 检测到滑块验证码，请在浏览器窗口中手动完成验证！")
                    # 滑块在 iframe 内，page.wait_for_selector 只监听主页面无效。
                    # 改为轮询：在所有 frame 中查找滑块，直到滑块消失或检测到成功信号。
                    verified = False
                    for _ in range(120):          # 最多等 120 秒
                        time.sleep(1.0)
                        # 1) 检测滑块是否还存在于任意 frame
                        slide_still_visible = False
                        for frame in page.frames:
                            try:
                                if frame.locator(sel).first.is_visible(timeout=300):
                                    slide_still_visible = True
                                    break
                            except Exception:
                                pass
                        if not slide_still_visible:
                            log_info("FishClaw: 滑块验证已完成（滑块消失），继续流程...")
                            verified = True
                            break
                        # 2) 备用：检测短信倒计时文字出现（表示验证码已发送）
                        for frame in page.frames:
                            try:
                                # 倒计时按钮通常显示 "60s后重新获取" 或 "重新发送"
                                retry_el = frame.locator('a:has-text("后重新获取"), span:has-text("后重新获取"), a:has-text("重新发送"), span:has-text("重新发送")').first
                                if retry_el.is_visible(timeout=300):
                                    log_info("FishClaw: 检测到倒计时提示，滑块验证已通过，继续流程...")
                                    verified = True
                                    break
                            except Exception:
                                pass
                        if verified:
                            break
                    if not verified:
                        return (
                            "滑块验证等待超时（120 秒）。"
                            "请手动在浏览器中完成滑块验证后，再次调用 send_sms_code 重试。"
                        )
                    break

            return (
                f"验证码已发送至 {phone[:3]}****{phone[-4:]}，"
                "请查收短信后调用 login_with_sms(phone, code) 提交验证码完成登录。"
            )

        except Exception as e:
            return f"发送验证码时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具方法 3：提交验证码完成登录
    # ══════════════════════════════════════════════════════

    def login_with_sms(self, phone: str, code: str) -> str:
        """
        输入短信验证码完成闲鱼登录，登录成功后自动保存 Cookies 到本地。
        请在调用 send_sms_code 并收到验证码后，再调用此方法。

        Args:
            phone (str): 手机号码（纯数字，11 位）
            code (str): 收到的短信验证码（通常 4-6 位数字）

        Returns:
            str: 登录结果描述。
        """
        if not code or not code.strip().isdigit():
            return "验证码格式错误，请传入纯数字验证码。"
        if not phone or not phone.strip().isdigit() or len(phone.strip()) != 11:
            return "手机号格式错误，请传入 11 位纯数字手机号。"

        phone = phone.strip()
        code = code.strip()

        try:
            page = self._get_page()

            # ── Step 4：填入验证码（跨 iframe 查找）──
            code_input_selectors = [
                'input[placeholder="请输入验证码"]',
                'input[placeholder*="验证码"]',
                'input[autocomplete="one-time-code"]',
                'input[name="smsCode"]',
                'input[name="checkCode"]',
                'input[name="TPL_checkcode"]',
            ]
            code_filled = False
            for sel in code_input_selectors:
                el = self._find_element(page, sel, timeout=2000)
                if el is not None:
                    try:
                        el.click()
                        _random_delay(0.3, 0.7)
                        el.click(click_count=3)
                        _random_delay(0.2, 0.4)
                        _human_type_el(el, page, code)        # 兼容 iframe 内元素
                        code_filled = True
                        log_info(f"FishClaw: 已填入验证码（selector: {sel}）")
                        break
                    except Exception as e:
                        log_warning(f"FishClaw: 填入验证码时出错（{sel}）: {e}")
                        continue

            if not code_filled:
                return (
                    "未能找到验证码输入框，请确认浏览器窗口中是否仍在登录弹框，"
                    "或者手动输入验证码后调用 check_login_status 验证。"
                )

            _random_delay(0.5, 1.2)

            # ── Step 5：点击「登录」按钮（跨 iframe 查找）──
            login_btn_selectors = [
                'button:has-text("登录")',
                'button[type="submit"]',
                'input[value="登录"]',
                '[class*="login-btn"]',
                '[class*="loginBtn"]',
                '[class*="submit-btn"]',
            ]
            login_clicked = False
            for sel in login_btn_selectors:
                el = self._find_element(page, sel, timeout=2000)
                if el is not None:
                    try:
                        _random_delay(0.5, 1.0)
                        el.click()
                        login_clicked = True
                        log_info(f"FishClaw: 已点击登录按钮（selector: {sel}）")
                        break
                    except Exception:
                        continue

            if not login_clicked:
                return "未能找到登录按钮，请在浏览器窗口中手动点击登录后调用 check_login_status 验证。"

            # ── 等待登录弹框消失（登录成功的标志）──
            log_info("FishClaw: 等待登录完成...")
            _random_delay(2.0, 3.5)

            # ── 验证登录结果：检测已登录特征元素 ──
            logged_in_selectors = [
                '[class*="avatar"]',
                '[class*="nickName"]',
                '[class*="nick-name"]',
                '[class*="userNick"]',
                '[class*="user-nick"]',
                '[class*="header-avatar"]',
                'img[class*="avatar"]',
            ]
            for sel in logged_in_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        self._save_cookies()
                        title = page.title()
                        log_info(f"FishClaw: 登录成功，当前页面：{title}")
                        return (
                            f"登录成功！当前页面：{title}。"
                            f"Cookies 已保存到 {self.cookies_path}，后续调用无需重新登录。"
                        )
                except Exception:
                    continue

            # 未找到已登录特征，可能验证码错误或弹框仍在
            try:
                error_el = page.locator('[class*="error"], [class*="alert"], [class*="tips"]').first
                if error_el.is_visible(timeout=2000):
                    error_msg = error_el.inner_text()
                    return f"登录失败：{error_msg.strip()}（请检查验证码是否正确或已过期）"
            except Exception:
                pass

            return "登录失败：未检测到已登录状态，验证码可能错误或已过期，请重新调用 send_sms_code 发送新验证码。"

        except Exception as e:
            return f"提交验证码登录时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具方法 4：扫码登录
    # ══════════════════════════════════════════════════════

    def login_with_qrcode(self, timeout_seconds: int = 180) -> str:
        """
        打开闲鱼首页，等待用户手动扫码登录，登录成功后自动保存 Cookies。

        Args:
            timeout_seconds (int): 等待用户扫码的最大超时时间（秒），默认 180 秒。

        Returns:
            str: 登录结果描述。
        """
        try:
            page = self._get_page()

            # ── 尝试加载已有 Cookies ──
            self._load_cookies()

            log_info("FishClaw: 正在打开闲鱼首页...")
            page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 2.5)

            # ── 检测「未登录」特征元素（与 check_login_status 保持一致）──
            # 反向检测更可靠：登录按钮消失是即时的，avatar 等元素渲染可能有延迟
            not_logged_in_selectors = [
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

            def _is_logged_in() -> bool:
                """检测页面是否已处于登录状态（反向逻辑：找不到未登录特征 → 已登录）"""
                # URL 跳转到登录页 → 肯定未登录
                if "login.taobao.com" in page.url or "login.xianyu" in page.url:
                    return False
                # 找到任意「未登录」特征元素 → 未登录
                for sel in not_logged_in_selectors:
                    try:
                        if page.locator(sel).first.is_visible(timeout=500):
                            return False
                    except Exception:
                        pass
                # 未找到「未登录」特征 → 判定已登录
                return True

            # 已有 Cookies 且直接登录成功
            if _is_logged_in():
                self._save_cookies()
                title = page.title()
                log_info(f"FishClaw: Cookie 有效，已登录，页面：{title}")
                return (
                    f"已通过本地 Cookie 自动登录！当前页面：{title}。"
                    f"Cookies 已刷新保存到 {self.cookies_path}。"
                )

            # ── 未登录：提示用户手动扫码 ──
            log_info(
                f"FishClaw: 浏览器已打开，请在浏览器窗口中手动扫码登录（等待最多 {timeout_seconds} 秒）..."
            )
            print(
                f"\n{'='*60}\n"
                f"请在弹出的浏览器窗口中手动扫码登录闲鱼。\n"
                f"登录成功后将自动保存 Cookies，等待最多 {timeout_seconds} 秒...\n"
                f"{'='*60}\n"
            )

            # ── 轮询等待用户完成登录 ──
            for elapsed in range(timeout_seconds):
                time.sleep(1.0)
                try:
                    if _is_logged_in():
                        self._save_cookies()
                        title = page.title()
                        log_info(f"FishClaw: 扫码登录成功，用时 {elapsed + 1} 秒，页面：{title}")
                        return (
                            f"扫码登录成功！当前页面：{title}。"
                            f"Cookies 已保存到 {self.cookies_path}，后续调用无需重新登录。"
                        )
                except Exception:
                    pass

            return (
                f"等待扫码超时（{timeout_seconds} 秒）。"
                "请重新调用 login_with_qrcode 再次尝试，或检查网络连接。"
            )

        except Exception as e:
            return f"扫码登录时出错：{e}"

    # ══════════════════════════════════════════════════════
    # 工具方法 5：发布闲置商品
    # ══════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════
    # post_item 内部步骤方法
    # ══════════════════════════════════════════════════════

    def _post_step_prepare_image(self, image: str) -> Tuple[bool, str, Optional[str]]:
        """
        Step 1：处理图片路径，URL 则下载到临时文件。

        Returns:
            (success, local_image_path_or_error_msg, tmp_file_path)
        """
        image = image.strip()
        if image.startswith("http://") or image.startswith("https://"):
            log_info(f"FishClaw [post_item] Step1: 下载图片 {image[:80]}...")
            try:
                suffix = Path(image.split("?")[0]).suffix or ".jpg"
                fd, tmp_file = tempfile.mkstemp(suffix=suffix)
                os.close(fd)
                urllib.request.urlretrieve(image, tmp_file)
                local_path = str(Path(tmp_file).resolve())
                log_info(f"FishClaw [post_item] Step1: 图片已下载到 {local_path}")
                return True, local_path, tmp_file
            except Exception as e:
                return False, f"下载图片失败：{e}", None
        else:
            local_path = str(Path(image).resolve())
            if not Path(local_path).exists():
                return False, f"图片文件不存在：{local_path}", None
            return True, local_path, None

    def _post_step_navigate_to_publish(self, page: Any) -> Tuple[bool, str, Optional[Any]]:
        """
        Step 2：点击侧边栏「发闲置」，捕获新标签页。

        Returns:
            (success, message, publish_page)
        """
        publish_text_selectors = [
            'div.sidebar-item-text-container--KNEB4FFf',
            'div[data-spm-anchor-id*="sidebar"] :text("发闲置")',
            ':text("发闲置")',
        ]
        for sel in publish_text_selectors:
            try:
                el = page.locator(sel).first
                if not el.is_visible(timeout=3000):
                    continue
                _random_delay(0.5, 1.0)
                with self._context.expect_page(timeout=8000) as new_page_info:
                    el.click()
                publish_page = new_page_info.value
                publish_page.wait_for_load_state("networkidle", timeout=15000)
                log_info(f"FishClaw [post_item] Step2: 已点击「发闲置」，新标签页 URL={publish_page.url}")
                return True, f"已进入发布页面：{publish_page.url[:80]}", publish_page
            except Exception as e:
                log_warning(f"FishClaw [post_item] Step2: 点击「发闲置」失败（{sel}）: {e}")
                continue
        return False, "未能找到「发闲置」按钮，请确认已登录，或页面结构已更新。", None

    def _post_step_upload_image(self, page: Any, local_image_path: str) -> Tuple[bool, str]:
        """
        Step 3：上传宝贝图片。

        Returns:
            (success, message)
        """
        all_frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
        log_info(f"FishClaw [post_item] Step3: 当前 URL={page.url}，共 {len(all_frames)} 个 frame")
        for frame in all_frames:
            try:
                count = frame.evaluate("() => document.querySelectorAll('input[type=\"file\"]').length")
                log_info(f"  frame {frame.url[:80]} → file inputs: {count}")
            except Exception:
                log_info(f"  frame {frame.url[:80]} → 无法访问")

        # 3a：set_input_files 方案（优先）
        file_input_css_list = [
            'input[name="file"][type="file"]',
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ]
        for frame in all_frames:
            for css in file_input_css_list:
                try:
                    el = frame.query_selector(css)
                    if el is None:
                        continue
                    el.set_input_files(local_image_path)
                    log_info(f"FishClaw [post_item] Step3: 已通过 set_input_files 上传图片（css={css}）")
                    _random_delay(2.0, 4.0)
                    return True, f"图片已上传（set_input_files，css={css}）"
                except Exception as e:
                    log_warning(f"FishClaw [post_item] Step3: set_input_files 失败（{css}）: {e}")
                    continue

        # 3b：file_chooser 方案（降级）
        log_warning("FishClaw [post_item] Step3: set_input_files 方案失败，尝试 file_chooser 降级...")
        upload_trigger_selectors = [
            ':text("添加首图")',
            ':text("添加图片")',
            ':text("上传图片")',
            'div[class*="addPic"]',
            'div[class*="add-pic"]',
            'label[class*="upload"]',
            'label[class*="Upload"]',
        ]
        for sel in upload_trigger_selectors:
            trigger = self._find_element(page, sel, timeout=2000)
            if trigger is None:
                continue
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    trigger.click()
                fc_info.value.set_files(local_image_path)
                log_info(f"FishClaw [post_item] Step3: 图片已通过 file_chooser 上传（{sel}）")
                _random_delay(2.0, 4.0)
                return True, f"图片已上传（file_chooser，sel={sel}）"
            except Exception as e:
                log_warning(f"FishClaw [post_item] Step3: file_chooser 也失败（{sel}）: {e}")
                continue

        return False, "未能上传图片。请确认已跳转到发布页面，或手动上传图片后继续。"

    def _post_step_fill_description(self, page: Any, description: str) -> Tuple[bool, str]:
        """
        Step 4：填写宝贝描述（致命步骤，失败即停止）。

        Returns:
            (success, message)
        """
        desc_selectors = [
            'div[contenteditable="true"][class*="editor"]',
            'div[contenteditable="true"][data-placeholder*="描述"]',
            'div[contenteditable="true"][data-spm-anchor-id*="publish"]',
            'div[contenteditable="true"][class*="desc"]',
            'div[contenteditable="true"][class*="Desc"]',
            'textarea[placeholder*="描述"]',
            'textarea',
        ]
        for sel in desc_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    _random_delay(0.3, 0.6)
                    el.click(click_count=3)
                    _random_delay(0.2, 0.4)
                    for char in description:
                        page.keyboard.type(char)
                        time.sleep(random.uniform(0.03, 0.12))
                    _random_delay(0.5, 1.0)
                    log_info(f"FishClaw [fill_item_info] Step4: 已填写宝贝描述（{sel}）")
                    return True, f"宝贝描述已填写（sel={sel}）"
            except Exception as e:
                log_warning(f"FishClaw [fill_item_info] Step4: 填写描述失败（{sel}）: {e}")
                continue
        return False, "未能找到描述输入框，发布页面结构可能已变更。"

    def _post_step_select_category(self, page: Any, categories: List) -> Tuple[bool, str]:
        """
        Step 5：选择商品分类（致命步骤，失败即停止）。

        Returns:
            (success, message)
        """
        category_selectors = [
            'div[class*="category"] select',
            'select[class*="category"]',
            'div[class*="Category"] select',
            'div[class*="category"][class*="select"]',
            'div[class*="categorySelect"]',
            '.ant-select',
            'span[class*="category"]',
        ]
        for category in categories:
            for sel in category_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000): 
                        el.click()
                        _random_delay(0.5, 1.0)
                        option_sel = (
                            f'div[class*="option"]:has-text("{category}"), '
                            f'li:has-text("{category}"), '
                            f'option:has-text("{category}")'
                        )
                        opt = page.locator(option_sel).first
                        if opt.is_visible(timeout=2000):
                            opt.click()
                            _random_delay(0.5, 1.0)
                            log_info(f"FishClaw [fill_item_info] Step5: 已选择分类「{category}」")
                            return True, f"已选择分类「{category}」"
                except Exception as e:
                    log_warning(f"FishClaw [fill_item_info] Step5: 选择分类失败（{sel}）: {e}")
                    continue

            return False, f"未能选择分类，发布页面结构可能已变更。"

    def _post_step_fill_price(self, page: Any, price: float) -> Tuple[bool, str]:
        """
        Step 6：填写商品价格（致命步骤，失败即停止）。

        Returns:
            (success, message)
        """
        price_str = f"{price:.2f}"
        price_selectors = [
            'input[placeholder="0.00"]',
            'input.ant-input[type="text"]',
            'input[data-spm-anchor-id*="publish"][type="text"]',
            'input[placeholder*="价格"]',
            'input[type="number"]',
        ]
        for sel in price_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click()
                    _random_delay(0.2, 0.5)
                    el.click(click_count=3)
                    _random_delay(0.1, 0.3)
                    for char in price_str:
                        page.keyboard.type(char)
                        time.sleep(random.uniform(0.05, 0.15))
                    _random_delay(0.5, 1.2)
                    log_info(f"FishClaw [fill_item_info] Step6: 已填写价格 {price_str}（{sel}）")
                    return True, f"价格已填写：¥{price_str}（sel={sel}）"
            except Exception as e:
                log_warning(f"FishClaw [fill_item_info] Step6: 填写价格失败（{sel}）: {e}")
                continue
        return False, f"未能找到价格输入框，发布页面结构可能已变更。"

    def _post_step_take_screenshot(self, page: Any) -> Tuple[bool, str]:
        """
        Step 7a：在发布前截图，保存到 .cache/screenshot 目录。

        Returns:
            (success, screenshot_path_or_error_msg)
        """
        try:
            screenshot_dir = Path(".cache") / "screenshot"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = screenshot_dir / f"post_item_{timestamp}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            log_info(f"FishClaw [post_item] Step7a: 截图已保存到 {screenshot_path}")
            return True, str(screenshot_path.resolve())
        except Exception as e:
            return False, f"截图失败：{e}"

    def _post_step_click_publish(self, page: Any) -> Tuple[bool, str]:
        """
        Step 7b：点击「发布」按钮并等待发布结果。

        Returns:
            (success, message)
        """
        publish_btn_selectors = [
            'button:has-text("发布")',
            'span:has-text("发布"):not(:has-text("发布闲置"))',
            'div[class*="publish-btn"]:has-text("发布")',
            'div[class*="publishBtn"]:has-text("发布")',
            'a:has-text("立即发布")',
            'button:has-text("立即发布")',
            '[type="submit"]:has-text("发布")',
        ]
        for sel in publish_btn_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    _random_delay(0.5, 1.0)
                    el.click()
                    log_info(f"FishClaw [post_item] Step7b: 已点击发布按钮（{sel}）")
                    break
            except Exception as e:
                log_warning(f"FishClaw [post_item] Step7b: 点击发布按钮失败（{sel}）: {e}")
                continue
        else:
            return False, "未能找到「发布」按钮，商品信息已填写完毕，请在浏览器窗口中手动点击发布按钮。"

        # 等待发布完成，检测成功提示或页面跳转
        _random_delay(2.0, 3.5)
        success_selectors = [
            ':text("发布成功")',
            ':text("成功发布")',
            '[class*="success"]',
        ]
        for sel in success_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=4000):
                    log_info(f"FishClaw [post_item] Step7b: 检测到发布成功提示（{sel}）")
                    return True, f"商品发布成功！检测到成功提示：{sel}"
            except Exception:
                continue

        # 未检测到标准成功提示，以当前页面信息作为结果
        current_url = page.url
        current_title = page.title()
        return True, (
            f"发布操作已完成（未检测到明确成功提示），"
            f"当前页面：{current_title}（{current_url[:80]}）"
        )

    # ══════════════════════════════════════════════════════
    # 工具方法 5a：填写商品信息
    # ══════════════════════════════════════════════════════

    def fill_item_info(
        self,
        image: str,
        description: str,
        price: float = 100.0,
    ) -> str:
        """
        在闲鱼发布页面中填写商品信息（图片、描述、分类、价格）。

        本工具只负责填写信息，不会点击发布按钮。
        每一步都是致命步骤，任意步骤失败则立即停止并返回失败原因。
        填写成功后，请调用 post_item 完成截图确认和最终发布。

        Args:
            image (str): 宝贝图片，支持本地路径或网络 URL。
            description (str): 宝贝描述文字。
            price (float): 商品售价（元），默认 100.0。

        Returns:
            str: 包含所有步骤结果的汇总报告，或第一个失败步骤的错误信息。
        """
        step_results: List[Dict[str, Any]] = []
        _tmp_file: Optional[str] = None
        categories = ["其他技能服务","其他闲置"]

        def _record(step: str, success: bool, message: str) -> None:
            step_results.append({"step": step, "success": success, "message": message})
            log_info(f"FishClaw [fill_item_info] {'OK' if success else 'FAIL'} {step}: {message}")

        def _summary() -> str:
            lines = ["=== fill_item_info 步骤汇总 ==="]
            for r in step_results:
                icon = "✓" if r["success"] else "✗"
                lines.append(f"  [{icon}] {r['step']}: {r['message']}")
            return "\n".join(lines)

        try:
            page = self._get_page()

            # ── Step 0：加载 Cookies，访问首页 ──
            self._load_cookies()
            log_info("FishClaw [fill_item_info] Step0: 正在访问闲鱼首页...")
            page.goto(XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=30000)
            _random_delay(1.5, 2.5)
            _record("Step0-加载首页", True, f"已访问 {XIANYU_HOME_URL}")

            # ── Step 1：处理图片路径 ──
            ok, img_result, _tmp_file = self._post_step_prepare_image(image)
            _record("Step1-处理图片", ok, img_result)
            if not ok:
                return f"填写失败（Step1）：{img_result}\n\n{_summary()}"
            local_image_path = img_result

            # ── Step 2：进入发布页 ──
            ok, msg, publish_page = self._post_step_navigate_to_publish(page)
            _record("Step2-进入发布页", ok, msg)
            if not ok:
                return f"填写失败（Step2）：{msg}\n\n{_summary()}"
            page = publish_page

            # ── Step 3：上传图片 ──
            ok, msg = self._post_step_upload_image(page, local_image_path)
            _record("Step3-上传图片", ok, msg)
            if not ok:
                return f"填写失败（Step3）：{msg}\n\n{_summary()}"

            # ── Step 4：填写描述（致命）──
            ok, msg = self._post_step_fill_description(page, description)
            _record("Step4-填写描述", ok, msg)
            if not ok:
                return f"填写失败（Step4）：{msg}\n\n{_summary()}"

            # ── Step 5：选择分类（致命）──
            ok, msg = self._post_step_select_category(page, categories)
            _record("Step5-选择分类", ok, msg)
            if not ok:
                return f"填写失败（Step5）：{msg}\n\n{_summary()}"

            # ── Step 6：填写价格（致命）──
            ok, msg = self._post_step_fill_price(page, price)
            _record("Step6-填写价格", ok, msg)
            if not ok:
                return f"填写失败（Step6）：{msg}\n\n{_summary()}"

            # ── Step 7：截图 ──
            ok, screenshot_result = self._post_step_take_screenshot(page)
            _record("Step7-截图", ok, screenshot_result)

            return (
                f"商品信息填写成功！"
                f"请调用 post_item 查看截图并确认后完成发布"
            )

        except Exception as e:
            return f"填写商品信息时出错：{e}\n\n{_summary()}"
        finally:
            if _tmp_file and Path(_tmp_file).exists():
                try:
                    os.remove(_tmp_file)
                    log_info(f"FishClaw [fill_item_info]: 已清理临时图片文件 {_tmp_file}")
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════
    # 工具方法 5b：截图确认并发布商品
    # ══════════════════════════════════════════════════════

    @tool(requires_confirmation=True)
    def post_item(self) -> str:
        """
        调用post_item工具发布商品(帖子)。
        Returns:
            str: 发布结果描述。
        """
        step_results: List[Dict[str, Any]] = []

        def _record(step: str, success: bool, message: str) -> None:
            step_results.append({"step": step, "success": success, "message": message})
            log_info(f"FishClaw [post_item] {'OK' if success else 'FAIL'} {step}: {message}")

        def _summary() -> str:
            lines = ["=== post_item 步骤汇总 ==="]
            for r in step_results:
                icon = "✓" if r["success"] else "✗"
                lines.append(f"  [{icon}] {r['step']}: {r['message']}")
            return "\n".join(lines)

        try:
            page = self._get_page()
            # requires_confirmation=True：Agent 框架在此暂停，
            # 用户查看截图并 confirm 后，框架才继续执行后续代码。

            # ── Step 2：点击发布按钮 ──
            ok, msg = self._post_step_click_publish(page)
            _record("Step2-点击发布", ok, msg)
            if not ok:
                return f"发布失败（Step2）：{msg}\n\n{_summary()}"

            return f"商品发布成功！\n\n{_summary()}"

        except Exception as e:
            return f"发布时出错：{e}\n\n{_summary()}"

    # ══════════════════════════════════════════════════════
    # 预留：评论商品（后续实现）
    # ══════════════════════════════════════════════════════

    # def comment_item(self, item_url: str, comment: str) -> str:
    #     """评论他人闲鱼商品"""
    #     ...

    # ══════════════════════════════════════════════════════
    # 析构：确保浏览器关闭
    # ══════════════════════════════════════════════════════

    def __del__(self):
        try:
            self._close_browser()
        except Exception:
            pass
