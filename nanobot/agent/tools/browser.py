"""Managed browser tools powered by Playwright."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import BooleanSchema, IntegerSchema, StringSchema, tool_parameters_schema
from nanobot.browser.service import BrowserService, BrowserServiceError


class _BrowserTool(Tool):
    read_only = False

    def __init__(self, service: BrowserService, workspace: str):
        self.service = service
        self.workspace = Path(workspace)

    async def _safe_call(self, func, *args, **kwargs) -> str:
        try:
            result = await func(*args, **kwargs)
            return json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
        except BrowserServiceError as exc:
            return f"Error: {exc}"


@tool_parameters(
    tool_parameters_schema(
        url=StringSchema("URL to open in the managed browser"),
        wait_until={"type": "string", "enum": ["domcontentloaded", "load", "networkidle"], "default": "domcontentloaded"},
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab before navigation"),
        required=["url"],
    )
)
class BrowserOpenTool(_BrowserTool):
    name = "browser_open"
    description = "Open a URL in the managed browser and return page title/status."

    async def execute(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.navigate,
            url,
            wait_until=wait_until,
            page_url_contains=page_url_contains,
        )


@tool_parameters(tool_parameters_schema())
class BrowserTabsTool(_BrowserTool):
    name = "browser_tabs"
    description = "List current browser tabs with titles and URLs."
    read_only = True

    async def execute(self, **kwargs: Any) -> str:
        return await self._safe_call(self.service.list_tabs)


@tool_parameters(
    tool_parameters_schema(
        max_chars=IntegerSchema(12000, description="Maximum snapshot text length", minimum=500, maximum=50000),
    )
)
class BrowserSnapshotTool(_BrowserTool):
    name = "browser_snapshot"
    description = "Read visible page text from the managed browser after JS rendering."
    read_only = True

    async def execute(self, max_chars: int = 12000, **kwargs: Any) -> str:
        return await self._safe_call(self.service.snapshot, max_chars=max_chars)


@tool_parameters(
    tool_parameters_schema(
        script=StringSchema("JavaScript expression or IIFE to run in the current page"),
        await_promise=BooleanSchema(description="Await a returned promise", default=True),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["script"],
    )
)
class BrowserEvalTool(_BrowserTool):
    name = "browser_eval"
    description = "Run JavaScript in the current browser page. Useful for site-specific extraction and DOM inspection."

    async def execute(
        self,
        script: str,
        await_promise: bool = True,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.evaluate,
            script,
            await_promise=await_promise,
            page_url_contains=page_url_contains,
        )


@tool_parameters(
    tool_parameters_schema(
        selector=StringSchema("CSS selector to click"),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["selector"],
    )
)
class BrowserClickTool(_BrowserTool):
    name = "browser_click"
    description = "Click the first element matching a CSS selector."

    async def execute(
        self,
        selector: str,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(self.service.click, selector, page_url_contains=page_url_contains)


@tool_parameters(
    tool_parameters_schema(
        x=IntegerSchema(0, description="Viewport X coordinate", minimum=0),
        y=IntegerSchema(0, description="Viewport Y coordinate", minimum=0),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["x", "y"],
    )
)
class BrowserClickPointTool(_BrowserTool):
    name = "browser_click_point"
    description = "Click a viewport coordinate. Useful as a fallback when DOM click targets are unreliable."

    async def execute(
        self,
        x: int,
        y: int,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.click_point,
            x,
            y,
            page_url_contains=page_url_contains,
        )


@tool_parameters(
    tool_parameters_schema(
        selector=StringSchema("CSS selector to type into"),
        text=StringSchema("Text to enter"),
        press_enter=BooleanSchema(description="Press Enter after typing", default=False),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["selector", "text"],
    )
)
class BrowserTypeTool(_BrowserTool):
    name = "browser_type"
    description = "Type text into the first element matching a CSS selector."

    async def execute(
        self,
        selector: str,
        text: str,
        press_enter: bool = False,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.type_text,
            selector,
            text,
            press_enter=press_enter,
            page_url_contains=page_url_contains,
        )


@tool_parameters(
    tool_parameters_schema(
        path=StringSchema("Relative path inside workspace for screenshot output"),
        full_page=BooleanSchema(description="Capture the full page", default=True),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["path"],
    )
)
class BrowserScreenshotTool(_BrowserTool):
    name = "browser_screenshot"
    description = "Capture a screenshot from the managed browser into the workspace."

    async def execute(
        self,
        path: str,
        full_page: bool = True,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        output_path = self.workspace / path
        return await self._safe_call(
            self.service.screenshot,
            str(output_path),
            full_page=full_page,
            page_url_contains=page_url_contains,
        )


@tool_parameters(tool_parameters_schema())
class BrowserNetworkTool(_BrowserTool):
    name = "browser_network"
    description = "Show recent network requests observed in the managed browser."
    read_only = True

    async def execute(self, **kwargs: Any) -> str:
        return await self._safe_call(self.service.recent_network)


@tool_parameters(tool_parameters_schema())
class BrowserCDPTabsTool(_BrowserTool):
    name = "browser_cdp_tabs"
    description = "List page tabs from the configured CDP endpoint."
    read_only = True

    async def execute(self, **kwargs: Any) -> str:
        return await self._safe_call(self.service.cdp_tabs)


@tool_parameters(
    tool_parameters_schema(
        selector=StringSchema("Optional CSS selector"),
        text_hint=StringSchema("Optional text hint used to locate an element"),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
    )
)
class BrowserElementProbeTool(_BrowserTool):
    name = "browser_element_probe"
    description = "Inspect one page element and return text/rect/html."

    async def execute(
        self,
        selector: str | None = None,
        text_hint: str | None = None,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.element_probe,
            selector=selector,
            text_hint=text_hint,
            page_url_contains=page_url_contains,
        )


@tool_parameters(
    tool_parameters_schema(
        text_hint=StringSchema("Action label to locate on the current page, e.g. 点赞/收藏/提交"),
        page_url_contains=StringSchema("Optional substring to pick a matching CDP page/tab"),
        required=["text_hint"],
    )
)
class BrowserFindActionTargetTool(_BrowserTool):
    name = "browser_find_action_target"
    description = "Locate a likely actionable target on the current page and return a click point."
    read_only = True

    async def execute(
        self,
        text_hint: str,
        page_url_contains: str | None = None,
        **kwargs: Any,
    ) -> str:
        return await self._safe_call(
            self.service.find_action_target,
            text_hint,
            page_url_contains=page_url_contains,
        )


@tool_parameters(
    tool_parameters_schema(
        site=StringSchema("Target site name, e.g. douyin/bilibili/xiaohongshu"),
        limit=IntegerSchema(5, description="Maximum number of comments to read", minimum=1, maximum=20),
    )
)
class BrowserReadSocialCommentsTool(_BrowserTool):
    name = "browser_read_social_comments"
    description = "Read visible comments from Douyin/Bilibili/Xiaohongshu."
    read_only = True

    async def execute(self, **kwargs: Any) -> str:
        return "Error: browser_read_social_comments is not implemented yet."
