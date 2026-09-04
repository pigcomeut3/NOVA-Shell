# NOVA Shell

一个用纯 Python 编写的跨平台自研命令行终端工具，可在 Windows、macOS、Linux 上运行。

## 特性

- 全新设计的命令体系，融合各主流终端的实用能力
- 彩色输出：普通文本、错误、进度、提示分色显示
- 内置内存虚拟文件系统，同时可桥接访问宿主真实文件
- tkinter 图形登录界面（无 GUI 环境自动回退到终端登录）
- 全屏文本编辑器，内置 40+ 种语言语法高亮
- 命令历史自动建议（输入时淡色提示，Tab 补全）
- 中文 / Emoji 宽字符正确处理，光标不错位
- 内置权限管理、进程管理、网络工具、压缩解压等 80+ 命令
- 友好的错误提示，不暴露 Python 原始堆栈

## 目录结构

```
NOVA-Shell-Release/
├── Windows/          Windows 可执行程序
│   ├── NOVA Shell.exe
│   ├── nova.ico / nova.png
│   └── 使用教程.txt
├── macOS/            macOS 应用包与构建脚本
│   ├── NOVA Shell.app/
│   └── build.sh
├── Linux/            Linux 构建脚本与桌面入口
│   ├── build.sh
│   ├── novashell
│   ├── nova-shell.desktop
│   └── nova-shell.png
├── novashell.py      完整源码
└── LICENSE
```

## Windows

直接双击 `Windows/NOVA Shell.exe` 运行，无需安装 Python。

## macOS

```bash
cd macOS
chmod +x build.sh
./build.sh
open "NOVA Shell.app"
```

需要系统自带或自行安装 Python 3。

## Linux

```bash
cd Linux
chmod +x build.sh
./build.sh           # 当前用户
sudo ./build.sh      # 系统级安装，之后可直接运行 novashell
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `guide` | 查看全部命令帮助 |
| `edit <file>` | 全屏编辑器（语法高亮） |
| `syntax list` | 列出编辑器支持的后缀 |
| `update install <pkg>` | 安装 Python 扩展库 |
| `py <code>` | 用内置解释器运行 Python |
| `preview <file>` | 预览文本 / 图片 / 视频 / PDF |
| `history` / `forget` | 查看 / 清空命令历史 |

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
