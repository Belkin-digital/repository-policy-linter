"""Local Markdown navigation, using an existing CommonMark parser, never rendering HTML."""

import posixpath
from collections import deque
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from .files import safe_path
from .model import PolicyError
from .rules import applies, diagnostic


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in {"pre", "code", "script", "style"}:
            self.hidden.append(tag)
        if tag == "a" and not self.hidden:
            self.links.extend(value for key, value in attrs if key == "href" and value)

    def handle_endtag(self, tag):
        if tag in self.hidden:
            index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
            del self.hidden[index:]

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def markdown_parser():
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise PolicyError(
            "markdown-reachable requires the optional repository-policy-linter[markdown] "
            "dependency; install the approved distribution with that extra"
        ) from exc
    return MarkdownIt("commonmark", {"html": True}).enable("table")


def link_destinations(text, parser):
    # YAML metadata is not document navigation. Preserve line positions in the body.
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        # An unclosed metadata header must not create navigation edges either.
        text = "\n" * (end + 1) + "".join(lines[end + 1 :]) if end is not None else ""
    html = HTMLLinks()
    links = []
    for token in parser.parse(text):
        if token.type == "html_block":
            html.feed(token.content)
        elif token.type == "inline":
            for child in token.children or []:
                if child.type == "html_inline":
                    html.feed(child.content)
                elif child.type == "link_open" and not html.hidden:
                    links.append(child.attrGet("href"))
                # Code and image-alt children are deliberately not traversed.
    html.close()
    return links + html.links


def local_target(source, destination, nodes):
    if not destination or "\\" in destination or any(ord(c) < 32 for c in destination):
        return None
    try:
        url = urlsplit(destination)
        if url.scheme or url.netloc or not url.path:
            return None
        path = unquote(url.path, errors="strict")
    except (ValueError, UnicodeError):
        return None
    if "\\" in path or any(ord(c) < 32 for c in path):
        return None
    joined = path.lstrip("/") if path.startswith("/") else str(PurePosixPath(source).parent / path)
    name = posixpath.normpath(joined)
    if name == ".." or name.startswith("../") or name.startswith("/"):
        return None
    if name in nodes:
        return name
    # A directory link may land on its README, never on an implicit directory listing.
    index = posixpath.join(name, "README.md")
    return index if index in nodes else None


def check_reachability(root, rule, names, limit, excepted):
    parser = markdown_parser()
    nodes = {name for name in names if name.lower().endswith((".md", ".markdown"))}
    diagnostics, graph = [], {}
    for name in sorted(nodes):
        with safe_path(root, name).open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise PolicyError(f"{name}: graph input exceeds max_file_bytes")
        try:
            if b"\0" in raw:
                raise UnicodeError()
            destinations = link_destinations(raw.decode("utf-8"), parser)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise PolicyError(f"{name}: cannot parse UTF-8 Markdown graph input") from exc
        graph[name] = {
            target
            for destination in destinations
            if (target := local_target(name, destination, nodes)) is not None
        }
    for name in rule["roots"]:
        if name not in nodes:
            diagnostics.append(
                diagnostic(rule, name, "Markdown graph root is missing, excluded or unsafe")
            )
    reached = set()
    queue = deque(sorted(set(rule["roots"]) & nodes))
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(sorted(graph[current] - reached))
    unreachable = [
        name for name in sorted(nodes - reached) if applies(name, rule) and not excepted(rule, name)
    ]
    for name in unreachable:
        diagnostics.append(
            diagnostic(rule, name, "Markdown file is unreachable from configured roots")
        )
    summary = {
        "rule": rule["id"],
        "roots": rule["roots"],
        "files_checked": sorted(nodes),
        "reachable": sorted(reached),
        "unreachable": unreachable,
    }
    return diagnostics, summary
