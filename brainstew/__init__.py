"""brainstew: a minimal LLM Wiki starter built for AgenC."""

from brainstew.frontmatter import FrontmatterError, parse_frontmatter
from brainstew.pages import Page, discover_pages

__all__ = [
    "FrontmatterError",
    "Page",
    "discover_pages",
    "parse_frontmatter",
]
