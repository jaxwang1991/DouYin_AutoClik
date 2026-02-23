# 抖音直播间自动点赞助手 - 打包设计文档

创建日期: 2026-02-23
分支: feature/packaging

## 概述

使用 PyInstaller 将项目打包为目录形式的 Windows 可执行程序，方便用户无需 Python 环境即可运行。

## 设计目标

- 打包形式：目录打包（非单文件）
- 入口：GUI 模式（gui.py）
- 一键打包：自动处理 Playwright 浏览器复制
- 包含用户文档：README.txt

## 目录结构

```
dist/DouYin_AutoClik/      # 最终打包输出目录
├── DouYin_AutoClik.exe    # 主程序
├── _internal/             # PyInstaller 内部依赖
│   └── playwright/
│       └── driver/package/  # Playwright 浏览器
├── data/                  # 数据目录（首次运行自动创建）
│   ├── logs/
│   ├── config.json
│   └── state.json
└── README.txt             # 简化版用户文档
```

## 文件清单

| 文件 | 操作 | 说明 |
|-----|------|------|
| `DouYin_AutoClik.spec` | 创建 | PyInstaller 规范文件 |
| `build.bat` | 修改 | 增强打包脚本 |
| `copy_browsers.bat` | 删除 | 功能合并到 build.bat |
| `README.txt` | 创建 | 简化版用户文档 |

## .spec 文件配置

```python
# DouYin_AutoClik.spec
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

## build.bat 工作流程

1. 检查 PyInstaller，未安装则自动安装
2. 清理旧构建目录（build/、dist/DouYin_AutoClik/）
3. 执行 PyInstaller 打包：`pyinstaller DouYin_AutoClik.spec`
4. 复制 Playwright 浏览器到 dist 目录
5. 创建 data 目录结构
6. 复制 README.txt 到输出目录
7. 验证输出文件完整性
8. 完成提示

## 错误处理

| 场景 | 处理方式 |
|-----|---------|
| PyInstaller 未安装 | 自动执行 `pip install pyinstaller` |
| Playwright 浏览器不存在 | 提示用户先运行 `python -m playwright install chromium` |
| 打包失败 | 显示错误信息并退出 |
| 复制失败 | 显示错误信息并退出 |

## README.txt 内容

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
```

## 测试计划

- [ ] .exe 能正常启动 GUI 界面
- [ ] 浏览器能正常打开
- [ ] 登录功能正常
- [ ] 自动点赞功能正常
- [ ] AI 评论功能正常（需配置 API）
- [ ] 音频录制功能正常
- [ ] 配置保存/加载正常

## 发布流程

1. 在 `feature/packaging` 分支完成开发和测试
2. 合并到 `main` 分支
3. 创建 GitHub Release
4. 上传 `dist/DouYin_AutoClik` 文件夹压缩包

## 依赖项

- PyInstaller >= 6.0
- Playwright（需先安装浏览器）
- Python >= 3.10
