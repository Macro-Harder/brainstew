"""llm-wiki-agenc: a minimal LLM Wiki starter driven by coding agents."""

from llmwiki.frontmatter import FrontmatterError, parse_frontmatter
from llmwiki.pages import Page, discover_pages

__all__ = [
    "FrontmatterError",
    "Page",
    "discover_pages",
    "parse_frontmatter",
]
