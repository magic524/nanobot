<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot：超轻量个人 AI Agent</h1>
</div>

🐈 **nanobot** 是一个受 OpenClaw 启发的超轻量个人 AI Agent。

⚡ 以极小代码量实现 Agent 核心能力，便于学习、改造与二次开发。

📏 实时代码行数可用以下命令查看：

```bash
bash core_agent_lines.sh
```

## 特性概览

- 超轻量：启动快、资源占用低。
- 研究友好：代码清晰，适合阅读和实验。
- 多通道：支持 Telegram、Discord、微信、Slack、邮箱等。
- 多模型：支持 OpenRouter、Anthropic、OpenAI、Ollama、vLLM、OVMS 等。
- 可扩展：支持 MCP 工具、技能系统、Python SDK。
- 可运行：支持 CLI、Gateway、OpenAI 兼容 API、Docker、systemd。

## 安装

> 如果你要跟进最新功能，建议源码安装。
> 如果你更重视稳定性，建议使用 PyPI 或 uv。

### 1) 源码安装（推荐开发）

```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .
```

### 2) 使用 uv 安装（稳定且快速）

```bash
uv tool install nanobot-ai
```

### 3) 使用 pip 安装（稳定版）

```bash
pip install nanobot-ai
```

### 升级

```bash
pip install -U nanobot-ai
nanobot --version
```

## 快速开始

### 1) 初始化

```bash
nanobot onboard
```

如需交互式向导：

```bash
nanobot onboard --wizard
```

### 2) 编辑配置文件

默认配置文件：`~/.nanobot/config.json`

至少需要配置两项：

- Provider API Key（示例 OpenRouter）
- 默认模型（可选固定 provider）

示例：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter"
    }
  }
}
```

### 3) 启动聊天

```bash
nanobot agent
```

## 常用命令速查

```bash
nanobot onboard                          # 初始化默认实例
nanobot onboard -c <config> -w <ws>     # 初始化指定实例
nanobot agent                            # 进入交互聊天
nanobot agent -m "你好"                  # 单次消息模式
nanobot agent -c <config> -w <ws>        # 指定配置/工作区运行
nanobot gateway                          # 启动网关（对接通道）
nanobot serve                            # 启动 OpenAI 兼容 API
nanobot status                           # 查看状态
nanobot channels login <channel>         # 通道登录（如 weixin / whatsapp）
nanobot channels status                  # 查看通道状态
```

## In-Chat 命令

以下命令可在聊天中直接输入：

- `/new`：开启新会话
- `/stop`：停止当前任务
- `/restart`：重启 bot
- `/status`：查看运行状态（含上下文占用）
- `/dream`：执行一次记忆整理
- `/dream-log`：查看最近记忆变更
- `/dream-restore`：恢复记忆版本
- `/help`：帮助信息

## 多实例（强烈推荐）

如果你希望“研究 / 生产 / 测试”彼此隔离，建议使用多实例。

### 初始化多个实例

```bash
nanobot onboard --config ~/.nanobot-research/config.json --workspace ~/.nanobot-research/workspace
nanobot onboard --config ~/.nanobot-prod/config.json --workspace ~/.nanobot-prod/workspace
nanobot onboard --config ~/.nanobot-test/config.json --workspace ~/.nanobot-test/workspace
```

### 运行指定实例

```bash
nanobot gateway --config ~/.nanobot-research/config.json
nanobot agent -c ~/.nanobot-research/config.json -m "你好"
```

## 工作区与会话说明

- `workspace`：文件读写、技能、心跳任务等运行目录。
- `session`：对话上下文。
- `/new`：只重置当前会话，不会切换 workspace。

## Provider（模型后端）

nanobot 支持主流云端与本地后端，包括但不限于：

- `openrouter`
- `anthropic`
- `openai`
- `ollama`（本地）
- `vllm`（本地）
- `ovms`（本地）
- `github_copilot`（OAuth）
- `openai_codex`（OAuth）

### Ollama 本地示例

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

## 通道（Chat Apps）

支持：Telegram、Discord、WhatsApp、Weixin、Feishu、Slack、Matrix、Email、QQ、Wecom、Mochat。

通用流程：

1. 在平台创建机器人并拿到凭据
2. 写入 `config.json` 对应 `channels.<name>`
3. 执行 `nanobot gateway`

## MCP（模型上下文协议）

支持将外部 MCP Server 作为工具接入。

示例：

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "remote": {
        "url": "https://example.com/mcp/",
        "headers": {
          "Authorization": "Bearer xxxxx"
        }
      }
    }
  }
}
```

## 安全建议

生产环境建议：

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

- `restrictToWorkspace=true`：限制工具访问范围。
- `sandbox=bwrap`：Linux 下对命令执行做沙箱隔离。

## Python SDK

```python
from nanobot import Nanobot

bot = Nanobot.from_config()
result = await bot.run("Summarize the README")
print(result.content)
```

可用 `session_key` 做会话隔离：

```python
await bot.run("hi", session_key="user-alice")
await bot.run("hi", session_key="task-42")
```

## OpenAI 兼容 API

```bash
pip install "nanobot-ai[api]"
nanobot serve
```

默认地址：`127.0.0.1:8900`

接口：

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

## Docker

```bash
docker build -t nanobot .
docker run -v ~/.nanobot:/home/nanobot/.nanobot --rm nanobot onboard
docker run -v ~/.nanobot:/home/nanobot/.nanobot --rm nanobot agent -m "Hello"
```

## Linux systemd（用户服务）

核心命令：

```bash
systemctl --user daemon-reload
systemctl --user enable --now nanobot-gateway
systemctl --user status nanobot-gateway
journalctl --user -u nanobot-gateway -f
```

## 项目结构

```text
nanobot/
├── agent/      # Agent 核心循环、上下文、记忆、工具
├── skills/     # 内置技能
├── channels/   # 各平台通道接入
├── bus/        # 消息路由
├── cron/       # 定时任务
├── heartbeat/  # 周期唤醒
├── providers/  # 模型后端
├── session/    # 会话管理
├── config/     # 配置加载与 schema
└── cli/        # 命令行入口
```

## 贡献指南

欢迎提 PR。

分支策略：

- `main`：稳定修复与小改动
- `nightly`：实验功能与可能 breaking changes

提交前建议：

1. 小步提交（一个 PR 一个目的）
2. 提供复现步骤和验证结果
3. 避免混入个人配置与无关改动

---

如果你想要与原英文 README 完全逐段对照的版本，可以在此文件基础上继续补全细节章节。