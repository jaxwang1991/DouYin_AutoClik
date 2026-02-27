# 抖音直播间自动点赞助手

基于 Python + Playwright 实现的抖音直播间自动化工具。支持自动点赞、AI 智能评论、音频转录等功能，内置多种防风控策略，稳定高效。

## 功能特性

### 自动点赞
- **拟人化点击**: 随机间隔 + 随机位置，模拟真实用户操作
- **智能循环模式**: 工作 X 分钟，休息 Y 分钟，避免长时间连续操作
- **实时倒计时**: 休息状态下显示剩余时间
- **多种运行模式**: 显示浏览器 / 后台静默运行

### AI 智能评论
- **画面理解**: 定时截图分析直播内容
- **语音上下文**: 录制直播间音频并转录（支持 DashScope Qwen3-ASR）
- **智能生成**: 基于画面 + 语音生成相关评论
- **去重机制**: 历史评论记录，避免重复发送
- **灵活配置**: 支持自定义 API 密钥、模型参数
- **历史参考开关**: 可选择是否参考历史评论生成新内容

### 自动异常处理
- **验证码检测**: 识别滑块/拼图验证码，自动暂停等待人工处理
- **手速冷却**: 检测到"手速太快"提示时自动冷却 3 分钟
- **直播结束检测**: 自动检测直播状态并停止任务
- **状态恢复**: 验证/冷却完成后自动恢复运行

### 账号管理
- **扫码登录**: 一次登录，长期有效（状态保存至 `data/state.json`）
- **游客模式**: 未登录状态也可运行（部分功能受限）

## 快速开始

### 1. 环境安装

双击运行 `setup.bat` 自动安装依赖：

```batch
setup.bat
```

或手动安装：

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 启动程序

双击运行 `run_gui.bat` 启动图形界面：

```batch
run_gui.bat
```

或使用 Python 直接运行：

```bash
python gui.py        # GUI 模式
python main.py <url> # CLI 模式
```

### 3. 使用步骤

1. **扫码登录**（推荐）: 点击"扫码登录"按钮，使用抖音 App 扫码
2. **输入链接**: 粘贴直播间分享链接或网址
3. **配置参数**:
   - 循环模式：设置工作时长和休息时长
   - 运行模式：选择是否显示浏览器窗口
   - AI 评论：配置 API 密钥和模型参数
4. **开始任务**: 点击"开始任务"按钮

## 脚本说明

| 脚本 | 说明 |
|-----|------|
| `run_gui.bat` | 启动图形界面 |
| `run.bat` | 直接运行主程序 |
| `login.bat` | 独立扫码登录 |
| `setup.bat` | 安装依赖和浏览器驱动 |
| `build.bat` | 打包为可执行文件（调用 PowerShell） |
| `build.ps1` | PowerShell 打包脚本（自动化构建） |

## 系统架构

### 任务状态机

```
IDLE → STARTING → LIKING → [RESTING / PAUSED_FOR_CAPTCHA / COOLDOWN] → STOPPED
         ↑                                                      ↓
         └──────────────────────────────────────────────────────┘
```

| 状态 | 说明 | 触发条件 |
|-----|------|---------|
| `IDLE` | 空闲状态 | 程序启动或任务停止 |
| `STARTING` | 启动中 | 点击"开始任务" |
| `LIKING` | 点赞运行中 | 进入直播间，开始点赞 |
| `RESTING` | 休息中 | 循环模式下达到工作时长 |
| `PAUSED_FOR_CAPTCHA` | 验证码暂停 | 检测到验证码弹窗 |
| `COOLDOWN` | 冷却中 | 检测到"手速太快"提示 |
| `STOPPED` | 已停止 | 点击"停止"或异常终止 |

### 线程与异步模型

GUI 采用 **线程 + 异步事件循环** 模式：

```
┌─────────────────┐     ┌──────────────────────┐
│   Tkinter GUI   │ ←→ │  Async Event Loop     │
│   (主线程)       │     │  (独立线程)           │
└─────────────────┘     └──────────────────────┘
         ↑                        ↑
         │                        │
    after() 调度         run_coroutine_threadsafe()
```

- GUI 在主线程运行，通过 `root.after()` 异步更新界面
- Playwright 异步操作在独立线程的事件循环中执行
- 使用 `asyncio.run_coroutine_threadsafe()` 跨线程调度任务

### AI 评论流程

```
┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────┐
│ 定时截图 │ → │ 音频录制 │ → │ 组装上下文  │ → │ API 调用 │
└─────────┘    └──────────┘    └─────────────┘    └──────────┘
                                              ↓
                                        ┌──────────┐
                                        │ 发送评论 │
                                        └──────────┘
```

1. 定时截图（base64 JPEG）
2. 音频录制与转录（DashScope Qwen3-ASR）
3. 组装消息：系统提示词 + 历史评论去重 + 语音上下文 + 画面
4. 调用 OpenAI 兼容 API（Dashscope Qwen3-Omni）
5. 自动发送评论到直播间

## 核心模块

| 模块 | 说明 |
|-----|------|
| `gui.py` | 图形化界面（Tkinter），通过独立线程运行异步事件循环 |
| `liker.py` | 核心点赞逻辑与浏览器控制，继承自 BrowserBase |
| `auth.py` | 扫码登录功能 |
| `base.py` | 浏览器操作基类，处理 Playwright 启动、反检测脚本、状态保存/加载 |
| `audio_handler.py` | 音频录制与转录（DashScope Qwen3-ASR） |
| `config.py` | 集中配置管理，包含所有默认值 |
| `build_config.py` | 打包环境路径配置 |
| `version.py` | 版本号配置（统一版本管理） |
| `config_wizard.py` | 配置向导（首次运行时创建 config.json） |

## 配置说明

配置文件保存至 `data/config.json`，优先级：**GUI 输入 > config.json > config.py 默认值**

### AI 评论配置

```json
{
  "ai_enabled": true,
  "ai_api_key": "YOUR_API_KEY",
  "ai_model": "qwen-plus",
  "ai_comment_interval_min": 60,
  "ai_comment_interval_max": 120,
  "ai_temperature": 1.0,
  "ai_use_audio": true,
  "ai_use_comment_history": true,
  "ai_enable_thinking": true
}
```

**配置项说明**：
- `ai_enabled`: 是否启用 AI 评论
- `ai_api_key`: DashScope API 密钥
- `ai_model`: 使用的模型（qwen-plus、qwen3-omni-flash 等）
- `ai_temperature`: 生成温度（0.0-2.0，值越高越随机）
- `ai_use_audio`: 是否使用音频转录作为上下文
- `ai_use_comment_history`: 是否参考历史评论避免重复
- `ai_enable_thinking`: 是否启用深度思考功能（提高评论质量）

### 循环模式配置

```json
{
  "use_cycle_mode": true,
  "work_duration": 10,
  "rest_duration": 5
}
```

### ASR 音频转录配置

```json
{
  "asr_model": "qwen3-asr-flash-filetrans",
  "asr_poll_interval": 2,
  "asr_max_poll_time": 300
}
```

## 数据文件

| 文件 | 说明 | 是否提交 |
|-----|------|---------|
| `data/state.json` | 登录状态（敏感信息） | ❌ 否 |
| `data/config.json` | 运行配置 | ❌ 否 |
| `data/comment_history.json` | AI 评论历史 | ❌ 否 |
| `logs/` | 日志、截图、音频文件 | ❌ 否 |
| `logs/audio/` | 录制的音频文件 | ❌ 否 |
| `logs/transcripts/` | 音频转录文本 | ❌ 否 |

## 项目结构

```
DouYin_AutoClik/
├── gui.py                 # 图形化界面
├── main.py                # CLI 入口
├── liker.py               # 核心点赞逻辑
├── auth.py                # 扫码登录
├── base.py                # 浏览器基类（反检测、状态管理）
├── audio_handler.py       # 音频录制与转录
├── config.py              # 配置管理（默认值）
├── build_config.py        # 打包环境路径配置
├── version.py             # 版本号配置
├── config_wizard.py       # 首次运行配置向导
├── run_gui.bat            # GUI 启动脚本
├── run.bat                # 直接运行脚本
├── login.bat              # 登录脚本
├── setup.bat              # 环境安装
├── build.bat              # 打包脚本（调用 PowerShell）
├── build.ps1              # PowerShell 自动化打包脚本
├── DouYin_AutoClik.spec   # PyInstaller 配置
├── requirements.txt       # Python 依赖
├── README.md              # 本文件（开发者文档）
├── README.txt             # 打包用户文档
├── CLAUDE.md              # Claude Code 项目说明
└── .gitignore             # Git 忽略规则
```

## 注意事项

- **验证码处理**: 检测到验证码时会暂停，请手动完成验证后程序会自动恢复
- **适度使用**: 建议合理设置点击频率和休息时间，避免长时间连续运行
- **API 配额**: AI 评论功能需要配置 DashScope API 密钥，注意使用配额
- **音频录制**: 音频转录功能需要系统声卡支持
- **游客模式**: 未登录状态也可运行，但 AI 评论等部分功能可能受限
- **路径配置**: 打包后的 exe 会自动处理路径问题，配置和状态保存在 `data/` 目录

## 隐私与安全

### 已忽略的敏感文件

| 文件 | 内容 | Git 追踪 |
|-----|------|---------|
| `state.json` | 登录状态、Cookie | ❌ 否 |
| `config.json` | API 密钥、个人配置 | ❌ 否 |
| `comment_history.json` | 评论历史 | ❌ 否 |
| `logs/` | 运行日志、截图、音频 | ❌ 否 |
| `*.spec` | PyInstaller 配置 | ❌ 否 |

**重要**: 请勿将包含 API 密钥或登录状态的文件提交到公共仓库。

## 依赖项

```
playwright   # 浏览器自动化
openai       # AI API 客户端
dashscope    # 阿里云 DashScope API
soundcard    # 音频录制
soundfile    # 音频文件处理
numpy        # 数值计算
```

## 打包发布

### 自动化打包

双击运行 `build.bat` 调用 PowerShell 自动化打包：

```batch
build.bat
```

### 打包流程

1. **PyInstaller 构建** - 打包 Python 代码为 exe
2. **Playwright 浏览器** - 自动复制 chromium + ffmpeg（仅复制必要组件）
3. **目录结构** - 创建 data/logs 子目录
4. **README 更新** - 自动替换版本号并复制到输出目录
5. **Zip 压缩** - 生成 `DouYin_AutoClik-v{version}-win64.zip`

### 输出产物

```
dist/DouYin_AutoClik-v1.0.0-win64.zip
└── DouYin_AutoClik/
    ├── DouYin_AutoClik.exe      # 无控制台窗口 GUI 程序
    ├── _internal/
    │   └── playwright/driver/
    │       ├── chromium-1200/    # ~387MB
    │       └── ffmpeg-1011/      # ~50MB
    ├── data/                     # 运行时数据目录
    │   ├── logs/
    │   │   ├── audio/
    │   │   └── transcripts/
    │   └── state.json
    └── README.txt
```

**体积参考**：
- 打包文件夹：~600MB
- Zip 压缩后：~247MB
- 压缩率：~59%

### 注意事项

- 打包产物不包含 `*.spec`、`logs/`、`data/`、`*.log`（由 .gitignore 控制）
- Playwright 浏览器仅复制必要组件（chromium + ffmpeg），大幅减小体积

## 许可证

MIT License

## 版本历史

- **v1.0.0** (2026-02-27)
  - 初始版本发布
  - 自动点赞、AI 评论、音频转录
  - 图形化界面、验证码检测
  - 循环模式、防风控策略
  - 优化打包流程（PowerShell 自动化）
  - 修复登录界面误判为验证码问题
  - 修复协程未等待警告
  - 窗口模式打包（无控制台）
