"""Browser tool configuration models."""

from pydantic import Field

from nanobot.config.schema import Base


class BrowserToolConfig(Base):
    """Configuration for managed browser tools."""

    enable: bool = False
    headless: bool = True
    cdp_url: str | None = None
    cdp_auto_launch_command: str | None = None
    cdp_auto_launch_cwd: str | None = None
    cdp_auto_launch_delay_s: int = Field(default=3, ge=1, le=30)
    cdp_http_timeout_s: int = Field(default=5, ge=1, le=30)
    cdp_ws_timeout_s: int = Field(default=10, ge=1, le=60)
    timeout_s: int = Field(default=20, ge=5, le=120)
    launch_timeout_s: int = Field(default=30, ge=5, le=180)
    user_data_dir: str = "~/.nanobot/browser-profile"
    locale: str = "zh-CN"
    browser_channel: str | None = None
    executable_path: str | None = None
    viewport_width: int = Field(default=1440, ge=320, le=4000)
    viewport_height: int = Field(default=900, ge=200, le=4000)
    max_snapshot_chars: int = Field(default=12000, ge=1000, le=50000)
    max_network_events: int = Field(default=25, ge=1, le=200)
    network_capture: bool = True
