"""Build a static report library without copying ignored or private files."""

import argparse
from datetime import date
import html
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import markdown
from markdown.extensions.toc import slugify_unicode


PROJECT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".md", ".html", ".json", ".txt", ".pdf", ".png", ".jpg", ".jpeg",
              ".webp", ".svg", ".gif", ".css", ".js", ".csv", ""}
PRIVATE = {"reports/portfolio-latest.md"}
ATTR = re.compile(r"""(\b(?:href|src)\s*=\s*)(["'])(.*?)\2""", re.IGNORECASE)
TAG = re.compile(r"<[A-Za-z][^>]*>")


def source_files(source):
    result = subprocess.run(
        ["git", "-C", str(source), "ls-files", "--cached", "--others",
         "--exclude-standard", "-z", "--", "reports"],
        check=True, capture_output=True, encoding="utf-8",
    )
    names = sorted(set(filter(None, result.stdout.split("\0"))))
    ignored = subprocess.run(
        ["git", "-C", str(source), "check-ignore", "--no-index", "-z", "--stdin"],
        input="\0".join(names) + "\0", capture_output=True, encoding="utf-8",
    )
    if ignored.returncode not in (0, 1):
        raise RuntimeError(ignored.stderr)
    excluded = set(ignored.stdout.split("\0")) | PRIVATE
    files = []
    for name in names:
        path = source / name
        if name in excluded or path.suffix.lower() not in EXTENSIONS:
            continue
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise ValueError(f"Refusing linked file: {name}")
        files.append(PurePosixPath(name))
    if not files:
        raise ValueError("No publishable reports found")
    return files


def page_path(path):
    return PurePosixPath(str(path) + ".html") if path.suffix.lower() == ".md" else path


def relative_url(target, current):
    return quote(posixpath.relpath(str(target), str(current.parent)), safe="/")


def rewrite_links(body, current, destinations):
    def replace_attr(match):
        value = html.unescape(match[3])
        url = urlsplit(value)
        if url.scheme or url.netloc or not url.path:
            return match[0]
        path = unquote(url.path).replace("\\", "/")
        resolved = posixpath.normpath(
            path.lstrip("/") if path.startswith("/")
            else posixpath.join(str(current.parent), path)
        )
        target = destinations.get(resolved)
        if target is None:
            return match[0]
        rewritten = urlunsplit(("", "", relative_url(target, current), url.query, url.fragment))
        return match[1] + match[2] + html.escape(rewritten, quote=True) + match[2]

    return TAG.sub(lambda match: ATTR.sub(replace_attr, match[0]), body)


def report_title(text, path):
    pattern = r"<title[^>]*>(.*?)</title>" if path.suffix == ".html" else r"^#\s+(.+)$"
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    title = match[1] if match else path.stem
    return html.unescape(re.sub(r"<[^>]+>|[*`]", "", title)).strip()


def report_date(path):
    dates = []
    for year, month, day in re.findall(r"(20\d{2})-?([01]\d)-?([0-3]\d)", str(path)):
        try:
            dates.append(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return max(dates, default="")


def document(title, body, current, script=False):
    home = relative_url(PurePosixPath("index.html"), current)
    css = relative_url(PurePosixPath("assets/site.css"), current)
    license_url = relative_url(PurePosixPath("LICENSE"), current)
    js = '<script src="assets/search.js" defer></script>' if script else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="AI Berkshire 研究报告，手机阅读与搜索。仅供学习，不构成投资建议。">
<title>{html.escape(title)} | AI Berkshire</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="{css}">{js}</head>
<body><header><a href="{home}">AI Berkshire · 研究报告库</a></header>
<main>{body}</main><footer>仅供学习与研究，不构成投资建议。报告中的价格并非实时行情。
<br>原始框架及研究：<a href="https://github.com/xbtlin/ai-berkshire">xbtlin/ai-berkshire</a> ·
<a href="{license_url}">MIT License</a> ·
<a href="https://github.com/sudoli/ai-berkshire-reports">GitHub</a></footer></body></html>
"""


def write(output, path, text):
    target = output / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def cards(entries, current):
    return '<ul class="cards">' + "".join(
        f'<li><a href="{relative_url(PurePosixPath(entry["destination"]), current)}">'
        f'{html.escape(entry["title"])}</a><small>'
        f'{html.escape(entry["date"] or "日期未标注")} · '
        f'{html.escape(entry["path"])}</small></li>' for entry in entries
    ) + "</ul>"


def build(source, output):
    source, output = source.resolve(), output.resolve()
    if not (source / "LICENSE").is_file():
        raise ValueError("The source repository must contain its license")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output must be separate from the source repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; build a fresh snapshot")
    files = source_files(source)
    directories = {parent for path in files for parent in path.parents if str(parent) != "."}
    destinations = {str(path): page_path(path) for path in files}
    destinations.update({str(folder): folder / "index.html" for folder in directories})
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT / "assets", output / "assets")
    shutil.copy2(source / "LICENSE", output / "LICENSE")
    write(output, PurePosixPath(".nojekyll"), "")
    entries = []
    for path in files:
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() not in {".md", ".html"}:
            shutil.copy2(source / path, target)
            continue
        text = (source / path).read_text(encoding="utf-8-sig")
        title = report_title(text, path)
        destination = page_path(path)
        if path.suffix.lower() == ".md":
            shutil.copy2(source / path, target)
            renderer = markdown.Markdown(
                extensions=["tables", "fenced_code", "toc", "sane_lists"],
                extension_configs={"toc": {"slugify": slugify_unicode}},
            )
            content = rewrite_links(renderer.convert(text), path, destinations)
            toc = f"<details><summary>阅读目录</summary>{renderer.toc}</details>" if renderer.toc_tokens else ""
            body = (
                f'<p class="meta"><a href="{quote(path.name)}">Markdown 原文</a> · '
                f'{html.escape(str(path.relative_to("reports")))}</p>{toc}'
                f'<article class="report">{content}</article>'
            )
            write(output, destination, document(title, body, destination))
        else:
            write(output, destination, rewrite_links(text, path, destinations))
        entries.append({
            "title": title, "path": str(path.relative_to("reports")),
            "date": report_date(path), "destination": str(destination),
            "url": quote(str(destination), safe="/"),
        })
    entries.sort(key=lambda entry: (entry["date"], entry["path"]), reverse=True)
    for folder in sorted(directories):
        current = folder / "index.html"
        if (output / current).exists():
            continue
        children = sorted(child for child in directories if child.parent == folder)
        child_links = "".join(
            f'<li><a href="{relative_url(child / "index.html", current)}">{html.escape(child.name)}/</a></li>'
            for child in children
        )
        local = [entry for entry in entries if PurePosixPath(entry["destination"]).parent == folder]
        body = f'<h1>{html.escape(str(folder))}</h1><ul>{child_links}</ul>{cards(local, current)}'
        write(output, current, document(str(folder), body, current))
    current = PurePosixPath("index.html")
    featured = PurePosixPath("reports/US38-20261002/index.html")
    feature_link = (
        f'<a class="featured" href="{featured}">最新专题：美股 38 家公司研究总览 →</a>'
        if (output / featured).is_file() else ""
    )
    body = f"""<section class="hero"><h1>把研究，放进口袋。</h1>
<p class="intro">{len(entries):,} 份报告 · 公司研究、行业分析与估值 · 手机直接阅读</p>
{feature_link}</section>
<div class="search"><label for="search">搜索公司、股票代码或报告标题</label>
<input id="search" type="search" placeholder="例如：微软、MSFT、腾讯、半导体" disabled></div>
<p><a href="reports/index.html">按文件夹浏览全部报告</a></p>
<p id="status" role="status">正在加载搜索目录；下方为最新报告。</p>
<noscript><p>搜索需要 JavaScript，也可通过上方文件夹目录阅读全部报告。</p></noscript>
{cards(entries[:60], current).replace('class="cards"', 'class="cards" id="reports"', 1)}
<button id="more" type="button" hidden>加载更多</button>"""
    write(output, current, document("研究报告库", body, current, script=True))
    write(output, PurePosixPath("reports.json"), json.dumps(entries, ensure_ascii=False))
    print(f"Built {len(entries)} report pages from {len(files)} source files: {output}", flush=True)
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT / "docs")
    args = parser.parse_args()
    build(args.source, args.output)
