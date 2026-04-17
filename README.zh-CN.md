<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot：超轻量个人 AI Agent</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanobot-ai"><img src="https://static.pepy.tech/badge/nanobot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://nanobot.wiki/docs/0.1.5/getting-started/nanobot-overview"><img src="https://img.shields.io/badge/Docs-nanobot.wiki-blue?style=flat&logo=readthedocs&logoColor=white" alt="Docs"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
    <a href="https://discord.gg/MnCvHqpUGB"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

🐈 **nanobot** 是一个受 [OpenClaw](https://github.com/openclaw/openclaw) 启发的**超轻量**个人 AI Agent。

⚡ 以**少 99% 代码量**交付 Agent 核心能力。

📏 可随时运行 `bash core_agent_lines.sh` 查看实时核心代码行数。

## 📢 更新动态

- **2026-04-05** 🚀 发布 **v0.1.5**：长任务更稳、Dream 双阶段记忆、生产级沙箱与 Agent SDK。详见 [release notes](https://github.com/HKUDS/nanobot/releases/tag/v0.1.5)。
- **2026-04-04** 🚀 新增 Jinja2 响应模板、Dream 记忆增强、重试策略更智能。
- **2026-04-03** 🧠 新增 Xiaomi MiMo provider，展示 reasoning 内容，优化 Telegram 体验。
- **2026-04-02** 🧱 长时间运行任务更可靠，核心运行时进一步加固。
- **2026-04-01** 🔑 恢复 GitHub Copilot 认证，强化 workspace 路径约束，修复 OpenRouter Claude cache。
- **2026-03-31** 🛰️ 优化微信多模态对齐、Discord/Matrix 细节、Python SDK、MCP 与工具链。
- **2026-03-30** 🧩 收紧 OpenAI-compatible API 行为，支持可组合 agent lifecycle hooks。
- **2026-03-29** 💬 修复微信语音/输入/二维码/媒体稳定性与 OpenAI-compatible API 会话行为。
- **2026-03-28** 📚 刷新 provider 文档并修正 skill 模板文案。
- **2026-03-27** 🚀 发布 **v0.1.4.post6**：架构解耦、移除 litellm、端到端流式输出、微信通道与安全修复。详见 [release notes](https://github.com/HKUDS/nanobot/releases/tag/v0.1.4.post6)。

<details>
<summary>更早更新</summary>

- **2026-03-26** 🏗️ 提取 Agent runner，统一生命周期 hook，优化流式边界合并。
- **2026-03-25** 🌏 新增 StepFun provider、可配置时区、Gemini thought signature。
- **2026-03-24** 🔧 优化微信兼容性、飞书 CardKit 流式渲染，重组测试套件。
- **2026-03-23** 🔧 重构插件命令路由，完善 WhatsApp/微信媒体与统一登录 CLI。
- **2026-03-22** ⚡ 端到端流式输出、微信通道、Anthropic cache 优化、`/status` 命令。
- **2026-03-21** 🔒 用原生 `openai` + `anthropic` SDK 替换 `litellm`。详见 [commit](https://github.com/HKUDS/nanobot/commit/3dfdab7)。
- **2026-03-20** 🧙 新增交互式初始化向导，可选择 provider 并自动补全模型名。
- **2026-03-19** 💬 强化 Telegram 稳定性，飞书代码块渲染更准确。
- **2026-03-18** 📷 Telegram 现可通过 URL 发送媒体，Cron 展示更易读。
- **2026-03-17** ✨ 飞书格式提升、Slack 完成后表情反馈、自定义 header 与图片处理更稳。

</details>

> 🐈 nanobot 仅用于教育、研究与技术交流，不涉及任何官方代币或加密货币项目。

## 核心特性

- **超轻量**：实现精简，启动快，资源占用低，适合长时间运行。
- **研究友好**：代码清晰，适合阅读、修改、实验和二次开发。
- **运行可靠**：支持长任务、Dream 记忆、重试、会话隔离与恢复。
- **易于扩展**：支持 MCP、技能系统、插件通道、Python SDK。
- **多通道**：支持 Telegram、Discord、Slack、微信、飞书、邮箱等。
- **多后端**：支持 OpenRouter、Anthropic、OpenAI、Ollama、vLLM、OVMS、GitHub Copilot、OpenAI Codex 等。

## 🏗️ 架构

<p align="center">
  <img src="nanobot_arch.png" alt="nanobot architecture" width="800">
</p>

## 目录

- [更新动态](#-更新动态)
- [核心特性](#核心特性)
- [架构](#️-架构)
- [安装](#-安装)
- [快速开始](#-快速开始)
- [Chat Apps](#-chat-apps)
- [配置](#️-配置)
- [Providers](#-providers)
- [统一会话](#-统一会话)
- [多实例](#-多实例)
- [记忆](#-记忆)
- [CLI 参考](#-cli-参考)
- [聊天内命令](#-聊天内命令)
- [Python SDK](#-python-sdk)
- [OpenAI 兼容 API](#-openai-兼容-api)
- [Docker](#-docker)
- [Linux 服务](#-linux-服务)
- [项目结构](#-项目结构)
- [贡献](#-贡献)

## 📦 安装

> [!IMPORTANT]
> README 可能会先描述源码分支中的新功能。
> 如果你想体验最新能力与实验特性，建议源码安装。
> 如果你更重视日常稳定性，建议使用 PyPI 或 `uv`。

**源码安装**（最新功能，适合开发）

```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .
```

**使用 [uv](https://github.com/astral-sh/uv) 安装**（稳定、快速）

```bash
uv tool install nanobot-ai
```

**使用 PyPI 安装**（稳定版）

```bash
pip install nanobot-ai
```

### 升级到最新版本

**PyPI / pip**

```bash
pip install -U nanobot-ai
nanobot --version
```

**uv**

```bash
uv tool upgrade nanobot-ai
nanobot --version
```

**如果你在使用 WhatsApp**，升级后请重建本地 bridge：

```bash
rm -rf ~/.nanobot/bridge
nanobot channels login whatsapp
```

## 🚀 快速开始

> [!TIP]
> 请先在 `~/.nanobot/config.json` 中设置 API key。
> 全球用户推荐使用 [OpenRouter](https://openrouter.ai/keys)。
>
> 其他模型供应商见 [Providers](#-providers)。
> Web 搜索能力配置见英文文档中的 Web Search 章节。

**1. 初始化**

```bash
nanobot onboard
```

如果想使用交互式向导：

```bash
nanobot onboard --wizard
```

**2. 配置**（`~/.nanobot/config.json`）

通常只需要先配置两部分，其余选项都有默认值。

*设置 API key*（以 OpenRouter 为例）：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

*设置模型*（可选固定 provider，否则默认自动识别）：

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter"
    }
  }
}
```

**3. 开始聊天**

```bash
nanobot agent
```

到这里，你已经可以在 2 分钟内启动一个可用的 AI Agent。

## 💬 Chat Apps

nanobot 支持多种聊天平台：

- Telegram
- Discord
- Slack
- Weixin
- Wecom
- Feishu
- WhatsApp
- Matrix
- Email
- QQ
- Mochat
- DingTalk

基本流程通常是：

1. 在对应平台创建机器人并获取凭据。
2. 将配置写入 `config.json` 中的 `channels.<name>`。
3. 执行 `nanobot channels login <channel>` 完成交互式认证。
4. 启动 `nanobot gateway`。

## ⚙️ 配置

常用配置位于：

- `agents.defaults`：默认模型、workspace、上下文窗口、重试、Dream 等
- `providers`：模型供应商 API key / API base / 额外请求头
- `channels`：通道配置
- `tools`：web、exec、MCP、沙箱与访问范围限制

一个较完整的最小示例：

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter",
      "maxTokens": 8192,
      "contextWindowTokens": 65536,
      "temperature": 0.1,
      "timezone": "Asia/Shanghai"
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

### 安全建议

> [!TIP]
> 生产环境建议启用 workspace 限制与 shell 沙箱。

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "exec": {
      "sandbox": "bwrap"
    }
  }
}
```

说明：

- `restrictToWorkspace: true`：限制文件与命令工具只能访问 workspace 范围。
- `sandbox: "bwrap"`：在 Linux 上用 bubblewrap 隔离 shell exec。

### 时区

默认时区为 `UTC`。如果你希望 Agent 使用本地时间语境，可设置：

```json
{
  "agents": {
    "defaults": {
      "timezone": "Asia/Shanghai"
    }
  }
}
```

## 🔌 Providers

nanobot 当前支持的主要模型后端包括：

- `custom`
- `openrouter`
- `volcengine`
- `byteplus`
- `anthropic`
- `azure_openai`
- `openai`
- `deepseek`
- `groq`
- `gemini`
- `zhipu`
- `dashscope`
- `moonshot`
- `minimax`
- `mistral`
- `stepfun`
- `xiaomi_mimo`
- `ollama`
- `ovms`
- `vllm`
- `openai_codex`
- `github_copilot`
- `qianfan`

### OpenAI Codex（OAuth）

Codex 使用 OAuth，不依赖普通 API key。通常需要 ChatGPT Plus 或 Pro。

```bash
nanobot provider login openai-codex
```

然后在配置中设置模型：

```json
{
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.1-codex"
    }
  }
}
```

### GitHub Copilot（OAuth）

```bash
nanobot provider login github-copilot
```

配置模型：

```json
{
  "agents": {
    "defaults": {
      "model": "github-copilot/gpt-4.1"
    }
  }
}
```

### Ollama（本地）

先启动本地模型，例如：

```bash
ollama run llama3.2
```

然后在配置中加入：

```json
{
  "providers": {
    "ollama": {
      "apiBase": "http://localhost:11434"
    }
  },
  "agents": {
    "defaults": {
      "provider": "ollama",
      "model": "llama3.2"
    }
  }
}
```

### Custom Provider（任意 OpenAI-compatible 接口）

```json
{
  "providers": {
    "custom": {
      "apiKey": "your-api-key",
      "apiBase": "https://api.your-provider.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "your-model-name"
    }
  }
}
```

## 🔄 统一会话

默认情况下，不同 channel 与 chat ID 之间彼此独立。

如果你希望 Telegram、Discord、CLI 等共享同一段对话上下文，可以开启：

```json
{
  "agents": {
    "defaults": {
      "unifiedSession": true
    }
  }
}
```

## 🧩 多实例

nanobot 支持通过 `--config` 与 `--workspace` 运行多个独立实例。

这很适合将研究、生产、测试、本地模型等环境隔离开来。

### 初始化多个实例

```bash
nanobot onboard --config ~/.nanobot-research/config.json --workspace ~/.nanobot-research/workspace
nanobot onboard --config ~/.nanobot-discord/config.json --workspace ~/.nanobot-discord/workspace
nanobot onboard --config ~/.nanobot-local/config.json --workspace ~/.nanobot-local/workspace
```

### 运行指定实例

```bash
nanobot agent -c ~/.nanobot-research/config.json
nanobot gateway -c ~/.nanobot-discord/config.json
nanobot agent -c ~/.nanobot-local/config.json -w /tmp/nanobot-local-test
```

如果你是用某个实例启动 `gateway`，也可以在聊天中直接切换当前运行时实例，而不需要重启进程：

```text
/instance
/instance local
/instance research
```

`/instance` 会列出自动发现的配置，例如 `~/.nanobot/config.json` 和 `~/.nanobot-*/config.json`，然后切换到你选择的实例。

你也可以只临时覆盖 workspace：

```bash
nanobot agent -c ~/.nanobot-research/config.json -w /tmp/test-workspace
```

## 🧠 记忆

nanobot 使用分层记忆系统，既保持当前会话轻量，也保留长期上下文。

- `session.messages`：当前短期对话
- `memory/history.jsonl`：追加式压缩历史
- `SOUL.md`：Agent 的长期风格与语气
- `USER.md`：用户稳定偏好
- `memory/MEMORY.md`：项目、事实与长期上下文

Dream 会周期性运行，也可以手动触发，用于将历史整理进长期记忆。

## 💻 CLI 参考

| 命令 | 说明 |
|------|------|
| `nanobot onboard` | 在 `~/.nanobot/` 初始化配置与 workspace |
| `nanobot onboard -c <config> -w <workspace>` | 初始化指定实例 |
| `nanobot agent` | 启动本地 CLI 对话 |
| `nanobot agent -m "..."` | 单次消息模式 |
| `nanobot agent -c <config> -w <workspace>` | 指定配置 / workspace 运行 |
| `nanobot gateway` | 启动通道网关 |
| `nanobot serve` | 启动 OpenAI-compatible API |
| `nanobot status` | 查看整体状态 |
| `nanobot provider login openai-codex` | 执行 OAuth 登录 |
| `nanobot channels login <channel>` | 交互式登录某个 channel |
| `nanobot channels status` | 查看 channel 状态 |

交互模式退出方式：`exit`、`quit`、`/exit`、`/quit`、`:q` 或 `Ctrl+D`。

## 💬 聊天内命令

以下命令可在聊天中直接输入：

- `/new`：开始一个新会话
- `/stop`：停止当前任务
- `/restart`：重启 bot
- `/status`：查看 bot 运行状态
- `/instance`：列出已发现实例，或用 `/instance <name>` 切换实例
- `/dream`：立即执行一次 Dream 记忆整理
- `/dream-log`：查看最近一次 Dream 变更
- `/dream-log <sha>`：查看某次指定 Dream 变更
- `/dream-restore`：列出最近记忆版本
- `/dream-restore <sha>`：恢复到某次变更前的状态
- `/help`：显示帮助

## 🐍 Python SDK

```python
from nanobot import Nanobot

bot = Nanobot.from_config()
result = await bot.run("Summarize the README")
print(result.content)
```

如需隔离会话，可使用 `session_key`：

```python
await bot.run("hi", session_key="user-alice")
await bot.run("hi", session_key="task-42")
```

## 🌐 OpenAI 兼容 API

安装 API 依赖并启动：

```bash
pip install "nanobot-ai[api]"
nanobot serve
```

默认地址：`127.0.0.1:8900`

常用接口：

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

## 🐳 Docker

```bash
docker build -t nanobot .
docker run -v ~/.nanobot:/home/nanobot/.nanobot --rm nanobot onboard
docker run -v ~/.nanobot:/home/nanobot/.nanobot --rm nanobot agent -m "Hello"
```

## 🐧 Linux 服务

如果你希望长期运行 gateway，可以用 `systemd --user`：

```bash
systemctl --user daemon-reload
systemctl --user enable --now nanobot-gateway
systemctl --user status nanobot-gateway
journalctl --user -u nanobot-gateway -f
```

## 📁 项目结构

```text
nanobot/
├── agent/      # Agent 核心循环、上下文、记忆、工具
├── skills/     # 内置技能
├── channels/   # 多平台通道接入
├── bus/        # 消息路由
├── cron/       # 定时任务
├── heartbeat/  # 周期唤醒
├── providers/  # 模型后端
├── session/    # 会话管理
├── config/     # 配置加载与 schema
└── cli/        # 命令行入口
```

## 🤝 贡献

欢迎提交 PR。

推荐遵循项目当前分支策略：

- `main`：稳定修复与小改动
- `nightly`：实验性功能与可能存在 breaking changes 的更新

提交前建议：

1. 一个 PR 只做一件事，范围尽量小。
2. 写清楚复现步骤、修改内容与验证方式。
3. 不要混入个人配置、无关格式化或额外噪音改动。

如果你希望逐段对照英文 README 继续完善，这个中文版现在已经覆盖了首个 PR 最关键的信息结构，后续可以继续逐步补充更细的 provider、channel 与部署章节。
