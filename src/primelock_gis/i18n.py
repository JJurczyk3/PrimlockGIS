"""Shared language selection and message translation."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Literal, cast

Language = Literal["en", "zh-CN"]

DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: tuple[Language, ...] = ("en", "zh-CN")
LANGUAGE_ENVIRONMENT_VARIABLE = "PRIMELOCK_GIS_LANGUAGE"

_LANGUAGE_ALIASES: Mapping[str, Language] = {
    "en": "en",
    "en-gb": "en",
    "en-us": "en",
    "english": "en",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "chinese": "zh-CN",
    "simplified-chinese": "zh-CN",
    "简体中文": "zh-CN",
    "中文": "zh-CN",
}

_MESSAGES: Mapping[str, Mapping[Language, str]] = {
    "title.viewer": {
        "en": "Primelock GIS - Viewer",
        "zh-CN": "Primelock GIS - 地图查看器",
    },
    "title.support": {
        "en": "Primelock GIS - Support / Control",
        "zh-CN": "Primelock GIS - 支持与控制面板",
    },
    "title.launcher": {
        "en": "Primelock GIS Launcher",
        "zh-CN": "Primelock GIS 启动器",
    },
    "cli.viewer_server_error": {
        "en": "ERROR: {error}. Close any old Primelock GIS windows and try again.",
        "zh-CN": "错误：{error}。请关闭旧的 Primelock GIS 窗口后重试。",
    },
    "cli.launch_error": {
        "en": "ERROR: {error}",
        "zh-CN": "错误：{error}",
    },
    "cli.launch_success": {
        "en": "Primelock GIS launched using {method} on localhost port {port}.",
        "zh-CN": "Primelock GIS 已使用 {method} 启动，本地主机端口为 {port}。",
    },
    "launch.method.windows-terminal": {
        "en": "Windows Terminal",
        "zh-CN": "Windows 终端",
    },
    "launch.method.windows-console": {
        "en": "Windows console",
        "zh-CN": "Windows 控制台",
    },
    "launch.windows_only": {
        "en": "The one-click launch mode is currently available on Windows only.",
        "zh-CN": "一键启动模式目前仅支持 Windows。",
    },
    "launch.console_failure": {
        "en": "Windows console windows could not be started: {error}",
        "zh-CN": "无法启动 Windows 控制台窗口：{error}",
    },
    "launch.port_conflict": {
        "en": (
            "Localhost port {port} is already in use. Close old Primelock GIS "
            "windows or omit --port so a free port can be selected."
        ),
        "zh-CN": (
            "本地主机端口 {port} 已被占用。请关闭旧的 Primelock GIS 窗口，"
            "或省略 --port 以自动选择可用端口。"
        ),
    },
    "startup.bind_failure": {
        "en": "could not bind localhost command server on {host}:{port}: {error}",
        "zh-CN": "无法在 {host}:{port} 绑定本地主机命令服务器：{error}",
    },
    "doctor.runtime_directory": {
        "en": "Runtime directory: {directory}",
        "zh-CN": "运行目录：{directory}",
    },
    "doctor.executable": {
        "en": "{status} executable: {path}",
        "zh-CN": "{status} 可执行文件：{path}",
    },
    "doctor.dataset": {
        "en": "{status} default dataset: {path}",
        "zh-CN": "{status} 默认数据集：{path}",
    },
    "doctor.port_available": {
        "en": "OK   loopback port available: {port}",
        "zh-CN": "正常 回环端口可用：{port}",
    },
    "doctor.port_failure": {
        "en": "FAIL loopback port allocation: {error}",
        "zh-CN": "失败 无法分配回环端口：{error}",
    },
    "doctor.windows_terminal": {
        "en": "OK   Windows Terminal: {path}",
        "zh-CN": "正常 Windows Terminal：{path}",
    },
    "doctor.console_fallback": {
        "en": "OK   Windows Terminal not found; ordinary consoles will be used",
        "zh-CN": "正常 未找到 Windows Terminal；将使用普通控制台",
    },
    "doctor.windows_only": {
        "en": "INFO one-click launch mode is Windows-only",
        "zh-CN": "信息 一键启动模式仅支持 Windows",
    },
}

_current_language: ContextVar[Language | None] = ContextVar(
    "primelock_gis_language",
    default=None,
)


def normalize_language(
    value: str | None,
    *,
    default: Language = DEFAULT_LANGUAGE,
) -> Language:
    """Return a canonical language code or raise for an unsupported value."""
    if value is None or not value.strip():
        return default
    normalized = value.strip().replace("_", "-").lower()
    try:
        return _LANGUAGE_ALIASES[normalized]
    except KeyError as error:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise ValueError(
            f"unsupported language {value!r}; expected one of: {supported}"
        ) from error


def resolve_language(
    explicit: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Language:
    """Resolve an explicit choice, then the environment, then English."""
    if explicit is not None:
        return normalize_language(explicit)
    environment = os.environ if env is None else env
    configured = environment.get(LANGUAGE_ENVIRONMENT_VARIABLE)
    if not configured:
        return DEFAULT_LANGUAGE
    try:
        return normalize_language(configured)
    except ValueError:
        return DEFAULT_LANGUAGE


def get_language() -> Language:
    """Return the current process context language."""
    return _current_language.get() or resolve_language()


def set_language(language: str | None) -> Language:
    """Set and return the current process context language."""
    selected = resolve_language(language)
    _current_language.set(selected)
    return selected


@contextmanager
def use_language(language: str | None) -> Iterator[Language]:
    """Temporarily select a language for the current execution context."""
    selected = resolve_language(language)
    token: Token[Language | None] = _current_language.set(selected)
    try:
        yield selected
    finally:
        _current_language.reset(token)


def translate(
    message_key: str,
    *,
    language: str | None = None,
    default: str | None = None,
    **values: object,
) -> str:
    """Translate a message key and interpolate its named values."""
    selected = normalize_language(language) if language is not None else get_language()
    translations = _MESSAGES.get(message_key)
    if translations is None:
        template = default if default is not None else message_key
    else:
        template = translations.get(selected) or translations[DEFAULT_LANGUAGE]
    return template.format(**values)


tr = translate


def supported_language(value: str) -> Language:
    """Argparse-compatible canonical language parser."""
    return cast(Language, normalize_language(value))
