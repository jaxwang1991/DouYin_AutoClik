# 抖音直播自动点赞助手打包 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 使用 PyInstaller 将项目打包为目录形式的 Windows 可执行程序，一键完成打包和浏览器复制。

**Architecture:**
- 创建 PyInstaller 规范文件（.spec）配置打包参数
- 修改 build.bat 合并浏览器复制功能
- 生成简化版用户文档 README.txt

**Tech Stack:**
- PyInstaller 6.0+
- Playwright（Chromium）
- Windows Batch

---

### Task 1: 创建 PyInstaller 规范文件

**Files:**
- Create: `DouYin_AutoClik.spec`

**Step 1: 创建 spec 文件**

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('playwright/driver/package/_internal', 'playwright/driver/package/_internal'),
    ],
    hiddenimports=['playwright.sync', 'soundcard', 'soundfile', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DouYin_AutoClik',
           debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
           upx_exclude=[], runtime_tmpdir=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               upx_exclude=[], name='DouYin_AutoClik')
```

**Step 2: 提交 spec 文件**

```bash
git add DouYin_AutoClik.spec
git commit -m "feat: 添加 PyInstaller 规范文件"
```

---

### Task 2: 修改 build.bat 脚本

**Files:**
- Modify: `build.bat`

**Step 1: 备份并删除 copy_browsers.bat（已废弃）**

```batch
del copy_browsers.bat
```

**Step 2: 重写 build.bat**

```batch
@echo off
echo ====================================
echo   DouYin AutoClik - Build Script
echo ====================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous build
if exist "build" (
    echo Cleaning previous build...
    rmdir /s /q build
)
if exist "dist\DouYin_AutoClik" (
    echo Cleaning previous dist...
    rmdir /s /q dist\DouYin_AutoClik
)

echo.
echo Starting PyInstaller build...
pyinstaller --clean DouYin_AutoClik.spec

if errorlevel 1 (
    echo.
    echo Build failed! Please check errors above.
    pause
    exit /b 1
)

REM Copy Playwright browsers
set PLAYWRIGHT_PATH=%LOCALAPPDATA%\ms-playwright
set DEST_PATH=dist\DouYin_AutoClik\_internal\playwright\driver\package

if not exist "%PLAYWRIGHT_PATH%" (
    echo.
    echo WARNING: Playwright browsers not found!
    echo Please run: python -m playwright install chromium
    echo.
)

if exist "%PLAYWRIGHT_PATH%" (
    echo.
    echo Copying Playwright browsers...
    xcopy /E /I /Y "%PLAYWRIGHT_PATH%" "%DEST_PATH%"
)

REM Create data directory structure
if not exist "dist\DouYin_AutoClik\data" mkdir "dist\DouYin_AutoClik\data"
if not exist "dist\DouYin_AutoClik\data\logs" mkdir "dist\DouYin_AutoClik\data\logs"
if not exist "dist\DouYin_AutoClik\data\logs\audio" mkdir "dist\DouYin_AutoClik\data\logs\audio"
if not exist "dist\DouYin_AutoClik\data\logs\transcripts" mkdir "dist\DouYin_AutoClik\data\logs\transcripts"

echo.
echo ====================================
echo   Build completed successfully!
echo ====================================
echo.
echo Package location: dist\DouYin_AutoClik\
echo.

pause
```

**Step 3: 提交 build.bat 修改**

```bash
git add build.bat
git add -u copy_browsers.bat
git commit -m "feat: 增强 build.bat，集成浏览器复制功能"
```

---

### Task 3: 创建简化版用户文档

**Files:**
- Create: `README.txt`

**Step 1: 创建 README.txt**

```
====================================
  抖音直播间自动点赞助手
====================================

快速开始:
1. 双击 DouYin_AutoClik.exe 启动程序
2. 扫码登录（推荐）
3. 输入直播间链接
4. 配置参数后开始任务

详细文档请访问: https://github.com/jaxwang1991/DouYin_AutoClik

功能特性:
- 自动点赞（拟人化点击）
- AI 智能评论（需配置 API）
- 音频转录（DashScope）
- 循环模式
- 验证码自动检测

注意事项:
- 首次使用请扫码登录
- 合理设置点击频率和休息时间
- AI 评论功能需要配置 DashScope API 密钥

====================================
  版本: 1.0.0
  更新: 2026-02-23
====================================
```

**Step 2: 提交 README.txt**

```bash
git add README.txt
git commit -m "docs: 添加简化版用户文档 README.txt"
```

---

### Task 4: 更新 .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: 添加 README.txt 到忽略列表（只忽略 txt 版本，保留 md 版本）**

```gitignore
# 用户文档
CLAUDE.md
README.txt
README.md  # 保留 md 版本在版本控制中
```

**Step 2: 提交 .gitignore 修改**

```bash
git add .gitignore
git commit -m "chore: 从 gitignore 中移除 README.txt"
```

---

### Task 5: 测试打包流程

**Files:**
- 无修改，仅验证

**Step 1: 运行打包脚本**

```batch
build.bat
```

**Step 2: 验证输出目录结构**

```batch
dir /b dist\DouYin_AutoClik
```

Expected output:
```
DouYin_AutoClik.exe
README.txt
_internal
data
```

**Step 3: 测试可执行文件启动**

双击 `dist\DouYin_AutoClik\DouYin_AutoClik.exe`，确认 GUI 界面能正常启动。

**Step 4: 验证 Playwright 浏览器**

检查 `_internal\playwright\driver\package` 目录下是否有浏览器驱动文件。

**Step 5: 功能测试**

在打包环境中测试：
- [ ] GUI 界面正常显示
- [ ] 浏览器能正常打开
- [ ] 登录功能正常
- [ ] 自动点赞功能正常

**Step 6: 清理测试产物**

```batch
rmdir /s /q build dist
```

---

### Task 6: 合并到主分支

**Files:**
- 无修改

**Step 1: 切换到主分支并合并**

```bash
git checkout main
git merge feature/packaging
```

**Step 2: 推送到远程**

```bash
git push origin main
```

**Step 3: 删除功能分支（可选）**

```bash
git branch -d feature/packaging
```
