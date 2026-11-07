"""The documents that must say the same thing (CLAUDE.md: each change goes to What's new and the project's Markdown):
  What's new (frontend/src/screens/WhatsNew.tsx)  ==  docs/CHANGELOG.md, entry for entry, word for word
  the API guide (frontend/src/screens/ApiGuide.tsx)  ==  docs/API.md, and both list every API route and MCP tool."""
import json
import re
from pathlib import Path

import api.main as main
from api import mcp

ROOT = Path(__file__).resolve().parents[1]
STRING = r'"((?:[^"\\]|\\.)*)"'


def test_every_whats_new_entry_is_in_the_changelog_word_for_word():
    page = (ROOT / "frontend/src/screens/WhatsNew.tsx").read_text()
    changelog = (ROOT / "docs/CHANGELOG.md").read_text()
    entries = [tuple(json.loads(f'"{g}"') for g in m.groups()) for m in re.finditer(r"\{ title: " + STRING + r",\s*body: " + STRING, page)]
    assert len(entries) > 30
    missing = [title for title, body in entries if f"### {title}\n\n{body}" not in changelog]
    assert not missing, f"Add these to docs/CHANGELOG.md as on the What's new page: {missing}"


def test_the_api_guide_page_and_docs_api_list_every_route_and_tool_alike():
    guide = (ROOT / "docs/API.md").read_text()
    page = (ROOT / "frontend/src/screens/ApiGuide.tsx").read_text()
    in_guide = set(re.findall(r"\| `((?:GET|POST|DELETE) /api/v1/[^`]+)` \|", guide))
    in_page = set(re.findall(r'\["((?:GET|POST|DELETE) /api/v1/[^"]+)"', page))
    assert in_guide == in_page, f"docs/API.md and ApiGuide.tsx differ: {in_guide ^ in_page}"
    served = {f"{method.upper()} {path}" for path, ops in main.app.openapi()["paths"].items()   # every router's routes
              if path.startswith("/api/v1/") and "/admin/" not in path for method in ops}
    assert served == in_guide, f"Routes not documented: {served - in_guide}; documented but gone: {in_guide - served}"
    tools = {t["name"] for t in mcp.TOOLS}
    page_tools = page.split("const TOOLS")[1].split("const Table")[0]
    assert tools == set(re.findall(r"\| `(\w+)` \|", guide)) == set(re.findall(r'\["(\w+)", "', page_tools))


def test_the_status_board_keeps_its_sections():
    """status/README.md is the hand-over between agents: its standard and its five sections stay in place."""
    board = (ROOT / "status/README.md").read_text()
    for section in ("## The standard", "## In progress", "## Waiting for deploy", "## Pending", "## Stuck", "## Done earlier"):
        assert section in board, f"status/README.md lost its {section!r} section"
