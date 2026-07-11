"""Build a deterministic, self-contained HTML source listing for printing."""

from __future__ import annotations

import argparse
import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_GIS = "gis"
FRONT_MATTER_PATH = "COURSEWORK_SOURCE_GUIDE.md"

EXCLUDED_PARTS = frozenset(
    {
        ".agents",
        ".git",
        ".idea",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__MACOSX",
        "__pycache__",
        "build",
        "dist",
        "release",
    }
)
EXCLUDED_SUFFIXES = frozenset(
    {
        ".exe",
        ".key",
        ".log",
        ".pem",
        ".pyc",
        ".pyo",
        ".whl",
        ".zip",
    }
)


@dataclass(frozen=True)
class SourceSection:
    """One ordered group of files in a printed-source profile."""

    title: str
    description: str
    paths: tuple[str, ...]


GIS_SECTIONS = (
    SourceSection(
        "Geometry and data loading",
        "Shared geometry operations and coursework CSV ingestion.",
        (
            "src/primelock_gis/core/load_data.py",
            "src/primelock_gis/core/geometry.py",
        ),
    ),
    SourceSection(
        "GIS data models",
        "Point, regular-grid, TIN, contour, and topology structures.",
        (
            "src/primelock_gis/core/models/vector.py",
            "src/primelock_gis/core/models/grid.py",
            "src/primelock_gis/core/models/tin.py",
            "src/primelock_gis/core/models/contour.py",
        ),
    ),
    SourceSection(
        "GIS algorithms",
        "Interpolation, grid, TIN, contour, and topology implementation.",
        (
            "src/primelock_gis/core/algorithms/interpolation.py",
            "src/primelock_gis/core/algorithms/grid.py",
            "src/primelock_gis/core/algorithms/tin.py",
            "src/primelock_gis/core/algorithms/contour.py",
            "src/primelock_gis/core/algorithms/topology.py",
        ),
    ),
)


PRINT_CSS = """
@page {
  size: A4 portrait;
  margin: 14mm 12mm 15mm 16mm;
}

:root {
  color-scheme: light;
  font-family: Inter, "Segoe UI", "Microsoft YaHei UI", Arial, sans-serif;
  color: #18212f;
  background: #ffffff;
}

body {
  margin: 0 auto;
  max-width: 1120px;
  line-height: 1.45;
}

code,
pre,
.source-code {
  font-family: "Cascadia Mono", "Cascadia Code", "Sarasa Mono SC",
    "Noto Sans Mono CJK SC", "Noto Sans Mono", "Microsoft YaHei UI",
    Consolas, "DejaVu Sans Mono", monospace;
}

.cover {
  min-height: 88vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 8px solid #155e75;
  padding: 0 10%;
  break-after: page;
  page-break-after: always;
}

.cover h1 {
  color: #0f4c5c;
  font-size: 34pt;
  margin: 0 0 8mm;
}

.cover .subtitle {
  font-size: 17pt;
  margin: 0 0 14mm;
}

.cover dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 2mm 7mm;
}

.cover dt,
.file-meta,
.manifest-count {
  color: #52606d;
}

.front-matter,
.manifest {
  break-after: page;
  page-break-after: always;
}

.front-matter-text {
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 5mm;
  background: #f8fafc;
  font-size: 9pt;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.manifest ol {
  padding-left: 8mm;
}

.manifest li {
  margin: 1.2mm 0;
}

.manifest a {
  color: #0f4c5c;
  text-decoration: none;
}

.source-file {
  break-before: page;
  page-break-before: always;
}

.source-file h2 {
  color: #0f4c5c;
  font-size: 14pt;
  margin: 0 0 1.5mm;
  overflow-wrap: anywhere;
}

.file-meta {
  font-size: 8.5pt;
  margin: 0 0 4mm;
}

.source-code {
  border-collapse: collapse;
  table-layout: fixed;
  width: 100%;
  font-size: 7.5pt;
  line-height: 1.25;
}

.source-code tr {
  break-inside: avoid;
  page-break-inside: avoid;
}

.line-number {
  box-sizing: border-box;
  width: 12mm;
  padding: 0 3mm 0 0;
  color: #64748b;
  text-align: right;
  vertical-align: top;
  user-select: none;
  border-right: 1px solid #dbe3ea;
}

.line-text {
  padding: 0 0 0 3mm;
  vertical-align: top;
  white-space: pre;
  overflow: visible;
}

@media print {
  body {
    max-width: none;
  }

  a {
    color: inherit;
  }
}
""".strip()


def profile_sections(profile: str = PROFILE_GIS) -> tuple[SourceSection, ...]:
    """Return the ordered source sections for a supported profile."""
    if profile != PROFILE_GIS:
        raise ValueError(f"Unknown printed-source profile: {profile}")
    return GIS_SECTIONS


def ordered_manifest(profile: str = PROFILE_GIS) -> tuple[str, ...]:
    """Return the deterministic flattened path manifest for a profile."""
    paths = tuple(
        path for section in profile_sections(profile) for path in section.paths
    )
    if len(paths) != len(set(paths)):
        raise RuntimeError("Printed-source profile contains duplicate paths")
    for path in paths:
        validate_manifest_path(path)
    return paths


def validate_manifest_path(path_text: str) -> None:
    """Reject unsafe, generated, cached, or archived manifest paths."""
    path = PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe printed-source path: {path_text}")
    if set(path.parts) & EXCLUDED_PARTS:
        raise ValueError(f"Generated/cache path is not printable: {path_text}")
    if any(part.endswith(".egg-info") for part in path.parts):
        raise ValueError(f"Generated package metadata is not printable: {path_text}")
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        raise ValueError(f"Archive/binary path is not printable: {path_text}")


def project_version(project_root: Path = PROJECT_ROOT) -> str:
    """Read the canonical project version from pyproject.toml."""
    metadata_path = Path(project_root) / "pyproject.toml"
    with metadata_path.open("rb") as file:
        metadata = tomllib.load(file)
    try:
        version = metadata["project"]["version"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Missing project.version in {metadata_path}") from error
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Invalid project.version in {metadata_path}")
    return version.strip()


def default_output_path(
    project_root: Path = PROJECT_ROOT,
    *,
    version: str | None = None,
) -> Path:
    """Return the versioned default HTML path under release/."""
    version = version or project_version(project_root)
    safe_version = re.sub(r"[^A-Za-z0-9._+-]", "_", version)
    return (
        Path(project_root)
        / "release"
        / f"PrimelockGIS-Printed-Source-v{safe_version}.html"
    )


def _read_required_text(project_root: Path, relative_path: str) -> str:
    path = project_root / Path(relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"Required printed-source file is missing: {path}")
    return path.read_text(encoding="utf-8")


def _render_source_lines(text: str) -> str:
    lines = text.splitlines() or [""]
    rendered = []
    for line_number, line in enumerate(lines, start=1):
        escaped_line = escape(line, quote=True) or "&#8203;"
        rendered.append(
            "<tr>"
            f'<td class="line-number">{line_number}</td>'
            f'<td class="line-text"><code>{escaped_line}</code></td>'
            "</tr>"
        )
    return "\n".join(rendered)


def render_html(
    project_root: Path = PROJECT_ROOT,
    *,
    profile: str = PROFILE_GIS,
) -> str:
    """Render a complete deterministic printed-source HTML document."""
    project_root = Path(project_root).resolve()
    version = project_version(project_root)
    sections = profile_sections(profile)
    manifest = ordered_manifest(profile)
    front_matter = _read_required_text(project_root, FRONT_MATTER_PATH)

    manifest_items = []
    source_sections = []
    file_index = 0
    for section in sections:
        section_items = []
        for relative_path in section.paths:
            file_index += 1
            file_id = f"source-{file_index:03d}"
            escaped_path = escape(relative_path, quote=True)
            section_items.append(
                f'<li><a href="#{file_id}"><code>{escaped_path}</code></a></li>'
            )
            source_text = _read_required_text(project_root, relative_path)
            line_count = len(source_text.splitlines()) or 1
            source_sections.append(
                f'<section class="source-file" id="{file_id}">\n'
                f"<h2>{escaped_path}</h2>\n"
                f'<p class="file-meta">{escape(section.title)} &middot; '
                f"{line_count} lines</p>\n"
                '<table class="source-code" aria-label="Source code with line numbers">\n'
                "<tbody>\n"
                f"{_render_source_lines(source_text)}\n"
                "</tbody>\n"
                "</table>\n"
                "</section>"
            )
        manifest_items.append(
            f"<h3>{escape(section.title)}</h3>\n"
            f"<p>{escape(section.description)}</p>\n"
            "<ol>\n" + "\n".join(section_items) + "\n</ol>"
        )

    title = f"Primelock GIS Printed Source v{version}"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>\n{PRINT_CSS}\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<header class="cover">\n'
        "<h1>Primelock GIS</h1>\n"
        '<p class="subtitle">Advanced GIS Coursework &mdash; Curated Printed Source</p>\n'
        "<dl>\n"
        f"<dt>Version</dt><dd>{escape(version)}</dd>\n"
        f"<dt>Profile</dt><dd>{escape(profile)}</dd>\n"
        f"<dt>Files</dt><dd>{len(manifest)}</dd>\n"
        "<dt>Ordering</dt><dd>GIS models and algorithms first</dd>\n"
        "</dl>\n"
        "</header>\n"
        '<section class="front-matter">\n'
        "<h2>Coursework source guide</h2>\n"
        f'<pre class="front-matter-text">{escape(front_matter, quote=True)}</pre>\n'
        "</section>\n"
        '<nav class="manifest" aria-label="Printed file manifest">\n'
        "<h2>Ordered file manifest</h2>\n"
        f'<p class="manifest-count">{len(manifest)} curated files</p>\n'
        + "\n".join(manifest_items)
        + "\n</nav>\n"
        + "\n".join(source_sections)
        + "\n</body>\n</html>\n"
    )


def build_printed_source(
    project_root: Path = PROJECT_ROOT,
    *,
    output: Path | None = None,
    profile: str = PROFILE_GIS,
) -> Path:
    """Write the standalone HTML source listing and return its path."""
    project_root = Path(project_root).resolve()
    destination = (
        Path(output) if output is not None else default_output_path(project_root)
    )
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_html(project_root, profile=profile),
        encoding="utf-8",
        newline="\n",
    )
    return destination


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Build a deterministic HTML source listing for printing."
    )
    parser.add_argument(
        "--profile",
        choices=(PROFILE_GIS,),
        default=PROFILE_GIS,
        help="printed-source selection and ordering profile",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="destination HTML path (default: release/versioned filename)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the printed-source builder."""
    arguments = build_parser().parse_args(argv)
    output = build_printed_source(output=arguments.output, profile=arguments.profile)
    print(f"Built {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
