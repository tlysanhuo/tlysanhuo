#!/usr/bin/env python3
"""Generate open-source contribution cards and clickable repository links."""

from __future__ import annotations

import calendar
import collections
import datetime as dt
import html
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


PROFILE_USER = os.environ.get("PROFILE_USER", "tlysanhuo")
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
API_ROOT = "https://api.github.com"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
VISIBLE_REPOSITORIES = 12
VISIBLE_PULL_REQUEST_LINKS = 6
REPOSITORIES_START = "<!-- oss-repositories:start -->"
REPOSITORIES_END = "<!-- oss-repositories:end -->"

THEMES = {
    "light": {
        "background": "#ffffff",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#656d76",
        "grid": "#d8dee4",
        "accent": "#8250df",
        "hero_start": "#8250df",
        "hero_end": "#0969da",
        "merged": "#1a7f37",
    },
    "dark": {
        "background": "#0d1117",
        "border": "#30363d",
        "text": "#f0f6fc",
        "muted": "#8b949e",
        "grid": "#30363d",
        "accent": "#a371f7",
        "hero_start": "#d2a8ff",
        "hero_end": "#58a6ff",
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


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def add_months(value: dt.date, offset: int) -> dt.date:
    month_index = value.year * 12 + value.month - 1 + offset
    return dt.date(month_index // 12, month_index % 12 + 1, 1)


def month_key(value: str) -> tuple[int, int]:
    timestamp = parse_timestamp(value)
    return timestamp.year, timestamp.month


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def repository_pull_requests_url(repository_name: str) -> str:
    params = urllib.parse.urlencode(
        {"q": f"is:pr is:merged author:{PROFILE_USER}"}
    )
    return f"https://github.com/{repository_name}/pulls?{params}"


def all_pull_requests_url() -> str:
    params = urllib.parse.urlencode(
        {
            "q": f"type:pr author:{PROFILE_USER} -user:{PROFILE_USER} is:merged",
            "type": "pullrequests",
        }
    )
    return f"https://github.com/search?{params}"


def render_repository_markdown(data: dict) -> str:
    repositories = data["repositories"]
    visible = repositories[:VISIBLE_REPOSITORIES]
    lines = [
        "| Repository | Merged PRs | Latest |",
        "| :--- | :--- | ---: |",
    ]

    for repository in visible:
        pull_requests = sorted(
            repository["pull_requests"],
            key=lambda item: item["created_at"],
            reverse=True,
        )
        repository_url = repository_pull_requests_url(repository["name"])
        repository_target = (
            pull_requests[0]["html_url"]
            if len(pull_requests) == 1
            else repository_url
        )
        repository_link = f'[{repository["name"]}]({repository_target})'

        pull_request_links = [
            f'[#{pull_request["number"]}]({pull_request["html_url"]})'
            for pull_request in pull_requests[:VISIBLE_PULL_REQUEST_LINKS]
        ]
        remaining = len(pull_requests) - len(pull_request_links)
        if remaining:
            pull_request_links.append(f"[+{remaining}]({repository_url})")

        latest = repository["last"].strftime("%b %Y")
        lines.append(
            f"| {repository_link} | {' · '.join(pull_request_links)} | {latest} |"
        )

    remaining_repositories = len(repositories) - len(visible)
    if remaining_repositories:
        lines.extend(
            [
                "",
                f"_Showing {len(visible)} of {len(repositories)} repositories · "
                f"[view all merged PRs]({all_pull_requests_url()})._",
            ]
        )

    return "\n".join(lines)


def update_readme(repository_markdown: str) -> None:
    source = README_PATH.read_text(encoding="utf-8")
    start = source.index(REPOSITORIES_START)
    end = source.index(REPOSITORIES_END, start) + len(REPOSITORIES_END)
    replacement = (
        f"{REPOSITORIES_START}\n{repository_markdown}\n{REPOSITORIES_END}"
    )
    README_PATH.write_text(
        source[:start] + replacement + source[end:],
        encoding="utf-8",
    )


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
        f'<circle cx="584" cy="{legend_y - 4}" r="4.5" class="merged"/>',
        render_switch(
            798,
            legend_y,
            "legend",
            "近 12 个月 · 仅已合并",
            "LAST 12 MONTHS · MERGED ONLY",
            anchor="end",
        ),
    ]

    peak_chinese = f"{peak_count} PRs · {peak_month.year}年{peak_month.month}月"
    peak_english = f"{peak_count} PRs · {calendar.month_abbr[peak_month.month].upper()} {peak_month.year}"

    return "".join(
        [
            '<g class="plot">',
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
            "</g>",
        ]
    )


def render_svg(data: dict, theme_name: str) -> str:
    theme = THEMES[theme_name]
    pull_request_count = len(data["pull_requests"])
    repository_count = len(data["repositories"])
    height = 414

    timeline = render_timeline(data, theme)
    subtitle = render_switch(
        43,
        72,
        "subtitle",
        f"上游开源贡献 · @{PROFILE_USER}",
        f"UPSTREAM OPEN SOURCE · @{PROFILE_USER}",
    )
    summary = render_switch(
        816,
        74,
        "hero-label",
        f"个已合并 PR · {repository_count} 个上游项目",
        f"MERGED PRS · {repository_count} UPSTREAM PROJECTS",
        anchor="end",
    )
    title = render_switch(24, 50, "title", "开源贡献", "OPEN SOURCE CONTRIBUTIONS")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" role="img" aria-labelledby="card-title card-desc">
  <title id="card-title">Merged upstream open-source contributions by @{PROFILE_USER}</title>
  <desc id="card-desc">{pull_request_count} merged pull requests across {repository_count} repositories, excluding repositories owned by @{PROFILE_USER}.</desc>
  <defs>
    <linearGradient id="hero-gradient" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{theme["hero_start"]}"/>
      <stop offset="100%" stop-color="{theme["hero_end"]}"/>
    </linearGradient>
    <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme["accent"]}" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="{theme["accent"]}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    text {{ font-family: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Noto Sans Mono CJK SC", "PingFang SC", monospace; font-variant-numeric: tabular-nums; }}
    .title {{ fill: {theme["text"]}; font-size: 18px; font-weight: 750; letter-spacing: 1.1px; }}
    .subtitle {{ fill: {theme["muted"]}; font-size: 12px; font-weight: 650; }}
    .hero {{ fill: url(#hero-gradient); font-size: 50px; font-weight: 800; letter-spacing: -2px; }}
    .hero-label {{ fill: {theme["muted"]}; font-size: 12px; font-weight: 650; letter-spacing: 0.3px; }}
    .axis {{ fill: {theme["muted"]}; font-size: 12px; }}
    .grid {{ stroke: {theme["grid"]}; stroke-width: 1; stroke-dasharray: 3 6; }}
    .area {{ fill: url(#area-gradient); }}
    .trend {{ fill: none; stroke: {theme["accent"]}; stroke-width: 2.2; stroke-linejoin: round; stroke-linecap: round; }}
    .bar {{ fill: {theme["accent"]}; opacity: 0.16; }}
    .peak-line {{ stroke: {theme["muted"]}; stroke-width: 1; stroke-dasharray: 3 3; }}
    .peak {{ fill: {theme["text"]}; font-size: 12px; font-weight: 700; }}
    .legend {{ fill: {theme["muted"]}; font-size: 12px; }}
    .merged {{ fill: {theme["merged"]}; }}
    .state-dot {{ stroke: {theme["background"]}; stroke-width: 1.3; }}
    .card {{ fill: {theme["background"]}; stroke: {theme["border"]}; stroke-width: 1; }}
    @keyframes enter {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .header {{ animation: enter 420ms cubic-bezier(0.22, 1, 0.36, 1) both; }}
    .plot {{ animation: enter 480ms 60ms cubic-bezier(0.22, 1, 0.36, 1) both; }}
    @media (prefers-reduced-motion: reduce) {{
      .header, .plot {{ animation: none !important; opacity: 1 !important; transform: none !important; }}
    }}
  </style>
  <rect x="0.5" y="0.5" width="839" height="{height - 1}" rx="12" class="card"/>
  <g class="header">
    {title}
    <circle cx="29" cy="68" r="4" fill="{theme["accent"]}"/>
    {subtitle}
    <text x="816" y="58" class="hero" text-anchor="end">{pull_request_count}</text>
    {summary}
  </g>
  {timeline}
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
    update_readme(render_repository_markdown(data))
    print(f"Updated {README_PATH}")


if __name__ == "__main__":
    main()
