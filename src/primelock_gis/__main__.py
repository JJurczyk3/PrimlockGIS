"""Primelock GIS command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from functools import partial

from primelock_gis import __version__
from primelock_gis.app.launcher import (
    LaunchError,
    doctor_lines,
    launch_windows_application,
    set_console_title,
    support_title,
    viewer_title,
)
from primelock_gis.app.startup import ViewerServerStartError, run_terminal_beta
from primelock_gis.i18n import (
    SUPPORTED_LANGUAGES,
    Language,
    normalize_language,
    resolve_language,
    supported_language,
    tr,
    use_language,
)
from primelock_gis.ui.terminal.support_panel import run_support_panel


def _interface_text(language: Language, english: str, chinese: str) -> str:
    return chinese if language == "zh-CN" else english


class LocalizedArgumentParser(argparse.ArgumentParser):
    """Present command help in the selected interface language."""

    def __init__(self, *args, language: Language = "en", **kwargs) -> None:
        self.interface_language = language
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = _interface_text(language, "commands", "命令")
        self._optionals.title = _interface_text(language, "options", "选项")
        self.add_argument(
            "-h",
            "--help",
            action="help",
            help=_interface_text(
                language,
                "show this help message and exit",
                "显示此帮助信息并退出",
            ),
        )

    def format_usage(self) -> str:
        usage = super().format_usage()
        if self.interface_language == "zh-CN":
            return usage.replace("usage:", "用法：", 1)
        return usage

    def format_help(self) -> str:
        help_text = super().format_help()
        if self.interface_language == "zh-CN":
            return help_text.replace("usage:", "用法：", 1)
        return help_text

    def error(self, message: str) -> None:
        if self.interface_language != "zh-CN":
            super().error(message)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 参数错误：{message}\n")


def _port_number(value: str, *, language: Language = "en") -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            _interface_text(language, "port must be an integer", "端口必须是整数")
        ) from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            _interface_text(
                language,
                "port must be between 1 and 65535",
                "端口必须介于 1 和 65535 之间",
            )
        )
    return port


def build_parser(language: Language | str | None = None) -> argparse.ArgumentParser:
    """Build the public frozen-executable command interface."""
    selected_language = resolve_language(language)
    text = partial(_interface_text, selected_language)
    parser = LocalizedArgumentParser(
        prog="PrimelockGIS",
        language=selected_language,
        description=text(
            "Terminal-based GIS viewer and support application.",
            "终端式 GIS 地图查看器与支持/控制应用程序。",
        ),
    )
    parser.add_argument(
        "--language",
        type=supported_language,
        choices=SUPPORTED_LANGUAGES,
        default=resolve_language(),
        help=text("interface language (en or zh-CN)", "界面语言（en 或 zh-CN）"),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Primelock GIS {__version__}",
        help=text("show version and exit", "显示版本并退出"),
    )
    commands = parser.add_subparsers(
        dest="command",
        title=text("commands", "命令"),
        metavar="{viewer,support,launch,doctor}",
        parser_class=partial(
            LocalizedArgumentParser,
            language=selected_language,
        ),
    )

    viewer = commands.add_parser(
        "viewer",
        help=text("open the GIS viewer", "打开 GIS 地图查看器"),
    )
    _add_command_language_option(viewer, selected_language)
    viewer.add_argument(
        "--port",
        type=partial(_port_number, language=selected_language),
        default=8765,
        help=text("localhost command port", "本地主机命令端口"),
    )
    viewer.add_argument(
        "--session-token",
        help=text("private launch-session token", "私有启动会话令牌"),
    )

    support = commands.add_parser(
        "support",
        help=text("open the support panel", "打开支持与控制面板"),
    )
    _add_command_language_option(support, selected_language)
    support.add_argument(
        "--port",
        type=partial(_port_number, language=selected_language),
        default=8765,
        help=text("viewer localhost port", "查看器本地主机端口"),
    )
    support.add_argument(
        "--session-token",
        help=text("private launch-session token", "私有启动会话令牌"),
    )
    support.add_argument(
        "--startup-timeout",
        type=float,
        default=15.0,
        help=text("viewer connection wait in seconds", "等待查看器连接的秒数"),
    )
    support.add_argument(
        "--manage-viewer",
        action="store_true",
        help=text("manage the launched viewer process", "管理已启动的查看器进程"),
    )

    launch = commands.add_parser(
        "launch",
        help=text(
            "open the complete two-window Windows application",
            "打开完整的双窗口 Windows 应用程序",
        ),
    )
    _add_command_language_option(launch, selected_language)
    launch.add_argument(
        "--port",
        type=partial(_port_number, language=selected_language),
        help=text("specific free localhost port", "指定可用的本地主机端口"),
    )
    launch.add_argument(
        "--no-windows-terminal",
        action="store_true",
        help=text("use ordinary console windows", "使用普通控制台窗口"),
    )

    doctor = commands.add_parser(
        "doctor",
        help=text("run offline launch diagnostics", "运行离线启动诊断"),
    )
    _add_command_language_option(doctor, selected_language)
    return parser


def _add_command_language_option(
    parser: argparse.ArgumentParser,
    language: Language = "en",
) -> None:
    """Accept --language after a subcommand without overriding a global choice."""
    parser.add_argument(
        "--language",
        type=supported_language,
        choices=SUPPORTED_LANGUAGES,
        default=argparse.SUPPRESS,
        help=_interface_text(
            language,
            "interface language (en or zh-CN)",
            "界面语言（en 或 zh-CN）",
        ),
    )


def _requested_language(arguments: Sequence[str]) -> Language:
    """Pre-read --language so help and parser errors use the requested language."""
    requested: str | None = None
    for index, argument in enumerate(arguments):
        if argument.startswith("--language="):
            requested = argument.split("=", 1)[1]
        elif argument == "--language" and index + 1 < len(arguments):
            requested = arguments[index + 1]
    if requested is None:
        return resolve_language()
    try:
        return normalize_language(requested)
    except ValueError:
        return resolve_language()


def _configure_windows_text_streams() -> None:
    """Keep CLI diagnostics Unicode-safe in consoles and redirected pipes."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            # A host may provide an immutable or already-closed stream. The
            # terminal backends still configure their real console handles.
            continue


def main(argv: Sequence[str] | None = None) -> int:
    """Run a selected application mode and return a process exit status."""
    _configure_windows_text_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["viewer"]
    parser_language = _requested_language(arguments)
    args = build_parser(parser_language).parse_args(arguments)
    language = resolve_language(args.language)
    with use_language(language):
        return _run_command(args, language)


def _run_command(args: argparse.Namespace, language: Language) -> int:
    """Run one parsed command in its selected language context."""

    if args.command == "viewer":
        set_console_title(viewer_title(language))
        try:
            run_terminal_beta(
                port=args.port,
                session_token=args.session_token,
                language=language,
            )
        except ViewerServerStartError as error:
            print(
                tr("cli.viewer_server_error", language=language, error=error),
                file=sys.stderr,
            )
            return 2
        return 0

    if args.command == "support":
        set_console_title(support_title(language))
        run_support_panel(
            port=args.port,
            session_token=args.session_token,
            startup_timeout=args.startup_timeout,
            manage_viewer=args.manage_viewer,
            language=language,
        )
        return 0

    if args.command == "launch":
        set_console_title(tr("title.launcher", language=language))
        try:
            result = launch_windows_application(
                port=args.port,
                prefer_windows_terminal=not args.no_windows_terminal,
                language=language,
            )
        except LaunchError as error:
            print(
                tr("cli.launch_error", language=language, error=error),
                file=sys.stderr,
            )
            return 2
        print(
            tr(
                "cli.launch_success",
                language=language,
                method=tr(
                    f"launch.method.{result.method}",
                    language=language,
                    default=result.method,
                ),
                port=result.port,
            )
        )
        return 0

    if args.command == "doctor":
        lines, healthy = doctor_lines(language=language)
        print("\n".join(lines))
        return 0 if healthy else 2

    build_parser(language).print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
