#!/usr/bin/env python3
"""Generate the light and dark open-source contribution cards."""

from __future__ import annotations

import calendar
import collections
import datetime as dt
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


PROFILE_USER = os.environ.get("PROFILE_USER", "tlysanhuo")
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
API_ROOT = "https://api.github.com"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets"
VISIBLE_REPOSITORIES = 12

THEMES = {
    "light": {
        "background": "#ffffff",
        "panel": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#656d76",
        "grid": "#d8dee4",
        "zero": "#ebedf0",
        "accent": "#8250df",
        "accent_soft": "#d8b9ff",
        "merged": "#1a7f37",
    },
    "dark": {
        "background": "#0d1117",
        "panel": "#161b22",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "grid": "#30363d",
        "zero": "#21262d",
        "accent": "#a371f7",
        "accent_soft": "#6e40c9",
        "merged": "#3fb950",
    },
}


def github_api(path: str) -> dict:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tlysanhuo-profile-card",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search_merged_pull_requests() -> list[dict]:
    query = f"type:pr author:{PROFILE_USER} -user:{PROFILE_USER} is:merged"
    items: list[dict] = []
    page = 1
    while True:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "sort": "created",
                "order": "desc",
                "per_page": 100,
                "page": page,
            }
        )
        payload = github_api(f"/search/issues?{params}")
        batch = payload["items"]
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def repository_name(pull_request: dict) -> str:
    return pull_request["repository_url"].split("/repos/", maxsplit=1)[1]


def pull_request_kind(title: str) -> str:
    match = re.match(r"^([a-zA-Z]+)(?:\([^)]*\))?!?:", title.strip())
    kind = match.group(1).lower() if match else "other"
    aliases = {
        "feature": "feat",
        "bugfix": "fix",
        "documentation": "docs",
    }
    return aliases.get(kind, kind)


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def add_months(value: dt.date, offset: int) -> dt.date:
    month_index = value.year * 12 + value.month - 1 + offset
    return dt.date(month_index // 12, month_index % 12 + 1, 1)


def month_key(value: str) -> tuple[int, int]:
    timestamp = parse_timestamp(value)
    return timestamp.year, timestamp.month


def format_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def collect_data() -> dict:
    pull_requests = search_merged_pull_requests()
    if not pull_requests:
        raise RuntimeError(
            f"No merged community pull requests found for @{PROFILE_USER}"
        )

    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for pull_request in pull_requests:
        grouped[repository_name(pull_request)].append(pull_request)

    repositories = {}
    for name, repository_pull_requests in grouped.items():
        metadata = github_api(f"/repos/{name}")
        repositories[name] = {
            "name": name,
            "stars": metadata["stargazers_count"],
            "pull_requests": sorted(
                repository_pull_requests,
                key=lambda item: item["created_at"],
            ),
            "last": max(
                parse_timestamp(item["created_at"]) for item in repository_pull_requests
            ),
        }

    ordered_repositories = sorted(
        repositories.values(),
        key=lambda item: (
            -item["stars"],
            -len(item["pull_requests"]),
            item["name"].lower(),
        ),
    )

    current_month = dt.datetime.now(dt.timezone.utc).date().replace(day=1)
    months = [add_months(current_month, offset) for offset in range(-11, 1)]
    monthly_pull_requests = {(month.year, month.month): [] for month in months}
    for pull_request in pull_requests:
        key = month_key(pull_request["created_at"])
        if key in monthly_pull_requests:
            monthly_pull_requests[key].append(pull_request)

    return {
        "pull_requests": pull_requests,
        "repositories": ordered_repositories,
        "months": months,
        "monthly_pull_requests": monthly_pull_requests,
    }


def render_switch(
    x: float,
    y: float,
    class_name: str,
    chinese: str,
    english: str,
    *,
    anchor: str | None = None,
) -> str:
    anchor_attribute = f' text-anchor="{anchor}"' if anchor else ""
    return (
        "<switch>"
        f'<text x="{x}" y="{y}" class="{class_name}"'
        f'{anchor_attribute} systemLanguage="zh,zh-CN,zh-Hans,zh-TW,zh-HK,zh-Hant,zh-SG">'
        f"{escape(chinese)}</text>"
        f'<text x="{x}" y="{y}" class="{class_name}"{anchor_attribute}>'
        f"{escape(english)}</text>"
        "</switch>"
    )


def render_timeline(data: dict, theme: dict) -> str:
    months = data["months"]
    monthly = data["monthly_pull_requests"]
    x_start = 54
    x_end = 786
    baseline = 342
    plot_height = 176
    step = (x_end - x_start) / (len(months) - 1)
    peak = max(len(monthly[(month.year, month.month)]) for month in months)
    scale = plot_height / max(peak, 1)

    points = []
    bars = []
    dots = []
    labels = []

    for index, month in enumerate(months):
        pull_requests = monthly[(month.year, month.month)]
        count = len(pull_requests)
        x = x_start + index * step
        y = baseline - count * scale
        points.append(f"{x:.1f},{y:.1f}")

        if count:
            bars.append(
                f'<rect class="bar bar-{index}" x="{x - 12:.1f}" y="{y:.1f}" '
                f'width="24" height="{baseline - y:.1f}" rx="8"/>'
            )
            dot_gap = min(15.0, (baseline - y - 12) / max(count - 1, 1))
            for dot_index, _ in enumerate(pull_requests):
                dot_y = baseline - 8 - dot_index * dot_gap
                dots.append(
                    f'<circle class="state-dot merged" cx="{x:.1f}" '
                    f'cy="{dot_y:.1f}" r="4.2"/>'
                )

        if index % 2 == 0 or index == len(months) - 1:
            english = month.strftime("%b")
            chinese = f"{month.month}月"
            if month.month == 1 or index == 0:
                english = month.strftime("%b %Y")
                chinese = f"{month.year}年{month.month}月"
            labels.append(
                render_switch(
                    round(x, 1),
                    365,
                    "axis",
                    chinese,
                    english,
                    anchor="middle",
                )
            )

    area_points = f"{x_start},{baseline} " + " ".join(points) + f" {x_end},{baseline}"
    grid = []
    for line_index in range(4):
        y = baseline - plot_height * line_index / 3
        grid.append(f'<line x1="42" y1="{y:.1f}" x2="798" y2="{y:.1f}" class="grid"/>')

    peak_index = max(
        range(len(months)),
        key=lambda index: len(monthly[(months[index].year, months[index].month)]),
    )
    peak_month = months[peak_index]
    peak_count = len(monthly[(peak_month.year, peak_month.month)])
    peak_x = x_start + peak_index * step
    peak_y = baseline - peak_count * scale
    peak_label_y = max(128, peak_y - 18)
    peak_label_x = min(max(peak_x, 120), 716)

    legend_y = 392
    legend_nodes = [
        f'<circle cx="684" cy="{legend_y - 4}" r="4.5" class="merged"/>',
        render_switch(
            694,
            legend_y,
            "legend",
            f"仅统计已合并 ×{len(data['pull_requests'])}",
            f"MERGED ONLY ×{len(data['pull_requests'])}",
        ),
    ]

    peak_chinese = f"{peak_count} PRs · {peak_month.year}年{peak_month.month}月"
    peak_english = f"{peak_count} PRs · {calendar.month_abbr[peak_month.month].upper()} {peak_month.year}"

    return "".join(
        [
            *grid,
            f'<polygon points="{area_points}" class="area"/>',
            f'<polyline points="{" ".join(points)}" class="trend"/>',
            *bars,
            *dots,
            *labels,
            f'<line x1="{peak_x:.1f}" y1="{peak_y - 6:.1f}" '
            f'x2="{peak_label_x:.1f}" y2="{peak_label_y + 5:.1f}" class="peak-line"/>',
            render_switch(
                round(peak_label_x, 1),
                round(peak_label_y, 1),
                "peak",
                peak_chinese,
                peak_english,
                anchor="middle",
            ),
            *legend_nodes,
        ]
    )


def render_repository_rows(data: dict) -> tuple[str, int]:
    repositories = data["repositories"]
    visible = repositories[:VISIBLE_REPOSITORIES]
    row_height = 22
    start_y = 466
    nodes = []

    for index, repository in enumerate(visible):
        y = start_y + index * row_height
        pull_requests = repository["pull_requests"]
        kinds = collections.Counter(
            pull_request_kind(pull_request["title"]) for pull_request in pull_requests
        )
        kind_text = " · ".join(
            f"{kind} ×{count}"
            for kind, count in sorted(
                kinds.items(),
                key=lambda item: (-item[1], item[0]),
            )[:3]
        )
        if len(kinds) > 3:
            kind_text += f" +{len(kinds) - 3}"

        nodes.append(
            f'<g class="repo-row row-{index}">'
            f'<rect x="30" y="{y - 15}" width="780" height="20" rx="5" class="row-bg"/>'
            f'<text x="42" y="{y}" class="repo-name">{escape(truncate(repository["name"], 38))}</text>'
            f'<text x="374" y="{y}" class="repo-num" text-anchor="end">'
            f"{escape(format_count(repository['stars']))}</text>"
        )

        dot_x = 424
        for _ in pull_requests[:8]:
            nodes.append(f'<circle cx="{dot_x}" cy="{y - 4}" r="4.2" class="merged"/>')
            dot_x += 13
        if len(pull_requests) > 8:
            nodes.append(
                f'<text x="{dot_x + 2}" y="{y}" class="repo-num">'
                f"+{len(pull_requests) - 8}</text>"
            )

        last = repository["last"]
        nodes.append(
            f'<text x="584" y="{y}" class="kinds">{escape(truncate(kind_text, 23))}</text>'
        )
        nodes.append(
            render_switch(
                798,
                y,
                "repo-num",
                f"{last.year}年{last.month}月",
                last.strftime("%b %Y").upper(),
                anchor="end",
            )
        )
        nodes.append("</g>")

    remaining = len(repositories) - len(visible)
    footer_y = start_y + len(visible) * row_height + 8
    if remaining:
        remaining_pull_requests = sum(
            len(repository["pull_requests"])
            for repository in repositories[len(visible) :]
        )
        nodes.append(
            render_switch(
                40,
                footer_y,
                "kinds",
                f"另有 {remaining} 个仓库 · {remaining_pull_requests} PRs",
                f"+{remaining} more repositories · {remaining_pull_requests} PRs",
            )
        )
        footer_y += 14

    return "".join(nodes), footer_y


def render_svg(data: dict, theme_name: str) -> str:
    theme = THEMES[theme_name]
    pull_request_count = len(data["pull_requests"])
    repository_count = len(data["repositories"])
    repository_rows, footer_y = render_repository_rows(data)
    height = max(620, footer_y + 12)

    timeline = render_timeline(data, theme)
    subtitle = render_switch(
        43,
        72,
        "subtitle",
        f"已合并的社区 Pull Requests · @{PROFILE_USER}",
        f"MERGED COMMUNITY PULL REQUESTS · @{PROFILE_USER}",
    )
    summary = render_switch(
        816,
        74,
        "hero-label",
        f"{repository_count} 个上游项目 · 全部已合并",
        f"{repository_count} UPSTREAM PROJECTS · ALL MERGED",
        anchor="end",
    )

    table_headers = "".join(
        [
            render_switch(
                40, 438, "panel-label", "参与的开源仓库", "UPSTREAM REPOSITORIES"
            ),
            render_switch(374, 438, "axis", "星标", "STARS", anchor="end"),
            render_switch(424, 438, "axis", "已合并 PR", "MERGED PRS"),
            render_switch(584, 438, "axis", "类型", "TYPES"),
            render_switch(798, 438, "axis", "最近", "LAST", anchor="end"),
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" role="img" aria-label="Open source contributions: {pull_request_count} merged pull requests across {repository_count} upstream projects">
  <defs>
    <linearGradient id="hero-gradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{theme["accent"]}"/>
      <stop offset="100%" stop-color="{theme["accent_soft"]}"/>
    </linearGradient>
    <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme["accent"]}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{theme["accent"]}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .title {{ fill: {theme["text"]}; font-size: 20px; font-weight: 700; letter-spacing: 1.2px; }}
    .subtitle {{ fill: {theme["muted"]}; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 600; }}
    .hero {{ fill: url(#hero-gradient); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 37px; font-weight: 800; }}
    .hero-label {{ fill: {theme["muted"]}; font-size: 12px; font-weight: 600; letter-spacing: 0.6px; }}
    .axis {{ fill: {theme["muted"]}; font-size: 11px; }}
    .grid {{ stroke: {theme["grid"]}; stroke-width: 1; stroke-dasharray: 3 6; }}
    .area {{ fill: url(#area-gradient); }}
    .trend {{ fill: none; stroke: {theme["accent"]}; stroke-width: 2.2; stroke-linejoin: round; stroke-linecap: round; }}
    .bar {{ fill: {theme["accent"]}; opacity: 0.16; }}
    .peak-line {{ stroke: {theme["muted"]}; stroke-width: 1; stroke-dasharray: 3 3; }}
    .peak {{ fill: {theme["text"]}; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 700; }}
    .legend {{ fill: {theme["muted"]}; font-size: 11px; }}
    .panel-label {{ fill: {theme["muted"]}; font-size: 12px; font-weight: 700; letter-spacing: 0.8px; }}
    .repo-name {{ fill: {theme["text"]}; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; font-weight: 650; }}
    .repo-num {{ fill: {theme["muted"]}; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; }}
    .kinds {{ fill: {theme["muted"]}; font-size: 11px; }}
    .row-bg {{ fill: {theme["panel"]}; opacity: 0; }}
    .repo-row:hover .row-bg {{ opacity: 1; }}
    .merged {{ fill: {theme["merged"]}; }}
    .state-dot {{ stroke: {theme["background"]}; stroke-width: 1.3; }}
    .card {{ fill: {theme["background"]}; stroke: {theme["border"]}; stroke-width: 1; }}
    .divider {{ stroke: {theme["border"]}; stroke-width: 1; }}
  </style>
  <rect x="0.5" y="0.5" width="839" height="{height - 1}" rx="12" class="card"/>
  <text x="24" y="50" class="title">OPEN SOURCE CONTRIBUTIONS</text>
  <circle cx="29" cy="68" r="4" fill="{theme["accent"]}"/>
  {subtitle}
  <text x="816" y="54" class="hero" text-anchor="end">{pull_request_count} MERGED</text>
  {summary}
  {timeline}
  <line x1="24" y1="414" x2="816" y2="414" class="divider"/>
  {table_headers}
  {repository_rows}
</svg>
"""


def main() -> None:
    data = collect_data()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme_name in THEMES:
        output_path = OUTPUT_DIR / f"oss-contributions-{theme_name}.svg"
        output_path.write_text(
            render_svg(data, theme_name),
            encoding="utf-8",
        )
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
