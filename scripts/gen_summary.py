import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# ========= CONFIG =========
INPUT_DIR = Path("flows")
OUTPUT_DIR = Path("summary")
GLOB_PATTERN = "*.afb"
SKIP_EXISTING = True

# Flow
COLLAPSE_WHITESPACE = True
REFERENCE_FORMAT = "{source_name} - {description} - {url}"
SECTION_SEP = "\n" + "-" * 60 + "\n"

# Notes
COLLAPSE_WHITESPACE_NOTES = True
INDENT_STR = "     "
CONTENT_INDENT_STR = "      "

# Actions
A_NAME_INDENT = "     "
A_BODY_INDENT = "          "
COLLAPSE_WHITESPACE_ACTIONS = True

# Assets
PRINT_ASSETS_LABEL = True
ASSET_NAME_INDENT = "     "
ASSET_DESC_INDENT = "          "
COLLAPSE_WHITESPACE_ASSETS = True

# Remainder filtering
APPLY_FILTERS_TO_REMAINDER = True
SKIP_IDS = {
    "horizontal_anchor", "vertical_anchor", "dynamic_line",
    "generic_latch", "generic_handle",
    "AND_operator", "OR_operator", "condition"     # drop logic nodes entirely
}
SKIP_KEYS = {"instance", "anchors", "objects"}
# =========================


def collapse_ws(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def strip_tz(dt: Optional[str]) -> str:
    if not dt:
        return ""
    return re.sub(r"(Z|[+-]\d{2}:\d{2})$", "", dt)

def _pairs_with_scalar_values(seq: list) -> bool:
    if not seq:
        return False
    for x in seq:
        if not (isinstance(x, list) and len(x) == 2):
            return False
        _, v = x
        if isinstance(v, (list, dict)):
            return False
    return True

def listprops_to_dict(props: List[List[Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in props:
        if isinstance(v, list) and _pairs_with_scalar_values(v):
            out[k] = {ik: iv for ik, iv in v}
        else:
            out[k] = v
    return out

def parse_external_refs(raw_refs: Any) -> List[Dict[str, str]]:
    results = []
    if not isinstance(raw_refs, list):
        return results
    for item in raw_refs:
        if not (isinstance(item, list) and len(item) == 2):
            continue
        ref_id, kvs = item
        kvdict = {}
        if isinstance(kvs, list):
            for kv in kvs:
                if isinstance(kv, list) and len(kv) == 2:
                    kvdict[kv[0]] = kv[1]
        results.append({
            "ref_id": ref_id,
            "source_name": kvdict.get("source_name", ""),
            "description": kvdict.get("description", ""),
            "url": kvdict.get("url", ""),
        })
    return results

def format_author(author: Optional[Dict[str, Any]]) -> str:
    if not isinstance(author, dict):
        return ""
    parts = [author.get("name", ""), author.get("identity_class", ""), author.get("contact_information", "")]
    return " - ".join([p for p in parts if p])

def format_refs(refs: List[Dict[str, str]]) -> List[str]:
    lines = []
    for r in refs:
        line = REFERENCE_FORMAT.format(**r)
        if COLLAPSE_WHITESPACE:
            line = collapse_ws(line)
        lines.append(line)
    return lines

def extract_flow(objects: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    remaining, flow_obj = [], None
    for obj in objects:
        if obj.get("id") == "flow" and flow_obj is None:
            flow_obj = obj
        else:
            remaining.append(obj)
    return flow_obj, remaining

def build_flow_summary(flow_obj: Dict[str, Any]) -> Dict[str, Any]:
    props = listprops_to_dict(flow_obj.get("properties", []))
    name = props.get("name", "")
    desc = props.get("description", "")
    if COLLAPSE_WHITESPACE: desc = collapse_ws(desc)
    author_str = format_author(props.get("author"))
    scope = props.get("scope", "")
    refs = parse_external_refs(props.get("external_references"))
    ref_lines = format_refs(refs)
    return {"name": name, "description": desc, "author": author_str, "scope": scope, "references": ref_lines}

def extract_notes(objects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    notes, remainder = [], []
    for obj in objects:
        if obj.get("id") != "note":
            remainder.append(obj); continue
        props = listprops_to_dict(obj.get("properties", []))
        abstract = props.get("abstract", "")
        content  = props.get("content", "")
        if COLLAPSE_WHITESPACE_NOTES:
            abstract = collapse_ws(abstract); content = collapse_ws(content)
        notes.append({"abstract": abstract or "", "content": content or ""})
    return notes, remainder

def extract_actions(objects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    actions, remainder = [], []
    for obj in objects:
        if obj.get("id") != "action":
            remainder.append(obj); continue

        props = listprops_to_dict(obj.get("properties", []))
        name = props.get("name", "")
        desc = props.get("description", "")

        # ttp can be dict (after collapse) or list-of-pairs
        tactic = technique = ""
        ttp = props.get("ttp", [])
        if isinstance(ttp, dict):
            tactic = ttp.get("tactic", "")
            technique = ttp.get("technique", "")
        elif isinstance(ttp, list) and all(isinstance(x, list) and len(x) == 2 for x in ttp):
            d = {k: v for k, v in ttp}
            tactic = d.get("tactic", "")
            technique = d.get("technique", "")

        def strip_tz(dt: Optional[str]) -> str:
            if not dt: return ""
            return re.sub(r"(Z|[+-]\d{2}:\d{2})$", "", dt)

        def get_time(val: Any) -> str:
            if isinstance(val, dict): return strip_tz(val.get("time"))
            if isinstance(val, str):  return strip_tz(val)
            return ""

        start = get_time(props.get("execution_start"))
        end   = get_time(props.get("execution_end"))

        if COLLAPSE_WHITESPACE_ACTIONS:
            name = collapse_ws(name); desc = collapse_ws(desc)
            tactic = collapse_ws(tactic); technique = collapse_ws(technique)

        actions.append({
            "name": name or "",
            "tactic": tactic or "NONE GIVEN",
            "technique": technique or "NONE GIVEN",
            "description": desc or "",
            "start": start or "",
            "end": end or "",
        })
    return actions, remainder

def extract_assets(objects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """Pull id=='asset' → name, description. Drop authors if present."""
    assets, remainder = [], []
    for obj in objects:
        if obj.get("id") != "asset":
            remainder.append(obj); continue
        props = listprops_to_dict(obj.get("properties", []))
        name = props.get("name", "")
        desc = props.get("description", "")
        if COLLAPSE_WHITESPACE_ASSETS:
            name = collapse_ws(name); desc = collapse_ws(desc)
        assets.append({"name": name or "", "description": desc or ""})
    return assets, remainder

def filter_objects(objs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for obj in objs:
        if obj.get("id") in SKIP_IDS:
            continue
        cleaned = {k: v for k, v in obj.items() if k not in SKIP_KEYS}
        out.append(cleaned)
    return out

def render_report(flow_summary: Dict[str, Any],
                  notes: List[Dict[str, str]],
                  assets: List[Dict[str, str]],
                  actions: List[Dict[str, str]],
                  remainder: List[Dict[str, Any]]) -> str:
    lines: List[str] = []

    # FLOW
    lines += [
        "FLOW:",
        f"name: {flow_summary['name']}",
        f"description: {flow_summary['description']}",
        f"author: {flow_summary['author']}",
        f"scope: {flow_summary['scope']}",
        "references:",
    ]
    for line in flow_summary["references"]:
        lines.append(f"  {line}")

    # NOTES
    lines.append(SECTION_SEP)
    empties = [n for n in notes if not n["content"]]
    with_content = [n for n in notes if n["content"]]
    if empties:
        lines.append("Empty Notes:")
        for n in empties: lines.append(f"{INDENT_STR}{n['abstract']}")
        if with_content: lines.append("")
    if with_content:
        lines.append("Notes:")
        for n in with_content:
            lines.append(f"{INDENT_STR}{n['abstract']}")
            lines.append(f"{CONTENT_INDENT_STR}{n['content']}")

    # ASSETS
    if assets:
        lines.append(SECTION_SEP)
        if PRINT_ASSETS_LABEL: lines.append("Assets:")
        for a in assets:
            lines.append(f"{ASSET_NAME_INDENT}{a['name']}")
            if a["description"]:
                lines.append(f"{ASSET_DESC_INDENT}{a['description']}")

    # ACTIONS
    lines.append(SECTION_SEP)
    lines.append("Actions:")
    for a in actions:
        lines.append(f"{A_NAME_INDENT}{a['name']}")
        lines.append(f"{A_BODY_INDENT}TACT/TECH: {a['tactic']} / {a['technique']}")
        if a["description"]:
            lines.append(f"{A_BODY_INDENT}{a['description']}")
        times = []
        if a["start"]: times.append(f"start: {a['start']}")
        if a["end"]:   times.append(f"end: {a['end']}")
        if times:
            lines.append(f"{A_BODY_INDENT}" + "   ".join(times))

    # REMAINDER (debug tail)
    lines.append(SECTION_SEP)
    lines.append("REMAINDER:")
    lines.append(json.dumps(remainder, ensure_ascii=False, indent=2))
    return "\n".join(lines) + "\n"

def process_file(in_path: Path, out_path: Path) -> None:
    data = json.loads(in_path.read_text(encoding="utf-8"))
    objects = data.get("objects", [])

    flow_obj, rest = extract_flow(objects)
    if not flow_obj:
        out_path.write_text("FLOW:\nname: (missing)\n", encoding="utf-8"); return
    flow_summary = build_flow_summary(flow_obj)

    notes, rest   = extract_notes(rest)
    assets, rest  = extract_assets(rest)
    actions, rest = extract_actions(rest)

    if APPLY_FILTERS_TO_REMAINDER:
        rest = filter_objects(rest)

    report = render_report(flow_summary, notes, assets, actions, rest)
    out_path.write_text(report, encoding="utf-8")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for afb in sorted(INPUT_DIR.glob(GLOB_PATTERN)):
        out = OUTPUT_DIR / (afb.stem + ".txt")
        if SKIP_EXISTING and out.exists():
            print(f"[skip] {out}"); continue
        try:
            process_file(afb, out)
            print(f"[ok]   {out}")
        except Exception as e:
            print(f"[err]  {afb}: {e}")

if __name__ == "__main__":
    main()
