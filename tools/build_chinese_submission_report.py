"""Build the print-ready Chinese coursework source-code report."""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import textwrap
import tokenize
import tomllib
import unicodedata
from collections.abc import Iterable, Sequence
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
INTRODUCTION_PATH = PROJECT_ROOT / "COURSEWORK_SOURCE_GUIDE_ZH.md"
TRANSLATIONS_PATH = TOOLS_DIR / "resources" / "chinese_code_translations.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "pdf"

CHINESE_SECTION_TEXT = {
    "Geometry and data loading": (
        "第一部分：数据读取与几何基础",
        "课程 CSV 数据读取、字段验证和公共二维几何运算。",
    ),
    "GIS data models": (
        "第二部分：GIS 数据模型",
        "采样点、规则格网、TIN、等值线和拓扑关系的数据结构。",
    ),
    "GIS algorithms": (
        "第三部分：GIS 核心算法",
        "插值、格网、TIN、等值线提取与追踪以及第一阶段拓扑实现。",
    ),
}

NON_PROSE_COMMENT_PREFIXES = (
    "#!",
    "# -*-",
    "# coding",
    "# noqa",
    "# type:",
    "# pragma:",
)


def project_version(project_root: Path = PROJECT_ROOT) -> str:
    """Read the canonical project version."""
    with (project_root / "pyproject.toml").open("rb") as file:
        return str(tomllib.load(file)["project"]["version"])


def default_output_path(project_root: Path = PROJECT_ROOT) -> Path:
    """Return the versioned Chinese report path."""
    version = project_version(project_root)
    return (
        project_root / "output" / "pdf" / f"PrimelockGIS-中文源代码报告-v{version}.pdf"
    )


def _load_print_profile() -> tuple[object, ...]:
    """Load the curated source profile from the HTML print builder."""
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    from build_printed_source import profile_sections

    return profile_sections("gis")


def ordered_manifest() -> tuple[str, ...]:
    """Return the curated source paths in printed order."""
    return tuple(path for section in _load_print_profile() for path in section.paths)


def load_translations(path: Path = TRANSLATIONS_PATH) -> dict[str, dict[str, str]]:
    """Load deterministic Chinese comment and docstring translations."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"comments", "docstrings"}:
        raise ValueError("Translation resource must contain comments and docstrings")
    return {
        category: {
            normalise_translation_key(source): translation.strip()
            for source, translation in entries.items()
        }
        for category, entries in data.items()
    }


def normalise_translation_key(text: str) -> str:
    """Collapse whitespace so formatted docstrings have stable lookup keys."""
    return " ".join(text.strip().split())


def _docstring_nodes(tree: ast.AST) -> Iterable[ast.Expr]:
    containers = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, containers) or not node.body:
            continue
        candidate = node.body[0]
        if (
            isinstance(candidate, ast.Expr)
            and isinstance(candidate.value, ast.Constant)
            and isinstance(candidate.value.value, str)
        ):
            yield candidate


def source_translation_keys(source_text: str) -> dict[str, set[str]]:
    """Collect prose comments and docstrings that require translation."""
    keys = {"comments": set(), "docstrings": set()}
    tree = ast.parse(source_text)
    for node in _docstring_nodes(tree):
        keys["docstrings"].add(normalise_translation_key(node.value.value))

    for token in tokenize.generate_tokens(io.StringIO(source_text).readline):
        if token.type != tokenize.COMMENT:
            continue
        stripped = token.string.strip()
        if stripped.startswith(NON_PROSE_COMMENT_PREFIXES):
            continue
        comment = token.string.lstrip("#").strip()
        if comment:
            keys["comments"].add(normalise_translation_key(comment))
    return keys


def untranslated_entries(
    project_root: Path = PROJECT_ROOT,
    translations: dict[str, dict[str, str]] | None = None,
) -> dict[str, list[str]]:
    """Return missing translations across every printed Python file."""
    translations = translations or load_translations()
    missing = {"comments": set(), "docstrings": set()}
    for relative_path in ordered_manifest():
        if not relative_path.endswith(".py"):
            continue
        source_text = (project_root / relative_path).read_text(encoding="utf-8")
        keys = source_translation_keys(source_text)
        for category in missing:
            missing[category].update(keys[category] - set(translations[category]))
    return {category: sorted(entries) for category, entries in missing.items()}


def translated_source_lines(
    source_text: str,
    translations: dict[str, dict[str, str]],
) -> list[tuple[int | None, str]]:
    """Replace prose comments and docstrings with their Chinese print versions."""
    lines = source_text.splitlines()
    tree = ast.parse(source_text)
    docstrings: dict[int, tuple[int, str, str]] = {}
    covered_docstring_lines: set[int] = set()
    for node in _docstring_nodes(tree):
        start = node.lineno
        end = node.end_lineno or start
        key = normalise_translation_key(node.value.value)
        translated = translations["docstrings"][key]
        indent = re.match(r"\s*", lines[start - 1]).group(0)
        docstrings[start] = (end, indent, translated)
        covered_docstring_lines.update(range(start, end + 1))

    comments_by_line: dict[int, list[tokenize.TokenInfo]] = {}
    for token in tokenize.generate_tokens(io.StringIO(source_text).readline):
        if token.type == tokenize.COMMENT:
            comments_by_line.setdefault(token.start[0], []).append(token)

    rendered: list[tuple[int | None, str]] = []
    line_number = 1
    while line_number <= len(lines):
        if line_number in docstrings:
            end, indent, translated = docstrings[line_number]
            rendered.append((line_number, f'{indent}"""{translated}"""'))
            line_number = end + 1
            continue
        if line_number in covered_docstring_lines:
            line_number += 1
            continue

        line = lines[line_number - 1].expandtabs(4)
        for token in sorted(
            comments_by_line.get(line_number, ()),
            key=lambda item: item.start[1],
            reverse=True,
        ):
            stripped = token.string.strip()
            if stripped.startswith(NON_PROSE_COMMENT_PREFIXES):
                continue
            source_comment = token.string.lstrip("#").strip()
            if not source_comment:
                continue
            key = normalise_translation_key(source_comment)
            translated = translations["comments"][key]
            column = token.start[1]
            line = line[:column] + f"# {translated}"
        rendered.append((line_number, line))
        line_number += 1
    return rendered


def _display_width(text: str) -> int:
    return sum(2 if ord(character) > 0xFF else 1 for character in text)


def _wrap_display_line(text: str, width: int) -> list[str]:
    if _display_width(text) <= width:
        return [text]
    chunks: list[str] = []
    current = ""
    current_width = 0
    for character in text:
        character_width = 2 if ord(character) > 0xFF else 1
        if current and current_width + character_width > width:
            chunks.append(current)
            current = ""
            current_width = 0
        current += character
        current_width += character_width
    chunks.append(current)
    return chunks


def formatted_code_text(lines: list[tuple[int | None, str]], width: int = 104) -> str:
    """Format translated source with stable original line numbers."""
    output: list[str] = []
    for line_number, line in lines:
        chunks = _wrap_display_line(line, width)
        for index, chunk in enumerate(chunks):
            number = (
                f"{line_number:04d}"
                if index == 0 and line_number is not None
                else "    "
            )
            marker = "|" if index == 0 else "> "
            output.append(f"{number} {marker} {chunk}")
    return "\n".join(output) or "0001 | "


def _register_fonts() -> dict[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = {
        "body": Path("C:/Windows/Fonts/simfang.ttf"),
        "heading": Path("C:/Windows/Fonts/simhei.ttf"),
        "code": Path("C:/Windows/Fonts/simfang.ttf"),
        "terminal": Path("C:/Windows/Fonts/CascadiaMono.ttf"),
    }
    missing = [str(path) for path in candidates.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Chinese font(s): " + ", ".join(missing))
    font_names = {
        "body": "PrimelockChineseBody",
        "heading": "PrimelockChineseHeading",
        "code": "PrimelockChineseCode",
        "terminal": "PrimelockTerminal",
    }
    for role, path in candidates.items():
        pdfmetrics.registerFont(TTFont(font_names[role], str(path)))
    return font_names


def _paragraph_styles(fonts: dict[str, str]):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ChineseTitle",
            parent=styles["Title"],
            fontName=fonts["heading"],
            fontSize=20,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#9A4D0A"),
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "ChineseHeading1",
            parent=styles["Heading1"],
            fontName=fonts["heading"],
            fontSize=15,
            leading=21,
            textColor=colors.HexColor("#9A4D0A"),
            spaceBefore=10,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "ChineseHeading2",
            parent=styles["Heading2"],
            fontName=fonts["heading"],
            fontSize=11.5,
            leading=17,
            textColor=colors.HexColor("#344054"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ChineseBody",
            parent=styles["BodyText"],
            fontName=fonts["body"],
            fontSize=9.5,
            leading=15.5,
            alignment=TA_LEFT,
            firstLineIndent=18,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "ChineseBullet",
            parent=styles["BodyText"],
            fontName=fonts["body"],
            fontSize=9,
            leading=14,
            leftIndent=16,
            firstLineIndent=-9,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "ChineseSmall",
            parent=styles["BodyText"],
            fontName=fonts["body"],
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#475467"),
        ),
        "caption": ParagraphStyle(
            "ChineseCaption",
            parent=styles["BodyText"],
            fontName=fonts["body"],
            fontSize=7.4,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#344054"),
        ),
        "table": ParagraphStyle(
            "ChineseTable",
            parent=styles["BodyText"],
            fontName=fonts["body"],
            fontSize=7.2,
            leading=10,
            spaceAfter=0,
        ),
        "code": ParagraphStyle(
            "ChineseCode",
            fontName=fonts["code"],
            fontSize=6.3,
            leading=7.8,
            leftIndent=5,
            rightIndent=5,
            borderColor=colors.HexColor("#D0D5DD"),
            borderWidth=0.4,
            borderPadding=5,
            backColor=colors.HexColor("#F8FAFC"),
            spaceAfter=7,
        ),
    }


def _markdown_flowables(markdown_text: str, styles: dict[str, object]) -> list[object]:
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Preformatted, Spacer, Table, TableStyle

    flowables: list[object] = []
    lines = markdown_text.splitlines()
    index = 0
    in_code = False
    code_lines: list[str] = []

    def inline_markup(text: str) -> str:
        marked_up = escape(text)
        marked_up = re.sub(
            r"`([^`]+)`",
            r"<font name='Courier'>\1</font>",
            marked_up,
        )
        return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", marked_up)

    def add_paragraph(paragraph_lines: list[str]) -> None:
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines)
        flowables.append(Paragraph(inline_markup(text), styles["body"]))

    paragraph_lines: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            if in_code:
                flowables.append(Preformatted("\n".join(code_lines), styles["code"]))
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if (
            line.startswith("|")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("|")
        ):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            rows = [
                [cell.strip() for cell in row.strip("|").split("|")]
                for row in table_lines
            ]
            if len(rows) >= 2:
                del rows[1]
            rendered_rows = [
                [Paragraph(inline_markup(cell), styles["table"]) for cell in row]
                for row in rows
            ]
            column_count = len(rendered_rows[0]) if rendered_rows else 1
            if column_count == 3:
                column_widths = (35 * mm, 78 * mm, 65 * mm)
            elif column_count == 2:
                column_widths = (50 * mm, 128 * mm)
            else:
                column_widths = tuple(
                    178 * mm / column_count for _ in range(column_count)
                )
            table = Table(
                rendered_rows,
                colWidths=column_widths,
                repeatRows=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), styles["body"].fontName),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                        ("LEADING", (0, 0), (-1, -1), 10),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            flowables.extend([table, Spacer(1, 7)])
            continue
        if not line.strip():
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            index += 1
            continue
        if line.startswith("# "):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            flowables.append(Paragraph(inline_markup(line[2:]), styles["title"]))
        elif line.startswith("## "):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            flowables.append(Paragraph(inline_markup(line[3:]), styles["h1"]))
        elif line.startswith("### "):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            flowables.append(Paragraph(inline_markup(line[4:]), styles["h2"]))
        elif re.match(r"^[-*] ", line):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            flowables.append(
                Paragraph("• " + inline_markup(line[2:]), styles["bullet"])
            )
        elif re.match(r"^\d+\. ", line):
            add_paragraph(paragraph_lines)
            paragraph_lines = []
            flowables.append(Paragraph(inline_markup(line), styles["bullet"]))
        else:
            paragraph_lines.append(line)
        index += 1
    add_paragraph(paragraph_lines)
    return flowables


def _page_decoration(canvas, document, fonts: dict[str, str]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.setLineWidth(0.35)
    canvas.line(17 * mm, height - 13 * mm, width - 17 * mm, height - 13 * mm)
    canvas.setFont(fonts["body"], 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(17 * mm, height - 10.5 * mm, "Primelock GIS 高级 GIS 课程作业")
    canvas.drawRightString(width - 17 * mm, height - 10.5 * mm, "中文源代码打印稿")
    canvas.line(17 * mm, 12 * mm, width - 17 * mm, 12 * mm)
    canvas.drawCentredString(width / 2, 8.5 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def _capture_result_frames(project_root: Path) -> dict[str, object]:
    """Render two representative viewer/support result pairs."""
    source_root = str(project_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    from primelock_gis.app.project_builder import build_project_state
    from primelock_gis.app.project_state import ProjectConfig
    from primelock_gis.core.rendering.viewport_builder import (
        initial_viewport_from_points,
    )
    from primelock_gis.ui.terminal import support_panel as support_panel_module
    from primelock_gis.ui.terminal.capabilities import TerminalCapabilities
    from primelock_gis.ui.terminal.interactive_app import InteractiveTerminalApp
    from primelock_gis.ui.terminal.screen import clip_text
    from primelock_gis.ui.terminal.support_panel import SupportPanelApp
    from primelock_gis.ui.terminal.theme import (
        TERMINAL_THEME,
        color_text,
        status_color,
    )

    columns = 56
    capabilities = TerminalCapabilities(
        name="printed-result",
        supports_unicode=True,
        supports_braille=True,
        supports_color=True,
        supports_truecolor=True,
    )
    config = ProjectConfig(
        dataset_path=project_root / "data" / "initial_coords.csv",
        grid_x_divisions=20,
        grid_y_divisions=20,
    )
    project_state = build_project_state(config)
    viewport = initial_viewport_from_points(
        project_state.points,
        view_width=columns,
        view_height=18,
    )
    viewer = InteractiveTerminalApp(
        project_state,
        viewport,
        capabilities,
        language="zh-CN",
    )

    sample_point = project_state.points[len(project_state.points) // 2]
    viewer._query_at_screen(*viewer._world_to_cell(sample_point.x, sample_point.y))

    def viewer_text() -> str:
        instruction = color_text(
            clip_text(viewer.status_instruction_text(), columns),
            TERMINAL_THEME.muted,
            capabilities,
        )
        information = color_text(
            clip_text(viewer.status_info_text(), columns),
            status_color(viewer.status_info_text()),
            capabilities,
        )
        return "\n".join((viewer.render_frame(), instruction, information))

    def support_text(mode: str, height: int) -> str:
        panel = SupportPanelApp(
            working_directory=project_root,
            capabilities=capabilities,
            language="zh-CN",
        )
        panel.viewer_connected = True
        panel.state.mode = mode
        panel.state.synced_viewer_mode = mode
        panel.state.status = panel._text(
            "support.viewer.connected",
            "Viewer connected",
            "查看器已连接",
        )
        panel.state.selected_feature = viewer.state.selected_feature
        panel.state.config_summary = viewer.handle_support_command(
            "config"
        ).removeprefix("OK: ")
        panel._parse_config_summary(panel.state.config_summary)
        panel.state.layer_summary = viewer.handle_support_command(
            "layers summary"
        ).removeprefix("OK: ")
        panel._parse_layer_summary(panel.state.layer_summary)
        panel.state.model_summary = viewer.handle_support_command(
            "model summary"
        ).removeprefix("OK: ")

        captured: list[str] = []
        original_get_terminal_size = support_panel_module.shutil.get_terminal_size
        original_clear_screen = support_panel_module.clear_screen
        original_draw_frame = support_panel_module.draw_frame
        try:
            support_panel_module.shutil.get_terminal_size = lambda: os.terminal_size(
                (columns, height)
            )
            support_panel_module.clear_screen = lambda: None
            support_panel_module.draw_frame = captured.append
            panel.render()
        finally:
            support_panel_module.shutil.get_terminal_size = original_get_terminal_size
            support_panel_module.clear_screen = original_clear_screen
            support_panel_module.draw_frame = original_draw_frame
        return captured[0]

    query_viewer = viewer_text()
    query_support = support_text("info", 20)

    viewer.handle_support_command("set grid 8 8")
    viewer.handle_support_command("show terrain")
    viewer.handle_support_command("show grid")
    viewer.handle_support_command("show contours")
    viewer.handle_support_command("hide tin")
    viewer.handle_support_command("contour source grid")
    viewer.handle_support_command("contour interval 50")
    viewer._resize_to(columns, 26)
    viewer.state.status_message = viewer._text(
        "viewer.results.ready",
        "Terrain, grid and contours visible",
        "地形、格网与等高线已显示",
    )

    model_viewer = viewer_text()
    model_support = support_text("layers", 26)
    contour_count = len(viewer.contour_polylines())

    return {
        "columns": columns,
        "query_viewer": query_viewer,
        "query_support": query_support,
        "model_viewer": model_viewer,
        "model_support": model_support,
        "points": len(viewer.project_state.points),
        "grid_x": viewer.project_state.grid.x_divisions,
        "grid_y": viewer.project_state.grid.y_divisions,
        "tin_vertices": len(viewer.project_state.tin.vertices),
        "tin_triangles": len(viewer.project_state.tin.triangles),
        "contours": contour_count,
    }


def _ansi_terminal_cells(
    text: str,
    *,
    columns: int,
    rows: int,
) -> list[tuple[int, int, str, int, str | None, str | None]]:
    """Convert ANSI terminal text into positioned printable cells."""
    cells: list[tuple[int, int, str, int, str | None, str | None]] = []
    row = 0
    column = 0
    foreground: str | None = None
    background: str | None = None
    index = 0

    while index < len(text) and row < rows:
        match = re.match(r"\x1b\[([0-9;]*)m", text[index:])
        if match:
            parameters = [
                int(value) if value else 0
                for value in match.group(1).split(";")
            ]
            parameter_index = 0
            while parameter_index < len(parameters):
                code = parameters[parameter_index]
                if code == 0:
                    foreground = None
                    background = None
                elif code == 39:
                    foreground = None
                elif code == 49:
                    background = None
                elif (
                    code in (38, 48)
                    and parameter_index + 4 < len(parameters)
                    and parameters[parameter_index + 1] == 2
                ):
                    red, green, blue = parameters[parameter_index + 2 : parameter_index + 5]
                    colour = f"#{red:02X}{green:02X}{blue:02X}"
                    if code == 38:
                        foreground = colour
                    else:
                        background = colour
                    parameter_index += 4
                parameter_index += 1
            index += match.end()
            continue

        character = text[index]
        index += 1
        if character == "\n":
            row += 1
            column = 0
            continue
        if character in ("\r", "\t") or unicodedata.combining(character):
            continue
        cell_width = (
            2 if unicodedata.east_asian_width(character) in ("F", "W") else 1
        )
        if column + cell_width <= columns:
            cells.append(
                (row, column, character, cell_width, foreground, background)
            )
        column += cell_width

    return cells


def _terminal_frame_flowable(
    text: str,
    *,
    columns: int,
    rows: int,
    width: float,
    fonts: dict[str, str],
):
    """Return a crisp vector rendering of one terminal frame."""
    from reportlab.lib import colors
    from reportlab.platypus import Flowable

    padding = 4.0
    cell_width = (width - 2 * padding) / columns
    line_height = 7.0
    height = rows * line_height + 2 * padding
    cells = _ansi_terminal_cells(text, columns=columns, rows=rows)

    class TerminalFrame(Flowable):
        def __init__(self) -> None:
            super().__init__()
            self.width = width
            self.height = height

        def wrap(self, available_width, available_height):
            return self.width, self.height

        def draw(self) -> None:
            canvas = self.canv
            canvas.saveState()
            canvas.setFillColor(colors.HexColor("#0B1020"))
            canvas.setStrokeColor(colors.HexColor("#475467"))
            canvas.setLineWidth(0.5)
            canvas.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=1)

            for row, column, character, character_cells, foreground, background in cells:
                x = padding + column * cell_width
                y = self.height - padding - (row + 1) * line_height
                if background:
                    canvas.setFillColor(colors.HexColor(background))
                    canvas.rect(
                        x,
                        y,
                        character_cells * cell_width + 0.15,
                        line_height + 0.15,
                        fill=1,
                        stroke=0,
                    )
                if character == " ":
                    continue
                is_wide = unicodedata.east_asian_width(character) in ("F", "W")
                canvas.setFont(fonts["code"] if is_wide else fonts["terminal"], 6.0)
                canvas.setFillColor(colors.HexColor(foreground or "#E6EDF3"))
                canvas.drawString(x, y + 0.82, character)

            canvas.restoreState()

    return TerminalFrame()


def _result_flowables(
    project_root: Path,
    styles: dict[str, object],
    fonts: dict[str, str],
) -> list[object]:
    """Build one compact page of representative running results."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    captures = _capture_result_frames(project_root)
    columns = int(captures["columns"])
    frame_width = 84.5 * mm

    def frame(key: str, rows: int):
        return _terminal_frame_flowable(
            str(captures[key]),
            columns=columns,
            rows=rows,
            width=frame_width,
            fonts=fonts,
        )

    def pair(left, right, left_caption: str, right_caption: str) -> Table:
        table = Table(
            [
                [left, "", right],
                [
                    Paragraph(escape(left_caption), styles["caption"]),
                    "",
                    Paragraph(escape(right_caption), styles["caption"]),
                ],
            ],
            colWidths=(85 * mm, 4 * mm, 85 * mm),
            hAlign="CENTER",
        )
        table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    summary = (
        f"默认数据集读取 {captures['points']} 个采样点；第二组结果将规则格网调整为 "
        f"{captures['grid_x']}×{captures['grid_y']}，TIN 含 {captures['tin_vertices']} 个顶点和 "
        f"{captures['tin_triangles']} 个三角形，并以 50 为等高距得到 "
        f"{captures['contours']} 条格网等高线。"
    )
    display_note = (
        "本页运行结果为适应 A4 版面已缩小；如需查看更清晰、更详细的输出，应直接运行程序。"
        "建议将查看器终端与支持/控制面板终端并排放置，以便同时观察和操作；适当减小查看器"
        "终端字号可以增加有效字符网格，使 Braille、TIN 与等高线渲染更加细密、清晰。Windows "
        "默认控制台在持续刷新时偶尔可能出现轻微画面撕裂。追求最流畅体验时，可在 macOS 或 "
        "Linux 的 POSIX 环境中运行对应版本，并使用 Kitty 或 Ghostty 等终端模拟器；这是可选的"
        "显示体验优化，Windows 可执行程序仍是本次提交的主要版本。"
    )
    return [
        Paragraph("运行结果", styles["title"]),
        Paragraph(
            "以下界面由默认数据集、真实 GIS 模型和终端渲染器直接生成。为控制纸质版篇幅，仅保留两组最能说明作业功能的结果：要素查询，以及地形、格网和等高线的联合显示。",
            styles["body"],
        ),
        pair(
            frame("query_viewer", 20),
            frame("query_support", 20),
            "图 1（左）：采样点与 TIN 查看器输出",
            "图 1（右）：支持面板显示实际要素查询结果",
        ),
        Spacer(1, 3.5 * mm),
        pair(
            frame("model_viewer", 26),
            frame("model_support", 26),
            "图 2（左）：地形着色、8×8 格网与格网等高线",
            "图 2（右）：图层、等高线来源、色带与不透明度控制",
        ),
        Spacer(1, 3 * mm),
        Table(
            [[Paragraph("运行摘要", styles["table"]), Paragraph(summary, styles["table"])]],
            colWidths=(22 * mm, 152 * mm),
            hAlign="CENTER",
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FFF4E8")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#D0D5DD")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
        Spacer(1, 2 * mm),
        Table(
            [
                [
                    Paragraph("显示质量说明", styles["table"]),
                    Paragraph(display_note, styles["table"]),
                ]
            ],
            colWidths=(22 * mm, 152 * mm),
            hAlign="CENTER",
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FFF4E8")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#D0D5DD")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
    ]


def build_report(
    project_root: Path = PROJECT_ROOT,
    *,
    output: Path | None = None,
) -> Path:
    """Build and return the final Chinese PDF report."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
    )

    project_root = Path(project_root).resolve()
    destination = (
        Path(output) if output is not None else default_output_path(project_root)
    )
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    translations = load_translations()
    missing = untranslated_entries(project_root, translations)
    if any(missing.values()):
        details = "\n".join(
            f"{category}:\n" + "\n".join(f"  - {entry}" for entry in entries)
            for category, entries in missing.items()
            if entries
        )
        raise RuntimeError(
            "Chinese code translation resource is incomplete:\n" + details
        )

    fonts = _register_fonts()
    styles = _paragraph_styles(fonts)
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=f"Primelock GIS 中文源代码报告 v{project_version(project_root)}",
        author="Primelock GIS 课程作业提交",
        subject="高级 GIS 课程作业中文源代码打印稿",
    )
    story: list[object] = []
    introduction = (project_root / INTRODUCTION_PATH.name).read_text(encoding="utf-8")
    story.extend(_markdown_flowables(introduction, styles))
    story.append(PageBreak())

    story.extend(_result_flowables(project_root, styles, fonts))
    story.append(PageBreak())

    story.append(Paragraph("源代码文件目录", styles["title"]))
    sections = _load_print_profile()
    for section in sections:
        title, description = CHINESE_SECTION_TEXT[section.title]
        story.append(Paragraph(escape(title), styles["h1"]))
        story.append(Paragraph(escape(description), styles["body"]))
        for relative_path in section.paths:
            story.append(Paragraph(escape(relative_path), styles["small"]))
    story.append(PageBreak())

    printable_files = [
        (section, relative_path)
        for section in sections
        for relative_path in section.paths
    ]
    for file_index, (section, relative_path) in enumerate(printable_files):
        section_title, section_description = CHINESE_SECTION_TEXT[section.title]
        source_path = project_root / relative_path
        source_text = source_path.read_text(encoding="utf-8")
        translated_lines = translated_source_lines(source_text, translations)
        code_text = formatted_code_text(translated_lines)
        header = KeepTogether(
            [
                Paragraph(escape(section_title), styles["h1"]),
                Paragraph(f"仓库路径：{escape(relative_path)}", styles["h2"]),
                Paragraph(escape(section_description), styles["small"]),
                Paragraph(
                    f"原始行数：{len(source_text.splitlines())}；"
                    "打印稿中的注释和文档字符串已翻译为中文。",
                    styles["small"],
                ),
                Spacer(1, 5),
            ]
        )
        story.extend([header, Preformatted(code_text, styles["code"])])
        if file_index < len(printable_files) - 1:
            story.append(PageBreak())

    document.build(
        story,
        onFirstPage=lambda canvas, doc: _page_decoration(canvas, doc, fonts),
        onLaterPages=lambda canvas, doc: _page_decoration(canvas, doc, fonts),
    )
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成中文课程作业源代码打印 PDF。")
    parser.add_argument("--output", type=Path, help="PDF 输出路径")
    parser.add_argument(
        "--check-translations",
        action="store_true",
        help="只检查打印范围内的注释和文档字符串翻译是否完整",
    )
    return parser


def _configure_unicode_stdio() -> None:
    """Keep Chinese diagnostics readable in Windows consoles and pipes."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_unicode_stdio()
    arguments = build_parser().parse_args(argv)
    if arguments.check_translations:
        missing = untranslated_entries()
        if any(missing.values()):
            print(json.dumps(missing, ensure_ascii=False, indent=2))
            return 1
        print("中文注释翻译资源完整。")
        return 0
    output = build_report(output=arguments.output)
    print(f"已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
