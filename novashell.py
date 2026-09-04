#!/usr/bin/env python3
import os
import sys
import getpass
import hashlib
import shutil
import time
import datetime
import platform
import subprocess
import json
import re
import base64
import zlib
import tempfile
import signal
import math
import random
import string
import urllib.request
import urllib.error
import socket
import struct
import stat
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TKINTER = True
except ImportError:
    tk = None
    ttk = None
    messagebox = None
    HAS_TKINTER = False

VERSION = "2.2.0"
BUILD_TAG = "NOVA-STABLE-2026"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".novashell")
CONFIG_FILE = os.path.join(CONFIG_DIR, "auth.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.log")
ALIAS_FILE = os.path.join(CONFIG_DIR, "aliases.json")
EMBEDDED_AUTH_B64 = "eyJ1c2VycyI6IFt7InVzZXJuYW1lIjogInBpZyIsICJzYWx0IjogIjMwMDE3MTRkNTdmYzU4ZTMxZjkxODNkYjVkNmY2NzNhIiwgInBhc3N3b3JkX2hhc2giOiAiZGVhMjYxZTFjNzVkN2NiMTA3ZjU2ZDdlMDUxZjk1MjE1ZTZhNjhhOWIwNWY5NzE2N2YwZDFiZjJmYTA3M2U3ZiIsICJjcmVhdGVkIjogMTc4NzMwMjc2OS4wMzE2OTI3fV19"
AUTH_MAGIC = b"NOVA_AUTH_DATA_v1_"

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

if IS_WINDOWS:
    import ctypes
    import msvcrt

class Palette:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

def enable_vt():
    if IS_WINDOWS:
        try:
            kernel32 = ctypes.windll.kernel32
            out_handle = kernel32.GetStdHandle(-11)
            omode = ctypes.c_ulong()
            kernel32.GetConsoleMode(out_handle, ctypes.byref(omode))
            kernel32.SetConsoleMode(out_handle, omode.value | 0x0004 | 0x0008)
            in_handle = kernel32.GetStdHandle(-10)
            imode = ctypes.c_ulong()
            kernel32.GetConsoleMode(in_handle, ctypes.byref(imode))
            in_val = imode.value
            in_val = in_val & ~0x0040 & ~0x0010
            in_val = in_val | 0x0080
            kernel32.SetConsoleMode(in_handle, in_val)
        except Exception:
            pass

class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

class _CONSOLE_FONT_INFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("nFont", ctypes.c_ulong),
        ("dwFontSize", _COORD),
        ("FontFamily", ctypes.c_uint),
        ("FontWeight", ctypes.c_uint),
        ("FaceName", ctypes.c_wchar * 32),
    ]

def set_console_font():
    if not IS_WINDOWS:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        for face in ["Cascadia Code", "Cascadia Mono", "Consolas", "Lucida Console"]:
            font = _CONSOLE_FONT_INFOEX()
            font.cbSize = ctypes.sizeof(_CONSOLE_FONT_INFOEX)
            font.FaceName = face
            font.dwFontSize = _COORD(0, 18)
            font.FontWeight = 400
            if kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(font)):
                break
    except Exception:
        pass

def init_animation():
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()
    line()
    emit("  NOVA Shell", Palette.BOLD + Palette.BRIGHT_CYAN)
    line()
    steps = [
        "Loading core modules",
        "Mounting virtual filesystem",
        "Initializing privilege manager",
        "Preparing command registry",
        "Configuring terminal environment",
        "Establishing session",
    ]
    spinner = ["\u25d4", "\u25d1", "\u25d5", "\u25d2"]
    for i, step in enumerate(steps):
        for frame in range(6):
            put(f"\r  {Palette.BRIGHT_CYAN}{spinner[frame % 4]}{Palette.RESET} {step}...")
            sys.stdout.flush()
            time.sleep(0.08)
        put(f"\r  {Palette.BRIGHT_GREEN}\u2713{Palette.RESET} {step}")
        line()
    line()
    done("environment initialized")
    time.sleep(0.3)
    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()

def set_console_title(title):
    if IS_WINDOWS:
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

def term_width():
    try:
        return os.get_terminal_size().columns
    except Exception:
        return 80

def vis_width(s):
    import unicodedata
    w = 0
    for ch in s:
        o = ord(ch)
        if ch == "\t":
            w += 4
        elif o < 32:
            continue
        elif 0xFE00 <= o <= 0xFE0F or o == 0x200D or o == 0x20E3 or 0x1F3FB <= o <= 0x1F3FF:
            continue
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w

def emit(text, color="", end="\n", flush=True):
    sys.stdout.write(f"{color}{text}{Palette.RESET}{end}")
    if flush:
        sys.stdout.flush()

def put(text, color=""):
    emit(text, color, end="")

def line(text="", color=""):
    emit(text, color)

def info(text):
    emit(f"[i] {text}", Palette.BRIGHT_CYAN)

def done(text):
    emit(f"[+] {text}", Palette.BRIGHT_GREEN)

def warn(text):
    emit(f"[!] {text}", Palette.BRIGHT_YELLOW)

def fail(text):
    emit(f"[x] {text}", Palette.BRIGHT_RED)

def debug(text):
    emit(f"[d] {text}", Palette.GRAY)

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200000).hex()
    return salt, digest

def verify_password(password, salt, digest):
    _, check = hash_password(password, salt)
    return check == digest

def ensure_config_dir():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)

def _is_exe_mode():
    return getattr(sys, "frozen", False) and sys.executable.lower().endswith(".exe")

def _read_auth_from_exe():
    if not _is_exe_mode():
        return None
    try:
        with open(sys.executable, "rb") as f:
            content = f.read()
        idx = content.rfind(AUTH_MAGIC)
        if idx == -1:
            return None
        blob = content[idx + len(AUTH_MAGIC):]
        raw = zlib.decompress(blob)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None

def _write_auth_to_exe(data):
    return False

AUTH_DATA_FILE = os.path.join(CONFIG_DIR, "auth.dat")

def _write_auth_file(data):
    try:
        ensure_config_dir()
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        blob = zlib.compress(raw, 9)
        with open(AUTH_DATA_FILE, "wb") as f:
            f.write(blob)
        return True
    except Exception:
        return False

def _read_auth_file():
    try:
        if os.path.exists(AUTH_DATA_FILE):
            with open(AUTH_DATA_FILE, "rb") as f:
                blob = f.read()
            raw = zlib.decompress(blob)
            return json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    return None

def load_auth():
    data = _read_auth_file()
    if data is not None:
        if "users" not in data:
            data = {"users": []}
        return data
    data = _read_auth_from_exe()
    if data is not None:
        if "users" not in data:
            data = {"users": []}
        _write_auth_file(data)
        return data
    try:
        raw = base64.b64decode(EMBEDDED_AUTH_B64).decode("utf-8")
        data = json.loads(raw)
        if "users" not in data:
            data = {"users": []}
        return data
    except Exception:
        return {"users": []}

def save_auth(data):
    _write_auth_file(data)

CONFIG_MAGIC = b"NOVA_CFG_DATA_v1_"
_embedded_configs = {}
_configs_dirty = False
CONFIG_DATA_FILE = os.path.join(CONFIG_DIR, "config.dat")

def _load_configs_from_exe():
    global _embedded_configs
    try:
        if os.path.exists(CONFIG_DATA_FILE):
            with open(CONFIG_DATA_FILE, "rb") as f:
                blob = f.read()
            raw = zlib.decompress(blob)
            _embedded_configs = json.loads(raw.decode("utf-8"))
            return
    except Exception:
        pass
    if not _is_exe_mode():
        _embedded_configs = {}
        return
    try:
        with open(sys.executable, "rb") as f:
            content = f.read()
        idx = content.rfind(CONFIG_MAGIC)
        if idx == -1:
            _embedded_configs = {}
            return
        blob = content[idx + len(CONFIG_MAGIC):]
        raw = zlib.decompress(blob)
        _embedded_configs = json.loads(raw.decode("utf-8"))
    except Exception:
        _embedded_configs = {}

def _save_configs_to_exe():
    global _configs_dirty
    if not _configs_dirty:
        return False
    try:
        ensure_config_dir()
        raw = json.dumps(_embedded_configs, ensure_ascii=False).encode("utf-8")
        blob = zlib.compress(raw, 9)
        with open(CONFIG_DATA_FILE, "wb") as f:
            f.write(blob)
        _configs_dirty = False
        return True
    except Exception:
        return False

def get_config(name, default=None):
    return _embedded_configs.get(name, default)

def set_config(name, data):
    global _configs_dirty
    _embedded_configs[name] = data
    _configs_dirty = True

def find_user(username):
    auth = load_auth()
    for u in auth["users"]:
        if u["username"] == username:
            return u
    return None

MAX_USERS = 30
AUTO_CLEANUP_THRESHOLD = 21
INACTIVE_DAYS = 30

def _cleanup_inactive_history(auth):
    return 0

def add_user(username, password):
    auth = load_auth()
    for u in auth["users"]:
        if u["username"] == username:
            return False, "用户名已存在"
    if len(auth["users"]) >= MAX_USERS:
        _cleanup_inactive_history(auth)
        if len(auth["users"]) >= MAX_USERS:
            return False, f"用户数已达上限({MAX_USERS})，请先清理不活跃用户"
    if len(auth["users"]) >= AUTO_CLEANUP_THRESHOLD:
        _cleanup_inactive_history(auth)
    salt, digest = hash_password(password)
    auth["users"].append({"username": username, "salt": salt, "password_hash": digest, "created": time.time(), "last_login": time.time()})
    save_auth(auth)
    return True, "注册成功"

def verify_user(username, password):
    user = find_user(username)
    if user is None:
        return False, "没有这个用户"
    if verify_password(password, user["salt"], user["password_hash"]):
        auth = load_auth()
        for u in auth["users"]:
            if u["username"] == username:
                u["last_login"] = time.time()
                break
        save_auth(auth)
        return True, "登录成功"
    return False, "密码错误"

def load_aliases():
    return get_config("aliases", {})

def save_aliases(data):
    set_config("aliases", data)

def load_history(username="default"):
    all_hist = get_config("history", {})
    return all_hist.get(username, [])

def append_history(cmd, username="default"):
    all_hist = get_config("history", {})
    user_hist = all_hist.get(username, [])
    if cmd in user_hist:
        user_hist.remove(cmd)
    user_hist.append(cmd)
    all_hist[username] = user_hist
    set_config("history", all_hist)
    _save_configs_to_exe()

class VNode:
    def __init__(self, name, node_type="dir", content=""):
        self.name = name
        self.type = node_type
        self.content = content
        self.children = {}
        self.created = time.time()
        self.modified = time.time()
        self.size = len(content.encode("utf-8")) if content else 0

    def update(self):
        self.modified = time.time()
        if self.type == "file":
            self.size = len(self.content.encode("utf-8"))

class VirtualFS:
    def __init__(self):
        self.root = VNode("/", "dir")
        self.cwd = "/"
        self._seed()

    def _seed(self):
        for d in ["docs", "bin", "tmp", "home", "mnt"]:
            node = VNode(d, "dir")
            self.root.children[d] = node
        readme = VNode("README.nova", "file", "Welcome to NOVA Virtual Filesystem.\nThis space exists only in memory.\nAll data is lost when the shell exits.\n")
        self.root.children["README.nova"] = readme

    def normalize(self, path):
        if not path:
            return self.cwd
        if path.startswith("/"):
            base = path
        elif path == "~":
            base = "/home"
        elif path.startswith("~/"):
            base = "/home/" + path[2:]
        else:
            if self.cwd == "/":
                base = "/" + path
            else:
                base = self.cwd + "/" + path
        parts = []
        for part in base.split("/"):
            if part == "" or part == ".":
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def resolve(self, path):
        norm = self.normalize(path)
        if norm == "/":
            return self.root
        parts = norm.strip("/").split("/")
        node = self.root
        for part in parts:
            if part not in node.children:
                return None
            node = node.children[part]
        return node

    def parent_of(self, path):
        norm = self.normalize(path)
        if norm == "/":
            return None, "/"
        parts = norm.strip("/").split("/")
        name = parts.pop()
        parent_path = "/" + "/".join(parts) if parts else "/"
        return self.resolve(parent_path), name

    def mkdir(self, path):
        parent, name = self.parent_of(path)
        if parent is None:
            return False, "invalid path"
        if name in parent.children:
            return False, f"'{name}' already exists"
        if parent.type != "dir":
            return False, "parent is not a directory"
        node = VNode(name, "dir")
        parent.children[name] = node
        parent.update()
        return True, ""

    def mkfile(self, path, content=""):
        parent, name = self.parent_of(path)
        if parent is None:
            return False, "invalid path"
        if name in parent.children:
            return False, f"'{name}' already exists"
        if parent.type != "dir":
            return False, "parent is not a directory"
        node = VNode(name, "file", content)
        parent.children[name] = node
        parent.update()
        return True, ""

    def write_file(self, path, content):
        node = self.resolve(path)
        if node is None:
            ok, err = self.mkfile(path, content)
            return ok, err
        if node.type != "file":
            return False, "not a file"
        node.content = content
        node.update()
        return True, ""

    def read_file(self, path):
        node = self.resolve(path)
        if node is None:
            return None, "no such file"
        if node.type != "file":
            return None, "is a directory"
        return node.content, ""

    def remove(self, path):
        norm = self.normalize(path)
        if norm == "/":
            return False, "cannot remove root"
        parent, name = self.parent_of(path)
        if parent is None or name not in parent.children:
            return False, "no such path"
        del parent.children[name]
        parent.update()
        return True, ""

    def list_dir(self, path):
        node = self.resolve(path)
        if node is None:
            return None, "no such directory"
        if node.type != "dir":
            return None, "not a directory"
        return sorted(node.children.values(), key=lambda n: (n.type != "dir", n.name.lower())), ""

    def chdir(self, path):
        node = self.resolve(path)
        if node is None:
            return False, "no such directory"
        if node.type != "dir":
            return False, "not a directory"
        self.cwd = self.normalize(path)
        return True, ""

    def copy(self, src, dst):
        src_node = self.resolve(src)
        if src_node is None:
            return False, "source not found"
        dst_norm = self.normalize(dst)
        dst_node = self.resolve(dst)
        if dst_node is not None and dst_node.type == "dir":
            dst_norm = dst_norm.rstrip("/") + "/" + src_node.name
            dst_node = self.resolve(dst_norm)
        if dst_node is not None:
            return False, "destination already exists"
        parent, name = self.parent_of(dst_norm)
        if parent is None:
            return False, "invalid destination"
        if src_node.type == "file":
            new_node = VNode(name, "file", src_node.content)
        else:
            new_node = VNode(name, "dir")
            self._copy_children(src_node, new_node)
        parent.children[name] = new_node
        parent.update()
        return True, ""

    def _copy_children(self, src, dst):
        for name, child in src.children.items():
            if child.type == "file":
                nc = VNode(name, "file", child.content)
            else:
                nc = VNode(name, "dir")
                self._copy_children(child, nc)
            dst.children[name] = nc

    def move(self, src, dst):
        src_node = self.resolve(src)
        if src_node is None:
            return False, "source not found"
        dst_norm = self.normalize(dst)
        dst_node = self.resolve(dst)
        if dst_node is not None and dst_node.type == "dir":
            dst_norm = dst_norm.rstrip("/") + "/" + src_node.name
        parent, name = self.parent_of(dst_norm)
        if parent is None:
            return False, "invalid destination"
        if name in parent.children:
            return False, "destination already exists"
        src_parent, src_name = self.parent_of(src)
        if src_parent is not None:
            del src_parent.children[src_name]
            src_parent.update()
        src_node.name = name
        parent.children[name] = src_node
        parent.update()
        return True, ""

    def exists(self, path):
        return self.resolve(path) is not None

class PrivilegeManager:
    def __init__(self):
        self.elevated = False
        self.level = "user"

    def check(self):
        if IS_WINDOWS:
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                return False
        else:
            return os.geteuid() == 0

    def current_level(self):
        if self.elevated:
            return "root"
        if self.check():
            return "admin"
        return "user"

    def elevate(self):
        if self.check():
            self.elevated = True
            self.level = "root"
            return True, "session already running with administrator privileges"
        if IS_WINDOWS:
            try:
                params = " ".join([sys.executable] + sys.argv)
                result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                if result > 32:
                    self.elevated = True
                    self.level = "root"
                    return True, "elevated session launched in new window"
                return False, "elevation declined or failed"
            except Exception as e:
                return False, f"elevation failed: {e}"
        else:
            try:
                subprocess.run(["sudo", "-v"], capture_output=True, timeout=30)
                self.elevated = True
                self.level = "root"
                return True, "sudo privileges acquired for this session"
            except subprocess.TimeoutExpired:
                return False, "sudo authentication timed out"
            except Exception as e:
                return False, f"elevation failed: {e}"

    def drop(self):
        self.elevated = False
        self.level = "user"
        return True, "privileges dropped to user level"

class LineEditor:
    def __init__(self, shell):
        self.shell = shell
        self.history = load_history(getattr(shell, "username", "default"))
        self.hist_idx = -1
        self.buffer = []
        self.cursor = 0
        self._last_cursor_row = 0

    def read(self, prompt_text):
        self.buffer = []
        self.cursor = 0
        self.hist_idx = -1
        self._last_cursor_row = 0
        put("\033[?25h")
        put(prompt_text)
        sys.stdout.flush()
        if IS_WINDOWS:
            return self._read_windows(prompt_text)
        else:
            return self._read_unix(prompt_text)

    def _get_suggestion(self):
        content = "".join(self.buffer)
        if not content or self.cursor < len(content):
            return ""
        for cmd in reversed(self.history):
            if cmd.startswith(content) and cmd != content:
                return cmd[len(content):]
        return ""

    def _refresh(self, prompt_text):
        content = "".join(self.buffer)
        cols = term_width()
        prompt_plain = re.sub(r'\x1b\[[0-9;]*m', '', prompt_text)
        prompt_vis = vis_width(prompt_plain)
        suggestion = self._get_suggestion()
        put("\033[?25l")
        if self._last_cursor_row > 0:
            put(f"\033[{self._last_cursor_row}A")
        put("\r\033[J")
        put(prompt_text)
        put(content)
        if suggestion:
            put(f"\033[2;32m{suggestion}\033[0m")
        before = content[:self.cursor]
        cursor_abs = prompt_vis + vis_width(before)
        cursor_row = cursor_abs // cols
        cursor_col = cursor_abs % cols
        total_vis = prompt_vis + vis_width(content)
        if suggestion:
            total_vis += vis_width(suggestion)
        total_rows = total_vis // cols
        row_diff = total_rows - cursor_row
        if row_diff > 0:
            put(f"\033[{row_diff}A")
        put(f"\033[{cursor_col + 1}G")
        put("\033[?25h")
        self._last_cursor_row = cursor_row
        sys.stdout.flush()

    def _read_windows(self, prompt_text):
        while True:
            try:
                ch = msvcrt.getwch()
            except Exception:
                continue
            if 0xD800 <= ord(ch) <= 0xDBFF:
                try:
                    ch2 = msvcrt.getwch()
                    if 0xDC00 <= ord(ch2) <= 0xDFFF:
                        ch = ch + ch2
                    else:
                        continue
                except Exception:
                    continue
            if ch == "\r":
                line()
                return "".join(self.buffer)
            if ch == "\t":
                suggestion = self._get_suggestion()
                if suggestion:
                    for ch2 in suggestion:
                        self.buffer.insert(self.cursor, ch2)
                        self.cursor += 1
                    self._refresh(prompt_text)
                else:
                    self._complete(prompt_text)
                continue
            if ch == "\x08":
                if self.cursor > 0:
                    self.buffer.pop(self.cursor - 1)
                    self.cursor -= 1
                    self._refresh(prompt_text)
                continue
            if ch == "\x03":
                put("^C")
                line()
                return ""
            if ch == "\x04":
                if not self.buffer:
                    return "__EXIT__"
                continue
            if ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                if code == "H":
                    self._history_up(prompt_text)
                elif code == "P":
                    self._history_down(prompt_text)
                elif code == "M":
                    if self.cursor < len(self.buffer):
                        self.cursor += 1
                        self._refresh(prompt_text)
                    else:
                        suggestion = self._get_suggestion()
                        if suggestion:
                            for ch2 in suggestion:
                                self.buffer.insert(self.cursor, ch2)
                                self.cursor += 1
                            self._refresh(prompt_text)
                elif code == "K":
                    if self.cursor > 0:
                        self.cursor -= 1
                        self._refresh(prompt_text)
                elif code == "S":
                    if self.cursor < len(self.buffer):
                        self.buffer.pop(self.cursor)
                        self._refresh(prompt_text)
                elif code == "G":
                    self.cursor = 0
                    self._refresh(prompt_text)
                elif code == "O":
                    self.cursor = len(self.buffer)
                    self._refresh(prompt_text)
                continue
            if ord(ch) >= 32:
                self.buffer.insert(self.cursor, ch)
                self.cursor += 1
                self._refresh(prompt_text)

    def _read_unix(self, prompt_text):
        fd = sys.stdin.fileno()
        import termios
        import tty
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\r" or ch == "\n":
                    line()
                    return "".join(self.buffer)
                if ch == "\t":
                    suggestion = self._get_suggestion()
                    if suggestion:
                        for ch2 in suggestion:
                            self.buffer.insert(self.cursor, ch2)
                            self.cursor += 1
                        self._refresh(prompt_text)
                    else:
                        self._complete(prompt_text)
                    continue
                if ch == "\x7f" or ch == "\x08":
                    if self.cursor > 0:
                        self.buffer.pop(self.cursor - 1)
                        self.cursor -= 1
                        self._refresh(prompt_text)
                    continue
                if ch == "\x03":
                    put("^C")
                    line()
                    return ""
                if ch == "\x04":
                    if not self.buffer:
                        return "__EXIT__"
                    continue
                if ch == "\x1b":
                    seq = ch
                    while True:
                        c = sys.stdin.read(1)
                        seq += c
                        if c.isalpha() or c == "~":
                            break
                        if len(seq) > 6:
                            break
                    if seq == "\x1b[A":
                        self._history_up(prompt_text)
                    elif seq == "\x1b[B":
                        self._history_down(prompt_text)
                    elif seq == "\x1b[C":
                        if self.cursor < len(self.buffer):
                            self.cursor += 1
                            self._refresh(prompt_text)
                        else:
                            suggestion = self._get_suggestion()
                            if suggestion:
                                for ch2 in suggestion:
                                    self.buffer.insert(self.cursor, ch2)
                                    self.cursor += 1
                                self._refresh(prompt_text)
                    elif seq == "\x1b[D":
                        if self.cursor > 0:
                            self.cursor -= 1
                            self._refresh(prompt_text)
                    elif seq == "\x1b[3~":
                        if self.cursor < len(self.buffer):
                            self.buffer.pop(self.cursor)
                            self._refresh(prompt_text)
                    elif seq == "\x1b[H" or seq == "\x1bOH":
                        self.cursor = 0
                        self._refresh(prompt_text)
                    elif seq == "\x1b[F" or seq == "\x1bOF":
                        self.cursor = len(self.buffer)
                        self._refresh(prompt_text)
                    continue
                if ord(ch) >= 32:
                    self.buffer.insert(self.cursor, ch)
                    self.cursor += 1
                    self._refresh(prompt_text)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _history_up(self, prompt_text):
        if not self.history:
            return
        if self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.buffer = list(self.history[-(self.hist_idx + 1)])
            self.cursor = len(self.buffer)
            self._refresh(prompt_text)

    def _history_down(self, prompt_text):
        if self.hist_idx > 0:
            self.hist_idx -= 1
            self.buffer = list(self.history[-(self.hist_idx + 1)])
            self.cursor = len(self.buffer)
        elif self.hist_idx == 0:
            self.hist_idx = -1
            self.buffer = []
            self.cursor = 0
        self._refresh(prompt_text)

    def _complete(self, prompt_text):
        content = "".join(self.buffer)
        before = content[:self.cursor]
        if " " not in before:
            prefix = before.lower()
            cands = set(self.shell.commands.keys()) | set(self.shell.aliases.keys())
            matches = sorted([c for c in cands if c.startswith(prefix)])
            is_cmd = True
        else:
            parts = before.rsplit(" ", 1)
            prefix = parts[1] if len(parts) == 2 else ""
            is_cmd = False
            try:
                cwd = self.shell.real_cwd
                all_f = os.listdir(cwd)
                matches = sorted([f for f in all_f if f.lower().startswith(prefix.lower())])
            except Exception:
                matches = []
        if not matches:
            return
        if len(matches) == 1:
            comp = matches[0][len(prefix):]
            if is_cmd:
                comp += " "
            else:
                fp = os.path.join(self.shell.real_cwd, matches[0])
                comp += "/" if os.path.isdir(fp) else " "
            for ch in comp:
                self.buffer.insert(self.cursor, ch)
                self.cursor += 1
            self._refresh(prompt_text)
            return
        common = matches[0]
        for m in matches[1:]:
            while not m.lower().startswith(common.lower()):
                common = common[:-1]
                if not common:
                    break
        if len(common) > len(prefix):
            comp = common[len(prefix):]
            for ch in comp:
                self.buffer.insert(self.cursor, ch)
                self.cursor += 1
            self._refresh(prompt_text)
        else:
            put("\r\n")
            cw = max(len(m) for m in matches) + 2
            cols = max(1, term_width() // cw)
            for i, m in enumerate(matches):
                put(m.ljust(cw))
                if (i + 1) % cols == 0:
                    put("\r\n")
            put("\r\n")
            self._refresh(prompt_text)

SYNTAX_SPECS = {
    ".py": {"keywords": {"False","None","True","and","as","assert","async","await","break","class","continue","def","del","elif","else","except","finally","for","from","global","if","import","in","is","lambda","nonlocal","not","or","pass","raise","return","try","while","with","yield","self"}, "comment": "#", "string": True},
    ".js": {"keywords": {"var","let","const","function","return","if","else","for","while","do","switch","case","break","continue","new","this","class","extends","super","import","export","from","default","try","catch","finally","throw","typeof","instanceof","in","of","void","null","undefined","true","false","async","await","yield","delete"}, "comment": "//", "string": True},
    ".ts": {"keywords": {"var","let","const","function","return","if","else","for","while","do","switch","case","break","continue","new","this","class","extends","super","import","export","from","default","try","catch","finally","throw","typeof","instanceof","in","of","void","null","undefined","true","false","async","await","yield","delete","interface","type","enum","implements","public","private","protected","readonly","static","abstract","as","is","keyof","namespace","module","declare"}, "comment": "//", "string": True},
    ".java": {"keywords": {"public","private","protected","class","interface","extends","implements","static","final","void","int","long","short","byte","float","double","boolean","char","String","new","return","if","else","for","while","do","switch","case","break","continue","try","catch","finally","throw","throws","this","super","import","package","abstract","synchronized","volatile","transient","instanceof","native","strictfp","enum","assert","true","false","null"}, "comment": "//", "string": True},
    ".c": {"keywords": {"int","char","float","double","void","short","long","unsigned","signed","const","static","extern","register","volatile","auto","struct","union","enum","typedef","return","if","else","for","while","do","switch","case","break","continue","goto","default","sizeof","include","define","ifdef","ifndef","endif","undef","pragma"}, "comment": "//", "string": True},
    ".cpp": {"keywords": {"int","char","float","double","void","short","long","unsigned","signed","const","static","extern","register","volatile","auto","struct","union","enum","typedef","return","if","else","for","while","do","switch","case","break","continue","goto","default","sizeof","include","define","class","public","private","protected","virtual","override","new","delete","this","template","typename","namespace","using","try","catch","throw","bool","true","false","nullptr","operator","friend","explicit","mutable"}, "comment": "//", "string": True},
    ".h": {"keywords": {"int","char","float","double","void","short","long","unsigned","signed","const","static","extern","struct","union","enum","typedef","define","ifdef","ifndef","endif","include","class","public","private","protected","virtual","template","typename","namespace","bool"}, "comment": "//", "string": True},
    ".cs": {"keywords": {"public","private","protected","internal","class","interface","struct","enum","static","readonly","const","void","int","long","short","byte","float","double","bool","char","string","var","new","return","if","else","for","foreach","while","do","switch","case","break","continue","try","catch","finally","throw","this","base","using","namespace","abstract","virtual","override","sealed","async","await","get","set","true","false","null","is","as","in","out","ref","params","typeof","default"}, "comment": "//", "string": True},
    ".go": {"keywords": {"package","import","func","var","const","type","struct","interface","map","chan","range","return","if","else","for","switch","case","break","continue","default","defer","go","select","fallthrough","goto","nil","true","false","iota","make","len","cap","new","append","copy","delete","close","panic","recover"}, "comment": "//", "string": True},
    ".rs": {"keywords": {"fn","let","mut","const","static","struct","enum","trait","impl","pub","use","mod","crate","self","super","return","if","else","for","while","loop","match","break","continue","in","as","ref","where","move","async","await","dyn","true","false","Some","None","Ok","Err","type","unsafe","extern","crate"}, "comment": "//", "string": True},
    ".rb": {"keywords": {"def","end","class","module","require","include","attr_accessor","attr_reader","attr_writer","if","elsif","else","unless","while","until","for","do","begin","rescue","ensure","case","when","then","yield","return","break","next","redo","retry","self","nil","true","false","super","lambda","proc","puts","print","and","or","not"}, "comment": "#", "string": True},
    ".php": {"keywords": {"function","class","public","private","protected","static","new","return","if","else","elseif","for","foreach","while","do","switch","case","break","continue","try","catch","finally","throw","echo","print","require","include","require_once","include_once","namespace","use","extends","implements","interface","abstract","final","true","false","null","array","string","int","float","bool","void","this","self"}, "comment": "//", "string": True},
    ".sh": {"keywords": {"if","then","else","elif","fi","for","while","do","done","case","esac","function","return","exit","export","local","echo","read","cd","ls","pwd","cat","grep","sed","awk","chmod","chown","mkdir","rm","cp","mv","sudo","source","set","unset","in","select","until","time","trap"}, "comment": "#", "string": True},
    ".bat": {"keywords": {"echo","set","if","else","for","goto","call","exit","rem","cd","dir","copy","del","md","rd","ren","pause","cls","errorlevel","exist","defined","not","equ","neq","lss","leq","gtr","geq","and","or","in","do","then","start","title","color","prompt","shift","setlocal","endlocal","enabledelayedexpansion"}, "comment": "rem", "string": True},
    ".ps1": {"keywords": {"function","param","if","else","elseif","for","foreach","while","do","switch","break","continue","return","try","catch","finally","throw","Write-Host","Write-Output","Get-ChildItem","Set-Location","Get-Location","New-Item","Remove-Item","Copy-Item","Move-Item","$true","$false","$null","$env","$PSScriptRoot","process","begin","end","class","using","namespace","Import-Module","Export-ModuleMember"}, "comment": "#", "string": True},
    ".html": {"keywords": {"div","span","p","a","img","ul","ol","li","h1","h2","h3","h4","h5","h6","table","tr","td","th","form","input","button","label","head","body","html","title","meta","link","script","style","div","header","footer","nav","section","article","main","aside","video","audio","canvas","iframe","br","hr","pre","code","blockquote","em","strong","b","i","u","small","sub","sup","select","option","textarea","fieldset","legend"}, "comment": None, "string": False, "html": True},
    ".css": {"keywords": {"color","background","margin","padding","border","font","width","height","display","position","top","left","right","bottom","flex","grid","text-align","font-size","font-weight","line-height","background-color","border-radius","box-shadow","opacity","z-index","overflow","cursor","transition","transform","animation","justify-content","align-items","flex-direction","gap","max-width","min-height","list-style","text-decoration"}, "comment": None, "string": False, "css": True},
    ".json": {"keywords": set(), "comment": None, "string": False, "json": True},
    ".xml": {"keywords": set(), "comment": None, "string": False, "xml": True},
    ".yaml": {"keywords": set(), "comment": "#", "string": True},
    ".yml": {"keywords": set(), "comment": "#", "string": True},
    ".toml": {"keywords": set(), "comment": "#", "string": True},
    ".md": {"keywords": set(), "comment": None, "string": False, "md": True},
    ".sql": {"keywords": {"SELECT","FROM","WHERE","INSERT","INTO","VALUES","UPDATE","SET","DELETE","CREATE","TABLE","DROP","ALTER","ADD","INDEX","VIEW","JOIN","INNER","LEFT","RIGHT","OUTER","ON","GROUP","BY","ORDER","HAVING","LIMIT","OFFSET","UNION","ALL","DISTINCT","AS","AND","OR","NOT","NULL","IS","IN","LIKE","BETWEEN","EXISTS","CASE","WHEN","THEN","ELSE","END","PRIMARY","KEY","FOREIGN","REFERENCES","INT","VARCHAR","TEXT","INTEGER","PRIMARY","AUTOINCREMENT","DEFAULT","CONSTRAINT","UNIQUE","CHECK","CASCADE"}, "comment": "--", "string": True},
    ".lua": {"keywords": {"function","end","if","then","else","elseif","for","while","do","repeat","until","return","break","local","in","and","or","not","nil","true","false","print","require","module","pairs","ipairs","table","string","math","io","os","coroutine","self"}, "comment": "--", "string": True},
    ".pl": {"keywords": {"sub","my","our","if","elsif","else","unless","while","until","for","foreach","do","return","last","next","redo","use","require","package","BEGIN","END","print","chomp","split","join","push","pop","shift","unshift","keys","values","exists","defined","and","or","not","cmp","eq","ne","lt","gt","le","ge"}, "comment": "#", "string": True},
    ".r": {"keywords": {"function","if","else","for","while","repeat","break","next","return","in","TRUE","FALSE","NULL","NA","Inf","NaN","library","require","c","list","data.frame","matrix","vector","apply","sapply","lapply","mapply","paste","cat","print","length","nrow","ncol","dim","names","str","summary","plot","read.csv","write.csv"}, "comment": "#", "string": True},
    ".swift": {"keywords": {"func","let","var","if","else","for","while","switch","case","break","continue","return","class","struct","enum","protocol","extension","import","init","deinit","self","super","nil","true","false","guard","defer","repeat","do","catch","throw","throws","try","as","is","in","where","private","public","internal","fileprivate","open","static","final","override","lazy","weak","strong","unowned","optional","some","Any","Int","String","Bool","Double","Float","Array","Dictionary","Set"}, "comment": "//", "string": True},
    ".kt": {"keywords": {"fun","val","var","if","else","for","while","when","return","class","interface","object","package","import","init","this","super","null","true","false","is","in","as","try","catch","finally","throw","data","sealed","enum","companion","override","open","abstract","private","public","protected","internal","const","lateinit","by","where","suspend","operator","infix","inline","reified","typealias","it"}, "comment": "//", "string": True},
    ".dart": {"keywords": {"void","int","double","bool","String","List","Map","Set","dynamic","var","final","const","class","enum","extends","implements","with","mixin","abstract","static","if","else","for","while","do","switch","case","break","continue","return","new","this","super","true","false","null","try","catch","finally","throw","rethrow","import","export","library","part","factory","get","set","async","await","yield","late","required","this","Function"}, "comment": "//", "string": True},
    ".txt": {"keywords": set(), "comment": None, "string": False},
    ".log": {"keywords": set(), "comment": None, "string": False},
    ".ini": {"keywords": set(), "comment": ";", "string": False},
    ".cfg": {"keywords": set(), "comment": "#", "string": False},
    ".conf": {"keywords": set(), "comment": "#", "string": False},
    ".csv": {"keywords": set(), "comment": None, "string": False},
    ".ipa": {"keywords": set(), "comment": None, "string": False},
    ".app": {"keywords": set(), "comment": None, "string": False},
    ".pkg": {"keywords": set(), "comment": None, "string": False},
    ".dmg": {"keywords": set(), "comment": None, "string": False},
    ".xcodeproj": {"keywords": set(), "comment": None, "string": False},
    ".xcworkspace": {"keywords": set(), "comment": None, "string": False},
    ".plist": {"keywords": set(), "comment": None, "string": False, "xml": True},
    ".entitlements": {"keywords": set(), "comment": None, "string": False, "xml": True},
    ".storyboard": {"keywords": set(), "comment": None, "string": False, "xml": True},
    ".xib": {"keywords": set(), "comment": None, "string": False, "xml": True},
    ".pbxproj": {"keywords": set(), "comment": "//", "string": True},
    ".m": {"keywords": {"int","char","float","double","void","short","long","unsigned","signed","const","static","extern","struct","union","enum","typedef","return","if","else","for","while","do","switch","case","break","continue","goto","default","sizeof","id","self","super","nil","YES","NO","BOOL","IBOutlet","IBAction","property","synthesize","dynamic","class","import","include","protocol","interface","implementation","end","public","private","protected","selectors","encode","autorelease","release","retain","nonatomic","atomic","strong","weak","copy","readonly","readwrite","block","instancetype","NSObject","NSString","NSArray","NSDictionary","NSSet","NSNumber","NSInteger","NSUInteger","CGFloat","BOOL"}, "comment": "//", "string": True},
    ".mm": {"keywords": {"int","char","float","double","void","short","long","unsigned","signed","const","static","extern","struct","union","enum","typedef","return","if","else","for","while","do","switch","case","break","continue","goto","default","sizeof","class","public","private","protected","virtual","new","delete","this","template","typename","namespace","using","try","catch","throw","id","self","super","nil","YES","NO","BOOL","property","synthesize","import","include","protocol","interface","implementation","end","autorelease","release","retain"}, "comment": "//", "string": True},
}

def highlight_line(text, ext):
    spec = SYNTAX_SPECS.get(ext)
    if not spec:
        return text
    result = []
    i = 0
    n = len(text)
    kw_set = spec.get("keywords", set())
    comment_sym = spec.get("comment")
    is_string = spec.get("string", False)
    if spec.get("md"):
        if text.startswith("#"):
            return f"\033[1;96m{text}\033[0m"
        if text.startswith(">"):
            return f"\033[90m{text}\033[0m"
        if text.startswith("- ") or text.startswith("* "):
            return f"\033[33m{text}\033[0m"
        if text.startswith("```"):
            return f"\033[95m{text}\033[0m"
    if spec.get("json"):
        i = 0
        while i < n:
            ch = text[i]
            if ch == '"':
                j = i + 1
                while j < n and text[j] != '"':
                    if text[j] == '\\':
                        j += 1
                    j += 1
                j = min(j + 1, n)
                segment = text[i:j]
                if j < n and text[j:j+1] == ":":
                    result.append(f"\033[96m{segment}\033[0m")
                else:
                    result.append(f"\033[92m{segment}\033[0m")
                i = j
            elif ch in "{}[]:,":
                result.append(f"\033[93m{ch}\033[0m")
                i += 1
            elif ch.isdigit():
                j = i
                while j < n and (text[j].isdigit() or text[j] in ".-+eE"):
                    j += 1
                result.append(f"\033[95m{text[i:j]}\033[0m")
                i = j
            else:
                result.append(ch)
                i += 1
        return "".join(result)
    if spec.get("html") or spec.get("xml"):
        i = 0
        while i < n:
            if text[i] == '<':
                j = text.find('>', i)
                if j == -1:
                    result.append(text[i:])
                    break
                tag = text[i:j+1]
                import re as _re
                tag = _re.sub(r'(\w[\w-]*)(=)', lambda m: f'\033[96m{m.group(1)}\033[0m\033[93m{m.group(2)}\033[0m', tag)
                tag = tag.replace('<', '\033[94m<', 1).replace('>', '>\033[0m', 1)
                result.append(tag)
                i = j + 1
            else:
                result.append(text[i])
                i += 1
        return "".join(result)
    if spec.get("css"):
        import re as _re
        text = _re.sub(r'([\w-]+)(\s*:)', lambda m: f'\033[96m{m.group(1)}\033[0m\033[93m{m.group(2)}\033[0m', text)
        text = _re.sub(r'(\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg)?)\b', lambda m: f'\033[95m{m.group(1)}\033[0m', text)
        return text
    while i < n:
        ch = text[i]
        if comment_sym and text[i:i+len(comment_sym)] == comment_sym:
            result.append(f"\033[90m{text[i:]}\033[0m")
            break
        if is_string and ch in ('"', "'", '`'):
            quote = ch
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            result.append(f"\033[92m{text[i:j]}\033[0m")
            i = j
            continue
        if ch.isalpha() or ch == '_' or ch == '$':
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_-$@."):
                j += 1
            word = text[i:j]
            if word in kw_set or (word.startswith('$') and word in kw_set):
                result.append(f"\033[96m{word}\033[0m")
            elif word.isdigit() or (word.replace('.','',1).isdigit() and '.' in word):
                result.append(f"\033[95m{word}\033[0m")
            else:
                result.append(word)
            i = j
            continue
        if ch.isdigit():
            j = i
            while j < n and (text[j].isdigit() or text[j] in ".xXabcdefABCDEF_"):
                j += 1
            result.append(f"\033[95m{text[i:j]}\033[0m")
            i = j
            continue
        result.append(ch)
        i += 1
    return "".join(result)

class NanoEditor:
    def __init__(self, filename, lines, save_fn, ext=None):
        self.filename = filename
        self.ext = ext if ext else os.path.splitext(filename)[1].lower()
        self.lines = [list(l.replace("\r", "").replace("\t", "    ")) for l in lines]
        if not self.lines:
            self.lines = [[]]
        self.cy = 0
        self.cx = 0
        self.modified = False
        self.save_fn = save_fn
        self.running = True
        self.msg = ""

    def run(self):
        sys.stdout.write("\033[?1049h\033[H\033[2J")
        sys.stdout.flush()
        try:
            if IS_WINDOWS:
                self._loop_win()
            else:
                self._loop_unix()
        finally:
            sys.stdout.write("\033[?1049l\033[?25h")
            sys.stdout.flush()

    def _draw(self):
        try:
            cols = os.get_terminal_size().columns
            rows = os.get_terminal_size().lines
        except Exception:
            cols, rows = 80, 24
        sys.stdout.write("\033[H")
        tag = " [MODIFIED]" if self.modified else ""
        title = f" NOVA Edit - {self.filename}{tag}"
        sys.stdout.write(f"\033[44m\033[97m{title.ljust(cols)[:cols]}\033[0m\033[K\r\n")
        content_h = rows - 3
        start = max(0, min(self.cy - content_h // 2, len(self.lines) - content_h))
        start = max(0, start)
        end = min(len(self.lines), start + content_h)
        for i in range(start, end):
            ln = "".join(self.lines[i])
            ln = ln.replace("\r", "").replace("\t", "    ")
            maxw = cols - 7
            if vis_width(ln) > maxw:
                cut = 0
                w = 0
                for ci, ch in enumerate(ln):
                    cw = vis_width(ch)
                    if w + cw > maxw - 3:
                        cut = ci
                        break
                    w += cw
                disp = ln[:cut] + "..."
            else:
                disp = ln
            num = str(i + 1).rjust(4)
            highlighted = highlight_line(disp, self.ext)
            sys.stdout.write(f"\033[90m{num}\033[0m {highlighted}\033[K\r\n")
        for _ in range(end - start, content_h):
            sys.stdout.write("\033[K\r\n")
        status = f" ^S Save   ^X Exit   |   Ln {self.cy+1}/{len(self.lines)}   Col {self.cx+1}"
        sys.stdout.write(f"\033[44m\033[97m{status.ljust(cols)[:cols]}\033[0m\033[K\r\n")
        sys.stdout.write(f"\033[90m{self.msg.ljust(cols)[:cols]}\033[0m\033[K")
        sy = self.cy - start + 2
        cur_line = "".join(self.lines[self.cy][:self.cx]).replace("\t", "    ")
        sx = vis_width(cur_line) + 6
        sys.stdout.write(f"\033[{sy};{sx}H")
        sys.stdout.flush()

    def _ins(self, ch):
        self.lines[self.cy].insert(self.cx, ch)
        self.cx += 1
        self.modified = True
        self.msg = ""

    def _bs(self):
        if self.cx > 0:
            self.lines[self.cy].pop(self.cx - 1)
            self.cx -= 1
        elif self.cy > 0:
            pl = len(self.lines[self.cy - 1])
            self.lines[self.cy - 1].extend(self.lines[self.cy])
            self.lines.pop(self.cy)
            self.cy -= 1
            self.cx = pl
        else:
            return
        self.modified = True
        self.msg = ""

    def _del(self):
        if self.cx < len(self.lines[self.cy]):
            self.lines[self.cy].pop(self.cx)
        elif self.cy < len(self.lines) - 1:
            self.lines[self.cy].extend(self.lines[self.cy + 1])
            self.lines.pop(self.cy + 1)
        else:
            return
        self.modified = True
        self.msg = ""

    def _enter(self):
        cur = self.lines[self.cy]
        self.lines[self.cy] = cur[:self.cx]
        self.lines.insert(self.cy + 1, cur[self.cx:])
        self.cy += 1
        self.cx = 0
        self.modified = True
        self.msg = ""

    def _up(self):
        if self.cy > 0:
            self.cy -= 1
            self.cx = min(self.cx, len(self.lines[self.cy]))

    def _down(self):
        if self.cy < len(self.lines) - 1:
            self.cy += 1
            self.cx = min(self.cx, len(self.lines[self.cy]))

    def _left(self):
        if self.cx > 0:
            self.cx -= 1
        elif self.cy > 0:
            self.cy -= 1
            self.cx = len(self.lines[self.cy])

    def _right(self):
        if self.cx < len(self.lines[self.cy]):
            self.cx += 1
        elif self.cy < len(self.lines) - 1:
            self.cy += 1
            self.cx = 0

    def _home(self):
        self.cx = 0

    def _end(self):
        self.cx = len(self.lines[self.cy])

    def _save(self):
        content = "\n".join("".join(l) for l in self.lines)
        try:
            self.save_fn(content)
            self.modified = False
            self.msg = f"Saved: {self.filename}"
        except Exception as e:
            self.msg = f"Save failed: {e}"

    def _try_exit(self):
        if self.modified:
            self.msg = "Unsaved changes! ^S to save, ^X again to discard"
            self._draw()
            if IS_WINDOWS:
                ch2 = msvcrt.getwch()
                if ch2 == "\x18":
                    self.running = False
                elif ch2 == "\x13":
                    self._save()
                else:
                    self.msg = ""
            else:
                ch2 = sys.stdin.read(1)
                if ch2 == "\x18":
                    self.running = False
                elif ch2 == "\x13":
                    self._save()
                else:
                    self.msg = ""
        else:
            self.running = False

    def _loop_win(self):
        while self.running:
            self._draw()
            try:
                ch = msvcrt.getwch()
            except Exception:
                continue
            if ch == "\x13":
                self._save()
            elif ch == "\x18":
                self._try_exit()
            elif ch == "\r":
                self._enter()
            elif ch == "\x08":
                self._bs()
            elif ch == "\x7f":
                self._del()
            elif ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                if code == "H": self._up()
                elif code == "P": self._down()
                elif code == "K": self._left()
                elif code == "M": self._right()
                elif code == "G": self._home()
                elif code == "O": self._end()
                elif code == "S": self._del()
            elif ord(ch) >= 32:
                self._ins(ch)

    def _loop_unix(self):
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while self.running:
                self._draw()
                ch = sys.stdin.read(1)
                if ch == "\x13":
                    self._save()
                elif ch == "\x18":
                    self._try_exit()
                elif ch == "\r" or ch == "\n":
                    self._enter()
                elif ch == "\x7f" or ch == "\x08":
                    self._bs()
                elif ch == "\x1b":
                    seq = ch
                    while True:
                        c = sys.stdin.read(1)
                        seq += c
                        if c.isalpha() or c == "~":
                            break
                        if len(seq) > 6:
                            break
                    if seq == "\x1b[A": self._up()
                    elif seq == "\x1b[B": self._down()
                    elif seq == "\x1b[D": self._left()
                    elif seq == "\x1b[C": self._right()
                    elif seq in ("\x1b[H", "\x1bOH"): self._home()
                    elif seq in ("\x1b[F", "\x1bOF"): self._end()
                    elif seq == "\x1b[3~": self._del()
                elif ord(ch) >= 32:
                    self._ins(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class NOVAShell:
    def __init__(self):
        self.username = ""
        self.vfs = VirtualFS()
        self.mode = "real"
        self.real_cwd = os.getcwd()
        self.priv = PrivilegeManager()
        self.editor = LineEditor(self)
        self.aliases = load_aliases()
        self.running = True
        self._signout = False
        self.last_dir = self.real_cwd
        self.commands = self._build_commands()

    def _build_commands(self):
        return {
            "guide": (self.cmd_guide, "display help for all commands or a specific command", "guide [command]"),
            "ver": (self.cmd_ver, "show NOVA Shell version and build info", "ver"),
            "banner": (self.cmd_banner, "display the NOVA Shell welcome banner", "banner"),
            "wipe": (self.cmd_wipe, "clear the terminal screen", "wipe"),
            "depart": (self.cmd_depart, "exit NOVA Shell", "depart"),
            "who": (self.cmd_who, "show current user and privilege level", "who"),
            "when": (self.cmd_when, "display current date and time", "when"),
            "say": (self.cmd_say, "print text to the terminal", "say <text>"),
            "roam": (self.cmd_roam, "change current directory", "roam <path>"),
            "peek": (self.cmd_peek, "list directory contents", "peek [path] [-l]"),
            "whereami": (self.cmd_whereami, "print current working directory", "whereami"),
            "goback": (self.cmd_goback, "return to previous directory", "goback"),
            "gohome": (self.cmd_gohome, "jump to home directory", "gohome"),
            "forge": (self.cmd_forge, "create a new empty file", "forge <name>"),
            "mold": (self.cmd_mold, "create a new directory", "mold <name>"),
            "erase": (self.cmd_erase, "remove a file or directory", "erase <path>"),
            "clone": (self.cmd_clone, "copy a file or directory", "clone <source> <destination>"),
            "relocate": (self.cmd_relocate, "move a file or directory", "relocate <source> <destination>"),
            "rebrand": (self.cmd_rebrand, "rename a file or directory", "rebrand <old> <new>"),
            "read": (self.cmd_read, "display file contents", "read <file>"),
            "inscribe": (self.cmd_inscribe, "write text to a file (overwrites)", "inscribe <file> <text>"),
            "append": (self.cmd_append, "append text to a file", "append <file> <text>"),
            "inspect": (self.cmd_inspect, "show detailed file metadata", "inspect <path>"),
            "measure": (self.cmd_measure, "calculate file or directory size", "measure <path>"),
            "tasks": (self.cmd_tasks, "list running system processes", "tasks"),
            "terminate": (self.cmd_terminate, "terminate a process by PID", "terminate <pid>"),
            "environ": (self.cmd_environ, "list all environment variables", "environ"),
            "setenv": (self.cmd_setenv, "set an environment variable", "setenv <name> <value>"),
            "unsetenv": (self.cmd_unsetenv, "remove an environment variable", "unsetenv <name>"),
            "sysinfo": (self.cmd_sysinfo, "display comprehensive system information", "sysinfo"),
            "uptime": (self.cmd_uptime, "show system uptime", "uptime"),
            "recall": (self.cmd_recall, "show command history", "recall [count]"),
            "elevate": (self.cmd_elevate, "attempt to gain administrator/root privileges", "elevate"),
            "droppriv": (self.cmd_droppriv, "drop elevated privileges back to user", "droppriv"),
            "privilege": (self.cmd_privilege, "show current privilege level", "privilege"),
            "vmode": (self.cmd_vmode, "switch between virtual and real filesystem", "vmode <virtual|real>"),
            "vstatus": (self.cmd_vstatus, "show current filesystem mode and virtual disk info", "vstatus"),
            "probe": (self.cmd_probe, "ping a host to check connectivity", "probe <host> [count]"),
            "fetch": (self.cmd_fetch, "download a file with colored progress", "fetch <url> [output]"),
            "resolve": (self.cmd_resolve, "perform DNS lookup on a domain", "resolve <domain>"),
            "calc": (self.cmd_calc, "evaluate a mathematical expression", "calc <expression>"),
            "digest": (self.cmd_digest, "compute hash of a file (md5/sha1/sha256)", "digest <file> [algorithm]"),
            "search": (self.cmd_search, "find files by name pattern", "search <path> <pattern>"),
            "filter": (self.cmd_filter, "search text lines matching a pattern", "filter <pattern> <file>"),
            "count": (self.cmd_count, "count lines, words, and characters in a file", "count <file>"),
            "sort": (self.cmd_sort, "sort lines of a file alphabetically", "sort <file>"),
            "alias": (self.cmd_alias, "create or list command aliases", "alias [name] [command]"),
            "unalias": (self.cmd_unalias, "remove an alias", "unalias <name>"),
            "pause": (self.cmd_pause, "sleep for specified seconds", "pause <seconds>"),
            "preview": (self.cmd_preview, "preview a file (image/video/pdf/text)", "preview <file>"),
            "password": (self.cmd_password, "generate a random password", "password [length]"),
            "cpu": (self.cmd_cpu, "show CPU usage", "cpu"),
            "memory": (self.cmd_memory, "show memory usage", "memory"),
            "disk": (self.cmd_disk, "show disk usage", "disk [path]"),
            "lockscreen": (self.cmd_lockscreen, "lock the workstation", "lockscreen"),
            "url": (self.cmd_url, "encode or decode URL text", "url <encode|decode> <text>"),
            "screenshot": (self.cmd_screenshot, "take a screenshot", "screenshot [filename]"),
            "edit": (self.cmd_edit, "full-screen interactive text editor with syntax highlighting", "edit <file>"),
            "syntax": (self.cmd_syntax, "register or list custom file extensions for the editor", "syntax [list|add <.ext> <comment_symbol> <keywords>]"),
            "tree": (self.cmd_tree, "show directory tree structure", "tree [path] [depth]"),
            "duplicate": (self.cmd_duplicate, "duplicate current shell session", "duplicate"),
            "clock": (self.cmd_clock, "display a live updating clock", "clock"),
            "dice": (self.cmd_dice, "roll dice (e.g. dice 2d6)", "dice [NdM]"),
            "uuid": (self.cmd_uuid, "generate a random UUID", "uuid"),
            "base64": (self.cmd_base64, "encode or decode base64 text", "base64 <encode|decode> <text>"),
            "weather": (self.cmd_weather, "show weather for a city (wttr.in)", "weather [city]"),
            "qr": (self.cmd_qr, "generate a QR code from text (terminal)", "qr <text>"),
            "urlcheck": (self.cmd_urlcheck, "check if a URL is reachable", "urlcheck <url>"),
            "speed": (self.cmd_speed, "simple network speed test indicator", "speed"),
            "ports": (self.cmd_ports, "list listening ports", "ports"),
            "killtree": (self.cmd_killtree, "terminate a process and its children", "killtree <pid>"),
            "top": (self.cmd_top, "show top processes by memory usage", "top [count]"),
            "diff": (self.cmd_diff, "compare two files line by line", "diff <file1> <file2>"),
            "merge": (self.cmd_merge, "merge two sorted files", "merge <file1> <file2>"),
            "reverse": (self.cmd_reverse, "reverse lines of a file", "reverse <file>"),
            "head": (self.cmd_head, "show first N lines of a file", "head <file> [count]"),
            "tail": (self.cmd_tail, "show last N lines of a file", "tail <file> [count]"),
            "truncate": (self.cmd_truncate, "truncate a file to specified size", "truncate <file> <size>"),
            "touch": (self.cmd_touch, "update file timestamp or create empty file", "touch <file>"),
            "link": (self.cmd_link, "create a symbolic link", "link <target> <linkname>"),
            "perm": (self.cmd_perm, "show or change file permissions", "perm <path> [mode]"),
            "owner": (self.cmd_owner, "show file owner information", "owner <path>"),
            "compress": (self.cmd_compress, "compress a file or directory", "compress <path>"),
            "extract": (self.cmd_extract, "extract an archive", "extract <archive>"),
            "path": (self.cmd_path, "display or modify PATH variable", "path [add|remove <dir>]"),
            "run": (self.cmd_run, "execute a native system command passthrough", "run <command...>"),
            "theme": (self.cmd_theme, "change prompt color theme", "theme <name>"),
            "history-clear": (self.cmd_history_clear, "clear all command history", "history-clear"),
            "forget": (self.cmd_history_clear, "wipe all command history and suggestions", "forget"),
            "rain": (self.cmd_rain, "matrix-style digital rain animation", "rain [duration]"),
            "jot": (self.cmd_jot, "quick note taking", "jot [text]"),
            "agenda": (self.cmd_agenda, "todo list manager", "agenda [add|done|remove|list] [item]"),
            "countdown": (self.cmd_countdown, "countdown timer", "countdown <seconds>"),
            "tick": (self.cmd_tick, "stopwatch (press Enter to stop)", "tick"),
            "lock": (self.cmd_lock, "encrypt a file with password", "lock <file>"),
            "unlock": (self.cmd_unlock, "decrypt an encrypted file", "unlock <file>"),
            "address": (self.cmd_address, "show local and public IP addresses", "address"),
            "wireless": (self.cmd_wireless, "show WiFi network information", "wireless"),
            "power": (self.cmd_power, "show battery and power status", "power"),
            "pasteboard": (self.cmd_pasteboard, "copy text to or paste from clipboard", "pasteboard [copy <text>|paste]"),
            "mark": (self.cmd_mark, "directory bookmarks for quick navigation", "mark [add|remove|go|list] [name]"),
            "leap": (self.cmd_leap, "fuzzy jump to a frequently used directory", "leap <keyword>"),
            "latest": (self.cmd_latest, "show most recently modified files", "latest [count]"),
            "bigfind": (self.cmd_bigfind, "find largest files in a directory", "bigfind [path] [count]"),
            "version": (self.cmd_version, "show git status of current directory", "version"),
            "hint": (self.cmd_hint, "quick reference for common native commands", "hint [topic]"),
            "locate": (self.cmd_locate, "find where a native command is installed", "locate <command>"),
            "fragment": (self.cmd_fragment, "save and retrieve code snippets", "fragment [save|get|list|delete <name>]"),
            "unique": (self.cmd_unique, "remove duplicate lines from a file", "unique <file>"),
            "freq": (self.cmd_freq, "word frequency analysis of a file", "freq <file> [top_n]"),
            "voidfind": (self.cmd_voidfind, "find empty files and directories", "voidfind [path]"),
            "twinfind": (self.cmd_twinfind, "find duplicate files by size and hash", "twinfind [path]"),
            "manual": (self.cmd_manual, "view manual page for a native command", "manual <command>"),
            "config": (self.cmd_config, "view or set shell configuration options", "config [key] [value]"),
            "mask": (self.cmd_mask, "view or set file creation permission mask", "mask [octal]"),
            "detach": (self.cmd_detach, "run a native command in background detached", "detach <command...>"),
            "signout": (self.cmd_signout, "log out and return to login screen", "signout"),
            "vanish": (self.cmd_vanish, "delete current user account and return to login", "vanish"),
            "roster": (self.cmd_roster, "list all registered users (root only)", "roster"),
            "fortune": (self.cmd_fortune, "display a random quote or saying", "fortune"),
            "colors": (self.cmd_colors, "display terminal color palette test", "colors"),
            "calendar": (self.cmd_calendar, "show a calendar for current month", "calendar [month] [year]"),
            "coins": (self.cmd_coins, "flip a coin or multiple coins", "coins [count]"),
            "lorem": (self.cmd_lorem, "generate placeholder lorem ipsum text", "lorem [paragraphs]"),
            "slug": (self.cmd_slug, "convert text to URL-friendly slug", "slug <text>"),
            "case": (self.cmd_case, "convert text case (upper|lower|title|swap)", "case <mode> <text>"),
            "morse": (self.cmd_morse, "encode or decode morse code", "morse <encode|decode> <text>"),
            "roman": (self.cmd_roman, "convert between integer and roman numerals", "roman <number|numeral>"),
            "temperature": (self.cmd_temperature, "convert temperature units", "temperature <value> <C|F|K>"),
            "joke": (self.cmd_joke, "tell a random programming joke", "joke"),
            "birthday": (self.cmd_birthday, "calculate days until a date", "birthday <YYYY-MM-DD>"),
            "ascii": (self.cmd_ascii, "render text as ASCII art banner", "ascii <text>"),
            "moon": (self.cmd_moon, "show current moon phase", "moon"),
            "reverse-text": (self.cmd_reverse_text, "reverse a string of text", "reverse-text <text>"),
            "exec": (self.cmd_exec, "run a script file (py/bat/ps1/sh/vbs/js and more)", "exec <script> [args...]"),
            "pkg": (self.cmd_pkg, "package manager - install/remove/list/search/update packages", "pkg <install|remove|list|search|update> [package]"),
            "update": (self.cmd_update, "install and manage Python extension libraries", "update <install|remove|list|upgrade|python> [package]"),
            "py": (self.cmd_py, "run Python code or scripts with the embedded interpreter", "py <code|file> [args...]"),
        }

    def prompt(self):
        level = self.priv.current_level()
        if level == "root":
            user_color = Palette.BRIGHT_RED
        elif level == "admin":
            user_color = Palette.BRIGHT_YELLOW
        else:
            user_color = Palette.BRIGHT_GREEN
        mode_tag = f" [{self.mode}]" if self.mode == "virtual" else ""
        cwd_display = self._display_cwd()
        return (
            f"{Palette.BOLD}{Palette.BRIGHT_CYAN}NOVA{Palette.RESET}"
            f"{Palette.GRAY}@{Palette.RESET}"
            f"{Palette.BOLD}{user_color}{self.username}{Palette.RESET}"
            f"{Palette.GRAY}{mode_tag}{Palette.RESET}"
            f" {Palette.BRIGHT_BLUE}{cwd_display}{Palette.RESET}"
            f" {Palette.BRIGHT_MAGENTA}>{Palette.RESET} "
        )

    def _display_cwd(self):
        if self.mode == "virtual":
            cwd = self.vfs.cwd
        else:
            cwd = self.real_cwd
        home = os.path.expanduser("~")
        if self.mode == "real" and cwd.startswith(home):
            return "~" + cwd[len(home):]
        return cwd

    def run(self):
        _load_configs_from_exe()
        self._show_banner()
        while self.running:
            try:
                prompt_text = self.prompt()
                raw = self.editor.read(prompt_text)
                if raw == "__EXIT__":
                    line()
                    break
                if not raw.strip():
                    continue
                cmd = raw.strip()
                append_history(cmd, self.username)
                self.editor.history = load_history(self.username)
                spinner = ["|", "/", "-", "\\"]
                for i in range(4):
                    sys.stdout.write(f"\r\033[2K\033[90m{spinner[i]} 执行中...\033[0m")
                    sys.stdout.flush()
                    time.sleep(0.05)
                sys.stdout.write("\r\033[2K")
                sys.stdout.flush()
                self._execute(cmd)
            except KeyboardInterrupt:
                line()
                continue
            except EOFError:
                line()
                break
            except Exception as e:
                fail(f"unexpected shell error: {e}")
        _save_configs_to_exe()
        self._goodbye()

    def _execute(self, cmd_line):
        parts = self._tokenize(cmd_line)
        if not parts:
            return
        name = parts[0].lower()
        args = [a.strip("<>") for a in parts[1:]]
        if name in self.aliases:
            alias_cmd = self.aliases[name]
            expanded = self._tokenize(alias_cmd) + args
            name = expanded[0].lower()
            args = expanded[1:]
        if name not in self.commands:
            fail(f"unknown command '{name}'. type 'guide' for available commands.")
            return
        try:
            func, _, _ = self.commands[name]
            func(args)
        except Exception as e:
            fail(f"command '{name}' failed: {e}")

    def _tokenize(self, text):
        tokens = []
        current = []
        in_quote = None
        i = 0
        while i < len(text):
            ch = text[i]
            if in_quote:
                if ch == in_quote:
                    in_quote = None
                else:
                    current.append(ch)
            elif ch in ('"', "'"):
                in_quote = ch
            elif ch.isspace():
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(ch)
            i += 1
        if current:
            tokens.append("".join(current))
        return tokens

    def _resolve_path(self, path):
        if self.mode == "virtual":
            return self.vfs.normalize(path)
        if path == "~":
            return os.path.expanduser("~")
        if path.startswith("~/"):
            return os.path.expanduser("~") + path[1:]
        return os.path.abspath(os.path.join(self.real_cwd, path))

    def _show_banner(self):
        line()
        emit(f"  NOVA Shell", Palette.BOLD + Palette.BRIGHT_CYAN)
        emit(f"  {'\u00b7' * 30}", Palette.BRIGHT_CYAN)
        emit(f"  version {VERSION}   \u00b7   build {BUILD_TAG}", Palette.GRAY)
        emit(f"  {platform.system()} {platform.release()} ({platform.machine()})", Palette.GRAY)
        emit(f"  session: {self.username}", Palette.BRIGHT_GREEN)
        line()
        info("type 'guide' to see all commands")
        info("Ctrl+C = cancel   \u00b7   Ctrl+D = exit")
        line()

    def _goodbye(self):
        line()
        emit(f"  NOVA Shell session ended. Goodbye, {self.username}.", Palette.BRIGHT_CYAN)
        line()

    def cmd_guide(self, args):
        if args:
            name = args[0].lower()
            if name in self.commands:
                _, desc, usage = self.commands[name]
                emit(f"  {name}", Palette.BOLD + Palette.BRIGHT_CYAN)
                emit(f"    {desc}", Palette.WHITE)
                emit(f"    usage: {usage}", Palette.GRAY)
            else:
                fail(f"no such command: {name}")
            return
        line()
        emit("  NOVA Shell Command Reference", Palette.BOLD + Palette.BRIGHT_CYAN)
        line()
        categories = {
            "Core": ["guide", "ver", "banner", "wipe", "depart", "say", "who", "when", "signout", "vanish", "config", "colors"],
            "Navigation": ["roam", "peek", "whereami", "goback", "gohome", "tree", "mark", "leap", "latest"],
            "Files": ["forge", "mold", "erase", "clone", "relocate", "rebrand", "read", "inscribe", "append", "inspect", "measure", "edit", "preview", "touch", "truncate", "link", "lock", "unlock", "bigfind", "voidfind", "twinfind", "unique"],
            "Text": ["filter", "count", "sort", "head", "tail", "reverse", "diff", "merge", "freq", "slug", "case", "morse", "roman", "reverse-text", "ascii"],
            "System": ["tasks", "terminate", "killtree", "top", "environ", "setenv", "unsetenv", "sysinfo", "uptime", "ports", "perm", "owner", "path", "address", "wireless", "power", "version", "detach", "mask", "manual", "locate", "hint", "exec", "pkg", "cpu", "memory", "disk", "lockscreen"],
            "Security": ["elevate", "droppriv", "privilege", "digest", "lock", "unlock"],
            "VirtualFS": ["vmode", "vstatus"],
            "Network": ["probe", "fetch", "resolve", "urlcheck", "weather", "speed"],
            "Productivity": ["jot", "agenda", "countdown", "tick", "pasteboard", "fragment", "fortune", "joke", "calendar", "birthday", "moon"],
            "Fun": ["rain", "coins", "lorem", "temperature"],
            "Utilities": ["calc", "search", "recall", "alias", "unalias", "pause", "duplicate", "clock", "dice", "uuid", "base64", "qr", "compress", "extract", "run", "theme", "history-clear", "forget", "password", "url", "screenshot"],
        }
        for cat, cmds in categories.items():
            emit(f"  [{cat}]", Palette.BOLD + Palette.BRIGHT_YELLOW)
            for c in cmds:
                if c in self.commands:
                    _, desc, _ = self.commands[c]
                    emit(f"    {c:<16} {desc}", Palette.WHITE)
            line()

    def cmd_ver(self, args):
        emit(f"  NOVA Shell {VERSION}", Palette.BOLD + Palette.BRIGHT_CYAN)
        emit(f"  build: {BUILD_TAG}", Palette.GRAY)
        emit(f"  python: {sys.version.split()[0]}", Palette.GRAY)
        emit(f"  platform: {platform.platform()}", Palette.GRAY)

    def cmd_banner(self, args):
        self._show_banner()

    def cmd_wipe(self, args):
        sys.stdout.write("\033[H\033[2J\033[3J")
        sys.stdout.flush()

    def cmd_depart(self, args):
        self.running = False

    def cmd_who(self, args):
        level = self.priv.current_level()
        emit(f"  user:      {self.username}", Palette.BRIGHT_GREEN)
        emit(f"  privilege: {level}", Palette.BRIGHT_YELLOW if level != "user" else Palette.WHITE)
        emit(f"  shell:     NOVA {VERSION}", Palette.GRAY)
        emit(f"  mode:      {self.mode} filesystem", Palette.BRIGHT_CYAN)

    def cmd_when(self, args):
        now = datetime.datetime.now()
        emit(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}", Palette.BRIGHT_CYAN)
        emit(f"  {now.strftime('%A, %B %d, %Y')}", Palette.GRAY)
        emit(f"  timezone: {time.tzname[0]} (UTC{time.strftime('%z')})", Palette.GRAY)

    def cmd_say(self, args):
        line(" ".join(args), Palette.WHITE)

    def cmd_roam(self, args):
        if not args:
            self.real_cwd = os.path.expanduser("~")
            os.chdir(self.real_cwd)
            return
        target = args[0]
        if self.mode == "virtual":
            ok, err = self.vfs.chdir(target)
            if not ok:
                fail(err)
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such directory: {target}")
                return
            if not os.path.isdir(path):
                fail(f"not a directory: {target}")
                return
            self.last_dir = self.real_cwd
            self.real_cwd = path
            os.chdir(path)

    def cmd_peek(self, args):
        show_detail = "-l" in args
        path_args = [a for a in args if a != "-l"]
        target = path_args[0] if path_args else "."
        if self.mode == "virtual":
            nodes, err = self.vfs.list_dir(target)
            if nodes is None:
                fail(err)
                return
            for node in nodes:
                if node.type == "dir":
                    name_color = Palette.BRIGHT_BLUE
                    type_tag = "/"
                else:
                    name_color = Palette.WHITE
                    type_tag = ""
                if show_detail:
                    mtime = datetime.datetime.fromtimestamp(node.modified).strftime("%Y-%m-%d %H:%M")
                    emit(f"  {node.type:<4} {node.size:>8}  {mtime}  ", Palette.GRAY, end="")
                    emit(f"{node.name}{type_tag}", name_color)
                else:
                    emit(f"  {node.name}{type_tag}", name_color)
            if not show_detail:
                line()
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such directory: {target}")
                return
            if not os.path.isdir(path):
                fail(f"not a directory: {target}")
                return
            try:
                entries = sorted(os.listdir(path), key=lambda n: n.lower())
            except PermissionError:
                fail(f"permission denied: {target}")
                return
            for name in entries:
                full = os.path.join(path, name)
                try:
                    is_dir = os.path.isdir(full)
                    if show_detail:
                        stat_info = os.stat(full)
                        size = stat_info.st_size
                        mtime = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M")
                        perms = stat.filemode(stat_info.st_mode)
                        emit(f"  {perms} {size:>10}  {mtime}  ", Palette.GRAY, end="")
                        emit(f"{name}{'/' if is_dir else ''}", Palette.BRIGHT_BLUE if is_dir else Palette.WHITE)
                    else:
                        emit(f"  {name}{'/' if is_dir else ''}", Palette.BRIGHT_BLUE if is_dir else Palette.WHITE)
                except PermissionError:
                    emit(f"  {name}  [permission denied]", Palette.BRIGHT_RED)
            if not show_detail:
                line()

    def cmd_whereami(self, args):
        if self.mode == "virtual":
            emit(f"  {self.vfs.cwd}", Palette.BRIGHT_CYAN)
        else:
            emit(f"  {self.real_cwd}", Palette.BRIGHT_CYAN)

    def cmd_goback(self, args):
        if self.mode == "virtual":
            parent = os.path.dirname(self.vfs.cwd.rstrip("/"))
            if parent:
                self.vfs.cwd = parent
            else:
                self.vfs.cwd = "/"
        else:
            tmp = self.real_cwd
            self.real_cwd = self.last_dir
            self.last_dir = tmp
            os.chdir(self.real_cwd)

    def cmd_gohome(self, args):
        if self.mode == "virtual":
            self.vfs.cwd = "/home"
        else:
            self.last_dir = self.real_cwd
            self.real_cwd = os.path.expanduser("~")
            os.chdir(self.real_cwd)

    def cmd_forge(self, args):
        if not args:
            fail("usage: forge <filename>")
            return
        name = args[0]
        if self.mode == "virtual":
            ok, err = self.vfs.mkfile(name)
            if ok:
                done(f"created file: {name}")
            else:
                fail(err)
        else:
            path = self._resolve_path(name)
            if os.path.exists(path):
                fail(f"already exists: {name}")
                return
            try:
                open(path, "a").close()
                done(f"created file: {name}")
            except PermissionError:
                fail(f"permission denied: {name}")
            except Exception as e:
                fail(str(e))

    def cmd_mold(self, args):
        if not args:
            fail("usage: mold <dirname>")
            return
        name = args[0]
        if self.mode == "virtual":
            ok, err = self.vfs.mkdir(name)
            if ok:
                done(f"created directory: {name}")
            else:
                fail(err)
        else:
            path = self._resolve_path(name)
            if os.path.exists(path):
                fail(f"already exists: {name}")
                return
            try:
                os.makedirs(path, exist_ok=True)
                done(f"created directory: {name}")
            except PermissionError:
                fail(f"permission denied: {name}")
            except Exception as e:
                fail(str(e))

    def cmd_erase(self, args):
        if not args:
            fail("usage: erase <path>")
            return
        target = args[0]
        if self.mode == "virtual":
            ok, err = self.vfs.remove(target)
            if ok:
                done(f"removed: {target}")
            else:
                fail(err)
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such path: {target}")
                return
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                done(f"removed: {target}")
            except PermissionError:
                fail(f"permission denied: {target}")
            except Exception as e:
                fail(str(e))

    def cmd_clone(self, args):
        if len(args) < 2:
            fail("usage: clone <source> <destination>")
            return
        src, dst = args[0], args[1]
        if self.mode == "virtual":
            ok, err = self.vfs.copy(src, dst)
            if ok:
                done(f"copied {src} -> {dst}")
            else:
                fail(err)
        else:
            src_path = self._resolve_path(src)
            dst_path = self._resolve_path(dst)
            if not os.path.exists(src_path):
                fail(f"source not found: {src}")
                return
            try:
                if os.path.isdir(src_path):
                    if os.path.exists(dst_path):
                        dst_path = os.path.join(dst_path, os.path.basename(src_path))
                    shutil.copytree(src_path, dst_path)
                else:
                    if os.path.isdir(dst_path):
                        dst_path = os.path.join(dst_path, os.path.basename(src_path))
                    shutil.copy2(src_path, dst_path)
                done(f"copied {src} -> {dst}")
            except PermissionError:
                fail(f"permission denied")
            except Exception as e:
                fail(str(e))

    def cmd_relocate(self, args):
        if len(args) < 2:
            fail("usage: relocate <source> <destination>")
            return
        src, dst = args[0], args[1]
        if self.mode == "virtual":
            ok, err = self.vfs.move(src, dst)
            if ok:
                done(f"moved {src} -> {dst}")
            else:
                fail(err)
        else:
            src_path = self._resolve_path(src)
            dst_path = self._resolve_path(dst)
            if not os.path.exists(src_path):
                fail(f"source not found: {src}")
                return
            try:
                shutil.move(src_path, dst_path)
                done(f"moved {src} -> {dst}")
            except PermissionError:
                fail(f"permission denied")
            except Exception as e:
                fail(str(e))

    def cmd_rebrand(self, args):
        if len(args) < 2:
            fail("usage: rebrand <oldname> <newname>")
            return
        old, new = args[0], args[1]
        if self.mode == "virtual":
            ok, err = self.vfs.move(old, new)
            if ok:
                done(f"renamed {old} -> {new}")
            else:
                fail(err)
        else:
            old_path = self._resolve_path(old)
            new_path = self._resolve_path(new)
            if not os.path.exists(old_path):
                fail(f"not found: {old}")
                return
            try:
                os.rename(old_path, new_path)
                done(f"renamed {old} -> {new}")
            except PermissionError:
                fail(f"permission denied")
            except Exception as e:
                fail(str(e))

    def cmd_read(self, args):
        if not args:
            fail("usage: read <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            sys.stdout.write(content)
            if not content.endswith("\n"):
                line()
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            if not os.path.isfile(path):
                fail(f"not a file: {target}")
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                sys.stdout.write(content)
                if not content.endswith("\n"):
                    line()
            except PermissionError:
                fail(f"permission denied: {target}")
            except Exception as e:
                fail(str(e))

    def cmd_inscribe(self, args):
        if len(args) < 2:
            fail("usage: inscribe <file> <text>")
            return
        target = args[0]
        text = " ".join(args[1:])
        if self.mode == "virtual":
            ok, err = self.vfs.write_file(target, text + "\n")
            if ok:
                done(f"written to {target}")
            else:
                fail(err)
        else:
            path = self._resolve_path(target)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
                done(f"written to {target}")
            except PermissionError:
                fail(f"permission denied: {target}")
            except Exception as e:
                fail(str(e))

    def cmd_append(self, args):
        if len(args) < 2:
            fail("usage: append <file> <text>")
            return
        target = args[0]
        text = " ".join(args[1:])
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                ok, err = self.vfs.mkfile(target, text + "\n")
            else:
                ok, err = self.vfs.write_file(target, content + text + "\n")
            if ok:
                done(f"appended to {target}")
            else:
                fail(err)
        else:
            path = self._resolve_path(target)
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
                done(f"appended to {target}")
            except PermissionError:
                fail(f"permission denied: {target}")
            except Exception as e:
                fail(str(e))

    def cmd_inspect(self, args):
        if not args:
            fail("usage: inspect <path>")
            return
        target = args[0]
        if self.mode == "virtual":
            node = self.vfs.resolve(target)
            if node is None:
                fail(f"no such path: {target}")
                return
            emit(f"  name:      {node.name}", Palette.BRIGHT_CYAN)
            emit(f"  type:      {node.type}", Palette.WHITE)
            emit(f"  size:      {node.size} bytes", Palette.WHITE)
            emit(f"  created:   {datetime.datetime.fromtimestamp(node.created).strftime('%Y-%m-%d %H:%M:%S')}", Palette.GRAY)
            emit(f"  modified:  {datetime.datetime.fromtimestamp(node.modified).strftime('%Y-%m-%d %H:%M:%S')}", Palette.GRAY)
            if node.type == "dir":
                emit(f"  entries:   {len(node.children)}", Palette.WHITE)
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such path: {target}")
                return
            try:
                st = os.stat(path)
                emit(f"  name:      {os.path.basename(path)}", Palette.BRIGHT_CYAN)
                emit(f"  type:      {'directory' if os.path.isdir(path) else 'file'}", Palette.WHITE)
                emit(f"  size:      {st.st_size} bytes", Palette.WHITE)
                emit(f"  created:   {datetime.datetime.fromtimestamp(st.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}", Palette.GRAY)
                emit(f"  modified:  {datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}", Palette.GRAY)
                emit(f"  accessed:  {datetime.datetime.fromtimestamp(st.st_atime).strftime('%Y-%m-%d %H:%M:%S')}", Palette.GRAY)
                emit(f"  mode:      {stat.filemode(st.st_mode)}", Palette.WHITE)
                if hasattr(st, "st_uid"):
                    emit(f"  uid/gid:   {st.st_uid}/{st.st_gid}", Palette.GRAY)
            except PermissionError:
                fail(f"permission denied: {target}")

    def cmd_measure(self, args):
        if not args:
            fail("usage: measure <path>")
            return
        target = args[0]
        if self.mode == "virtual":
            node = self.vfs.resolve(target)
            if node is None:
                fail(f"no such path: {target}")
                return
            total = self._vfs_size(node)
            emit(f"  {self._human_size(total)}  ({target})", Palette.BRIGHT_GREEN)
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such path: {target}")
                return
            total = 0
            count = 0
            if os.path.isfile(path):
                total = os.path.getsize(path)
                count = 1
            else:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                            count += 1
                        except Exception:
                            pass
            emit(f"  {self._human_size(total)}  in {count} file(s)  ({target})", Palette.BRIGHT_GREEN)

    def _vfs_size(self, node):
        if node.type == "file":
            return node.size
        total = 0
        for child in node.children.values():
            total += self._vfs_size(child)
        return total

    def _human_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def cmd_tasks(self, args):
        try:
            if IS_WINDOWS:
                result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10)
                lines = result.stdout.strip().split("\n")
                emit(f"  {'PID':<8} {'MEM(KB)':<12} {'NAME'}", Palette.BOLD + Palette.BRIGHT_YELLOW)
                for ln in lines[:50]:
                    parts = [p.strip('"') for p in ln.split('","')]
                    if len(parts) >= 5:
                        name = parts[0]
                        pid = parts[1]
                        mem = parts[4].replace(",", "").replace(" K", "")
                        emit(f"  {pid:<8} {mem:<12} {name}", Palette.WHITE)
            else:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
                lines = result.stdout.strip().split("\n")
                header = lines[0]
                emit(f"  {header}", Palette.BOLD + Palette.BRIGHT_YELLOW)
                for ln in lines[1:51]:
                    emit(f"  {ln}", Palette.WHITE)
        except Exception as e:
            fail(f"could not list processes: {e}")

    def cmd_terminate(self, args):
        if not args:
            fail("usage: terminate <pid>")
            return
        try:
            pid = int(args[0])
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
            else:
                os.kill(pid, signal.SIGTERM)
            done(f"sent termination signal to PID {pid}")
        except ValueError:
            fail("PID must be a number")
        except ProcessLookupError:
            fail(f"no process with PID {pid}")
        except PermissionError:
            fail(f"permission denied: cannot terminate PID {pid}")
        except Exception as e:
            fail(str(e))

    def cmd_environ(self, args):
        for key in sorted(os.environ.keys()):
            val = os.environ[key]
            if len(val) > 80:
                val = val[:77] + "..."
            emit(f"  {key}=", Palette.BRIGHT_CYAN, end="")
            emit(f"{val}", Palette.WHITE)

    def cmd_setenv(self, args):
        if len(args) < 2:
            fail("usage: setenv <name> <value>")
            return
        name = args[0]
        value = " ".join(args[1:])
        os.environ[name] = value
        done(f"set {name}={value}")

    def cmd_unsetenv(self, args):
        if not args:
            fail("usage: unsetenv <name>")
            return
        name = args[0]
        if name in os.environ:
            del os.environ[name]
            done(f"removed {name}")
        else:
            warn(f"{name} was not set")

    def cmd_sysinfo(self, args):
        line()
        emit(f"  System Information", Palette.BOLD + Palette.BRIGHT_CYAN)
        line()
        emit(f"  OS:          {platform.system()} {platform.release()}", Palette.WHITE)
        emit(f"  Version:     {platform.version()}", Palette.WHITE)
        emit(f"  Architecture:{platform.machine()}", Palette.WHITE)
        emit(f"  Processor:   {platform.processor() or 'unknown'}", Palette.WHITE)
        emit(f"  Hostname:    {platform.node()}", Palette.WHITE)
        emit(f"  Python:      {sys.version.split()[0]}", Palette.WHITE)
        emit(f"  Shell:       NOVA {VERSION}", Palette.WHITE)
        try:
            if IS_WINDOWS:
                mem = ctypes.windll.kernel32
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                mem.GlobalMemoryStatusEx(ctypes.byref(stat))
                emit(f"  Total RAM:   {self._human_size(stat.ullTotalPhys)}", Palette.WHITE)
                emit(f"  Available:   {self._human_size(stat.ullAvailPhys)}", Palette.WHITE)
                emit(f"  Memory Load: {stat.dwMemoryLoad}%", Palette.WHITE)
            else:
                with open("/proc/meminfo", "r") as f:
                    for ln in f:
                        if "MemTotal" in ln or "MemAvailable" in ln:
                            parts = ln.split()
                            val_kb = int(parts[1])
                            emit(f"  {parts[0].rstrip(':'):<12} {self._human_size(val_kb * 1024)}", Palette.WHITE)
        except Exception:
            pass
        try:
            cpu_count = os.cpu_count() or 0
            emit(f"  CPU Cores:   {cpu_count}", Palette.WHITE)
        except Exception:
            pass
        line()

    def cmd_uptime(self, args):
        try:
            if IS_WINDOWS:
                result = subprocess.run(["net", "statistics", "workstation"], capture_output=True, text=True, timeout=10)
                for ln in result.stdout.split("\n"):
                    if "Statistics since" in ln or "统计时间" in ln:
                        emit(f"  {ln.strip()}", Palette.BRIGHT_CYAN)
                        return
                boot = ctypes.windll.kernel32.GetTickCount64() / 1000
                hours = int(boot // 3600)
                mins = int((boot % 3600) // 60)
                emit(f"  system uptime: {hours}h {mins}m", Palette.BRIGHT_CYAN)
            else:
                with open("/proc/uptime", "r") as f:
                    uptime_sec = float(f.read().split()[0])
                days = int(uptime_sec // 86400)
                hours = int((uptime_sec % 86400) // 3600)
                mins = int((uptime_sec % 3600) // 60)
                emit(f"  system uptime: {days}d {hours}h {mins}m", Palette.BRIGHT_CYAN)
        except Exception as e:
            fail(str(e))

    def cmd_recall(self, args):
        history = load_history(self.username)
        count = int(args[0]) if args else len(history)
        if not history:
            info("no command history yet")
            return
        start = max(0, len(history) - count)
        for i, cmd in enumerate(history[start:], start + 1):
            emit(f"  {i:>5}  ", Palette.GRAY, end="")
            emit(f"{cmd}", Palette.WHITE)

    def cmd_elevate(self, args):
        info("attempting privilege elevation...")
        ok, msg = self.priv.elevate()
        if ok:
            done(msg)
        else:
            fail(msg)

    def cmd_droppriv(self, args):
        ok, msg = self.priv.drop()
        if ok:
            done(msg)

    def cmd_privilege(self, args):
        level = self.priv.current_level()
        color = Palette.BRIGHT_RED if level == "root" else (Palette.BRIGHT_YELLOW if level == "admin" else Palette.WHITE)
        emit(f"  current privilege level: {level}", color)
        if self.priv.elevated:
            emit(f"  session elevation: active", Palette.BRIGHT_GREEN)
        else:
            emit(f"  session elevation: inactive", Palette.GRAY)

    def cmd_vmode(self, args):
        if not args:
            fail("usage: vmode <virtual|real>")
            return
        mode = args[0].lower()
        if mode == "virtual":
            self.mode = "virtual"
            done("switched to virtual in-memory filesystem")
            info("all changes exist only in memory and are lost on exit")
        elif mode == "real":
            self.mode = "real"
            done("switched to real host filesystem")
            info("changes follow native OS permission rules")
        else:
            fail(f"unknown mode: {mode}. use 'virtual' or 'real'")

    def cmd_vstatus(self, args):
        emit(f"  mode:          {self.mode}", Palette.BRIGHT_CYAN)
        if self.mode == "virtual":
            emit(f"  virtual cwd:   {self.vfs.cwd}", Palette.WHITE)
            total = self._vfs_size(self.vfs.root)
            emit(f"  virtual size:  {self._human_size(total)}", Palette.WHITE)
            emit(f"  persistence:   memory only (lost on exit)", Palette.BRIGHT_YELLOW)
        else:
            emit(f"  real cwd:      {self.real_cwd}", Palette.WHITE)
            emit(f"  persistence:   native OS filesystem", Palette.BRIGHT_GREEN)

    def cmd_probe(self, args):
        if not args:
            fail("usage: probe <host> [count]")
            return
        host = args[0]
        count = int(args[1]) if len(args) > 1 else 4
        info(f"probing {host} ({count} packets)...")
        try:
            if IS_WINDOWS:
                cmd = ["ping", "-n", str(count), host]
            else:
                cmd = ["ping", "-c", str(count), host]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            for ln in result.stdout.split("\n"):
                if ln.strip():
                    if "TTL" in ln or "ttl" in ln or "bytes from" in ln:
                        emit(f"  {ln.strip()}", Palette.BRIGHT_GREEN)
                    elif "Request timeout" in ln or "100% packet loss" in ln or "Destination" in ln:
                        emit(f"  {ln.strip()}", Palette.BRIGHT_RED)
                    elif "packets" in ln or "rtt" in ln or "Approximate" in ln or "Minimum" in ln:
                        emit(f"  {ln.strip()}", Palette.BRIGHT_CYAN)
        except subprocess.TimeoutExpired:
            fail("ping timed out")
        except Exception as e:
            fail(str(e))

    def cmd_fetch(self, args):
        if not args:
            fail("usage: fetch <url> [output_filename]")
            return
        url = args[0]
        output = args[1] if len(args) > 1 else os.path.basename(url.split("?")[0]) or "download.bin"
        if self.mode == "virtual":
            output_path = output
        else:
            output_path = self._resolve_path(output)
        info(f"downloading: {url}")
        info(f"saving to:   {output}")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NOVA-Shell/2.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 8192
                data = b""
                start_time = time.time()
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    data += chunk
                    downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    if total > 0:
                        pct = downloaded / total * 100
                        bar_len = 30
                        filled = int(bar_len * downloaded / total)
                        bar = "=" * filled + ">" + "." * (bar_len - filled - 1)
                        put(f"\r  [{Palette.BRIGHT_GREEN}{bar}{Palette.RESET}] ")
                        put(f"{Palette.BRIGHT_CYAN}{pct:5.1f}%{Palette.RESET}  ")
                        put(f"{Palette.BRIGHT_YELLOW}{self._human_size(downloaded)}/{self._human_size(total)}{Palette.RESET}  ")
                        put(f"{Palette.BRIGHT_MAGENTA}{self._human_size(speed)}/s{Palette.RESET}   ")
                    else:
                        put(f"\r  {Palette.BRIGHT_CYAN}{self._human_size(downloaded)}{Palette.RESET} downloaded  ")
                        put(f"{Palette.BRIGHT_MAGENTA}{self._human_size(speed)}/s{Palette.RESET}   ")
                    sys.stdout.flush()
                line()
                if self.mode == "virtual":
                    text_content = data.decode("utf-8", errors="replace")
                    ok, err = self.vfs.write_file(output, text_content)
                    if not ok:
                        fail(err)
                        return
                else:
                    with open(output_path, "wb") as f:
                        f.write(data)
                elapsed = time.time() - start_time
                done(f"download complete: {output} ({self._human_size(downloaded)} in {elapsed:.1f}s)")
        except urllib.error.URLError as e:
            fail(f"download failed: {e.reason}")
        except Exception as e:
            fail(f"download failed: {e}")

    def cmd_resolve(self, args):
        if not args:
            fail("usage: resolve <domain>")
            return
        domain = args[0]
        info(f"resolving {domain}...")
        try:
            infos = socket.getaddrinfo(domain, None)
            seen = set()
            for info in infos:
                ip = info[4][0]
                if ip not in seen:
                    seen.add(ip)
                    family = "IPv6" if info[0] == socket.AF_INET6 else "IPv4"
                    emit(f"  {family:<6} {ip}", Palette.BRIGHT_GREEN)
            if not seen:
                warn("no addresses found")
        except socket.gaierror as e:
            fail(f"DNS resolution failed: {e}")
        except Exception as e:
            fail(str(e))

    def cmd_calc(self, args):
        if not args:
            fail("usage: calc <expression>")
            return
        expr = " ".join(args)
        try:
            safe_dict = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
            safe_dict.update({"abs": abs, "round": round, "min": min, "max": max, "int": int, "float": float})
            result = eval(expr, {"__builtins__": {}}, safe_dict)
            emit(f"  {expr} = {result}", Palette.BRIGHT_GREEN)
        except Exception as e:
            fail(f"calculation error: {e}")

    def cmd_digest(self, args):
        if not args:
            fail("usage: digest <file> [md5|sha1|sha256|sha512]")
            return
        target = args[0]
        algo = args[1].lower() if len(args) > 1 else "sha256"
        if algo not in ("md5", "sha1", "sha256", "sha512"):
            fail(f"unsupported algorithm: {algo}")
            return
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            h = hashlib.new(algo)
            h.update(content.encode("utf-8"))
            emit(f"  {algo.upper()}: {h.hexdigest()}", Palette.BRIGHT_GREEN)
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            try:
                h = hashlib.new(algo)
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        h.update(chunk)
                emit(f"  {algo.upper()}: {h.hexdigest()}", Palette.BRIGHT_GREEN)
            except PermissionError:
                fail(f"permission denied: {target}")

    def cmd_search(self, args):
        if len(args) < 2:
            fail("usage: search <path> <pattern>")
            return
        root_path = args[0]
        pattern = args[1]
        if self.mode == "virtual":
            node = self.vfs.resolve(root_path)
            if node is None:
                fail(f"no such path: {root_path}")
                return
            matches = []
            self._vfs_search(node, pattern, root_path, matches)
            for m in matches:
                emit(f"  {m}", Palette.BRIGHT_GREEN)
            if not matches:
                info("no matches found")
        else:
            path = self._resolve_path(root_path)
            if not os.path.exists(path):
                fail(f"no such path: {root_path}")
                return
            regex = re.compile(pattern, re.IGNORECASE)
            count = 0
            for root, dirs, files in os.walk(path):
                for name in files + dirs:
                    if regex.search(name):
                        full = os.path.join(root, name)
                        emit(f"  {full}", Palette.BRIGHT_GREEN)
                        count += 1
                        if count >= 100:
                            warn("showing first 100 matches")
                            return
            if count == 0:
                info("no matches found")

    def _vfs_search(self, node, pattern, path, matches):
        regex = re.compile(pattern, re.IGNORECASE)
        for child in node.children.values():
            child_path = path.rstrip("/") + "/" + child.name
            if regex.search(child.name):
                matches.append(child_path)
            if child.type == "dir":
                self._vfs_search(child, pattern, child_path, matches)

    def cmd_filter(self, args):
        if len(args) < 2:
            fail("usage: filter <pattern> <file>")
            return
        pattern = args[0]
        target = args[1]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception as e:
                fail(str(e))
                return
        regex = re.compile(pattern, re.IGNORECASE)
        count = 0
        for i, ln in enumerate(lines, 1):
            if regex.search(ln):
                emit(f"  {i:>5}:", Palette.GRAY, end="")
                highlighted = regex.sub(lambda m: f"{Palette.BRIGHT_YELLOW}{m.group()}{Palette.RESET}", ln.rstrip())
                emit(f" {highlighted}", Palette.WHITE)
                count += 1
        if count == 0:
            info("no matching lines")

    def cmd_count(self, args):
        if not args:
            fail("usage: count <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            text = content
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                fail(str(e))
                return
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        words = len(text.split())
        chars = len(text)
        bytes_count = len(text.encode("utf-8"))
        emit(f"  lines:   {lines}", Palette.BRIGHT_CYAN)
        emit(f"  words:   {words}", Palette.BRIGHT_CYAN)
        emit(f"  chars:   {chars}", Palette.BRIGHT_CYAN)
        emit(f"  bytes:   {bytes_count}", Palette.BRIGHT_CYAN)

    def cmd_sort(self, args):
        if not args:
            fail("usage: sort <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
            lines.sort(key=str.lower)
            self.vfs.write_file(target, "\n".join(lines))
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                lines.sort(key=str.lower)
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                done(f"sorted {target}")
            except Exception as e:
                fail(str(e))

    def cmd_alias(self, args):
        if not args:
            if not self.aliases:
                info("no aliases defined")
            for name, cmd in sorted(self.aliases.items()):
                emit(f"  {name} = {cmd}", Palette.BRIGHT_CYAN)
            return
        if len(args) < 2:
            fail("usage: alias <name> <command>")
            return
        name = args[0].lower()
        cmd = " ".join(args[1:])
        self.aliases[name] = cmd
        save_aliases(self.aliases)
        done(f"alias '{name}' -> '{cmd}'")

    def cmd_unalias(self, args):
        if not args:
            fail("usage: unalias <name>")
            return
        name = args[0].lower()
        if name in self.aliases:
            del self.aliases[name]
            save_aliases(self.aliases)
            done(f"removed alias '{name}'")
        else:
            fail(f"no such alias: {name}")

    def cmd_pause(self, args):
        if not args:
            fail("usage: pause <seconds>")
            return
        try:
            seconds = float(args[0])
            time.sleep(seconds)
            done(f"paused for {seconds}s")
        except ValueError:
            fail("seconds must be a number")

    def _show_image_window(self, path, title=None, extra_info=""):
        if not HAS_TKINTER:
            fail("image preview requires tkinter GUI environment")
            return False
        try:
            from PIL import Image, ImageTk
            import tkinter as tk
            img = Image.open(path)
            ow, oh = img.width, img.height
            root = tk.Tk()
            root.title(title or os.path.basename(path))
            root.configure(bg="#0f0f1a")
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            max_w = int(sw * 0.85)
            max_h = int(sh * 0.8)
            if ow > max_w or oh > max_h:
                ratio = min(max_w / ow, max_h / oh)
                img = img.resize((int(ow * ratio), int(oh * ratio)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label = tk.Label(root, image=photo, bg="#0f0f1a")
            label.image = photo
            label.pack(padx=12, pady=12)
            info_text = f"{os.path.basename(path)}  |  {ow} x {oh}"
            if extra_info:
                info_text += f"  |  {extra_info}"
            info = tk.Label(root, text=info_text, bg="#0f0f1a", fg="#6b7280", font=("Consolas", 9))
            info.pack(pady=(0, 12))
            root.bind("<Escape>", lambda e: root.destroy())
            root.mainloop()
            return True
        except Exception as e:
            fail(f"preview window error: {e}")
            return False

    def cmd_preview(self, args):
        if not args:
            fail("usage: preview <file>")
            return
        target = args[0]
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"file not found: {target}")
            return
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        text_exts = {".txt", ".py", ".bat", ".cmd", ".ps1", ".sh", ".json", ".xml", ".html", ".css", ".js", ".md", ".csv", ".log", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml"}
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp", ".tiff"}
        video_exts = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}
        audio_exts = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"}
        if ext in text_exts:
            info(f"preview: {target} ({size:,} bytes)")
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                lines = content.split("\n")
                for i, ln in enumerate(lines[:50], 1):
                    emit(f"  {i:>4}: {ln}", Palette.WHITE)
                if len(lines) > 50:
                    info(f"... ({len(lines) - 50} more lines, use read to see all)")
            except Exception as e:
                fail(str(e))
        elif ext in image_exts:
            info(f"opening preview window: {target} ({size:,} bytes)")
            self._show_image_window(path, title=f"NOVA Preview - {os.path.basename(path)}")
        elif ext in video_exts:
            info(f"preview video: {target} ({size:,} bytes)")
            try:
                import cv2
                cap = cv2.VideoCapture(path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    dur = fc / fps if fps > 0 else 0
                    emit(f"  resolution: {w}x{h}", Palette.WHITE)
                    emit(f"  fps: {fps:.1f}", Palette.WHITE)
                    emit(f"  frames: {fc}", Palette.WHITE)
                    emit(f"  duration: {dur:.1f}s", Palette.WHITE)
                    ret, frame = cap.read()
                    if ret:
                        from PIL import Image
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(frame_rgb)
                        tmp = os.path.join(tempfile.gettempdir(), f"nova_frame_{int(time.time())}.png")
                        pil_img.save(tmp)
                        cap.release()
                        info("opening first frame preview window...")
                        extra = f"{dur:.1f}s  |  {fps:.0f}fps"
                        self._show_image_window(tmp, title=f"NOVA Preview - {os.path.basename(path)} (first frame)", extra_info=extra)
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                    else:
                        cap.release()
                else:
                    fail("could not open video")
            except ImportError:
                emit(f"  (OpenCV required for video preview: pkg install opencv-python)", Palette.GRAY)
            except Exception as e:
                fail(str(e))
        elif ext in audio_exts:
            info(f"preview audio: {target} ({size:,} bytes)")
            try:
                import wave
                if ext == ".wav":
                    with wave.open(path, "rb") as wf:
                        ch = wf.getnchannels()
                        sw = wf.getsampwidth()
                        fr = wf.getframerate()
                        nf = wf.getnframes()
                        dur = nf / fr if fr > 0 else 0
                        emit(f"  channels: {ch}", Palette.WHITE)
                        emit(f"  sample width: {sw*8} bit", Palette.WHITE)
                        emit(f"  sample rate: {fr} Hz", Palette.WHITE)
                        emit(f"  duration: {dur:.1f}s", Palette.WHITE)
                else:
                    emit(f"  (metadata preview for {ext} not available, file size: {size:,} bytes)", Palette.GRAY)
            except Exception as e:
                fail(str(e))
        elif ext == ".pdf":
            info(f"preview PDF: {target} ({size:,} bytes)")
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
                npages = len(reader.pages)
                emit(f"  pages: {npages}", Palette.WHITE)
                line()
                for i, page in enumerate(reader.pages[:3]):
                    text = page.extract_text() or ""
                    emit(f"  --- Page {i+1} ---", Palette.BRIGHT_CYAN)
                    for ln in text.split("\n")[:20]:
                        emit(f"  {ln}", Palette.WHITE)
                    if len(text.split("\n")) > 20:
                        emit(f"  ... (more on page {i+1})", Palette.GRAY)
                    line()
                if npages > 3:
                    info(f"... ({npages - 3} more pages)")
            except ImportError:
                emit(f"  (install PyPDF2 for PDF preview: pkg install PyPDF2)", Palette.GRAY)
            except Exception as e:
                fail(str(e))
        else:
            info(f"preview: {target} ({size:,} bytes)")
            warn(f"unknown file type: {ext}")
            emit(f"  use 'read' for text files, 'edit' to edit", Palette.GRAY)

    def cmd_password(self, args):
        length = 16
        if args:
            try:
                length = int(args[0])
            except ValueError:
                fail("length must be a number")
                return
        if length < 4:
            fail("length must be at least 4")
            return
        if length > 128:
            fail("length must be at most 128")
            return
        chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"
        password = "".join(random.choice(chars) for _ in range(length))
        emit(f"  {password}", Palette.BRIGHT_GREEN)
        try:
            import subprocess
            subprocess.run(["clip"], input=password.encode("utf-16"), check=False)
            info("copied to clipboard")
        except Exception:
            pass

    def cmd_cpu(self, args):
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            emit(f"  CPU Usage: {cpu_percent}%", Palette.BRIGHT_YELLOW)
            for i, p in enumerate(psutil.cpu_percent(percpu=True)):
                bar = "#" * int(p / 5) + "-" * (20 - int(p / 5))
                emit(f"  Core {i}: [{bar}] {p}%", Palette.WHITE)
        except ImportError:
            if IS_WINDOWS:
                try:
                    import ctypes
                    class FILETIME(ctypes.Structure):
                        _fields_ = [("dwLowDateTime", ctypes.c_uint), ("dwHighDateTime", ctypes.c_uint)]
                    def get_times():
                        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
                        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
                        return (idle.dwLowDateTime | (idle.dwHighDateTime << 32),
                                kernel.dwLowDateTime | (kernel.dwHighDateTime << 32),
                                user.dwLowDateTime | (user.dwHighDateTime << 32))
                    i1, k1, u1 = get_times()
                    time.sleep(0.5)
                    i2, k2, u2 = get_times()
                    idle_d = i2 - i1
                    kernel_d = k2 - k1
                    user_d = u2 - u1
                    total = kernel_d + user_d
                    if total > 0:
                        cpu = (1 - idle_d / total) * 100
                        emit(f"  CPU Usage: {cpu:.1f}%", Palette.BRIGHT_YELLOW)
                    else:
                        fail("could not read CPU usage")
                except Exception as e:
                    fail(str(e))
            else:
                fail("psutil not installed, run: pkg install psutil")

    def cmd_memory(self, args):
        try:
            import psutil
            mem = psutil.virtual_memory()
            emit(f"  Total: {mem.total / 1024**3:.1f} GB", Palette.WHITE)
            emit(f"  Used:  {mem.used / 1024**3:.1f} GB ({mem.percent}%)", Palette.BRIGHT_RED)
            emit(f"  Free:  {mem.available / 1024**3:.1f} GB", Palette.BRIGHT_GREEN)
            bar = "#" * int(mem.percent / 5) + "-" * (20 - int(mem.percent / 5))
            emit(f"  [{bar}] {mem.percent}%", Palette.WHITE)
        except ImportError:
            if IS_WINDOWS:
                try:
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [("dwLength", ctypes.c_uint), ("dwMemoryLoad", ctypes.c_uint),
                                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(stat)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    total_gb = stat.ullTotalPhys / 1024**3
                    avail_gb = stat.ullAvailPhys / 1024**3
                    used_gb = total_gb - avail_gb
                    emit(f"  Total: {total_gb:.1f} GB", Palette.WHITE)
                    emit(f"  Used:  {used_gb:.1f} GB ({stat.dwMemoryLoad}%)", Palette.BRIGHT_RED)
                    emit(f"  Free:  {avail_gb:.1f} GB", Palette.BRIGHT_GREEN)
                except Exception as e:
                    fail(str(e))
            else:
                fail("psutil not installed, run: pkg install psutil")

    def cmd_disk(self, args):
        target = args[0] if args else self.real_cwd
        try:
            usage = shutil.disk_usage(target)
            total_gb = usage.total / 1024**3
            used_gb = usage.used / 1024**3
            free_gb = usage.free / 1024**3
            percent = (usage.used / usage.total) * 100
            emit(f"  Disk: {target}", Palette.BRIGHT_CYAN)
            emit(f"  Total: {total_gb:.1f} GB", Palette.WHITE)
            emit(f"  Used:  {used_gb:.1f} GB ({percent:.1f}%)", Palette.BRIGHT_RED)
            emit(f"  Free:  {free_gb:.1f} GB", Palette.BRIGHT_GREEN)
            bar = "#" * int(percent / 5) + "-" * (20 - int(percent / 5))
            emit(f"  [{bar}] {percent:.1f}%", Palette.WHITE)
        except Exception as e:
            fail(str(e))

    def cmd_lockscreen(self, args):
        if IS_WINDOWS:
            try:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                done("workstation locked")
            except Exception as e:
                fail(str(e))
        else:
            try:
                subprocess.Popen(["xdg-screensaver", "lock"])
                done("workstation locked")
            except Exception:
                fail("could not lock screen")

    def cmd_weather(self, args):
        city = args[0] if args else ""
        try:
            url = f"https://wttr.in/{city}?format=j1" if city else "https://wttr.in/?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "NOVA-Shell/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            current = data["current_condition"][0]
            area = data["nearest_area"][0]
            city_name = area["areaName"][0]["value"]
            country = area["country"][0]["value"]
            temp_c = current["temp_C"]
            feels = current["FeelsLikeC"]
            humidity = current["humidity"]
            desc = current["weatherDesc"][0]["value"]
            wind = current["windspeedKmph"]
            emit(f"  Weather: {city_name}, {country}", Palette.BRIGHT_CYAN)
            emit(f"  {desc}", Palette.WHITE)
            emit(f"  Temperature: {temp_c}C (feels like {feels}C)", Palette.BRIGHT_YELLOW)
            emit(f"  Humidity: {humidity}%", Palette.BRIGHT_BLUE)
            emit(f"  Wind: {wind} km/h", Palette.WHITE)
        except Exception as e:
            fail(f"could not fetch weather: {e}")

    def cmd_url(self, args):
        if not args:
            fail("usage: url <encode|decode> <text>")
            return
        action = args[0].lower()
        text = " ".join(args[1:])
        if action in ("encode", "enc"):
            encoded = urllib.parse.quote(text, safe="")
            emit(f"  {encoded}", Palette.BRIGHT_GREEN)
        elif action in ("decode", "dec"):
            decoded = urllib.parse.unquote(text)
            emit(f"  {decoded}", Palette.BRIGHT_GREEN)
        else:
            fail("usage: url <encode|decode> <text>")

    def cmd_screenshot(self, args):
        filename = args[0] if args else f"screenshot_{int(time.time())}.png"
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            path = self._resolve_path(filename)
            img.save(path)
            done(f"screenshot saved: {filename} ({img.size[0]}x{img.size[1]})")
        except ImportError:
            fail("Pillow not installed, run: pkg install Pillow")
        except Exception as e:
            fail(str(e))

    def cmd_syntax(self, args):
        if not args or args[0] == "list":
            emit("  built-in extensions:", Palette.BOLD + Palette.BRIGHT_CYAN)
            built_in = sorted(SYNTAX_SPECS.keys())
            for i in range(0, len(built_in), 6):
                emit("  " + "  ".join(f"{e:<7}" for e in built_in[i:i+6]), Palette.WHITE)
            return
        if args[0] == "add":
            if len(args) < 2:
                fail("usage: syntax add <.ext> [comment_symbol] [keyword1,keyword2,...]")
                return
            ext = args[1].lower()
            if not ext.startswith("."):
                ext = "." + ext
            comment_sym = args[2] if len(args) > 2 and args[2] != "-" else None
            keywords = set()
            if len(args) > 3:
                keywords = {k.strip() for k in args[3].split(",") if k.strip()}
            SYNTAX_SPECS[ext] = {"keywords": keywords, "comment": comment_sym, "string": True}
            done(f"registered extension '{ext}' (comment={comment_sym}, keywords={len(keywords)})")
            return
        if args[0] == "remove":
            if len(args) < 2:
                fail("usage: syntax remove <.ext>")
                return
            ext = args[1].lower()
            if not ext.startswith("."):
                ext = "." + ext
            if ext in SYNTAX_SPECS:
                del SYNTAX_SPECS[ext]
                done(f"removed extension '{ext}'")
            else:
                fail(f"extension '{ext}' not found")
            return
        fail("usage: syntax [list|add|remove] ...")

    def cmd_edit(self, args):
        if not args:
            fail("usage: edit <file>")
            return
        target = args[0]
        ext = os.path.splitext(target)[1].lower()
        if self.mode != "virtual":
            path = self._resolve_path(target)
            is_new = not os.path.exists(path)
        else:
            content, exists = self.vfs.read_file(target)
            is_new = not exists
            path = target
        if is_new and ext and ext not in SYNTAX_SPECS:
            fail(f"unsupported extension '{ext}' - cannot create new file")
            info("use 'syntax' command to register custom extensions")
            info(f"supported: {', '.join(sorted(SYNTAX_SPECS.keys()))}")
            return
        lines = []
        if self.mode == "virtual":
            content, _ = self.vfs.read_file(target)
            if content:
                lines = content.split("\n")
        else:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.read().split("\n")
                except Exception:
                    pass

        def save_fn(content):
            if self.mode == "virtual":
                self.vfs.write_file(target, content)
            else:
                p = self._resolve_path(target)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)

        editor = NanoEditor(target, lines, save_fn, ext=ext)
        editor.run()
        if editor.modified:
            warn(f"{target} has unsaved changes (discarded)")
        else:
            done(f"closed {target}")

    def cmd_tree(self, args):
        path = args[0] if args else "."
        depth = int(args[1]) if len(args) > 1 else 3
        if self.mode == "virtual":
            node = self.vfs.resolve(path)
            if node is None or node.type != "dir":
                fail("not a directory")
                return
            self._vfs_tree(node, "", depth, 0)
        else:
            full = self._resolve_path(path)
            if not os.path.isdir(full):
                fail("not a directory")
                return
            self._real_tree(full, "", depth, 0)

    def _vfs_tree(self, node, prefix, max_depth, current):
        if current >= max_depth:
            return
        children = sorted(node.children.values(), key=lambda n: (n.type != "dir", n.name.lower()))
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "`-- " if is_last else "|-- "
            color = Palette.BRIGHT_BLUE if child.type == "dir" else Palette.WHITE
            emit(f"{prefix}{connector}{child.name}{'/' if child.type == 'dir' else ''}", color)
            if child.type == "dir":
                ext = "    " if is_last else "|   "
                self._vfs_tree(child, prefix + ext, max_depth, current + 1)

    def _real_tree(self, path, prefix, max_depth, current):
        if current >= max_depth:
            return
        try:
            entries = sorted(os.listdir(path), key=str.lower)
        except PermissionError:
            emit(f"{prefix}[permission denied]", Palette.BRIGHT_RED)
            return
        for i, name in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "`-- " if is_last else "|-- "
            full = os.path.join(path, name)
            is_dir = os.path.isdir(full)
            color = Palette.BRIGHT_BLUE if is_dir else Palette.WHITE
            emit(f"{prefix}{connector}{name}{'/' if is_dir else ''}", color)
            if is_dir:
                ext = "    " if is_last else "|   "
                self._real_tree(full, prefix + ext, max_depth, current + 1)

    def cmd_duplicate(self, args):
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=self.real_cwd)
            done("new NOVA Shell session launched")
        except Exception as e:
            fail(str(e))

    def cmd_clock(self, args):
        info("live clock (press Ctrl+C to stop)")
        try:
            while True:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                put(f"\r  {Palette.BOLD}{Palette.BRIGHT_CYAN}{now}{Palette.RESET}   ")
                sys.stdout.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            line()
            done("clock stopped")

    def cmd_dice(self, args):
        spec = args[0] if args else "1d6"
        try:
            parts = spec.lower().split("d")
            count = int(parts[0])
            sides = int(parts[1])
            if count > 100 or sides > 1000:
                fail("dice count or sides too large")
                return
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls)
            emit(f"  rolling {count}d{sides}:", Palette.BRIGHT_YELLOW)
            emit(f"  rolls: {rolls}", Palette.WHITE)
            emit(f"  total: {total}", Palette.BRIGHT_GREEN)
        except Exception:
            fail("invalid dice format. use NdM (e.g. 2d6)")

    def cmd_uuid(self, args):
        import uuid
        emit(f"  {uuid.uuid4()}", Palette.BRIGHT_GREEN)
        emit(f"  {uuid.uuid4()}", Palette.BRIGHT_CYAN)

    def cmd_base64(self, args):
        import base64 as b64
        if len(args) < 2:
            fail("usage: base64 <encode|decode> <text>")
            return
        mode = args[0].lower()
        text = " ".join(args[1:])
        try:
            if mode == "encode":
                encoded = b64.b64encode(text.encode("utf-8")).decode("utf-8")
                emit(f"  {encoded}", Palette.BRIGHT_GREEN)
            elif mode == "decode":
                decoded = b64.b64decode(text).decode("utf-8")
                emit(f"  {decoded}", Palette.BRIGHT_GREEN)
            else:
                fail("mode must be 'encode' or 'decode'")
        except Exception as e:
            fail(f"base64 error: {e}")

    def cmd_weather(self, args):
        city = args[0] if args else ""
        url = f"https://wttr.in/{city}?format=3" if city else "https://wttr.in/?format=3"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(request, timeout=15) as resp:
                data = resp.read().decode("utf-8").strip()
                emit(f"  {data}", Palette.BRIGHT_CYAN)
        except Exception as e:
            fail(f"weather lookup failed: {e}")

    def cmd_qr(self, args):
        if not args:
            fail("usage: qr <text>")
            return
        text = " ".join(args)
        try:
            url = f"https://api.qrserver.com/v1/create-qr-code/?size=25x25&data={urllib.parse.quote(text)}"
            request = urllib.request.Request(url, headers={"User-Agent": "NOVA-Shell"})
            with urllib.request.urlopen(request, timeout=15) as resp:
                img_data = resp.read()
            info("QR code generated (use a QR scanner)")
            emit(f"  data length: {len(img_data)} bytes", Palette.GRAY)
        except Exception as e:
            fail(f"QR generation failed: {e}")

    def cmd_urlcheck(self, args):
        if not args:
            fail("usage: urlcheck <url>")
            return
        url = args[0]
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        try:
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "NOVA-Shell/2.0"})
            start = time.time()
            with urllib.request.urlopen(request, timeout=15) as resp:
                elapsed = (time.time() - start) * 1000
                emit(f"  {resp.status} {resp.reason}", Palette.BRIGHT_GREEN)
                emit(f"  response time: {elapsed:.0f}ms", Palette.BRIGHT_CYAN)
                emit(f"  content-type:  {resp.headers.get('Content-Type', 'unknown')}", Palette.GRAY)
                emit(f"  server:        {resp.headers.get('Server', 'unknown')}", Palette.GRAY)
        except urllib.error.HTTPError as e:
            emit(f"  {e.code} {e.reason}", Palette.BRIGHT_YELLOW)
        except Exception as e:
            fail(f"URL check failed: {e}")

    def cmd_speed(self, args):
        info("running network speed test...")
        try:
            url = "https://speed.cloudflare.com/__down?bytes=10000000"
            request = urllib.request.Request(url, headers={"User-Agent": "NOVA-Shell"})
            start = time.time()
            with urllib.request.urlopen(request, timeout=30) as resp:
                data = resp.read()
            elapsed = time.time() - start
            size_mb = len(data) / (1024 * 1024)
            speed_mbps = (len(data) * 8) / (1024 * 1024) / elapsed
            emit(f"  downloaded: {size_mb:.2f} MB in {elapsed:.2f}s", Palette.BRIGHT_CYAN)
            emit(f"  speed:      {speed_mbps:.2f} Mbps", Palette.BRIGHT_GREEN)
        except Exception as e:
            fail(f"speed test failed: {e}")

    def cmd_ports(self, args):
        try:
            if IS_WINDOWS:
                result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
                emit(f"  {'PROTO':<6} {'LOCAL ADDRESS':<25} {'STATE':<15} {'PID'}", Palette.BOLD + Palette.BRIGHT_YELLOW)
                for ln in result.stdout.split("\n"):
                    if "LISTENING" in ln:
                        parts = ln.split()
                        if len(parts) >= 5:
                            emit(f"  {parts[0]:<6} {parts[1]:<25} {parts[3]:<15} {parts[4]}", Palette.WHITE)
            else:
                result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=10)
                for ln in result.stdout.split("\n"):
                    if ln.strip():
                        emit(f"  {ln}", Palette.WHITE)
        except Exception as e:
            fail(str(e))

    def cmd_killtree(self, args):
        if not args:
            fail("usage: killtree <pid>")
            return
        try:
            pid = int(args[0])
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=10)
            else:
                result = subprocess.run(["pstree", "-p", str(pid)], capture_output=True, text=True, timeout=10)
                pids = re.findall(r"\((\d+)\)", result.stdout)
                for p in pids:
                    try:
                        os.kill(int(p), signal.SIGTERM)
                    except Exception:
                        pass
            done(f"terminated process tree rooted at PID {pid}")
        except ValueError:
            fail("PID must be a number")
        except Exception as e:
            fail(str(e))

    def cmd_top(self, args):
        count = int(args[0]) if args else 10
        try:
            if IS_WINDOWS:
                result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10)
                procs = []
                for ln in result.stdout.strip().split("\n"):
                    parts = [p.strip('"') for p in ln.split('","')]
                    if len(parts) >= 5:
                        try:
                            mem = int(parts[4].replace(",", "").replace(" K", ""))
                            procs.append((parts[0], int(parts[1]), mem))
                        except Exception:
                            pass
                procs.sort(key=lambda x: x[2], reverse=True)
                emit(f"  {'PID':<8} {'MEM(KB)':<12} {'NAME'}", Palette.BOLD + Palette.BRIGHT_YELLOW)
                for name, pid, mem in procs[:count]:
                    emit(f"  {pid:<8} {mem:<12} {name}", Palette.WHITE)
            else:
                result = subprocess.run(["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=10)
                lines = result.stdout.strip().split("\n")
                emit(f"  {lines[0]}", Palette.BOLD + Palette.BRIGHT_YELLOW)
                for ln in lines[1:count + 1]:
                    emit(f"  {ln}", Palette.WHITE)
        except Exception as e:
            fail(str(e))

    def cmd_diff(self, args):
        if len(args) < 2:
            fail("usage: diff <file1> <file2>")
            return
        f1, f2 = args[0], args[1]
        if self.mode == "virtual":
            c1, _ = self.vfs.read_file(f1)
            c2, _ = self.vfs.read_file(f2)
            if c1 is None or c2 is None:
                fail("one or both files not found")
                return
            l1 = c1.split("\n")
            l2 = c2.split("\n")
        else:
            p1 = self._resolve_path(f1)
            p2 = self._resolve_path(f2)
            if not os.path.exists(p1) or not os.path.exists(p2):
                fail("one or both files not found")
                return
            with open(p1, "r", encoding="utf-8", errors="replace") as f:
                l1 = f.readlines()
            with open(p2, "r", encoding="utf-8", errors="replace") as f:
                l2 = f.readlines()
        import difflib
        diff = difflib.unified_diff(l1, l2, fromfile=f1, tofile=f2, lineterm="")
        found = False
        for ln in diff:
            found = True
            if ln.startswith("+"):
                emit(f"  {ln}", Palette.BRIGHT_GREEN)
            elif ln.startswith("-"):
                emit(f"  {ln}", Palette.BRIGHT_RED)
            elif ln.startswith("@"):
                emit(f"  {ln}", Palette.BRIGHT_CYAN)
            else:
                emit(f"  {ln}", Palette.GRAY)
        if not found:
            done("files are identical")

    def cmd_merge(self, args):
        if len(args) < 2:
            fail("usage: merge <file1> <file2>")
            return
        f1, f2 = args[0], args[1]
        out = args[2] if len(args) > 2 else "merged.txt"
        if self.mode == "virtual":
            c1, _ = self.vfs.read_file(f1)
            c2, _ = self.vfs.read_file(f2)
            if c1 is None or c2 is None:
                fail("one or both files not found")
                return
            merged = sorted((c1 + "\n" + c2).split("\n"), key=str.lower)
            self.vfs.write_file(out, "\n".join(merged))
        else:
            p1 = self._resolve_path(f1)
            p2 = self._resolve_path(f2)
            if not os.path.exists(p1) or not os.path.exists(p2):
                fail("one or both files not found")
                return
            with open(p1, "r", encoding="utf-8", errors="replace") as f:
                l1 = f.readlines()
            with open(p2, "r", encoding="utf-8", errors="replace") as f:
                l2 = f.readlines()
            merged = sorted(l1 + l2, key=str.lower)
            with open(self._resolve_path(out), "w", encoding="utf-8") as f:
                f.writelines(merged)
        done(f"merged into {out}")

    def cmd_reverse(self, args):
        if not args:
            fail("usage: reverse <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
            lines.reverse()
            self.vfs.write_file(target, "\n".join(lines))
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            lines.reverse()
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        done(f"reversed lines in {target}")

    def cmd_head(self, args):
        if not args:
            fail("usage: head <file> [count]")
            return
        target = args[0]
        count = int(args[1]) if len(args) > 1 else 10
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        for ln in lines[:count]:
            emit(f"  {ln.rstrip()}", Palette.WHITE)

    def cmd_tail(self, args):
        if not args:
            fail("usage: tail <file> [count]")
            return
        target = args[0]
        count = int(args[1]) if len(args) > 1 else 10
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        for ln in lines[-count:]:
            emit(f"  {ln.rstrip()}", Palette.WHITE)

    def cmd_truncate(self, args):
        if len(args) < 2:
            fail("usage: truncate <file> <size_bytes>")
            return
        target = args[0]
        try:
            size = int(args[1])
        except ValueError:
            fail("size must be a number")
            return
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            encoded = content.encode("utf-8")[:size]
            self.vfs.write_file(target, encoded.decode("utf-8", errors="replace"))
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r+b") as f:
                f.truncate(size)
        done(f"truncated {target} to {size} bytes")

    def cmd_touch(self, args):
        if not args:
            fail("usage: touch <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            node = self.vfs.resolve(target)
            if node is None:
                ok, err = self.vfs.mkfile(target)
                if ok:
                    done(f"created {target}")
                else:
                    fail(err)
            else:
                node.modified = time.time()
                done(f"updated timestamp: {target}")
        else:
            path = self._resolve_path(target)
            if os.path.exists(path):
                now = time.time()
                os.utime(path, (now, now))
                done(f"updated timestamp: {target}")
            else:
                open(path, "a").close()
                done(f"created {target}")

    def cmd_link(self, args):
        if len(args) < 2:
            fail("usage: link <target> <linkname>")
            return
        target, linkname = args[0], args[1]
        if self.mode == "virtual":
            fail("symlinks not supported in virtual filesystem")
            return
        t_path = self._resolve_path(target)
        l_path = self._resolve_path(linkname)
        try:
            os.symlink(t_path, l_path)
            done(f"created symlink: {linkname} -> {target}")
        except OSError as e:
            fail(str(e))

    def cmd_perm(self, args):
        if not args:
            fail("usage: perm <path> [mode]")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("permissions not applicable in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such path: {target}")
            return
        if len(args) > 1:
            try:
                mode = int(args[1], 8)
                os.chmod(path, mode)
                done(f"set permissions to {oct(mode)} on {target}")
            except ValueError:
                fail("mode must be octal (e.g. 755)")
            except Exception as e:
                fail(str(e))
        else:
            st = os.stat(path)
            emit(f"  {stat.filemode(st.st_mode)}  ({oct(st.st_mode & 0o777)})", Palette.BRIGHT_CYAN)

    def cmd_owner(self, args):
        if not args:
            fail("usage: owner <path>")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("owner info not applicable in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such path: {target}")
            return
        try:
            st = os.stat(path)
            if hasattr(st, "st_uid"):
                import pwd
                import grp
                try:
                    user = pwd.getpwuid(st.st_uid).pw_name
                except Exception:
                    user = str(st.st_uid)
                try:
                    group = grp.getgrgid(st.st_gid).gr_name
                except Exception:
                    group = str(st.st_gid)
                emit(f"  owner: {user} ({st.st_uid})", Palette.BRIGHT_CYAN)
                emit(f"  group: {group} ({st.st_gid})", Palette.BRIGHT_CYAN)
            else:
                emit(f"  owner info not available on this platform", Palette.GRAY)
        except Exception as e:
            fail(str(e))

    def cmd_compress(self, args):
        if not args:
            fail("usage: compress <path>")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("compression not supported in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such path: {target}")
            return
        try:
            if os.path.isdir(path):
                output = path.rstrip("/\\") + ".tar.gz"
                subprocess.run(["tar", "-czf", output, "-C", os.path.dirname(path), os.path.basename(path)], check=True)
            else:
                output = path + ".gz"
                import gzip
                with open(path, "rb") as f_in:
                    with gzip.open(output, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            done(f"compressed to {os.path.basename(output)}")
        except Exception as e:
            fail(str(e))

    def cmd_extract(self, args):
        if not args:
            fail("usage: extract <archive>")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("extraction not supported in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such archive: {target}")
            return
        try:
            if path.endswith(".tar.gz") or path.endswith(".tgz"):
                subprocess.run(["tar", "-xzf", path, "-C", os.path.dirname(path)], check=True)
            elif path.endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(path, "r") as z:
                    z.extractall(os.path.dirname(path))
            elif path.endswith(".gz"):
                import gzip
                output = path[:-3]
                with gzip.open(path, "rb") as f_in:
                    with open(output, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                fail(f"unsupported archive format: {target}")
                return
            done(f"extracted {target}")
        except Exception as e:
            fail(str(e))

    def cmd_path(self, args):
        if not args:
            emit(f"  {os.environ.get('PATH', '')}", Palette.BRIGHT_CYAN)
            return
        if args[0] == "add" and len(args) > 1:
            new_dir = self._resolve_path(args[1])
            current = os.environ.get("PATH", "")
            if new_dir not in current.split(os.pathsep):
                os.environ["PATH"] = new_dir + os.pathsep + current
                done(f"added {new_dir} to PATH")
            else:
                warn("already in PATH")
        elif args[0] == "remove" and len(args) > 1:
            target = self._resolve_path(args[1])
            current = os.environ.get("PATH", "")
            parts = [p for p in current.split(os.pathsep) if p != target]
            os.environ["PATH"] = os.pathsep.join(parts)
            done(f"removed {target} from PATH")
        else:
            fail("usage: path [add|remove <dir>]")

    def cmd_run(self, args):
        if not args:
            fail("usage: run <native_command...>")
            return
        cmd = " ".join(args)
        try:
            result = subprocess.run(cmd, shell=True, cwd=self.real_cwd, capture_output=True, text=True, timeout=120)
            if result.stdout:
                sys.stdout.write(result.stdout)
                if not result.stdout.endswith("\n"):
                    line()
            if result.stderr:
                emit(result.stderr.rstrip(), Palette.BRIGHT_RED)
            if result.returncode != 0:
                warn(f"exit code: {result.returncode}")
        except subprocess.TimeoutExpired:
            fail("command timed out (120s)")
        except Exception as e:
            fail(str(e))

    def cmd_theme(self, args):
        if not args:
            info("available themes: default, ocean, sunset, forest, mono")
            return
        theme = args[0].lower()
        themes = {
            "default": {"user": Palette.BRIGHT_GREEN, "path": Palette.BRIGHT_BLUE, "arrow": Palette.BRIGHT_MAGENTA},
            "ocean": {"user": Palette.BRIGHT_CYAN, "path": Palette.BRIGHT_BLUE, "arrow": Palette.CYAN},
            "sunset": {"user": Palette.BRIGHT_YELLOW, "path": Palette.BRIGHT_RED, "arrow": Palette.BRIGHT_MAGENTA},
            "forest": {"user": Palette.BRIGHT_GREEN, "path": Palette.GREEN, "arrow": Palette.BRIGHT_YELLOW},
            "mono": {"user": Palette.WHITE, "path": Palette.GRAY, "arrow": Palette.WHITE},
        }
        if theme in themes:
            self._theme = themes[theme]
            done(f"theme set to {theme}")
        else:
            fail(f"unknown theme: {theme}")

    def cmd_history_clear(self, args):
        all_hist = get_config("history", {})
        all_hist[self.username] = []
        set_config("history", all_hist)
        self.editor.history = []
        done("all command history and suggestions wiped")

    def cmd_rain(self, args):
        duration = float(args[0]) if args else 8
        info(f"digital rain ({duration}s) \u00b7 press Ctrl+C to stop")
        cols = term_width()
        rows = 20
        drops = [0] * cols
        chars = "0123456789ABCDEFabcdef!@#$%^&*()_+-=[]{}|;:,.<>?"
        start = time.time()
        try:
            while time.time() - start < duration:
                line_text = ""
                for i in range(cols):
                    if drops[i] == 0:
                        if random.random() < 0.05:
                            drops[i] = random.randint(5, 20)
                    if drops[i] > 0:
                        line_text += f"{Palette.BRIGHT_GREEN}{random.choice(chars)}{Palette.RESET}"
                        drops[i] -= 1
                    else:
                        line_text += " "
                put(f"\r{line_text}")
                sys.stdout.flush()
                time.sleep(0.06)
        except KeyboardInterrupt:
            pass
        line()

    def cmd_jot(self, args):
        jot_file = os.path.join(CONFIG_DIR, "jots.txt")
        if not args:
            if os.path.exists(jot_file):
                with open(jot_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    sys.stdout.write(content)
                else:
                    info("no jots yet")
            else:
                info("no jots yet")
            return
        text = " ".join(args)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ensure_config_dir()
        with open(jot_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")
        done(f"jot saved: {text}")

    def cmd_agenda(self, args):
        todos = get_config("agenda", [])
        if not args or args[0] == "list":
            if not todos:
                info("agenda is empty")
                return
            for i, t in enumerate(todos, 1):
                status = f"{Palette.BRIGHT_GREEN}\u2713{Palette.RESET}" if t["done"] else f"{Palette.BRIGHT_YELLOW}\u25cb{Palette.RESET}"
                emit(f"  {status} {i:>2}. {t['text']}", Palette.WHITE)
            return
        action = args[0].lower()
        if action == "add":
            text = " ".join(args[1:])
            if not text:
                fail("usage: agenda add <text>")
                return
            todos.append({"text": text, "done": False, "created": time.time()})
            set_config("agenda", todos)
            done(f"added: {text}")
        elif action == "done":
            try:
                idx = int(args[1]) - 1
                todos[idx]["done"] = True
                set_config("agenda", todos)
                done(f"marked done: {todos[idx]['text']}")
            except Exception:
                fail("invalid item number")
        elif action == "remove":
            try:
                idx = int(args[1]) - 1
                removed = todos.pop(idx)
                set_config("agenda", todos)
                done(f"removed: {removed['text']}")
            except Exception:
                fail("invalid item number")
        else:
            fail(f"unknown action: {action}")

    def cmd_countdown(self, args):
        if not args:
            fail("usage: countdown <seconds>")
            return
        try:
            total = int(args[0])
        except ValueError:
            fail("seconds must be a number")
            return
        try:
            for remaining in range(total, 0, -1):
                mins, secs = divmod(remaining, 60)
                put(f"\r  {Palette.BOLD}{Palette.BRIGHT_CYAN}{mins:02d}:{secs:02d}{Palette.RESET} remaining   ")
                sys.stdout.flush()
                time.sleep(1)
            line()
            done("time's up!")
            for _ in range(3):
                put("\a")
                sys.stdout.flush()
                time.sleep(0.3)
        except KeyboardInterrupt:
            line()
            warn("countdown cancelled")

    def cmd_tick(self, args):
        info("stopwatch running \u00b7 press Enter to stop")
        start = time.time()
        try:
            while True:
                elapsed = time.time() - start
                mins, secs = divmod(int(elapsed), 60)
                ms = int((elapsed % 1) * 100)
                put(f"\r  {Palette.BOLD}{Palette.BRIGHT_GREEN}{mins:02d}:{secs:02d}.{ms:02d}{Palette.RESET}   ")
                sys.stdout.flush()
                time.sleep(0.05)
                if IS_WINDOWS and msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch == "\r":
                        break
        except KeyboardInterrupt:
            pass
        elapsed = time.time() - start
        mins, secs = divmod(int(elapsed), 60)
        line()
        done(f"stopped at {mins:02d}:{secs:02d}")

    def cmd_lock(self, args):
        if not args:
            fail("usage: lock <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("encryption not supported in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such file: {target}")
            return
        password = getpass.getpass(f"  {Palette.BRIGHT_CYAN}Encryption password:{Palette.RESET} ")
        if len(password) < 4:
            fail("password must be at least 4 characters")
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            salt = os.urandom(16)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000, 32)
            from Crypto.Cipher import AES
            nonce = os.urandom(12)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(data)
            out_path = path + ".nova"
            with open(out_path, "wb") as f:
                f.write(b"NOVAENC" + salt + nonce + tag + ciphertext)
            os.remove(path)
            done(f"encrypted -> {os.path.basename(out_path)}")
        except ImportError:
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"novashell", 200000, 32)
            encrypted = bytes(b ^ key[i % 32] for i, b in enumerate(data))
            out_path = path + ".nova"
            with open(out_path, "wb") as f:
                f.write(b"NOVAXOR" + encrypted)
            os.remove(path)
            done(f"encrypted -> {os.path.basename(out_path)}")
        except Exception as e:
            fail(str(e))

    def cmd_unlock(self, args):
        if not args:
            fail("usage: unlock <file.nova>")
            return
        target = args[0]
        if self.mode == "virtual":
            fail("decryption not supported in virtual filesystem")
            return
        path = self._resolve_path(target)
        if not os.path.exists(path):
            fail(f"no such file: {target}")
            return
        password = getpass.getpass(f"  {Palette.BRIGHT_CYAN}Decryption password:{Palette.RESET} ")
        try:
            with open(path, "rb") as f:
                header = f.read(7)
                if header == b"NOVAENC":
                    salt = f.read(16)
                    nonce = f.read(12)
                    tag = f.read(16)
                    ciphertext = f.read()
                    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000, 32)
                    from Crypto.Cipher import AES
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                    data = cipher.decrypt_and_verify(ciphertext, tag)
                elif header == b"NOVAXOR":
                    encrypted = f.read()
                    key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"novashell", 200000, 32)
                    data = bytes(b ^ key[i % 32] for i, b in enumerate(encrypted))
                else:
                    fail("not a NOVA encrypted file")
                    return
            out_path = path[:-5] if path.endswith(".nova") else path + ".dec"
            with open(out_path, "wb") as f:
                f.write(data)
            os.remove(path)
            done(f"decrypted -> {os.path.basename(out_path)}")
        except Exception as e:
            fail(f"decryption failed: {e}")

    def cmd_address(self, args):
        try:
            hostname = socket.gethostname()
            emit(f"  hostname:   {hostname}", Palette.BRIGHT_CYAN)
        except Exception:
            hostname = "unknown"
            emit(f"  hostname:   unknown", Palette.BRIGHT_CYAN)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                local_ip = socket.gethostbyname(hostname)
            except Exception:
                local_ip = "127.0.0.1"
        emit(f"  local IP:   {local_ip}", Palette.BRIGHT_GREEN)
        public_sources = [
            ("https://api.ipify.org?format=json", "json"),
            ("https://ifconfig.me/ip", "text"),
            ("https://icanhazip.com", "text"),
            ("https://api.ip.sb/ip", "text"),
            ("https://ipinfo.io/ip", "text"),
        ]
        public_ip = None
        for url, fmt in public_sources:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=8) as resp:
                    raw = resp.read().decode().strip()
                    if fmt == "json":
                        public_ip = json.loads(raw)["ip"]
                    else:
                        public_ip = raw
                    if public_ip and len(public_ip) <= 45:
                        break
            except Exception:
                continue
        if public_ip:
            emit(f"  public IP:  {public_ip}", Palette.BRIGHT_YELLOW)
        else:
            warn("public IP unavailable, check network connection")

    def cmd_wireless(self, args):
        try:
            if IS_WINDOWS:
                result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
                for ln in result.stdout.split("\n"):
                    ln = ln.strip()
                    if any(k in ln for k in ["SSID", "Signal", "State", "Radio type", "Authentication", "Channel"]):
                        emit(f"  {ln}", Palette.WHITE)
            else:
                result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=10)
                sys.stdout.write(result.stdout)
        except Exception as e:
            fail(str(e))

    def cmd_power(self, args):
        try:
            if IS_WINDOWS:
                result = subprocess.run(["powercfg", "/batteryreport", "/output", os.path.join(tempfile.gettempdir(), "batt.xml")], capture_output=True, text=True, timeout=10)
                class _SYSTEM_POWER_STATUS(ctypes.Structure):
                    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte), ("Reserved1", ctypes.c_byte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
                status = _SYSTEM_POWER_STATUS()
                ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
                ac = "plugged in" if status.ACLineStatus == 1 else "on battery"
                pct = status.BatteryLifePercent
                emit(f"  power:      {ac}", Palette.BRIGHT_CYAN)
                emit(f"  battery:    {pct}%", Palette.BRIGHT_GREEN if pct > 20 else Palette.BRIGHT_RED)
                if status.BatteryLifeTime != 0xFFFFFFFF:
                    mins = status.BatteryLifeTime // 60
                    emit(f"  remaining:  {mins} min", Palette.GRAY)
            else:
                with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                    pct = f.read().strip()
                with open("/sys/class/power_supply/BAT0/status", "r") as f:
                    status = f.read().strip()
                emit(f"  power:      {status}", Palette.BRIGHT_CYAN)
                emit(f"  battery:    {pct}%", Palette.BRIGHT_GREEN)
        except Exception as e:
            fail(str(e))

    def cmd_pasteboard(self, args):
        if not args or args[0] == "paste":
            try:
                if IS_WINDOWS:
                    import ctypes.wintypes
                    CF_UNICODETEXT = 13
                    user32 = ctypes.windll.user32
                    user32.OpenClipboard(0)
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        data = ctypes.wstring_at(handle)
                        emit(f"  {data}", Palette.WHITE)
                    else:
                        info("clipboard is empty")
                    user32.CloseClipboard()
                else:
                    result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
                    emit(f"  {result.stdout}", Palette.WHITE)
            except Exception as e:
                fail(str(e))
        elif args[0] == "copy":
            text = " ".join(args[1:])
            try:
                if IS_WINDOWS:
                    import ctypes.wintypes
                    CF_UNICODETEXT = 13
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32
                    user32.OpenClipboard(0)
                    user32.EmptyClipboard()
                    h_data = kernel32.GlobalAlloc(0x2000, (len(text) + 1) * 2)
                    p_data = kernel32.GlobalLock(h_data)
                    ctypes.memmove(p_data, text.encode("utf-16-le"), len(text) * 2)
                    kernel32.GlobalUnlock(h_data)
                    user32.SetClipboardData(CF_UNICODETEXT, h_data)
                    user32.CloseClipboard()
                    done("copied to clipboard")
                else:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, timeout=5)
                    done("copied to clipboard")
            except Exception as e:
                fail(str(e))
        else:
            fail("usage: pasteboard [copy <text>|paste]")

    def cmd_mark(self, args):
        marks = get_config("marks", {})
        if not args or args[0] == "list":
            if not marks:
                info("no bookmarks yet")
                return
            for name, path in sorted(marks.items()):
                emit(f"  {Palette.BRIGHT_CYAN}{name}{Palette.RESET} -> {path}", Palette.WHITE)
            return
        action = args[0].lower()
        if action == "add" and len(args) > 1:
            name = args[1]
            marks[name] = self.real_cwd if self.mode == "real" else self.vfs.cwd
            set_config("marks", marks)
            done(f"bookmark '{name}' -> {marks[name]}")
        elif action == "remove" and len(args) > 1:
            name = args[1]
            if name in marks:
                del marks[name]
                set_config("marks", marks)
                done(f"removed bookmark '{name}'")
            else:
                fail(f"no such bookmark: {name}")
        elif action == "go" and len(args) > 1:
            name = args[1]
            if name in marks:
                target = marks[name]
                if self.mode == "virtual":
                    self.vfs.cwd = target
                else:
                    self.real_cwd = target
                    os.chdir(target)
                done(f"jumped to '{name}': {target}")
            else:
                fail(f"no such bookmark: {name}")
        else:
            fail("usage: mark [add|remove|go|list] [name]")

    def cmd_leap(self, args):
        if not args:
            fail("usage: leap <keyword>")
            return
        keyword = args[0].lower()
        freq = get_config("dirfreq", {})
        matches = [(d, c) for d, c in freq.items() if keyword in d.lower()]
        matches.sort(key=lambda x: x[1], reverse=True)
        if matches:
            target = matches[0][0]
            if self.mode == "real":
                self.real_cwd = target
                os.chdir(target)
            done(f"leaped to: {target}")
        else:
            home = os.path.expanduser("~")
            found = []
            for root, dirs, _ in os.walk(home):
                for d in dirs:
                    if keyword in d.lower():
                        found.append(os.path.join(root, d))
                        if len(found) >= 5:
                            break
                if len(found) >= 5:
                    break
            if found:
                target = found[0]
                if self.mode == "real":
                    self.real_cwd = target
                    os.chdir(target)
                done(f"leaped to: {target}")
            else:
                fail(f"no directory matching '{keyword}'")

    def cmd_latest(self, args):
        count = int(args[0]) if args else 15
        path = self.real_cwd if self.mode == "real" else "."
        files = []
        for root, dirs, fnames in os.walk(path):
            for f in fnames:
                full = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(full)
                    files.append((mtime, full))
                except Exception:
                    pass
        files.sort(reverse=True)
        for mtime, full in files[:count]:
            ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            emit(f"  {ts}  {full}", Palette.WHITE)

    def cmd_bigfind(self, args):
        path = args[0] if args else "."
        count = int(args[1]) if len(args) > 1 else 10
        full_path = self._resolve_path(path) if self.mode == "real" else path
        files = []
        for root, dirs, fnames in os.walk(full_path):
            for f in fnames:
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                    files.append((size, full))
                except Exception:
                    pass
        files.sort(reverse=True)
        for size, full in files[:count]:
            emit(f"  {self._human_size(size):>10}  {full}", Palette.WHITE)

    def cmd_version(self, args):
        try:
            path = self.real_cwd if self.mode == "real" else "."
            result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=path, timeout=10)
            if result.returncode != 0:
                info("not a git repository")
                return
            branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=path, timeout=10).stdout.strip()
            emit(f"  branch: {branch}", Palette.BRIGHT_CYAN)
            if result.stdout.strip():
                for ln in result.stdout.strip().split("\n"):
                    status_char = ln[0]
                    if status_char == "M":
                        color = Palette.BRIGHT_YELLOW
                    elif status_char == "A":
                        color = Palette.BRIGHT_GREEN
                    elif status_char == "D":
                        color = Palette.BRIGHT_RED
                    elif status_char == "?":
                        color = Palette.GRAY
                    else:
                        color = Palette.WHITE
                    emit(f"  {ln}", color)
            else:
                done("working tree clean")
        except Exception as e:
            fail(str(e))

    def cmd_hint(self, args):
        hints = {
            "files": "find . -name '*.txt' | head -20  |  du -sh * | sort -rh | head -10",
            "network": "netstat -tlnp  |  ss -tlnp  |  curl -I https://example.com",
            "process": "ps aux | grep keyword  |  kill -9 PID  |  top / htop",
            "text": "grep -rn 'pattern' .  |  sed -i 's/old/new/g' file  |  awk '{print $1}' file",
            "system": "df -h  |  free -h  |  uname -a  |  dmesg | tail",
            "git": "git add . && git commit -m 'msg' && git push  |  git pull --rebase",
        }
        if args:
            topic = args[0].lower()
            if topic in hints:
                emit(f"  {hints[topic]}", Palette.BRIGHT_CYAN)
            else:
                fail(f"no hint for '{topic}'. available: {', '.join(hints.keys())}")
        else:
            for topic, hint in hints.items():
                emit(f"  {Palette.BOLD}{topic}{Palette.RESET}: {hint}", Palette.WHITE)

    def cmd_locate(self, args):
        if not args:
            fail("usage: locate <command>")
            return
        cmd = args[0]
        try:
            if IS_WINDOWS:
                result = subprocess.run(["where", cmd], capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(["which", "-a", cmd], capture_output=True, text=True, timeout=10)
            if result.stdout.strip():
                for ln in result.stdout.strip().split("\n"):
                    emit(f"  {ln}", Palette.BRIGHT_GREEN)
            else:
                warn(f"'{cmd}' not found in PATH")
        except Exception as e:
            fail(str(e))

    def cmd_fragment(self, args):
        frag_dir = os.path.join(CONFIG_DIR, "fragments")
        ensure_config_dir()
        os.makedirs(frag_dir, exist_ok=True)
        if not args or args[0] == "list":
            files = [f for f in os.listdir(frag_dir) if f.endswith(".txt")]
            if not files:
                info("no fragments saved")
                return
            for f in sorted(files):
                emit(f"  {f[:-4]}", Palette.BRIGHT_CYAN)
            return
        action = args[0].lower()
        if action == "save" and len(args) > 1:
            name = args[1]
            info(f"enter fragment text (Ctrl+D or empty line to finish):")
            lines = []
            try:
                while True:
                    ln = input()
                    if not ln:
                        break
                    lines.append(ln)
            except EOFError:
                pass
            with open(os.path.join(frag_dir, f"{name}.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            done(f"fragment '{name}' saved")
        elif action == "get" and len(args) > 1:
            name = args[1]
            path = os.path.join(frag_dir, f"{name}.txt")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    sys.stdout.write(f.read())
                line()
            else:
                fail(f"no such fragment: {name}")
        elif action == "delete" and len(args) > 1:
            name = args[1]
            path = os.path.join(frag_dir, f"{name}.txt")
            if os.path.exists(path):
                os.remove(path)
                done(f"deleted fragment '{name}'")
            else:
                fail(f"no such fragment: {name}")
        else:
            fail("usage: fragment [save|get|list|delete <name>]")

    def cmd_unique(self, args):
        if not args:
            fail("usage: unique <file>")
            return
        target = args[0]
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            lines = content.split("\n")
            seen = set()
            result = []
            for ln in lines:
                if ln not in seen:
                    seen.add(ln)
                    result.append(ln)
            self.vfs.write_file(target, "\n".join(result))
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            seen = set()
            result = []
            for ln in lines:
                if ln not in seen:
                    seen.add(ln)
                    result.append(ln)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(result)
        done(f"removed duplicates from {target}")

    def cmd_freq(self, args):
        if not args:
            fail("usage: freq <file> [top_n]")
            return
        target = args[0]
        top_n = int(args[1]) if len(args) > 1 else 20
        if self.mode == "virtual":
            content, err = self.vfs.read_file(target)
            if content is None:
                fail(err)
                return
            text = content
        else:
            path = self._resolve_path(target)
            if not os.path.exists(path):
                fail(f"no such file: {target}")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]+", text.lower())
        from collections import Counter
        counter = Counter(words)
        emit(f"  total words: {len(words)}", Palette.BRIGHT_CYAN)
        emit(f"  unique:      {len(counter)}", Palette.BRIGHT_CYAN)
        line()
        for word, count in counter.most_common(top_n):
            bar = "\u2588" * min(count, 40)
            emit(f"  {word:<20} {count:>5}  {Palette.BRIGHT_GREEN}{bar}{Palette.RESET}", Palette.WHITE)

    def cmd_voidfind(self, args):
        path = args[0] if args else "."
        full_path = self._resolve_path(path) if self.mode == "real" else path
        empty_files = []
        empty_dirs = []
        for root, dirs, files in os.walk(full_path):
            if not dirs and not files:
                empty_dirs.append(root)
            for f in files:
                full = os.path.join(root, f)
                try:
                    if os.path.getsize(full) == 0:
                        empty_files.append(full)
                except Exception:
                    pass
        if empty_dirs:
            emit(f"  empty directories:", Palette.BRIGHT_YELLOW)
            for d in empty_dirs[:20]:
                emit(f"    {d}", Palette.WHITE)
        if empty_files:
            emit(f"  empty files:", Palette.BRIGHT_RED)
            for f in empty_files[:20]:
                emit(f"    {f}", Palette.WHITE)
        if not empty_dirs and not empty_files:
            done("no empty files or directories found")

    def cmd_twinfind(self, args):
        path = args[0] if args else "."
        full_path = self._resolve_path(path) if self.mode == "real" else path
        info("scanning for duplicates...")
        size_map = {}
        for root, dirs, files in os.walk(full_path):
            for f in files:
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                    if size > 0:
                        size_map.setdefault(size, []).append(full)
                except Exception:
                    pass
        duplicates = {}
        for size, paths in size_map.items():
            if len(paths) > 1:
                hash_map = {}
                for p in paths:
                    try:
                        h = hashlib.md5(open(p, "rb").read(65536)).hexdigest()
                        hash_map.setdefault(h, []).append(p)
                    except Exception:
                        pass
                for h, plist in hash_map.items():
                    if len(plist) > 1:
                        duplicates[h] = plist
        if not duplicates:
            done("no duplicate files found")
            return
        total_wasted = 0
        for h, paths in duplicates.items():
            size = os.path.getsize(paths[0])
            wasted = size * (len(paths) - 1)
            total_wasted += wasted
            emit(f"  {self._human_size(size)}  ({len(paths)} copies)", Palette.BRIGHT_YELLOW)
            for p in paths:
                emit(f"    {p}", Palette.WHITE)
        line()
        warn(f"total potential savings: {self._human_size(total_wasted)}")

    def cmd_manual(self, args):
        if not args:
            fail("usage: manual <command>")
            return
        cmd = args[0]
        try:
            if IS_WINDOWS:
                result = subprocess.run([cmd, "/?"], capture_output=True, text=True, timeout=10)
                output = result.stdout or result.stderr
            else:
                result = subprocess.run(["man", cmd], capture_output=True, text=True, timeout=10)
                output = result.stdout
            if output:
                lines = output.split("\n")
                for ln in lines[:60]:
                    emit(f"  {ln}", Palette.WHITE)
                if len(lines) > 60:
                    emit(f"  ... ({len(lines) - 60} more lines)", Palette.GRAY)
            else:
                warn(f"no manual entry for '{cmd}'")
        except Exception as e:
            fail(str(e))

    def cmd_config(self, args):
        config = get_config("settings", {})
        if not args:
            if not config:
                info("no custom configuration set")
            else:
                for k, v in sorted(config.items()):
                    emit(f"  {k} = {v}", Palette.BRIGHT_CYAN)
            return
        if len(args) == 1:
            key = args[0]
            if key in config:
                emit(f"  {key} = {config[key]}", Palette.BRIGHT_CYAN)
            else:
                warn(f"key '{key}' not set")
            return
        key, value = args[0], " ".join(args[1:])
        config[key] = value
        set_config("settings", config)
        done(f"set {key} = {value}")

    def cmd_mask(self, args):
        if args:
            try:
                mask_val = int(args[0], 8)
                os.umask(mask_val)
                done(f"umask set to {oct(mask_val)}")
            except ValueError:
                fail("mask must be octal (e.g. 022)")
        else:
            current = os.umask(0)
            os.umask(current)
            emit(f"  current umask: {oct(current)}", Palette.BRIGHT_CYAN)

    def cmd_detach(self, args):
        if not args:
            fail("usage: detach <command...>")
            return
        cmd = " ".join(args)
        try:
            if IS_WINDOWS:
                subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen(cmd, shell=True, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            done(f"detached: {cmd}")
        except Exception as e:
            fail(str(e))

    def cmd_signout(self, args):
        info("signing out...")
        time.sleep(0.5)
        self._signout = True
        self.running = False

    def cmd_vanish(self, args):
        auth = load_auth()
        auth["users"] = [u for u in auth["users"] if u["username"] != self.username]
        save_auth(auth)
        warn(f"account '{self.username}' has been deleted")
        time.sleep(1)
        self._signout = True
        self.running = False

    def cmd_roster(self, args):
        if self.priv.current_level() != "root":
            fail("permission denied: root privileges required")
            return
        auth = load_auth()
        users = auth.get("users", [])
        emit(f"  registered users ({len(users)}/{MAX_USERS})", Palette.BOLD + Palette.BRIGHT_YELLOW)
        for u in users:
            try:
                created = datetime.datetime.fromtimestamp(u.get("created", 0)).strftime("%Y-%m-%d")
            except Exception:
                created = "unknown"
            try:
                last = datetime.datetime.fromtimestamp(u.get("last_login", 0)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                last = "never"
            emit(f"    {u['username']:<18} created {created}   last login {last}", Palette.WHITE)

    def cmd_fortune(self, args):
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Talk is cheap. Show me the code. - Linus Torvalds",
            "First, solve the problem. Then, write the code. - John Johnson",
            "The best error message is the one that never shows up. - Thomas Fuchs",
            "Code is like humor. When you have to explain it, it's bad. - Cory House",
            "Any fool can write code that a computer can understand. - Martin Fowler",
            "Programs must be written for people to read. - Harold Abelson",
            "Simplicity is the soul of efficiency. - Austin Freeman",
            "Make it work, make it right, make it fast. - Kent Beck",
            "Premature optimization is the root of all evil. - Donald Knuth",
            "There are only two hard things in CS: cache invalidation and naming things. - Phil Karlton",
            "It works on my machine. - Every Developer",
            "There is no place like 127.0.0.1. - Unknown",
            "I would love to change the world, but they won't give me the source code. - Unknown",
        ]
        emit(f"  {random.choice(quotes)}", Palette.BRIGHT_MAGENTA)

    def cmd_colors(self, args):
        line()
        emit("  16-color palette:", Palette.BOLD)
        for i, (name, code) in enumerate([
            ("BLACK", "\033[30m"), ("RED", "\033[31m"), ("GREEN", "\033[32m"),
            ("YELLOW", "\033[33m"), ("BLUE", "\033[34m"), ("MAGENTA", "\033[35m"),
            ("CYAN", "\033[36m"), ("WHITE", "\033[37m"), ("GRAY", "\033[90m"),
            ("BRIGHT_RED", "\033[91m"), ("BRIGHT_GREEN", "\033[92m"), ("BRIGHT_YELLOW", "\033[93m"),
            ("BRIGHT_BLUE", "\033[94m"), ("BRIGHT_MAGENTA", "\033[95m"), ("BRIGHT_CYAN", "\033[96m"),
            ("BRIGHT_WHITE", "\033[97m"),
        ]):
            put(f"  {code}{name:<16}{Palette.RESET}")
            if (i + 1) % 2 == 0:
                line()
        line()
        emit("  256-color cube:", Palette.BOLD)
        for r in range(6):
            for g in range(6):
                for b in range(6):
                    code = 16 + r * 36 + g * 6 + b
                    put(f"\033[48;5;{code}m  \033[0m")
                put(" ")
            line()
        line()

    def cmd_calendar(self, args):
        now = datetime.datetime.now()
        month = int(args[0]) if len(args) > 0 else now.month
        year = int(args[1]) if len(args) > 1 else now.year
        try:
            import calendar
            cal = calendar.month(year, month)
            for ln in cal.split("\n"):
                emit(f"  {ln}", Palette.BRIGHT_CYAN)
        except Exception as e:
            fail(str(e))

    def cmd_coins(self, args):
        count = int(args[0]) if args else 1
        results = [random.choice(["Heads", "Tails"]) for _ in range(count)]
        heads = results.count("Heads")
        tails = results.count("Tails")
        for r in results:
            symbol = "\u25cf" if r == "Heads" else "\u25cb"
            color = Palette.BRIGHT_YELLOW if r == "Heads" else Palette.GRAY
            emit(f"  {symbol} {r}", color)
        line()
        emit(f"  Heads: {heads}  Tails: {tails}", Palette.BRIGHT_CYAN)

    def cmd_lorem(self, args):
        paragraphs = int(args[0]) if args else 3
        words = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident sunt in culpa qui officia deserunt mollit anim id est laborum".split()
        for _ in range(paragraphs):
            length = random.randint(40, 80)
            para = " ".join(random.choice(words) for _ in range(length)).capitalize() + "."
            emit(f"  {para}", Palette.WHITE)
            line()

    def cmd_slug(self, args):
        if not args:
            fail("usage: slug <text>")
            return
        text = " ".join(args).lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = text.strip("-")
        emit(f"  {text}", Palette.BRIGHT_GREEN)

    def cmd_case(self, args):
        if len(args) < 2:
            fail("usage: case <upper|lower|title|swap> <text>")
            return
        mode = args[0].lower()
        text = " ".join(args[1:])
        if mode == "upper":
            result = text.upper()
        elif mode == "lower":
            result = text.lower()
        elif mode == "title":
            result = text.title()
        elif mode == "swap":
            result = text.swapcase()
        else:
            fail(f"unknown mode: {mode}")
            return
        emit(f"  {result}", Palette.BRIGHT_GREEN)

    def cmd_morse(self, args):
        if len(args) < 2:
            fail("usage: morse <encode|decode> <text>")
            return
        mode = args[0].lower()
        text = " ".join(args[1:]).upper()
        morse_map = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.", " ": "/"}
        if mode == "encode":
            result = " ".join(morse_map.get(c, "?") for c in text)
            emit(f"  {result}", Palette.BRIGHT_YELLOW)
        elif mode == "decode":
            reverse_map = {v: k for k, v in morse_map.items()}
            result = "".join(reverse_map.get(code, "?") for code in text.split())
            emit(f"  {result}", Palette.BRIGHT_GREEN)
        else:
            fail("mode must be 'encode' or 'decode'")

    def cmd_roman(self, args):
        if not args:
            fail("usage: roman <number|numeral>")
            return
        val = args[0]
        roman_map = [("M", 1000), ("CM", 900), ("D", 500), ("CD", 400), ("C", 100), ("XC", 90), ("L", 50), ("XL", 40), ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1)]
        if val.isdigit():
            num = int(val)
            if num > 3999:
                fail("number too large for roman numerals (max 3999)")
                return
            result = ""
            for letter, value in roman_map:
                while num >= value:
                    result += letter
                    num -= value
            emit(f"  {result}", Palette.BRIGHT_YELLOW)
        else:
            values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
            total = 0
            prev = 0
            for c in val.upper()[::-1]:
                v = values.get(c, 0)
                if v < prev:
                    total -= v
                else:
                    total += v
                prev = v
            emit(f"  {total}", Palette.BRIGHT_GREEN)

    def cmd_temperature(self, args):
        if len(args) < 2:
            fail("usage: temperature <value> <C|F|K>")
            return
        try:
            value = float(args[0])
            unit = args[1].upper()
            if unit == "C":
                c = value
                f = c * 9/5 + 32
                k = c + 273.15
            elif unit == "F":
                f = value
                c = (f - 32) * 5/9
                k = c + 273.15
            elif unit == "K":
                k = value
                c = k - 273.15
                f = c * 9/5 + 32
            else:
                fail("unit must be C, F, or K")
                return
            emit(f"  Celsius:    {c:.2f} \u00b0C", Palette.BRIGHT_CYAN)
            emit(f"  Fahrenheit: {f:.2f} \u00b0F", Palette.BRIGHT_YELLOW)
            emit(f"  Kelvin:     {k:.2f} K", Palette.BRIGHT_RED)
        except ValueError:
            fail("value must be a number")

    def cmd_joke(self, args):
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "There are 10 types of people: those who understand binary and those who don't.",
            "Why do Java developers wear glasses? Because they don't C#.",
            "I told my computer I needed a break, and now it won't stop sending me KitKat ads.",
            "Why did the developer go broke? Because he used up all his cache.",
            "A SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'",
            "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25.",
            "There are only two hard things in programming: cache invalidation, naming things, and off-by-one errors.",
            "Why did the function stop calling? Because it didn't get any arguments.",
            "I would tell you a UDP joke, but you might not get it.",
        ]
        emit(f"  {random.choice(jokes)}", Palette.BRIGHT_MAGENTA)

    def cmd_birthday(self, args):
        if not args:
            fail("usage: birthday <YYYY-MM-DD>")
            return
        try:
            target = datetime.datetime.strptime(args[0], "%Y-%m-%d")
            now = datetime.datetime.now()
            next_occurrence = target.replace(year=now.year)
            if next_occurrence < now:
                next_occurrence = target.replace(year=now.year + 1)
            delta = next_occurrence - now
            days = delta.days
            age = now.year - target.year - ((now.month, now.day) < (target.month, target.day))
            emit(f"  next occurrence: {next_occurrence.strftime('%Y-%m-%d')}", Palette.BRIGHT_CYAN)
            emit(f"  days until:      {days}", Palette.BRIGHT_GREEN)
            emit(f"  will turn:       {age + 1}", Palette.BRIGHT_YELLOW)
        except ValueError:
            fail("invalid date format. use YYYY-MM-DD")

    def cmd_ascii(self, args):
        if not args:
            fail("usage: ascii <text>")
            return
        text = " ".join(args).upper()
        font = {
            "A": ["  ██  ", " █  █ ", "██████", "█    █", "█    █"],
            "B": ["█████ ", "█    █", "█████ ", "█    █", "█████ "],
            "C": [" █████", "█     ", "█     ", "█     ", " █████"],
            "D": ["█████ ", "█    █", "█    █", "█    █", "█████ "],
            "E": ["██████", "█     ", "████  ", "█     ", "██████"],
            "F": ["██████", "█     ", "████  ", "█     ", "█     "],
            "G": [" █████", "█     ", "█  ███", "█    █", " █████"],
            "H": ["█    █", "█    █", "██████", "█    █", "█    █"],
            "I": ["██████", "  ██  ", "  ██  ", "  ██  ", "██████"],
            "J": ["  ████", "    █ ", "    █ ", "█   █ ", " ███  "],
            "K": ["█   █ ", "█  █  ", "███   ", "█  █  ", "█   █ "],
            "L": ["█     ", "█     ", "█     ", "█     ", "██████"],
            "M": ["█    █", "██  ██", "█ ██ █", "█    █", "█    █"],
            "N": ["█    █", "██   █", "█ █  █", "█  █ █", "█   ██"],
            "O": [" ████ ", "█    █", "█    █", "█    █", " ████ "],
            "P": ["█████ ", "█    █", "█████ ", "█     ", "█     "],
            "Q": [" ████ ", "█    █", "█  █ █", "█   █ ", " ███ █"],
            "R": ["█████ ", "█    █", "█████ ", "█  █  ", "█   █ "],
            "S": [" █████", "█     ", " ████ ", "     █", "█████ "],
            "T": ["███████", "   █   ", "   █   ", "   █   ", "   █   "],
            "U": ["█    █", "█    █", "█    █", "█    █", " ████ "],
            "V": ["█    █", "█    █", "█    █", " █  █ ", "  ██  "],
            "W": ["█    █", "█    █", "█ ██ █", "██  ██", "█    █"],
            "X": ["█   █ ", " █ █  ", "  █   ", " █ █  ", "█   █ "],
            "Y": ["█   █ ", " █ █  ", "  █   ", "  █   ", "  █   "],
            "Z": ["██████", "    █ ", "   █  ", "  █   ", "██████"],
            " ": ["      ", "      ", "      ", "      ", "      "],
            "0": [" ████ ", "█  █ █", "█ █ █ ", "██  █ ", " ████ "],
            "1": ["  ██  ", " ███  ", "  ██  ", "  ██  ", "██████"],
            "2": [" ████ ", "█    █", "   ██ ", "  █   ", "██████"],
            "3": ["████  ", "    █ ", " ███  ", "    █ ", "████  "],
            "4": ["  █ █ ", " █  █ ", "██████", "    █ ", "    █ "],
            "5": ["██████", "█     ", "█████ ", "     █", "█████ "],
            "6": [" ████ ", "█     ", "█████ ", "█    █", " ████ "],
            "7": ["██████", "    █ ", "   █  ", "  █   ", " █    "],
            "8": [" ████ ", "█    █", " ████ ", "█    █", " ████ "],
            "9": [" ████ ", "█    █", " █████", "     █", " ████ "],
        }
        for row in range(5):
            line_text = ""
            for ch in text:
                if ch in font:
                    line_text += font[ch][row] + " "
                else:
                    line_text += "       "
            emit(f"  {line_text}", Palette.BRIGHT_CYAN)

    def cmd_moon(self, args):
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        if month < 3:
            year -= 1
            month += 12
        a = year // 100
        b = 2 - a + a // 4
        jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524
        moon_age = (jd - 2451550.1) % 29.53058867
        phase = int((moon_age / 29.53058867) * 8) % 8
        phases = [
            ("New Moon", "\u25cf"),
            ("Waxing Crescent", "\u25d4"),
            ("First Quarter", "\u25d3"),
            ("Waxing Gibbous", "\u25d1"),
            ("Full Moon", "\u25cb"),
            ("Waning Gibbous", "\u25d2"),
            ("Last Quarter", "\u25d0"),
            ("Waning Crescent", "\u25d5"),
        ]
        name, symbol = phases[phase]
        emit(f"  {symbol}  {name}", Palette.BRIGHT_YELLOW)
        emit(f"  moon age: {moon_age:.1f} days", Palette.GRAY)

    def cmd_reverse_text(self, args):
        if not args:
            fail("usage: reverse-text <text>")
            return
        text = " ".join(args)
        emit(f"  {text[::-1]}", Palette.BRIGHT_GREEN)

    def cmd_exec(self, args):
        if not args:
            fail("usage: exec <script> [args...]")
            return
        script = args[0].strip("<>")
        extra_args = args[1:]
        path = self._resolve_path(script) if self.mode == "real" else script
        if not os.path.exists(path) and self.mode == "real":
            fail(f"script not found: {script}")
            return
        ext = os.path.splitext(script)[1].lower()
        interpreters = {
            ".py": [sys.executable],
            ".pyw": [sys.executable],
            ".bat": ["cmd", "/c"],
            ".cmd": ["cmd", "/c"],
            ".ps1": ["powershell", "-ExecutionPolicy", "Bypass", "-File"],
            ".psm1": ["powershell", "-ExecutionPolicy", "Bypass", "-File"],
            ".sh": ["bash"],
            ".bash": ["bash"],
            ".zsh": ["zsh"],
            ".vbs": ["cscript", "//nologo"],
            ".vbe": ["cscript", "//nologo"],
            ".js": ["cscript", "//nologo"],
            ".jse": ["cscript", "//nologo"],
            ".wsf": ["cscript", "//nologo"],
            ".rb": ["ruby"],
            ".pl": ["perl"],
            ".php": ["php"],
            ".lua": ["lua"],
            ".tcl": ["tclsh"],
            ".ahk": ["autohotkey"],
            ".r": ["Rscript"],
            ".go": ["go", "run"],
            ".rs": ["rustc"],
            ".java": ["java"],
            ".class": ["java"],
            ".jar": ["java", "-jar"],
            ".exe": [],
            ".msi": ["msiexec", "/i"],
        }
        if ext in interpreters:
            cmd_list = interpreters[ext] + [path] + extra_args
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
                if first_line.startswith("#!"):
                    shebang = first_line[2:].strip()
                    if "python" in shebang:
                        cmd_list = [sys.executable, path] + extra_args
                    elif "bash" in shebang or "sh" in shebang:
                        cmd_list = ["bash", path] + extra_args
                    elif "node" in shebang:
                        cmd_list = ["node", path] + extra_args
                    else:
                        cmd_list = [shebang.split()[0], path] + extra_args
                else:
                    cmd_list = [sys.executable, path] + extra_args
                    info(f"unknown extension '{ext}', trying Python interpreter")
            except Exception:
                cmd_list = [path] + extra_args
        try:
            info(f"running: {os.path.basename(script)}")
            result = subprocess.run(cmd_list, cwd=self.real_cwd if self.mode == "real" else None)
            if result.returncode != 0:
                warn(f"script exited with code {result.returncode}")
        except FileNotFoundError:
            fail(f"interpreter not found for '{ext}' files. install it first with 'pkg install'")
        except Exception as e:
            fail(str(e))

    def cmd_pkg(self, args):
        if not args:
            fail("usage: pkg <install|remove|list|search|info|update|upgrade> [package]")
            return
        action = args[0].lower()
        if action == "list":
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, timeout=30)
                for ln in result.stdout.strip().split("\n"):
                    emit(f"  {ln}", Palette.WHITE)
            except Exception as e:
                fail(str(e))
            return
        if action == "update":
            info("updating pip...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    done("pip updated successfully")
                else:
                    fail(result.stderr.strip() or "update failed")
            except Exception as e:
                fail(str(e))
            return
        if len(args) < 2 and action in ("install", "remove", "search", "info", "upgrade"):
            fail(f"usage: pkg {action} <package>")
            return
        package = args[1]
        if action == "install":
            info(f"installing {package}...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "install", package], capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    done(f"{package} installed successfully")
                    for ln in result.stdout.strip().split("\n")[-5:]:
                        if ln.strip():
                            emit(f"  {ln.strip()}", Palette.GRAY)
                else:
                    fail(result.stderr.strip() or f"failed to install {package}")
            except Exception as e:
                fail(str(e))
        elif action == "remove":
            info(f"removing {package}...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", package], capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    done(f"{package} removed successfully")
                else:
                    fail(result.stderr.strip() or f"failed to remove {package}")
            except Exception as e:
                fail(str(e))
        elif action == "search":
            info(f"searching for {package}...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "index", "versions", package], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    emit(f"  {result.stdout.strip()}", Palette.BRIGHT_CYAN)
                else:
                    result2 = subprocess.run([sys.executable, "-m", "pip", "install", f"{package}==", "--dry-run"], capture_output=True, text=True, timeout=30)
                    if "from versions" in result2.stderr:
                        versions_line = [l for l in result2.stderr.split("\n") if "from versions" in l]
                        if versions_line:
                            emit(f"  {versions_line[0].strip()}", Palette.BRIGHT_CYAN)
                    else:
                        fail(f"package '{package}' not found")
            except Exception as e:
                fail(str(e))
        elif action == "info":
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "show", package], capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    for ln in result.stdout.strip().split("\n"):
                        emit(f"  {ln}", Palette.WHITE)
                else:
                    fail(f"package '{package}' is not installed")
            except Exception as e:
                fail(str(e))
        elif action == "upgrade":
            info(f"upgrading {package}...")
            try:
                result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", package], capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    done(f"{package} upgraded successfully")
                else:
                    fail(result.stderr.strip() or f"failed to upgrade {package}")
            except Exception as e:
                fail(str(e))
        else:
            fail(f"unknown action: {action}. use install, remove, list, search, info, update, or upgrade")

    def _pkg_dir(self):
        d = os.path.join(CONFIG_DIR, "packages")
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        if d not in sys.path:
            sys.path.insert(0, d)
        return d

    def cmd_update(self, args):
        if not args:
            fail("usage: update <install|remove|list|upgrade|python> [package]")
            return
        action = args[0].lower()
        pkg_dir = self._pkg_dir()
        if action == "python":
            if getattr(sys, "frozen", False):
                info("embedded Python runtime:")
                emit(f"  version:  {sys.version}", Palette.WHITE)
                emit(f"  prefix:   {sys.prefix}", Palette.WHITE)
                emit(f"  executable: {sys.executable}", Palette.GRAY)
                emit(f"  packages dir: {pkg_dir}", Palette.GRAY)
                syspy = find_system_python()
                if syspy:
                    done(f"system Python found: {syspy} (used for pip install)")
                else:
                    warn("no system Python found - install Python 3 to use 'update install'")
            else:
                info(f"Python: {sys.version}")
                emit(f"  executable: {sys.executable}", Palette.WHITE)
            return
        if action == "list":
            if not os.listdir(pkg_dir):
                info("no extension libraries installed")
                return
            info("installed extension libraries:")
            for name in sorted(os.listdir(pkg_dir)):
                if name.endswith(".dist-info") or name.endswith(".egg-info"):
                    continue
                full = os.path.join(pkg_dir, name)
                if os.path.isdir(full) and not name.startswith("__"):
                    emit(f"  {name}", Palette.BRIGHT_GREEN)
                elif name.endswith(".py"):
                    emit(f"  {name}", Palette.BRIGHT_GREEN)
            return
        if action == "install":
            if len(args) < 2:
                fail("usage: update install <package>")
                return
            package = args[1]
            if getattr(sys, "frozen", False):
                syspy = find_system_python()
                if not syspy:
                    fail("no system Python found. Install Python 3 from python.org first")
                    return
                info(f"using system Python: {syspy}")
                info(f"installing {package} to extension library...")
                try:
                    proc = subprocess.Popen(
                        [syspy, "-m", "pip", "install", "--target", pkg_dir, package],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                    )
                    for line in proc.stdout:
                        line = line.strip()
                        if line:
                            lower = line.lower()
                            if "error" in lower or "failed" in lower:
                                fail(line)
                            elif "successfully installed" in lower:
                                done(line)
                            elif "collecting" in lower or "downloading" in lower:
                                emit(f"  {line}", Palette.BRIGHT_CYAN)
                            elif "installing" in lower:
                                emit(f"  {line}", Palette.BRIGHT_YELLOW)
                            else:
                                emit(f"  {line}", Palette.GRAY)
                    proc.wait()
                    if proc.returncode == 0:
                        done(f"{package} ready - restart shell to use it")
                    else:
                        fail(f"install failed (exit code {proc.returncode})")
                except Exception as e:
                    fail(str(e))
            else:
                info(f"installing {package}...")
                try:
                    result = subprocess.run([sys.executable, "-m", "pip", "install", package], capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        done(f"{package} installed successfully")
                    else:
                        fail(result.stderr.strip() or "install failed")
                except Exception as e:
                    fail(str(e))
            return
        if action == "remove":
            if len(args) < 2:
                fail("usage: update remove <package>")
                return
            package = args[1].replace("-", "_")
            removed = False
            for name in os.listdir(pkg_dir):
                if name.lower().replace("-", "_").startswith(package.lower()):
                    full = os.path.join(pkg_dir, name)
                    try:
                        if os.path.isdir(full):
                            shutil.rmtree(full)
                        else:
                            os.remove(full)
                        removed = True
                    except Exception:
                        pass
            if removed:
                done(f"removed {package}")
            else:
                fail(f"package '{package}' not found in extension library")
            return
        if action == "upgrade":
            pkgs = args[1:] if len(args) > 1 else []
            if not pkgs:
                fail("usage: update upgrade <package1> [package2...]")
                return
            for p in pkgs:
                self.cmd_update(["install", "--upgrade", p])
            return
        fail(f"unknown action: {action}. use install, remove, list, upgrade, or python")

    def cmd_py(self, args):
        if not args:
            info("Python interactive mode (type exit() to return)")
            info(f"Python {sys.version}")
            line()
            ns = {}
            while True:
                try:
                    code = input(f"{Palette.BRIGHT_YELLOW}py>{Palette.RESET} ")
                    if code.strip() in ("exit()", "exit", "quit()", "quit"):
                        break
                    if code.strip():
                        try:
                            result = eval(code, ns)
                            if result is not None:
                                emit(f"  {result}", Palette.BRIGHT_GREEN)
                        except SyntaxError:
                            exec(code, ns)
                except KeyboardInterrupt:
                    line()
                    break
                except Exception as e:
                    fail(str(e))
            return
        target = args[0]
        if os.path.isfile(target):
            import runpy
            sys.argv = [target] + args[1:]
            try:
                runpy.run_path(target, run_name="__main__")
            except SystemExit:
                pass
            except Exception as e:
                fail(str(e))
        else:
            code = " ".join(args)
            try:
                result = eval(code)
                if result is not None:
                    emit(f"  {result}", Palette.BRIGHT_GREEN)
            except SyntaxError:
                try:
                    exec(code)
                except Exception as e:
                    fail(str(e))
            except Exception as e:
                fail(str(e))

def tkinter_login():
    if not HAS_TKINTER:
        raise ImportError("tkinter not available")
    result = {"username": None}

    def on_close():
        root.destroy()
        sys.exit(0)

    def show_login():
        register_frame.pack_forget()
        login_frame.pack(fill="both", expand=True, padx=30, pady=10)
        status_label.config(text="", fg="#ff6b6b")

    def show_register():
        login_frame.pack_forget()
        register_frame.pack(fill="both", expand=True, padx=30, pady=10)
        status_label.config(text="", fg="#ff6b6b")

    def do_login():
        username = login_user_entry.get().strip()
        password = login_pass_entry.get()
        if not username:
            status_label.config(text="请输入用户名", fg="#ff6b6b")
            return
        if not password:
            status_label.config(text="请输入密码", fg="#ff6b6b")
            return
        ok, msg = verify_user(username, password)
        if ok:
            result["username"] = username
            root.destroy()
        else:
            status_label.config(text=f"{msg}：{username}", fg="#ff6b6b")
            login_pass_entry.delete(0, tk.END)

    def do_register():
        username = reg_user_entry.get().strip()
        password = reg_pass_entry.get()
        confirm = reg_confirm_entry.get()
        if not username:
            status_label.config(text="请输入用户名", fg="#ff6b6b")
            return
        if not re.match(r"^[a-zA-Z0-9_-]{2,20}$", username):
            status_label.config(text="用户名需2-20位字母数字下划线", fg="#ff6b6b")
            return
        if len(password) < 4:
            status_label.config(text="密码至少4位", fg="#ff6b6b")
            return
        if password != confirm:
            status_label.config(text="两次密码不一致", fg="#ff6b6b")
            return
        ok, msg = add_user(username, password)
        if ok:
            result["username"] = username
            root.destroy()
        else:
            status_label.config(text=msg, fg="#ff6b6b")

    root = tk.Tk()
    root.title("NOVA Shell 登录")
    root.geometry("420x520")
    root.resizable(False, False)
    root.configure(bg="#0f172a")
    root.protocol("WM_DELETE_WINDOW", on_close)

    try:
        icon_loaded = False
        if getattr(sys, "frozen", False):
            ico = os.path.join(os.path.dirname(sys.executable), "nova.ico")
            png = os.path.join(os.path.dirname(sys.executable), "nova.png")
        else:
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova.ico")
            png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova.png")
        if IS_WINDOWS and os.path.exists(ico):
            root.iconbitmap(ico)
            icon_loaded = True
        elif os.path.exists(png):
            img = tk.PhotoImage(file=png)
            root.iconphoto(True, img)
            root._icon_img = img
            icon_loaded = True
        elif os.path.exists(ico):
            root.iconbitmap(ico)
            icon_loaded = True
        if not icon_loaded and getattr(sys, "frozen", False):
            try:
                root.iconbitmap(sys.executable)
            except Exception:
                pass
    except Exception:
        pass

    title_frame = tk.Frame(root, bg="#0f172a")
    title_frame.pack(fill="x", pady=(30, 10))
    tk.Label(title_frame, text="NOVA Shell", font=("Consolas", 28, "bold"), fg="#00e5ff", bg="#0f172a").pack()
    tk.Label(title_frame, text="· · · · · · · · · · · · · · ·", font=("Consolas", 10), fg="#00e5ff", bg="#0f172a").pack(pady=5)

    btn_frame = tk.Frame(root, bg="#0f172a")
    btn_frame.pack(fill="x", padx=30, pady=(0, 5))
    login_tab = tk.Button(btn_frame, text="登 录", font=("Consolas", 11, "bold"), fg="#0f172a", bg="#00e5ff", relief="flat", cursor="hand2", command=show_login)
    login_tab.pack(side="left", fill="x", expand=True, ipady=6)
    register_tab = tk.Button(btn_frame, text="注 册", font=("Consolas", 11, "bold"), fg="#94a3b8", bg="#1e293b", relief="flat", cursor="hand2", command=show_register)
    register_tab.pack(side="left", fill="x", expand=True, ipady=6)

    def switch_tabs(to_login):
        if to_login:
            login_tab.config(bg="#00e5ff", fg="#0f172a")
            register_tab.config(bg="#1e293b", fg="#94a3b8")
        else:
            register_tab.config(bg="#00e5ff", fg="#0f172a")
            login_tab.config(bg="#1e293b", fg="#94a3b8")

    login_tab.config(command=lambda: [switch_tabs(True), show_login()])
    register_tab.config(command=lambda: [switch_tabs(False), show_register()])

    login_frame = tk.Frame(root, bg="#0f172a")
    tk.Label(login_frame, text="用户名", font=("Consolas", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(15, 3))
    login_user_entry = tk.Entry(login_frame, font=("Consolas", 12), bg="#1e293b", fg="#e2e8f0", insertbackground="#00e5ff", relief="flat", justify="center")
    login_user_entry.pack(fill="x", ipady=8)
    tk.Label(login_frame, text="密码", font=("Consolas", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(12, 3))
    login_pass_entry = tk.Entry(login_frame, font=("Consolas", 12), bg="#1e293b", fg="#e2e8f0", insertbackground="#00e5ff", relief="flat", show="*", justify="center")
    login_pass_entry.pack(fill="x", ipady=8)
    tk.Button(login_frame, text="登 录", font=("Consolas", 12, "bold"), fg="#0f172a", bg="#00e5ff", relief="flat", cursor="hand2", command=do_login).pack(fill="x", pady=(20, 0), ipady=8)
    login_user_entry.bind("<Return>", lambda e: login_pass_entry.focus_set())
    login_pass_entry.bind("<Return>", lambda e: do_login())

    register_frame = tk.Frame(root, bg="#0f172a")
    tk.Label(register_frame, text="用户名", font=("Consolas", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(10, 3))
    reg_user_entry = tk.Entry(register_frame, font=("Consolas", 12), bg="#1e293b", fg="#e2e8f0", insertbackground="#00e5ff", relief="flat", justify="center")
    reg_user_entry.pack(fill="x", ipady=7)
    tk.Label(register_frame, text="密码", font=("Consolas", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(8, 3))
    reg_pass_entry = tk.Entry(register_frame, font=("Consolas", 12), bg="#1e293b", fg="#e2e8f0", insertbackground="#00e5ff", relief="flat", show="*", justify="center")
    reg_pass_entry.pack(fill="x", ipady=7)
    tk.Label(register_frame, text="确认密码", font=("Consolas", 10), fg="#94a3b8", bg="#0f172a").pack(anchor="w", pady=(8, 3))
    reg_confirm_entry = tk.Entry(register_frame, font=("Consolas", 12), bg="#1e293b", fg="#e2e8f0", insertbackground="#00e5ff", relief="flat", show="*", justify="center")
    reg_confirm_entry.pack(fill="x", ipady=7)
    tk.Button(register_frame, text="注 册", font=("Consolas", 12, "bold"), fg="#0f172a", bg="#00e5ff", relief="flat", cursor="hand2", command=do_register).pack(fill="x", pady=(15, 0), ipady=8)
    reg_user_entry.bind("<Return>", lambda e: reg_pass_entry.focus_set())
    reg_pass_entry.bind("<Return>", lambda e: reg_confirm_entry.focus_set())
    reg_confirm_entry.bind("<Return>", lambda e: do_register())

    status_label = tk.Label(root, text="", font=("Consolas", 10), fg="#ff6b6b", bg="#0f172a", wraplength=360)
    status_label.pack(fill="x", padx=30, pady=(10, 0))

    tk.Label(root, text="NOVA Shell v" + VERSION, font=("Consolas", 8), fg="#475569", bg="#0f172a").pack(side="bottom", pady=8)

    show_login()
    login_user_entry.focus_set()
    root.mainloop()
    return result["username"]

def cli_login():
    auth = load_auth()
    line()
    emit("  NOVA Shell   -   Login", Palette.BOLD + Palette.BRIGHT_CYAN)
    emit(f"  {'-' * 38}", Palette.BRIGHT_CYAN)
    line()
    attempts = 0
    while attempts < 3:
        username = input(f"  {Palette.BRIGHT_CYAN}>{Palette.RESET} {Palette.BOLD}Username:{Palette.RESET} ").strip()
        password = getpass.getpass(f"  {Palette.BRIGHT_CYAN}>{Palette.RESET} {Palette.BOLD}Password:{Palette.RESET} ")
        ok, msg = verify_user(username, password)
        if ok:
            line()
            done(f"welcome back, {username}")
            line()
            return username
        attempts += 1
        fail(f"{msg} - {3 - attempts} attempt(s) remaining")
        if attempts >= 3:
            sys.exit(1)
    return None

def cleanup_temp_files():
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        for name in os.listdir(exe_dir):
            low = name.lower()
            if low.startswith("nova_temp_") and low.endswith(".exe"):
                try:
                    os.remove(os.path.join(exe_dir, name))
                except Exception:
                    pass
            elif low.startswith("nova_") and low.endswith(".bat"):
                try:
                    os.remove(os.path.join(exe_dir, name))
                except Exception:
                    pass

def find_system_python():
    candidates = []
    if IS_WINDOWS:
        candidates = ["py", "python", "python3"]
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for exe in ("python.exe", "python3.exe", "py.exe"):
                fp = os.path.join(p, exe)
                if os.path.isfile(fp):
                    candidates.insert(0, fp)
                    break
    else:
        candidates = ["python3", "python"]
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for exe in ("python3", "python"):
                fp = os.path.join(p, exe)
                if os.path.isfile(fp) and os.access(fp, os.X_OK):
                    candidates.insert(0, fp)
                    break
    for c in candidates:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return None

def _wait_any_key():
    try:
        if IS_WINDOWS:
            import msvcrt as _m
            _m.getwch()
        else:
            import termios as _te, tty as _tt
            _fd = sys.stdin.fileno()
            _old = _te.tcgetattr(_fd)
            try:
                _tt.setraw(_fd)
                sys.stdin.read(1)
            finally:
                _te.tcsetattr(_fd, _te.TCSADRAIN, _old)
    except Exception:
        try:
            input()
        except Exception:
            pass

def main():
    cleanup_temp_files()
    enable_vt()
    set_console_font()
    set_console_title("NOVA Shell")
    ensure_config_dir()
    pkg_dir = os.path.join(CONFIG_DIR, "packages")
    if os.path.isdir(pkg_dir) and pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    sys.stdout.write("\033[?25h\033[5 q")
    sys.stdout.flush()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    while True:
        username = None
        if HAS_TKINTER:
            try:
                username = tkinter_login()
            except Exception:
                username = None
        if username is None:
            try:
                username = cli_login()
            except Exception:
                username = None
        if username is None:
            sys.stdout.write("\033[?25h\033[0 q")
            sys.stdout.flush()
            sys.exit(1)
        init_animation()
        shell = NOVAShell()
        shell.username = username
        try:
            shell.run()
        finally:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        if getattr(shell, "_signout", False):
            line()
            emit("  NOVA Shell terminal user session ended", Palette.BRIGHT_CYAN)
            emit("  Press any key to exit", Palette.GRAY)
            _wait_any_key()
            sys.stdout.write("\033[H\033[2J\033[3J")
            sys.stdout.flush()
            continue
        sys.stdout.write("\033[0 q")
        sys.stdout.flush()
        break

if __name__ == "__main__":
    main()
