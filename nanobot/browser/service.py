"""Playwright-backed managed browser service."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import websockets
from loguru import logger

from nanobot.browser.config import BrowserToolConfig


class BrowserServiceError(RuntimeError):
    """Raised when browser operations fail."""


@dataclass
class NetworkEvent:
    method: str
    url: str
    resource_type: str


@dataclass
class ActionTarget:
    found: bool
    text_hint: str
    tag: str = ""
    text: str = ""
    title: str = ""
    aria_label: str = ""
    class_name: str = ""
    rect: dict[str, float] | None = None
    click_point: dict[str, float] | None = None
    visible: bool = False


class BrowserService:
    """Lazy singleton-like browser manager for tools."""

    def __init__(self, config: BrowserToolConfig):
        self.config = config
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._hooked_pages: set[int] = set()
        self._network_events: deque[NetworkEvent] = deque(maxlen=config.max_network_events)
        self._cdp_auto_launch_attempted = False

    def _runtime_alive(self) -> bool:
        """Best-effort health check for cached browser handles."""
        try:
            if self._page is None:
                return False
            is_closed = getattr(self._page, "is_closed", None)
            if callable(is_closed) and is_closed():
                return False
            if self._browser is not None:
                is_connected = getattr(self._browser, "is_connected", None)
                if callable(is_connected) and not is_connected():
                    return False
            if self._context is not None:
                pages = getattr(self._context, "pages", None)
                if pages is not None and len(list(pages)) == 0 and not self.config.cdp_url:
                    return False
            return True
        except Exception:
            return False

    def _reset_runtime(self) -> None:
        """Forget stale Playwright/CDP handles so the next call can reattach/relaunch."""
        self._browser = None
        self._context = None
        self._page = None
        self._hooked_pages.clear()
        # 外部关闭 Chrome 后，允许下一轮再次尝试 auto-launch。
        self._cdp_auto_launch_attempted = False

    async def ensure_ready(self):
        if self._page is not None and self._runtime_alive():
            return self._page
        if self._page is not None and not self._runtime_alive():
            logger.info("Browser runtime became stale; resetting cached handles")
            self._reset_runtime()
        async with self._lock:
            if self._page is not None and self._runtime_alive():
                return self._page
            if self._page is not None and not self._runtime_alive():
                logger.info("Browser runtime became stale inside lock; resetting cached handles")
                self._reset_runtime()
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise BrowserServiceError(
                    "Playwright is not installed. Run: pip install playwright && playwright install chromium"
                ) from exc

            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self.config.cdp_url:
                await self._connect_over_cdp()
            else:
                await self._launch_managed_browser()
            logger.info(
                "Browser service started (headless={}, cdp={})",
                self.config.headless,
                bool(self.config.cdp_url),
            )
            return self._page

    async def _launch_managed_browser(self) -> None:
        launch_kwargs: dict[str, Any] = {
            "headless": self.config.headless,
            "args": ["--disable-dev-shm-usage", "--no-default-browser-check", "--no-sandbox"],
            "timeout": self.config.launch_timeout_s * 1000,
        }
        if self.config.executable_path:
            launch_kwargs["executable_path"] = str(Path(self.config.executable_path).expanduser())
        elif self.config.browser_channel:
            launch_kwargs["channel"] = self.config.browser_channel

        profile_dir = Path(self.config.user_data_dir).expanduser()
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            locale=self.config.locale,
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
            **launch_kwargs,
        )
        self._browser = self._context.browser
        self._install_context_hooks(self._context)
        self._page = await self._pick_page()

    async def _connect_over_cdp(self) -> None:
        endpoint = str(self.config.cdp_url or "").strip()
        if not endpoint:
            raise BrowserServiceError("cdp_url is empty")
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                endpoint_url=endpoint,
                timeout=self.config.launch_timeout_s * 1000,
            )
        except Exception as exc:
            launched = await self._maybe_auto_launch_cdp_browser()
            if launched:
                try:
                    self._browser = await self._playwright.chromium.connect_over_cdp(
                        endpoint_url=endpoint,
                        timeout=self.config.launch_timeout_s * 1000,
                    )
                except Exception as retry_exc:
                    raise BrowserServiceError(f"connect_over_cdp failed after auto-launch: {retry_exc}") from retry_exc
            else:
                raise BrowserServiceError(f"connect_over_cdp failed: {exc}") from exc

        contexts = list(self._browser.contexts)
        if not contexts:
            raise BrowserServiceError("CDP browser has no accessible contexts")
        self._context = contexts[0]
        self._install_context_hooks(self._context)
        self._page = await self._pick_page()

    async def _maybe_auto_launch_cdp_browser(self) -> bool:
        """Best-effort helper: auto-start a CDP browser once, then retry attach."""
        command = str(self.config.cdp_auto_launch_command or "").strip()
        if not command or self._cdp_auto_launch_attempted:
            return False

        self._cdp_auto_launch_attempted = True
        cwd = None
        if self.config.cdp_auto_launch_cwd:
            cwd = str(Path(self.config.cdp_auto_launch_cwd).expanduser())

        try:
            # 这里故意不等待子进程结束：GUI 浏览器应当在后台持续存活。
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            logger.info("Auto-launching CDP browser with command: {}", command)
            with contextlib.suppress(ProcessLookupError):
                if proc.returncode is not None and proc.returncode != 0:
                    logger.warning("CDP auto-launch command exited immediately with code {}", proc.returncode)
            await asyncio.sleep(max(int(self.config.cdp_auto_launch_delay_s), 1))
            return True
        except Exception as exc:
            logger.warning("Failed to auto-launch CDP browser: {}", exc)
            return False

    async def _pick_page(self):
        if self._context is None:
            raise BrowserServiceError("browser context not initialized")
        pages = list(self._context.pages)
        preferred = [p for p in pages if p.url and p.url not in ("about:blank", "chrome://newtab/")]
        if preferred:
            return preferred[-1]
        if pages:
            return pages[-1]
        return await self._context.new_page()
    
    async def cdp_tabs(self) -> list[dict[str, Any]]:
        endpoint = str(self.config.cdp_url or "").rstrip("/")
        if not endpoint:
            raise BrowserServiceError("cdp_url is not configured")

        timeout = max(float(getattr(self.config, "cdp_http_timeout_s", 5)), 1.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            r = await client.get(f"{endpoint}/json/list")
            r.raise_for_status()

        tabs = r.json()
        return [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "url": t.get("url"),
                "type": t.get("type"),
                "ws": t.get("webSocketDebuggerUrl"),
            }
            for t in tabs
            if t.get("type") == "page"
        ]

    @staticmethod
    def _dom_helpers_script() -> str:
        return """
          const __nb_allRoots = () => {
            const roots = [];
            const seen = new Set();
            const queue = [document];
            while (queue.length) {
              const root = queue.shift();
              if (!root || seen.has(root)) continue;
              seen.add(root);
              roots.push(root);
              const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
              for (const el of nodes) {
                if (el && el.shadowRoot && !seen.has(el.shadowRoot)) {
                  queue.push(el.shadowRoot);
                }
              }
            }
            return roots;
          };
          const __nb_queryAll = (sel) => {
            if (!sel) return [];
            const out = [];
            for (const root of __nb_allRoots()) {
              try { out.push(...root.querySelectorAll(sel)); } catch {}
            }
            return out;
          };
          const __nb_findByText = (hint) => {
            if (!hint) return null;
            for (const root of __nb_allRoots()) {
              const nodes = root.querySelectorAll ? [...root.querySelectorAll('*')] : [];
              const found = nodes.find(x => ((x.innerText || x.textContent || '').includes(hint)));
              if (found) return found;
            }
            return null;
          };
        """

    async def element_probe(
        self,
        selector: str | None = None,
        text_hint: str | None = None,
        page_url_contains: str | None = None,
    ):
        script = f"""(() => {{
          {self._dom_helpers_script()}
          const sel = {selector!r};
          const hint = {text_hint!r};
          let el = null;
          if (sel) el = __nb_queryAll(sel)[0] || null;
          if (!el && hint) el = __nb_findByText(hint);
          if (!el) return {{found:false}};
          const r = el.getBoundingClientRect();
          return {{
            found: true,
            tag: el.tagName,
            text: (el.innerText || '').trim().slice(0, 300),
            html: el.outerHTML.slice(0, 500),
            rect: {{x:r.x, y:r.y, width:r.width, height:r.height}},
            visible: r.width > 0 && r.height > 0
          }};
        }})()"""
        return await self.evaluate(script, page_url_contains=page_url_contains)

    @staticmethod
    def _build_action_target_script(text_hint: str) -> str:
        """Return a generic DOM probe script for action-like controls.

        The heuristic intentionally favors semantic attributes (`title`, `aria-label`)
        and returns a left-biased hotspot instead of the container center. This keeps
        the browser layer generic while still being more reliable for icon+count UIs.
        """
        return f"""(() => {{
          const hint = {text_hint!r};
          const walker = [...document.querySelectorAll('[title],[aria-label],button,[role="button"],a,div,span')];
          const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const candidates = [];

          for (const el of walker) {{
            const text = norm(el.innerText);
            const title = norm(el.getAttribute('title'));
            const aria = norm(el.getAttribute('aria-label'));
            const all = `${{text}} ${{title}} ${{aria}}`;
            if (!all.includes(hint)) continue;

            const r = el.getBoundingClientRect();
            if (r.width <= 0 || r.height <= 0) continue;

            const clickX = r.x + Math.min(20, Math.max(8, r.width * 0.25));
            const clickY = r.y + (r.height / 2);
            candidates.push({{
              tag: el.tagName,
              text: text.slice(0, 200),
              title,
              ariaLabel: aria,
              className: String(el.className || '').slice(0, 160),
              rect: {{ x: r.x, y: r.y, width: r.width, height: r.height }},
              clickPoint: {{ x: clickX, y: clickY }},
              visible: true,
            }});
          }}

          const preferred = candidates.find(c => c.title.includes(hint) || c.ariaLabel.includes(hint));
          if (preferred) return {{ found: true, textHint: hint, ...preferred }};
          if (candidates.length) return {{ found: true, textHint: hint, ...candidates[0] }};
          return {{ found: false, textHint: hint }};
        }})()"""

    async def find_action_target(
        self,
        text_hint: str,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Locate an actionable UI target on the current page and return a click point.

        The returned click point is intentionally biased toward the left icon/hot area
        instead of the full container center, which is more reliable for controls like
        bilibili's like/favorite/coin buttons.
        """
        script = self._build_action_target_script(text_hint)
        result = await self.evaluate(script, page_url_contains=page_url_contains)
        if not isinstance(result, dict):
            raise BrowserServiceError("find_action_target failed: invalid result")
        target = ActionTarget(
            found=bool(result.get("found")),
            text_hint=str(result.get("textHint") or text_hint),
            tag=str(result.get("tag") or ""),
            text=str(result.get("text") or ""),
            title=str(result.get("title") or ""),
            aria_label=str(result.get("ariaLabel") or ""),
            class_name=str(result.get("className") or ""),
            rect=result.get("rect") if isinstance(result.get("rect"), dict) else None,
            click_point=result.get("clickPoint") if isinstance(result.get("clickPoint"), dict) else None,
            visible=bool(result.get("visible")),
        )
        return {
            "found": target.found,
            "textHint": target.text_hint,
            "tag": target.tag,
            "text": target.text,
            "title": target.title,
            "ariaLabel": target.aria_label,
            "className": target.class_name,
            "rect": target.rect,
            "clickPoint": target.click_point,
            "visible": target.visible,
        }

    async def click_action_target(
        self,
        text_hint: str,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Find an action target on the current page and click its suggested hotspot."""
        target = await self.find_action_target(text_hint, page_url_contains=page_url_contains)
        if not target.get("found"):
            raise BrowserServiceError(f"click_action_target failed: target not found: {text_hint}")
        click_point = target.get("clickPoint")
        if not isinstance(click_point, dict):
            raise BrowserServiceError(f"click_action_target failed: no click point for target: {text_hint}")

        try:
            x = int(round(float(click_point["x"])))
            y = int(round(float(click_point["y"])))
        except Exception as exc:
            raise BrowserServiceError(f"click_action_target failed: invalid click point: {click_point}") from exc

        click_result = await self.click_point(x, y, page_url_contains=page_url_contains)
        return {
            "target": target,
            "click": click_result,
        }

    async def scroll(
        self,
        delta_y: int = 800,
        selector: str | None = None,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Scroll the page or a matching scroll container."""
        await self.ensure_ready()
        if self.config.cdp_url:
            script = f"""(() => {{
              const sel = {selector!r};
              const deltaY = {delta_y};
              let target = null;
              if (sel) target = document.querySelector(sel);
              if (target && typeof target.scrollTop === 'number') {{
                const before = target.scrollTop;
                target.scrollTop = before + deltaY;
                target.dispatchEvent(new Event('scroll', {{ bubbles: true }}));
                return {{
                  target: 'element',
                  selector: sel,
                  before,
                  after: target.scrollTop,
                  deltaY,
                }};
              }}
              const before = window.scrollY;
              window.scrollBy(0, deltaY);
              return {{
                target: 'window',
                before,
                after: window.scrollY,
                deltaY,
              }};
            }})()"""
            try:
                result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
                if not isinstance(result, dict):
                    raise BrowserServiceError("scroll failed: invalid result")
                return result
            except Exception as exc:
                raise BrowserServiceError(f"scroll failed: {exc}") from exc

        page = await self.ensure_ready()
        try:
            if selector:
                locator = page.locator(selector).first
                before = await locator.evaluate("(el) => el.scrollTop")
                after = await locator.evaluate(
                    "(el, dy) => { el.scrollTop += dy; return el.scrollTop; }",
                    delta_y,
                )
                return {"target": "element", "selector": selector, "before": before, "after": after, "deltaY": delta_y}
            before = await page.evaluate("() => window.scrollY")
            await page.mouse.wheel(0, delta_y)
            after = await page.evaluate("() => window.scrollY")
            return {"target": "window", "before": before, "after": after, "deltaY": delta_y}
        except Exception as exc:
            raise BrowserServiceError(f"scroll failed: {exc}") from exc

    async def scroll_into_view(
        self,
        selector: str | None = None,
        text_hint: str | None = None,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Scroll an element into view by selector or visible text hint."""
        if not selector and not text_hint:
            raise BrowserServiceError("scroll_into_view failed: selector or text_hint is required")

        script = f"""(() => {{
          {self._dom_helpers_script()}
          const sel = {selector!r};
          const hint = {text_hint!r};
          let el = null;
          if (sel) el = __nb_queryAll(sel)[0] || null;
          if (!el && hint) el = __nb_findByText(hint);
          if (!el) return {{ found: false }};
          el.scrollIntoView({{ behavior: 'instant', block: 'center', inline: 'nearest' }});
          const r = el.getBoundingClientRect();
          return {{
            found: true,
            tag: el.tagName,
            text: (el.innerText || '').trim().slice(0, 200),
            rect: {{ x: r.x, y: r.y, width: r.width, height: r.height }},
            visible: r.width > 0 && r.height > 0
          }};
        }})()"""
        try:
            result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
            if not isinstance(result, dict):
                raise BrowserServiceError("scroll_into_view failed: invalid result")
            return result
        except Exception as exc:
            raise BrowserServiceError(f"scroll_into_view failed: {exc}") from exc

    async def inspect_scroll_targets(
        self,
        page_url_contains: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return likely scrollable containers on the current page."""
        script = f"""(() => {{
          const maxItems = {int(limit)};
          const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const all = [document.scrollingElement || document.documentElement, ...document.querySelectorAll('*')];
          const out = [];
          for (const el of all) {{
            const isRoot = el === document.scrollingElement || el === document.documentElement || el === document.body;
            const sh = isRoot ? Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) : el.scrollHeight;
            const ch = isRoot ? window.innerHeight : el.clientHeight;
            const sw = isRoot ? Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) : el.scrollWidth;
            const cw = isRoot ? window.innerWidth : el.clientWidth;
            const canScrollY = sh - ch > 40;
            const canScrollX = sw - cw > 40;
            if (!canScrollY && !canScrollX) continue;
            const r = isRoot
              ? {{ x: 0, y: 0, width: window.innerWidth, height: window.innerHeight }}
              : el.getBoundingClientRect();
            const selector = isRoot
              ? 'document.scrollingElement'
              : (() => {{
                  if (el.id) return `#${{el.id}}`;
                  const cls = norm(el.className).split(' ')[0];
                  if (cls) return `${{el.tagName.toLowerCase()}}.${{cls}}`;
                  return el.tagName.toLowerCase();
                }})();
            out.push({{
              selector,
              tag: el.tagName || 'ROOT',
              text: norm(el.innerText).slice(0, 80),
              scrollHeight: sh,
              clientHeight: ch,
              scrollWidth: sw,
              clientWidth: cw,
              rect: r,
              canScrollY,
              canScrollX,
            }});
          }}
          out.sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
          return out.slice(0, maxItems);
        }})()"""
        try:
            result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
            if not isinstance(result, list):
                raise BrowserServiceError("inspect_scroll_targets failed: invalid result")
            return result
        except Exception as exc:
            raise BrowserServiceError(f"inspect_scroll_targets failed: {exc}") from exc

    async def wait_for(
        self,
        selector: str | None = None,
        text_hint: str | None = None,
        timeout_ms: int = 5000,
        poll_ms: int = 250,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Wait until a selector or visible text appears on the current page."""
        if not selector and not text_hint:
            raise BrowserServiceError("wait_for failed: selector or text_hint is required")
        timeout_ms = max(int(timeout_ms), 100)
        poll_ms = max(int(poll_ms), 50)
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)

        script = f"""(() => {{
          {self._dom_helpers_script()}
          const sel = {selector!r};
          const hint = {text_hint!r};
          let el = null;
          if (sel) el = __nb_queryAll(sel)[0] || null;
          if (!el && hint) el = __nb_findByText(hint);
          if (!el) return {{ found: false }};
          const r = el.getBoundingClientRect();
          return {{
            found: true,
            tag: el.tagName,
            text: (el.innerText || '').trim().slice(0, 200),
            rect: {{ x: r.x, y: r.y, width: r.width, height: r.height }},
            visible: r.width > 0 && r.height > 0,
          }};
        }})()"""

        last_result: dict[str, Any] = {"found": False}
        while asyncio.get_event_loop().time() < deadline:
            try:
                result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
                if isinstance(result, dict):
                    last_result = result
                    if result.get("found"):
                        return result
            except Exception:
                pass
            await asyncio.sleep(poll_ms / 1000.0)

        return {
            "found": False,
            "selector": selector,
            "textHint": text_hint,
            "timeoutMs": timeout_ms,
            "last": last_result,
        }

    async def wait_for_change(
        self,
        selector: str | None = None,
        metric: str = "count",
        baseline: str | None = None,
        timeout_ms: int = 5000,
        poll_ms: int = 250,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Wait until a page metric changes after user-like interaction."""
        metric = str(metric or "count").strip().lower()
        timeout_ms = max(int(timeout_ms), 100)
        poll_ms = max(int(poll_ms), 50)
        allowed = {"count", "url", "title", "scrolly", "text"}
        if metric not in allowed:
            raise BrowserServiceError(f"wait_for_change failed: unsupported metric: {metric}")
        if metric in {"count", "text"} and not selector:
            raise BrowserServiceError(f"wait_for_change failed: selector is required for metric {metric}")

        if baseline is None:
            initial = await self._read_change_metric(
                selector=selector,
                metric=metric,
                page_url_contains=page_url_contains,
            )
            baseline = str(initial.get("value", ""))

        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        last = {"value": baseline}
        while asyncio.get_event_loop().time() < deadline:
            current = await self._read_change_metric(
                selector=selector,
                metric=metric,
                page_url_contains=page_url_contains,
            )
            last = current
            if str(current.get("value", "")) != str(baseline):
                return {
                    "changed": True,
                    "metric": metric,
                    "selector": selector,
                    "before": baseline,
                    "after": current.get("value"),
                }
            await asyncio.sleep(poll_ms / 1000.0)

        return {
            "changed": False,
            "metric": metric,
            "selector": selector,
            "before": baseline,
            "after": last.get("value"),
            "timeoutMs": timeout_ms,
        }

    async def _read_change_metric(
        self,
        selector: str | None,
        metric: str,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        script = f"""(() => {{
          {self._dom_helpers_script()}
          const sel = {selector!r};
          const metric = {metric!r};
          if (metric === 'url') return {{ value: location.href }};
          if (metric === 'title') return {{ value: document.title }};
          if (metric === 'scrolly') return {{ value: window.scrollY }};
          if (metric === 'count') return {{ value: sel ? __nb_queryAll(sel).length : 0 }};
          if (metric === 'text') {{
            const nodes = sel ? __nb_queryAll(sel) : [];
            return {{
              value: nodes
                .map(n => (n.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(Boolean)
                .join('\\n')
            }};
          }}
          return {{ value: null }};
        }})()"""
        result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
        if not isinstance(result, dict):
            raise BrowserServiceError("wait_for_change failed: invalid metric result")
        return result

    async def collect_lazy_items(
        self,
        selector: str,
        container_selector: str | None = None,
        step_y: int = 900,
        max_steps: int = 8,
        wait_ms: int = 700,
        stable_rounds: int = 2,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Incrementally scroll and collect items from a lazy-loaded list until growth stops."""
        selector = str(selector or "").strip()
        if not selector:
            raise BrowserServiceError("collect_lazy_items failed: selector is required")
        max_steps = max(int(max_steps), 1)
        wait_ms = max(int(wait_ms), 100)
        stable_rounds = max(int(stable_rounds), 1)

        seen_items: list[str] = []
        seen_set: set[str] = set()
        rounds_without_growth = 0
        snapshots: list[dict[str, Any]] = []

        for step in range(max_steps):
            current = await self._read_lazy_items(selector=selector, page_url_contains=page_url_contains)
            visible_items = [str(x) for x in current.get("items", []) if str(x).strip()]
            before = len(seen_set)
            for item in visible_items:
                cleaned = " ".join(item.split())
                if cleaned and cleaned not in seen_set:
                    seen_set.add(cleaned)
                    seen_items.append(cleaned)
            after = len(seen_set)
            snapshots.append({"step": step, "visibleCount": len(visible_items), "uniqueCount": after})

            if after == before:
                rounds_without_growth += 1
            else:
                rounds_without_growth = 0
            if rounds_without_growth >= stable_rounds:
                break

            await self.scroll(
                delta_y=step_y,
                selector=container_selector,
                page_url_contains=page_url_contains,
            )
            await asyncio.sleep(wait_ms / 1000.0)

        final_state = await self._read_lazy_items(selector=selector, page_url_contains=page_url_contains)
        return {
            "selector": selector,
            "containerSelector": container_selector,
            "uniqueCount": len(seen_set),
            "visibleCount": final_state.get("count", 0),
            "items": seen_items,
            "snapshots": snapshots,
        }

    async def _read_lazy_items(
        self,
        selector: str,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        script = f"""(() => {{
          {self._dom_helpers_script()}
          const sel = {selector!r};
          const nodes = __nb_queryAll(sel);
          const items = nodes
            .map(el => (el.textContent || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean);
          return {{ count: nodes.length, items }};
        }})()"""
        result = await self.evaluate(script, await_promise=True, page_url_contains=page_url_contains)
        if not isinstance(result, dict):
            raise BrowserServiceError("collect_lazy_items failed: invalid result")
        return result


    def _install_context_hooks(self, context) -> None:
        for page in context.pages:
            self._install_network_hooks(page)
        context.on("page", self._install_network_hooks)

    def _install_network_hooks(self, page) -> None:
        if not self.config.network_capture:
            return
        page_id = id(page)
        if page_id in self._hooked_pages:
            return
        self._hooked_pages.add(page_id)

        def _record(request):
            try:
                self._network_events.append(
                    NetworkEvent(
                        method=request.method,
                        url=request.url,
                        resource_type=request.resource_type,
                    )
                )
            except Exception:
                logger.debug("Failed to record network event", exc_info=True)

        page.on("request", _record)

    @staticmethod
    def _is_loopback_http(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        host = (parsed.hostname or "").lower()
        return host in {"127.0.0.1", "localhost", "::1"}

    async def _cdp_page_ws(self, page_url_contains: str | None = None) -> str:
        endpoint = str(self.config.cdp_url or "").strip().rstrip("/")
        if endpoint.startswith("ws://") or endpoint.startswith("wss://"):
            return endpoint

        list_url = f"{endpoint}/json/list"
        timeout = max(float(self.config.timeout_s), 1.0)
        trust_env = not self._is_loopback_http(endpoint)
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=trust_env) as client:
                response = await client.get(list_url)
                response.raise_for_status()
            tabs = response.json()
        except Exception as exc:
            raise BrowserServiceError(f"CDP tab discovery failed: {exc}") from exc

        page_tabs = [tab for tab in tabs if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl")]
        if not page_tabs:
            raise BrowserServiceError("CDP endpoint returned no page targets")

        chosen = None
        if page_url_contains:
            chosen = next((tab for tab in page_tabs if page_url_contains in str(tab.get("url", ""))), None)
        if chosen is None:
            preferred = [tab for tab in page_tabs if str(tab.get("url", "")) not in ("about:blank", "chrome://newtab/")]
            # 在 CDP 模式下，self._page 很容易落后于真实激活 tab。
            # 这里优先取 /json/list 中排序靠前的非空页面，避免操作后仍错误命中旧 tab。
            chosen = preferred[0] if preferred else page_tabs[0]

        return str(chosen.get("webSocketDebuggerUrl", ""))

    async def _cdp_send(self, method: str, params: dict[str, Any] | None = None, *, page_url_contains: str | None = None) -> Any:
        ws_url = await self._cdp_page_ws(page_url_contains=page_url_contains)
        timeout = max(float(self.config.timeout_s), 1.0)
        try:
            async with websockets.connect(ws_url, open_timeout=timeout, close_timeout=timeout) as ws:
                message_id = 0

                async def _send_once(name: str, payload: dict[str, Any] | None = None) -> Any:
                    nonlocal message_id
                    message_id += 1
                    await ws.send(json.dumps({"id": message_id, "method": name, "params": payload or {}}))
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        msg = json.loads(raw)
                        if msg.get("id") != message_id:
                            continue
                        if msg.get("error"):
                            raise BrowserServiceError(f"CDP {name} failed: {msg['error']}")
                        return msg.get("result", {})

                await _send_once("Page.enable")
                await _send_once("Runtime.enable")
                return await _send_once(method, params)
        except BrowserServiceError:
            raise
        except Exception as exc:
            raise BrowserServiceError(f"CDP {method} failed: {exc}") from exc

    async def navigate(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        page = await self.ensure_ready()
        if self.config.cdp_url:
            try:
                await self._cdp_send("Page.navigate", {"url": url}, page_url_contains=page_url_contains)
                await asyncio.sleep(1.0)
                result = await self.evaluate(
                    """(() => ({
                        title: document.title,
                        url: location.href
                    }))()""",
                    await_promise=True,
                    page_url_contains=page_url_contains,
                )
                if not isinstance(result, dict):
                    raise BrowserServiceError("navigate failed: invalid CDP navigation result")
                return {
                    "url": result.get("url") or url,
                    "title": result.get("title") or "",
                    "status": None,
                }
            except Exception as exc:
                raise BrowserServiceError(f"navigate failed: {exc}") from exc
        try:
            response = await page.goto(url, wait_until=wait_until, timeout=self.config.timeout_s * 1000)
            title = await page.title()
            return {
                "url": page.url,
                "title": title,
                "status": getattr(response, "status", None),
            }
        except Exception as exc:
            raise BrowserServiceError(f"navigate failed: {exc}") from exc

    async def snapshot(self, max_chars: int | None = None) -> dict[str, Any]:
        page = await self.ensure_ready()
        limit = max_chars or self.config.max_snapshot_chars
        if self.config.cdp_url:
            try:
                result = await self.evaluate(
                    """(() => ({
                        title: document.title,
                        url: location.href,
                        text: (document.body?.innerText || "")
                    }))()""",
                    await_promise=True,
                )
                if not isinstance(result, dict):
                    raise BrowserServiceError("snapshot failed: invalid CDP result")
                text = str(result.get("text") or "")
                return {
                    "url": result.get("url") or "",
                    "title": result.get("title") or "",
                    "text": text[:limit],
                    "truncated": len(text) > limit,
                }
            except Exception as exc:
                raise BrowserServiceError(f"snapshot failed: {exc}") from exc
        try:
            title = await page.title()
            text = await page.locator("body").inner_text(timeout=self.config.timeout_s * 1000)
            return {
                "url": page.url,
                "title": title,
                "text": text[:limit],
                "truncated": len(text) > limit,
            }
        except Exception as exc:
            raise BrowserServiceError(f"snapshot failed: {exc}") from exc

    async def evaluate(self, script: str, await_promise: bool = True, page_url_contains: str | None = None) -> Any:
        page = await self.ensure_ready()
        if self.config.cdp_url:
            result = await self._cdp_send(
                "Runtime.evaluate",
                {
                    "expression": script,
                    "awaitPromise": await_promise,
                    "returnByValue": True,
                },
                page_url_contains=page_url_contains,
            )
            return (result.get("result") or {}).get("value")
        try:
            return await page.evaluate(script)
        except Exception as exc:
            raise BrowserServiceError(f"evaluate failed: {exc}") from exc

    async def click(self, selector: str, page_url_contains: str | None = None) -> str:
        page = await self.ensure_ready()
        if self.config.cdp_url:
            try:
                probe = await self.evaluate(
                    f"""(() => {{
                        const el = document.querySelector({selector!r});
                        if (!el) return {{found:false}};
                        const r = el.getBoundingClientRect();
                        return {{
                            found: true,
                            x: r.x + r.width / 2,
                            y: r.y + r.height / 2,
                            visible: r.width > 0 && r.height > 0
                        }};
                    }})()""",
                    await_promise=True,
                    page_url_contains=page_url_contains,
                )
                if not isinstance(probe, dict) or not probe.get("found"):
                    raise BrowserServiceError(f"click failed: selector not found: {selector}")
                if not probe.get("visible"):
                    raise BrowserServiceError(f"click failed: selector not visible: {selector}")
                await self.click_point(
                    int(round(float(probe["x"]))),
                    int(round(float(probe["y"]))),
                    page_url_contains=page_url_contains,
                )
                return f"Clicked: {selector}"
            except Exception as exc:
                raise BrowserServiceError(f"click failed: {exc}") from exc
        try:
            await page.locator(selector).first.click(timeout=self.config.timeout_s * 1000)
            return f"Clicked: {selector}"
        except Exception as exc:
            raise BrowserServiceError(f"click failed: {exc}") from exc

    async def click_point(self, x: int, y: int, page_url_contains: str | None = None) -> dict[str, Any]:
        await self.ensure_ready()
        if self.config.cdp_url:
            await self._cdp_send(
                "Input.dispatchMouseEvent",
                {"type": "mouseMoved", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 0},
                page_url_contains=page_url_contains,
            )
            await self._cdp_send(
                "Input.dispatchMouseEvent",
                {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1},
                page_url_contains=page_url_contains,
            )
            await self._cdp_send(
                "Input.dispatchMouseEvent",
                {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1},
                page_url_contains=page_url_contains,
            )
            return {"ok": True, "x": x, "y": y, "backend": "cdp"}
        page = await self.ensure_ready()
        try:
            await page.mouse.click(x, y)
            return {"ok": True, "x": x, "y": y, "backend": "playwright"}
        except Exception as exc:
            raise BrowserServiceError(f"click_point failed: {exc}") from exc

    async def type_text(
        self,
        selector: str,
        text: str,
        press_enter: bool = False,
        page_url_contains: str | None = None,
    ) -> str:
        page = await self.ensure_ready()
        if self.config.cdp_url:
            try:
                focused = await self.evaluate(
                    f"""(() => {{
                        const el = document.querySelector({selector!r});
                        if (!el) return {{found:false}};
                        el.focus();
                        if ('value' in el) {{
                            el.value = {text!r};
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                        return {{found:true}};
                    }})()""",
                    await_promise=True,
                    page_url_contains=page_url_contains,
                )
                if not isinstance(focused, dict) or not focused.get("found"):
                    raise BrowserServiceError(f"type failed: selector not found: {selector}")
                if press_enter:
                    await self._cdp_send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
                        page_url_contains=page_url_contains,
                    )
                    await self._cdp_send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
                        page_url_contains=page_url_contains,
                    )
                return f"Typed into {selector}"
            except Exception as exc:
                raise BrowserServiceError(f"type failed: {exc}") from exc
        try:
            locator = page.locator(selector).first
            await locator.click(timeout=self.config.timeout_s * 1000)
            await locator.fill(text, timeout=self.config.timeout_s * 1000)
            if press_enter:
                await locator.press("Enter")
            return f"Typed into {selector}"
        except Exception as exc:
            raise BrowserServiceError(f"type failed: {exc}") from exc

    async def press_key(
        self,
        key: str,
        page_url_contains: str | None = None,
    ) -> dict[str, Any]:
        """Press a keyboard key on the current page or focused element."""
        key = str(key or "").strip()
        if not key:
            raise BrowserServiceError("press failed: key is required")

        key_map: dict[str, tuple[str, str, int]] = {
            "enter": ("Enter", "Enter", 13),
            "tab": ("Tab", "Tab", 9),
            "escape": ("Escape", "Escape", 27),
            "esc": ("Escape", "Escape", 27),
            "space": (" ", "Space", 32),
            "arrowdown": ("ArrowDown", "ArrowDown", 40),
            "arrowup": ("ArrowUp", "ArrowUp", 38),
            "arrowleft": ("ArrowLeft", "ArrowLeft", 37),
            "arrowright": ("ArrowRight", "ArrowRight", 39),
        }
        mapped = key_map.get(key.lower())

        page = await self.ensure_ready()
        if self.config.cdp_url:
            try:
                if mapped:
                    key_value, code, vk = mapped
                elif len(key) == 1:
                    key_value, code, vk = key, f"Key{key.upper()}", ord(key.upper())
                else:
                    key_value, code, vk = key, key, 0
                await self._cdp_send(
                    "Input.dispatchKeyEvent",
                    {"type": "keyDown", "key": key_value, "code": code, "windowsVirtualKeyCode": vk},
                    page_url_contains=page_url_contains,
                )
                await self._cdp_send(
                    "Input.dispatchKeyEvent",
                    {"type": "keyUp", "key": key_value, "code": code, "windowsVirtualKeyCode": vk},
                    page_url_contains=page_url_contains,
                )
                return {"ok": True, "key": key_value, "backend": "cdp"}
            except Exception as exc:
                raise BrowserServiceError(f"press failed: {exc}") from exc
        try:
            playwright_key = mapped[0] if mapped else key
            await page.keyboard.press(playwright_key)
            return {"ok": True, "key": playwright_key, "backend": "playwright"}
        except Exception as exc:
            raise BrowserServiceError(f"press failed: {exc}") from exc

    async def screenshot(
        self,
        output_path: str,
        full_page: bool = True,
        page_url_contains: str | None = None,
    ) -> str:
        page = await self.ensure_ready()
        out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.config.cdp_url:
            try:
                result = await self._cdp_send(
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": bool(full_page)},
                    page_url_contains=page_url_contains,
                )
                raw = result.get("data")
                if not raw:
                    raise BrowserServiceError("screenshot failed: no image data returned")
                out.write_bytes(base64.b64decode(raw))
                return str(out)
            except Exception as exc:
                raise BrowserServiceError(f"screenshot failed: {exc}") from exc
        try:
            await page.screenshot(path=str(out), full_page=full_page)
            return str(out)
        except Exception as exc:
            raise BrowserServiceError(f"screenshot failed: {exc}") from exc

    async def list_tabs(self) -> list[dict[str, Any]]:
        await self.ensure_ready()
        if self.config.cdp_url:
            tabs = await self.cdp_tabs()
            return [
                {
                    "index": idx,
                    "url": tab.get("url", ""),
                    "title": tab.get("title", ""),
                }
                for idx, tab in enumerate(tabs)
            ]
        if self._context is None:
            return []
        tabs = []
        for idx, p in enumerate(self._context.pages):
            tabs.append({"index": idx, "url": p.url, "title": await p.title()})
        return tabs

    async def recent_network(self) -> list[dict[str, str]]:
        await self.ensure_ready()
        return [event.__dict__ for event in list(self._network_events)]
