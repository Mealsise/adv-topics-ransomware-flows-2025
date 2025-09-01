#!/usr/bin/env python3
from __future__ import annotations
import pathlib
import re as regex
from typing import Dict, List

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CAMPAIGNS_DIR = REPO_ROOT / "campaigns"
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_MD = DOCS_DIR / "overview.md"

STATUS_DIRS: Dict[str, str] = {
    "pending": "PENDING",
    "shortlist": "SHORTLIST",
    "graveyard": "GRAVEYARD",
}

FIELD_PATTERNS = {
    "name": regex.compile(r"^#\s*(.+?)\s*$"),
    "group": regex.compile(r"^\s*-\s*\*\*Group/Family\*\*:\s*(.+?)\s*$", regex.I),
    "years": regex.compile(r"^\s*-\s*\*\*Year\(s\)\*\*:\s*(.+?)\s*$", regex.I),
    "analytical": regex.compile(r"^\s*-\s*\*\*Analytical Value\*\*:\s*(.+?)\s*$", regex.I),
    "docq": regex.compile(r"^\s*-\s*\*\*Documentation Quality\*\*:\s*(.+?)\s*$", regex.I),
}

ANALYTIC_ORDER: Dict[str, int] = {"VH": 0, "H": 1, "M": 2, "L": 3, "?": 4}


def normalize_analytical(analytical_text: str) -> str:
    text = analytical_text.strip().lower()
    # handle template values like "Very High | High | Medium"
    text = text.split("|")[0].strip()
    mapping = {
        "medium-high": "Medium-High",
        "very high": "Very High",
        "vhigh": "Very High",
        "v-high": "Very High",
        "vh": "Very High",
        "high": "High",
        "h": "High",
        "medium": "Medium",
        "med": "Medium",
        "m": "Medium",
        "low": "Low",
        "l": "Low",
    }
    return mapping.get(text, analytical_text.strip())


def normalize_doc_quality(doc_quality_text: str) -> str:
    primary = doc_quality_text.strip().split("|")[0].strip()
    return primary.capitalize() if primary else "?"


def extract_first_year(years_field: str) -> str:
    text = years_field.strip()
    match = regex.search(r"(19|20)\d{2}", text)
    return match.group(0) if match else text or "?"


def parse_campaign_markdown(markdown_path: pathlib.Path) -> Dict[str, str]:
    parsed: Dict[str, str] = {
        "name": "",
        "group": "",
        "years": "",
        "analytical": "",
        "docq": "",
    }
    try:
        with markdown_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not parsed["name"]:
                    name_match = FIELD_PATTERNS["name"].match(line)
                    if name_match:
                        parsed["name"] = name_match.group(1).strip()
                group_match = FIELD_PATTERNS["group"].match(line)
                if group_match:
                    parsed["group"] = group_match.group(1).strip()
                years_match = FIELD_PATTERNS["years"].match(line)
                if years_match:
                    parsed["years"] = years_match.group(1).strip()
                analytical_match = FIELD_PATTERNS["analytical"].match(line)
                if analytical_match:
                    parsed["analytical"] = normalize_analytical(analytical_match.group(1))
                docq_match = FIELD_PATTERNS["docq"].match(line)
                if docq_match:
                    parsed["docq"] = normalize_doc_quality(docq_match.group(1))
    except Exception as error:
        print(f"Warn: failed to parse {markdown_path}: {error}")

    if not parsed["name"]:
        parsed["name"] = markdown_path.stem.replace("_", "-")
    if not parsed["analytical"]:
        parsed["analytical"] = "?"
    if not parsed["docq"]:
        parsed["docq"] = "?"
    if not parsed["years"]:
        parsed["years"] = "?"

    return parsed


def collect_campaign_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for subdirectory_name, status_label in STATUS_DIRS.items():
        subdirectory_path = CAMPAIGNS_DIR / subdirectory_name
        if not subdirectory_path.exists():
            continue
        for markdown_path in sorted(subdirectory_path.rglob("*.md")):
            if markdown_path.name.lower() == "campaign_template.md":
                continue
            parsed = parse_campaign_markdown(markdown_path)
            rows.append(
                {
                    "status": status_label,
                    "name": parsed["name"],
                    "group": parsed["group"] or "?",
                    "year": extract_first_year(parsed["years"]),
                    "analytical": parsed["analytical"],
                    "docq": parsed["docq"],
                    "path": str(markdown_path.relative_to(REPO_ROOT)),
                }
            )
    return rows


def build_md_table(rows: List[Dict[str, str]]) -> str:
    header = (
        "| Name | Group | Year | Analytic | DocQ | Status |\n"
        "|---|---|---:|:---:|:---:|:---:|\n"
    )
    body_lines: List[str] = []
    for row in rows:
        body_lines.append(
            f"| [{row['name']}](../{row['path']}) | {row['group']} | {row['year']} | "
            f"{row['analytical']} | {row['docq']} | {row['status']} |"
        )
    return header + "\n".join(body_lines) + "\n"


def write_overview(all_rows: List[Dict[str, str]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Campaign Overview\n")
    lines.append("_Auto-generated. Edit individual campaign files in `campaigns/`._\n")

    # Section per status: sort by Analytic (VH>H>M>L>?) then Group asc, then Year desc
    for status_label in ["SHORTLIST", "PENDING", "GRAVEYARD"]:
        status_rows = [row for row in all_rows if row["status"] == status_label]
        status_rows.sort(
            key=lambda row: (
                ANALYTIC_ORDER.get(row["analytical"], 9),
                row["group"].lower(),
                -int(row["year"]) if row["year"].isdigit() else 0,
            )
        )
        lines.append(f"## {status_label}\n")
        lines.append(build_md_table(status_rows) if status_rows else "_None_\n")

    # All campaigns table: sort by Group asc, then Year desc
    all_sorted = sorted(
        all_rows,
        key=lambda row: (
            row["group"].lower(),
            -int(row["year"]) if row["year"].isdigit() else 0,
        ),
    )
    lines.append("## All Campaigns (by Group, then Year desc)\n")
    lines.append(build_md_table(all_sorted))

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_MD.relative_to(REPO_ROOT)}")


def main() -> None:
    campaign_rows = collect_campaign_rows()
    if not campaign_rows:
        print(
            "No campaign files found. Add markdowns in campaigns/pending|shortlist|graveyard."
        )
        raise SystemExit(1)
    write_overview(campaign_rows)


if __name__ == "__main__":
    main()
