"""A self-contained, bilingual HTML report; no external requests or file links."""

import base64
import hashlib
from html import escape
from importlib.resources import files

from . import __version__
from .core import STATUSES

WORDS = {
    "en": {
        "html_lang": "en", "title": "Folder receipt", "print": "Print / PDF",
        "compare": "Version comparison", "verify": "Delivery verification",
        "same": "Folders match", "different": "Changes to review", "failed": "Delivery does not match",
        "before": "Expected" , "after": "Received", "old": "Before", "new": "After",
        "files": "files", "search": "Search file paths", "placeholder": "Find a file or folder…",
        "all": "All", "changes": "Changes", "shown": "shown", "of": "of",
        "none": "No files match this filter.", "bytes": "bytes", "size": "Size", "path": "Path",
        "details": "Show file details", "missing": "Not present",
        "modified": "Modified", "moved": "Same-content move", "added": "Added", "removed": "Removed", "unchanged": "Unchanged",
        "limit": "Checks relative paths and file bytes. Does not check empty folders, metadata, quality or sender identity.",
        "move_note": "Same-content moves pair only one unmatched old path with one unmatched new path. Matching bytes do not prove a rename occurred; any path change fails delivery verification.",
        "ambiguous": "Repeated content has multiple possible path matches. Those files remain added / removed.",
        "created": "Report time (UTC)", "empty": "Both folders contain no regular files.",
    },
    "zh": {
        "html_lang": "zh-CN", "title": "文件夹交付核对", "print": "打印 / PDF",
        "compare": "版本比较", "verify": "接收核验",
        "same": "文件一致", "different": "有变化，待核对", "failed": "交付不一致",
        "before": "预期交付", "after": "实际收到", "old": "上一版", "new": "当前版",
        "files": "个文件", "search": "搜索文件路径", "placeholder": "查找文件或文件夹…",
        "all": "全部", "changes": "仅变化", "shown": "显示", "of": "/",
        "none": "没有符合筛选的文件。", "bytes": "字节", "size": "大小", "path": "路径",
        "details": "展开文件明细", "missing": "无此文件",
        "modified": "内容修改", "moved": "同内容移位", "added": "新增", "removed": "移除", "unchanged": "相同",
        "limit": "核对相对路径和文件字节，不检查空目录、元数据、作品质量或发送者身份。",
        "move_note": "同内容移位只配对未匹配路径中唯一的一对相同字节文件，不能证明实际发生过改名；接收核验中，路径变化仍算不一致。",
        "ambiguous": "存在重复内容的多种路径配对，相关文件保留为新增或移除。",
        "created": "报告时间（UTC）", "empty": "两个目录均无普通文件。",
    },
}


def integrity(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def size_text(size: int) -> str:
    if size < 1024:
        return f"{size:,} B"
    units = ("KiB", "MiB", "GiB", "TiB")
    number = float(size)
    for unit in units:
        number /= 1024
        if number < 1024 or unit == units[-1]:
            return f"{number:,.1f} {unit}"
    raise AssertionError("unreachable")


def render(result: dict, lang: str = "en") -> str:
    w = WORDS[lang]
    css = files("packreceipt").joinpath("report.css").read_text(encoding="utf-8")
    js = files("packreceipt").joinpath("report.js").read_text(encoding="utf-8")
    mode = result["mode"]
    labels = (w["before"], w["after"]) if mode == "verify" else (w["old"], w["new"])
    heading = w["same"] if result["matches"] else w["failed"] if mode == "verify" else w["different"]
    counts = result["counts"]
    badge_class = "match" if result["matches"] else "review"
    total = len(result["files"])
    changes = total - counts["unchanged"]
    stats = "".join(
        f'<div class="stat {kind}"><span class="stat-value">{counts[kind]}</span><span>{w[kind]}</span></div>'
        for kind in STATUSES
    )
    buttons = [f'<button class="filter active" type="button" data-filter="changes" aria-pressed="true">{w["changes"]} <span>{changes}</span></button>']
    buttons.append(f'<button class="filter" type="button" data-filter="all" aria-pressed="false">{w["all"]} <span>{total}</span></button>')
    for kind in STATUSES:
        if counts[kind]:
            buttons.append(f'<button class="filter" type="button" data-filter="{kind}" aria-pressed="false">{w[kind]} <span>{counts[kind]}</span></button>')
    rows = []
    for row in result["files"]:
        kind = row["status"]
        before, after = row["before"], row["after"]
        path = (after or before)["path"]
        path_html = escape(path)
        old_path = f'<span class="old-path">{escape(before["path"])}</span>' if kind == "moved" else ""
        delta = (f'{size_text(before["size"])} <span aria-hidden="true">→</span> {size_text(after["size"])}'
                 if kind == "modified" else size_text((after or before)["size"]))
        detail = []
        for index, item in enumerate((before, after)):
            values = (f'<dl><dt>{w["path"]}</dt><dd>{escape(item["path"])}</dd>'
                      f'<dt>{w["size"]}</dt><dd>{item["size"]:,} {w["bytes"]}</dd>'
                      f'<dt>SHA-256</dt><dd class="digest">{item["sha256"]}</dd></dl>') if item else f'<p>{w["missing"]}</p>'
            detail.append(f'<section class="file-side"><h3>{labels[index]}</h3>{values}</section>')
        search = " ".join(item["path"] for item in (before, after) if item).casefold()
        # File names are untrusted data: escape text and attributes, never interpolate into JS.
        rows.append(f'''<details class="file-row {kind}" data-kind="{kind}" data-search="{escape(search, quote=True)}">
<summary><span class="status">{w[kind]}</span><span class="file-path">{old_path}<span>{path_html}</span></span><span class="file-size">{delta}</span><span class="chevron" aria-hidden="true">+</span></summary>
<div class="file-details">{"".join(detail)}</div></details>''')
    sides = []
    for index, key in enumerate(("before", "after")):
        part = result[key]
        sides.append(f'<div class="folder"><span class="folder-label">{labels[index]}</span><strong>{escape(part["label"])}</strong><span>{part["file_count"]:,} {w["files"]} <span aria-hidden="true">·</span> {size_text(part["bytes"])}</span></div>')
    notes = [w["limit"]]
    if counts["moved"]:
        notes.append(w["move_note"])
    if result["ambiguous_content_groups"]:
        notes.append(w["ambiguous"])
    if not total:
        notes.append(w["empty"])
    # Exact CSP hashes allow only the shipped inline code and styling.
    policy = f"default-src 'none'; style-src 'sha256-{integrity(css)}'; script-src 'sha256-{integrity(js)}'; base-uri 'none'; form-action 'none'"
    return f'''<!doctype html>
<html lang="{w["html_lang"]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(policy, quote=True)}">
<title>PackReceipt · {w["title"]}</title><style>{css}</style></head>
<body><header class="topbar"><a class="brand" href="#main"><span class="brand-mark" aria-hidden="true">P</span>PackReceipt</a><button id="print" type="button">{w["print"]}</button></header>
<main id="main"><section class="verdict {badge_class}"><p class="mode">{w[mode]}</p><h1>{heading}</h1><div class="folder-pair">{"".join(sides)}</div></section>
<section class="stats" aria-label="{w[mode]}">{stats}</section>
<section class="file-list"><div class="toolbar"><label class="search"><span>{w["search"]}</span><input id="search" type="search" placeholder="{w["placeholder"]}" autocomplete="off"></label><p id="visible-count" aria-live="polite" data-prefix="{w["shown"]}" data-of="{w["of"]}" data-total="{total}"></p></div>
<nav class="filters" aria-label="{w["title"]}">{"".join(buttons)}</nav>
<noscript><p>JavaScript is disabled. All files are shown; search and filters need JavaScript.</p></noscript>
<div id="rows">{"".join(rows)}</div><p id="empty" hidden>{w["none"]}</p></section>
<footer><div class="notes">{"".join(f"<p>{escape(note)}</p>" for note in notes)}</div><p class="stamp">PackReceipt {__version__} <span aria-hidden="true">·</span> {w["created"]} {escape(result["created_at"])}</p></footer>
</main><script>{js}</script></body></html>'''
