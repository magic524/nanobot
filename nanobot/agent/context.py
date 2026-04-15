"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any

from nanobot.utils.helpers import current_time_str

from nanobot.agent.memory import MemoryStore
from nanobot.utils.prompt_templates import render_template
from nanobot.agent.skills import SkillsLoader
from nanobot.utils.helpers import build_assistant_message, detect_image_mime


class ContextBuilder:
    """Builds the context (system prompt + messages) for the agent."""

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"
    _MAX_RECENT_HISTORY = 50

    def __init__(self, workspace: Path, timezone: str | None = None):
        self.workspace = workspace
        self.timezone = timezone
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        channel: str | None = None,
        session_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Build the system prompt from identity, bootstrap files, memory, and skills."""
        parts = [self._get_identity(channel=channel)]

        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(render_template("agent/skills_section.md", skills_summary=skills_summary))

        entries = self.memory.read_unprocessed_history(since_cursor=self.memory.get_last_dream_cursor())
        if entries:
            capped = entries[-self._MAX_RECENT_HISTORY:]
            parts.append("# Recent History\n\n" + "\n".join(
                f"- [{e['timestamp']}] {e['content']}" for e in capped
            ))

        web_mode = self._build_web_mode_section(session_metadata or {})
        if web_mode:
            parts.append(web_mode)

        return "\n\n---\n\n".join(parts)

    def _get_identity(self, channel: str | None = None) -> str:
        """Get the core identity section."""
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        return render_template(
            "agent/identity.md",
            workspace_path=workspace_path,
            runtime=runtime,
            platform_policy=render_template("agent/platform_policy.md", system=system),
            channel=channel or "",
        )

    @staticmethod
    def _build_runtime_context(
        channel: str | None, chat_id: str | None, timezone: str | None = None,
    ) -> str:
        """Build untrusted runtime metadata block for injection before the user message."""
        lines = [f"Current Time: {current_time_str(timezone)}"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    @staticmethod
    def _merge_message_content(left: Any, right: Any) -> str | list[dict[str, Any]]:
        if isinstance(left, str) and isinstance(right, str):
            return f"{left}\n\n{right}" if left else right

        def _to_blocks(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [item if isinstance(item, dict) else {"type": "text", "text": str(item)} for item in value]
            if value is None:
                return []
            return [{"type": "text", "text": str(value)}]

        return _to_blocks(left) + _to_blocks(right)

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _build_web_mode_section(session_metadata: dict[str, Any]) -> str:
        """Inject browser-first operating guidance for sessions that enable max web mode."""
        if not session_metadata.get("max_web_permission_mode"):
            return ""

        return """# Web Agent Mode

The user has enabled "maximum web permission" for this session. For webpage and web app tasks, you should actively use the browser automation framework instead of stopping at high-level guidance.

When a task involves interacting with a website, prefer this workflow:
1. Inspect or select the right tab with `browser_cdp_tabs` or `browser_tabs`.
2. Open the target page with `browser_open` if needed.
3. Read page state with `browser_eval`, `browser_snapshot`, or `browser_element_probe`.
4. Re-locate the exact target element on the current page immediately before any page-specific action, preferably with `browser_find_action_target` for controls like buttons, tabs, likes, favorites, or submit actions.
5. If needed, inspect likely scrollable containers with `browser_inspect_scroll_targets`.
6. Bring off-screen or lazy-loaded content into view with `browser_scroll` or `browser_scroll_into_view` before concluding that the content is unavailable.
7. After scrolling or navigation, use `browser_wait_for` to verify that the target content actually appeared.
8. For lazy-loaded feeds, comments, or result lists, use `browser_wait_for_change` and `browser_collect_lazy_items` to confirm that scrolling actually produced new content instead of assuming it did.
9. If the goal is "find and trigger a labeled control on the current page", prefer `browser_click_action_target` instead of manually reusing stale coordinates.
10. Otherwise perform the smallest necessary action with `browser_click`, `browser_click_point`, `browser_type`, or `browser_press`.
11. Verify the result with `browser_eval`, `browser_element_probe`, or `browser_screenshot`.

After search, navigation, popup, or any action that may open a new tab, you must refresh tab selection again before continuing.
Do not assume the original tab remains the target tab after search results or website redirects.
Do not reuse element coordinates, selector assumptions, or button positions from a previous page, previous tab, or earlier step after navigation.
For any action such as clicking a like button, submit button, search result, or video card:
- first confirm the active target tab,
- then probe the target element again on that exact page,
- then execute the action,
- then verify the result.
Typing into a field does not finish a search or form interaction by itself. If the task implies submit/search/go/login and the page did not change yet, submit it explicitly by clicking a labeled submit/search control or pressing Enter with `browser_press`, then verify that the page or results changed.
If the user gives an exact URL or a stable resource identifier that can be mapped to a canonical page URL, opening that page directly is often more reliable than homepage search UI.
If the same interaction pattern fails twice in a row, do not keep repeating it. Change strategy. Examples:
- if homepage search input did not navigate, switch to a direct search results URL or a canonical resource URL;
- if plain DOM selectors return empty on a modern web app, inspect web components and shadow roots with `browser_eval` instead of retrying the same selector;
- if scrolling does not reveal new content, inspect likely scroll containers first, then scroll the correct container, then use `browser_wait_for_change` or `browser_collect_lazy_items` to confirm the page actually changed.
When extracting content from modern web apps, remember that useful data may live in:
- shadow DOM trees,
- web components,
- page-initialized state objects,
- lazily mounted sections that only appear after verified scrolling.
If the target page was opened in a new tab, prefer closing that tab when the task says to return, instead of blindly using `history.back()`.

Use this framework as the default second choice whenever plain reasoning is not enough to complete a webpage task.
Do not claim browser tasks are impossible until you have checked whether the browser tools can handle them.
If the user says something short like "再试" or "继续" while the session is already in a webpage task, interpret that as a request to retry the previous webpage workflow, not as a request for a high-level explanation.
If the browser may be unavailable, first attempt the relevant browser tools so the runtime can auto-launch or reconnect before telling the user to reopen Chrome manually.
Keep actions scoped to the user's stated goal and report findings succinctly."""

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        current_role: str = "user",
        session_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        runtime_ctx = self._build_runtime_context(channel, chat_id, self.timezone)
        user_content = self._build_user_content(current_message, media)

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        if isinstance(user_content, str):
            merged = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content
        messages = [
            {
                "role": "system",
                "content": self.build_system_prompt(
                    skill_names,
                    channel=channel,
                    session_metadata=session_metadata,
                ),
            },
            *history,
        ]
        if messages[-1].get("role") == current_role:
            last = dict(messages[-1])
            last["content"] = self._merge_message_content(last.get("content"), merged)
            messages[-1] = last
            return messages
        messages.append({"role": current_role, "content": merged})
        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            # Detect real MIME type from magic bytes; fallback to filename guess
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self, messages: list[dict[str, Any]],
        tool_call_id: str, tool_name: str, result: Any,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    def add_assistant_message(
        self, messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        messages.append(build_assistant_message(
            content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        ))
        return messages
