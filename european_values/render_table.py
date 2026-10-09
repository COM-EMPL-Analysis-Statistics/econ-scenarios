"""Render calibration_parameters.yaml as an HTML table.

Run from the repository root:  uv run python european_values/render_table.py
Writes calibration_parameters.html beside the YAML. The YAML is the source of truth; edit it,
rerun this, and never edit the output by hand.

The HTML page has one collapsible panel per section of Table 1, a status legend whose chips
filter the rows, a text filter, and expand / collapse all. Discuss rows are tinted amber
with a left bar; parameters that share a `group` are tinted grey with a left bar and labelled.
"""

from __future__ import annotations

import html
import re
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE / "calibration_parameters.yaml"
SCENARIOS = ("modest", "substantial", "extreme")
STATUSES = ("decided", "discuss", "open")

COLUMNS = [
    "Symbol",
    "Parameter (code)",
    "Meaning",
    "US value",
    "US source",
    "EU treatment",
    "EU value",
    "EU source / hint",
    "Justification",
    "Status",
]


def fmt_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        if set(v) == set(SCENARIOS):
            return " / ".join(str(v[s]) for s in SCENARIOS) + " (M / S / E)"
        return "; ".join(f"{k} {val}" for k, val in v.items())
    return str(v)


def clean(s) -> str:
    """Collapse runs of spaces within lines; keep line breaks and single blank lines."""
    if not s:
        return ""
    out: list[str] = []
    for line in str(s).splitlines():
        indent = len(line) - len(line.lstrip(" "))
        line = " " * indent + " ".join(line.split())
        if line.strip() or (out and out[-1].strip()):
            out.append(line if line.strip() else "")
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


BULLET = re.compile(r"^(?:[-*•]\s+|\+\s+)")
ENUM = re.compile(r"^(?:\([ivx]+\)|\([a-z]\)|\d{1,2}[.)]|[ivx]+[.)])\s+")
INLINE_ENUM = re.compile(r"\s+(?=\([ivx]+\)\s)")


def structure(e, text: str, link: bool = True) -> str:
    """Turn the YAML text into HTML blocks.

    A line starting with "- ", "* " or "+ " is a bullet; one starting with "(i)", "(a)", "1." or
    "1)" is an enumerated item with a hanging indent; a blank line separates paragraphs. A plain
    line after another plain line continues that paragraph; after a bullet or item, it continues
    that bullet or item (so block scalars written with | reflow like folded ones written with >).
    """
    if not text:
        return ""
    conv = (lambda t: _linkify(e, t)) if link else e
    blocks: list[tuple[str, str]] = []  # (kind, text) with kind in p, li, en, br
    last_indent = 0
    for raw in text.split("\n"):
        line = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if not line:
            blocks.append(("br", ""))
        elif BULLET.match(line):
            blocks.append(("li", BULLET.sub("", line)))
            last_indent = indent
        elif ENUM.match(line):
            blocks.append(("en", line))
            last_indent = indent
        elif blocks and blocks[-1][0] == "p":
            blocks[-1] = ("p", blocks[-1][1] + " " + line)  # a wrapped line continues its paragraph
        elif blocks and blocks[-1][0] in ("li", "en") and indent > last_indent:
            blocks[-1] = (blocks[-1][0], blocks[-1][1] + " " + line)  # indented: continues the item
        else:
            blocks.append(("p", line))
            last_indent = indent
    # Enumerators folded into one line by YAML (">") are split back into items.
    split: list[tuple[str, str]] = []
    for kind, t in blocks:
        if kind in ("p", "en", "li"):
            pieces = INLINE_ENUM.split(t)
            if len(pieces) > 1:
                head, rest = pieces[0].strip(), pieces[1:]
                if head:
                    split.append((kind, head))
                split.extend(("en", r.strip()) for r in rest)
                continue
        split.append((kind, t))
    blocks = split
    parts: list[str] = []
    i = 0
    while i < len(blocks):
        kind, t = blocks[i]
        if kind == "li":
            items = []
            while i < len(blocks) and blocks[i][0] == "li":
                items.append(f"<li>{conv(blocks[i][1])}</li>")
                i += 1
            parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        if kind == "en":
            parts.append(f'<div class="en">{conv(t)}</div>')
        elif kind == "p":
            parts.append(f"<p>{conv(t)}</p>")
        i += 1
    return "".join(parts)


def code_cell(p: dict) -> str:
    code = clean(p.get("code")) or "not in code"
    tag = " [derived]" if p.get("derived") else ""
    return f"{p['id']}{tag}\n{code}"


def rows_for(p: dict) -> list[str]:
    eu = p["eu"]
    return [
        clean(p.get("symbol")),
        code_cell(p),
        clean(p.get("meaning")),
        fmt_value(p.get("us_value")),
        clean(p.get("us_source")),
        clean(eu.get("treatment")),
        fmt_value(eu.get("value")),
        clean(eu.get("source")) or clean(eu.get("source_hint")),
        clean(eu.get("justification")),
        clean(eu.get("status")) or "open",
    ]


def by_section(spec: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in spec["parameters"]:
        out.setdefault(p["section"], []).append(p)
    return out


def status_counts(params: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(STATUSES, 0)
    for p in params:
        counts[p["eu"].get("status") or "open"] += 1
    return counts


# ------------------------------------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------------------------------------

CSS = """
:root {
  --bg:#f6f7f9; --panel:#ffffff; --fg:#1c1f24; --muted:#5f6670; --line:#e3e6ea; --line-strong:#c9ced5;
  --head:#f0f2f5; --zebra:#fafbfc; --accent:#2f5fa8; --accent-soft:#e6eef9;
  --decided:#2e8b57; --decided-soft:#e4f3ea;
  --discuss:#d9891f; --discuss-soft:#fdf1dc; --discuss-row:#fff7e8;
  --draft:#b58b00; --draft-soft:#fbf3cf;
  --open:#b9433e; --open-soft:#fbe7e5;
  --group-row:#eff1f4; --group-line:#8d96a3;
  --shadow:0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#0f1115; --panel:#171a20; --fg:#e7e9ee; --muted:#9aa3ae; --line:#272c35; --line-strong:#3a414c;
  --head:#1d2129; --zebra:#1a1e25; --accent:#7ea6e8; --accent-soft:#1f2b40;
  --decided:#5ec28a; --decided-soft:#173324;
  --discuss:#e6a24a; --discuss-soft:#3d2d14; --discuss-row:#2b2316;
  --draft:#d8b24a; --draft-soft:#3a3115;
  --open:#e0736d; --open-soft:#3b1f1d;
  --group-row:#20242c; --group-line:#6b7482;
  --shadow:none;
} }
:root[data-theme="dark"] {
  --bg:#0f1115; --panel:#171a20; --fg:#e7e9ee; --muted:#9aa3ae; --line:#272c35; --line-strong:#3a414c;
  --head:#1d2129; --zebra:#1a1e25; --accent:#7ea6e8; --accent-soft:#1f2b40;
  --decided:#5ec28a; --decided-soft:#173324;
  --discuss:#e6a24a; --discuss-soft:#3d2d14; --discuss-row:#2b2316;
  --draft:#d8b24a; --draft-soft:#3a3115;
  --open:#e0736d; --open-soft:#3b1f1d;
  --group-row:#20242c; --group-line:#6b7482;
  --shadow:none;
}
* { box-sizing:border-box; }
html { background:var(--bg); }
body { margin:0; padding:28px 48px 56px; background:var(--bg); color:var(--fg);
       font:14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.page { max-width:1680px; margin:0 auto; }
header h1 { font-size:22px; font-weight:650; letter-spacing:-.01em; margin:0 0 4px; }
header p { color:var(--muted); margin:0; max-width:900px; }
.toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:18px 0 14px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px;
        border:1px solid var(--line-strong); background:var(--panel); cursor:pointer; font-size:13px;
        user-select:none; }
.chip .dot { width:9px; height:9px; border-radius:50%; }
.chip .n { color:var(--muted); font-variant-numeric:tabular-nums; }
.chip.off { opacity:.45; }
.chip.legend { cursor:default; }
.chip.on { border-color:var(--accent); background:var(--accent-soft); }
.spacer { flex:1; }
input.filter { padding:6px 10px; border:1px solid var(--line-strong); border-radius:8px;
               background:var(--panel); color:var(--fg); min-width:220px; font:inherit; }
button { font:inherit; font-size:13px; padding:6px 10px; border-radius:8px; border:1px solid var(--line-strong);
         background:var(--panel); color:var(--fg); cursor:pointer; }
button:hover, .chip:hover { border-color:var(--accent); }
details.panel { background:var(--panel); border:1px solid var(--line); border-radius:12px;
                box-shadow:var(--shadow); margin:0 0 14px; overflow:hidden; }
details.panel > summary { list-style:none; cursor:pointer; display:flex; align-items:center; gap:12px;
                          padding:12px 16px; user-select:none; }
details.panel > summary::-webkit-details-marker { display:none; }
summary .letter { width:30px; height:30px; border-radius:8px; background:var(--accent-soft); color:var(--accent);
                  display:inline-flex; align-items:center; justify-content:center; font-weight:700; }
summary .title { font-size:15px; font-weight:600; }
summary .meta { color:var(--muted); font-size:13px; }
summary .mini { display:inline-flex; gap:4px; margin-left:4px; }
summary .mini span { display:inline-block; min-width:18px; padding:1px 6px; border-radius:999px; font-size:11px;
                     font-weight:600; text-align:center; }
summary .chev { margin-left:auto; color:var(--muted); transition:transform .15s; }
details[open] > summary .chev { transform:rotate(90deg); }
details[open] > summary { border-bottom:1px solid var(--line); }
.wrap { overflow-x:auto; padding:4px 14px 10px; }
table { border-collapse:separate; border-spacing:0; width:100%; min-width:1300px; table-layout:fixed; }
th { position:sticky; top:0; z-index:1; background:var(--head); color:var(--muted); font-weight:600;
     font-size:12px; text-transform:uppercase; letter-spacing:.03em; text-align:left; padding:9px 10px;
     border-bottom:1px solid var(--line-strong); }
td { padding:11px 12px; border-bottom:1px solid var(--line); vertical-align:top; }
td:first-child, th:first-child { padding-left:14px; }
td:last-child, th:last-child { padding-right:14px; }
tbody tr:nth-child(even) td { background:var(--zebra); }
tbody tr.hide { display:none; }
td.sym { font-family:"Cambria Math", Cambria, "Times New Roman", Georgia, serif; font-size:16px; }
td.sym i { font-style:italic; }
td.sym sub, td.sym sup { font-size:11px; font-style:italic; line-height:0; }
td.code { font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:12px;
          white-space:pre-wrap; }
td.code .id { font-weight:600; font-size:13px; }
td.code .loc { color:var(--muted); display:block; margin-top:2px; }
td.code .derived { color:var(--accent); font-size:11px; margin-left:4px; }
td.num { font-variant-numeric:tabular-nums; }
td.num .mse { display:block; font-size:11px; color:var(--muted); font-weight:400; margin-top:2px; }
td.euval { font-weight:600; }
td { overflow-wrap:anywhere; }
td p, td ul, td .en { margin:0; }
td p + p, td ul + p, td .en + p, td p + ul, td .en + ul, td ul + .en, td p + .en { margin-top:6px; }
td ul { padding-left:18px; }
td li { margin:2px 0; }
td li + li { margin-top:3px; }
td .en { padding-left:1.9em; text-indent:-1.9em; }
td .en + .en { margin-top:4px; }
td.src a { color:var(--accent); word-break:break-all; }
td.treat { text-transform:capitalize; white-space:nowrap; }
.pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600;
        text-transform:capitalize; white-space:nowrap; }
.pill.decided { background:var(--decided-soft); color:var(--decided); }
.pill.discuss { background:var(--discuss-soft); color:var(--discuss); }
.pill.draft { background:var(--draft-soft); color:var(--draft); }
.pill.open { background:var(--open-soft); color:var(--open); }
.star { color:var(--accent); font-size:14px; margin-right:4px; }
.pill.todo { background:var(--accent-soft); color:var(--accent); margin-top:6px; }
.todo-text { font-size:12px; color:var(--muted); margin-top:3px; }
.chip.key .star { margin-right:0; }
tbody tr.key td.code .id { color:var(--accent); }
tbody tr.discuss td { background:var(--discuss-row) !important; }
tbody tr.discuss td:first-child { box-shadow:inset 4px 0 0 var(--discuss); }
tbody tr.grouped td { background:var(--group-row) !important; }
tbody tr.grouped td:first-child { box-shadow:inset 4px 0 0 var(--group-line); }
tbody tr.grouped.discuss td { background:var(--discuss-row) !important; }
tbody tr.grouped.discuss td:first-child { box-shadow:inset 4px 0 0 var(--discuss); }
tbody tr.group-first td { border-top:1px solid var(--group-line); }
tbody tr.group-last td { border-bottom:1px solid var(--group-line); }
.grouplabel { display:block; font-family:system-ui, sans-serif; font-size:11px; color:var(--muted); margin-top:5px;
              white-space:normal; }
.empty { padding:14px 16px; color:var(--muted); display:none; }
details.panel.allhidden .empty { display:block; }
footer { color:var(--muted); font-size:12px; margin-top:18px; }
@media (max-width:900px) { body { padding:16px 16px 32px; } .wrap { padding:0 4px 6px; } th, td { padding:7px 8px; } }
"""

JS = """
(function(){
  var KEY = 'calib-table-state';
  var state = {collapsed:{}, statuses:{}, q:''};
  try { var s = localStorage.getItem(KEY); if (s) state = Object.assign(state, JSON.parse(s)); } catch(e){}
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e){} }
  var panels = document.querySelectorAll('details.panel');
  var chips = document.querySelectorAll('.chip[data-status]');
  var q = document.getElementById('q');
  panels.forEach(function(d){ if (state.collapsed[d.dataset.sec]) d.removeAttribute('open');
    d.addEventListener('toggle', function(){ state.collapsed[d.dataset.sec] = !d.open; save(); }); });
  chips.forEach(function(c){ var st = c.dataset.status; if (state.statuses[st] === false) c.classList.add('off');
    c.addEventListener('click', function(){ c.classList.toggle('off'); state.statuses[st] = !c.classList.contains('off'); save(); apply(); }); });
  q.value = state.q || '';
  q.addEventListener('input', function(){ state.q = q.value; save(); apply(); });
  document.getElementById('expand').addEventListener('click', function(){ panels.forEach(function(d){ d.open = true; }); });
  document.getElementById('collapse').addEventListener('click', function(){ panels.forEach(function(d){ d.open = false; }); });
  document.getElementById('reset').addEventListener('click', function(){ q.value=''; state.q='';
    chips.forEach(function(c){ c.classList.remove('off'); }); state.statuses = {}; save(); apply(); });
  var todoChip = document.getElementById('todoonly');
  if (state.todoonly) todoChip.classList.add('on');
  todoChip.addEventListener('click', function(){ todoChip.classList.toggle('on'); state.todoonly = todoChip.classList.contains('on'); save(); apply(); });
  var keyChip = document.getElementById('keyonly');
  if (state.keyonly) keyChip.classList.add('on');
  keyChip.addEventListener('click', function(){ keyChip.classList.toggle('on'); state.keyonly = keyChip.classList.contains('on'); save(); apply(); });
  function apply(){
    var keyOnly = keyChip.classList.contains('on');
    var needle = (q.value || '').trim().toLowerCase();
    var on = {}; chips.forEach(function(c){ on[c.dataset.status] = !c.classList.contains('off'); });
    panels.forEach(function(d){
      var shown = 0;
      d.querySelectorAll('tbody tr').forEach(function(tr){
        var todoOnly = todoChip.classList.contains('on');
        var ok = on[tr.dataset.status] !== false && (!keyOnly || tr.dataset.key === '1') && (!todoOnly || tr.dataset.todo === '1') && (!needle || tr.textContent.toLowerCase().indexOf(needle) >= 0);
        tr.classList.toggle('hide', !ok); if (ok) shown++;
      });
      d.classList.toggle('allhidden', shown === 0);
      d.querySelector('.shown').textContent = shown;
    });
  }
  apply();
})();
"""


def _sym(e, text: str) -> str:
    """Typeset a symbol: `x_ab` -> x with subscript ab, `x^T_o` -> superscript T, subscript o.

    Works token by token on whitespace, so "s_C,t0 / s_L,t0" and "1 − ϕ_R" come out right. Bars
    and Greek letters are already in the text as Unicode.
    """
    out = []
    for tok in text.split(" "):
        m = re.match(r"^([^_^]+)(?:\^([^_]+))?(?:_(.+))?$", tok)
        if not m:
            out.append(e(tok))
            continue
        base, sup, sub = m.groups()
        s = f"<i>{e(base)}</i>"
        if sup:
            s += f"<sup>{e(sup)}</sup>"
        if sub:
            s += f"<sub>{e(sub)}</sub>"
        out.append(s)
    return " ".join(out)


def _num(e, text: str) -> str:
    """A value cell: scenario triples wrap at the slashes and carry their M / S / E tag below."""
    tag = " (M / S / E)"
    if text.endswith(tag):
        return e(text[: -len(tag)]) + '<span class="mse">modest / substantial / extreme</span>'
    return e(text)


def _linkify(e, text: str) -> str:
    """Escape text and turn bare http(s) URLs into links."""
    parts = []
    for tok in text.split(" "):
        bare = tok.rstrip(".,;)")
        tail = tok[len(bare):]
        if bare.startswith(("http://", "https://")):
            parts.append(f'<a href="{e(bare)}" target="_blank" rel="noopener">{e(bare)}</a>{e(tail)}')
        else:
            parts.append(e(tok))
    return " ".join(parts)


def render_html(spec: dict) -> str:
    e = html.escape
    sections = by_section(spec)
    totals = status_counts(spec["parameters"])
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Calibration parameters</title>",
        f"<style>{CSS}</style></head><body><div class=\"page\">",
        "<header><h1>Calibration parameters: US values and EU treatment</h1>",
        "<p>Generated from <code>calibration_parameters.yaml</code>. "
        "Please edit the YAML and rerun <code>render_table.py</code> to update this table. "
        "The estimated model imports parameters directly from that YAML.</p></header>",
        '<div class="toolbar"><div class="chips">',
    ]
    
    for st in STATUSES:
        out.append(
            f'<span class="chip" data-status="{st}" title="click to hide or show these rows">'
            f'<span class="dot" style="background:var(--{st})"></span>'
            f'{st} <span class="n">{totals[st]}</span></span>'
        )
    out += [
        '<span class="chip" id="todoonly" title="show only the parameters with an open to-do">to-do '
        f'<span class="n">{sum(1 for p in spec["parameters"] if p["eu"].get("todo"))}</span></span>',
        '<span class="chip key" id="keyonly" title="show only the parameters that differ from the US and matter">'
        '<span class="star">★</span> key EU difference '
        f'<span class="n">{sum(1 for p in spec["parameters"] if p["eu"].get("key_difference"))}</span></span>',
        '</div><span class="spacer"></span>',
        '<input id="q" class="filter" type="search" placeholder="filter rows (symbol, id, text)">',
        '<button id="expand">Expand all</button><button id="collapse">Collapse all</button>'
        '<button id="reset">Reset</button></div>',
    ]
    for sec, title in spec["sections"].items():
        plist = sections.get(sec, [])
        counts = status_counts(plist)
        mini = "".join(
            f'<span class="pill {st}" title="{st}">{counts[st]}</span>' for st in STATUSES if counts[st]
        )
        out.append(
            f'<details class="panel" open data-sec="{e(sec)}"><summary>'
            f'<span class="letter">{e(sec)}</span><span class="title">{e(title)}</span>'
            f'<span class="meta"><span class="shown">{len(plist)}</span> of {len(plist)} parameters</span>'
            f'<span class="mini">{mini}</span><span class="chev">&#9656;</span></summary>'
        )
        widths = (6, 11, 8, 6, 10, 6, 6, 12, 28, 7)
        out.append('<div class="wrap"><table><colgroup>' + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup><thead><tr>")
        out += [f'<th{" class=\"just\"" if c == "Justification" else ""}>{e(c)}</th>' for c in COLUMNS]
        out.append("</tr></thead><tbody>")
        for n, p in enumerate(plist):
            cells = rows_for(p)
            status = cells[-1]
            classes = [status]
            grp = p.get("group")
            if grp:
                classes.append("grouped")
                if n == 0 or plist[n - 1].get("group") != grp:
                    classes.append("group-first")
                if n == len(plist) - 1 or plist[n + 1].get("group") != grp:
                    classes.append("group-last")
            key = bool(p["eu"].get("key_difference"))
            if key:
                classes.append("key")
            todo = clean(p["eu"].get("todo"))
            out.append(f'<tr class="{e(" ".join(classes))}" data-status="{e(status)}" data-key="{int(key)}" data-todo="{int(bool(todo))}">')
            # symbol
            out.append(f'<td class="sym">{_sym(e, cells[0])}</td>')
            # parameter id + code location
            code = clean(p.get("code")) or "not in code"
            derived = '<span class="derived">[derived]</span>' if p.get("derived") else ""
            label = f'<span class="grouplabel">group: {e(grp)}</span>' if grp and "group-first" in classes else ""
            out.append(
                f'<td class="code">{"<span class=\"star\" title=\"key EU difference\">★</span>" if key else ""}'
                f'<span class="id">{e(p["id"])}</span>{derived}'
                f'<span class="loc">{e(code)}</span>{label}</td>'
            )
            out.append(f'<td class="meaning">{e(cells[2])}</td>')
            out.append(f'<td class="num">{_num(e, cells[3])}</td>')
            out.append(f'<td class="src">{structure(e, cells[4])}</td>')
            out.append(f'<td class="treat">{e(cells[5])}</td>')
            out.append(f'<td class="num euval">{_num(e, cells[6])}</td>')
            out.append(f'<td class="src">{structure(e, cells[7])}</td>')
            out.append(f'<td class="just">{structure(e, cells[8])}</td>')
            todo_html = f'<br><span class="pill todo">to-do</span><div class="todo-text">{e(todo)}</div>' if todo else ""
            out.append(f'<td><span class="pill {e(status)}">{e(status)}</span>{todo_html}</td>')
            out.append("</tr>")
        out.append('</tbody></table></div><div class="empty">No rows match the current filter.</div></details>')
    out.append(
        f"<footer>{len(spec['parameters'])} parameters. "
        + ", ".join(f"{totals[st]} {st}" for st in STATUSES)
        + ". Collapsed panels and filters are remembered in this browser.</footer>"
    )
    out.append(f"</div><script>{JS}</script></body></html>\n")
    return "\n".join(out)


def main() -> None:
    spec = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    (HERE / "calibration_parameters.html").write_text(render_html(spec), encoding="utf-8")
    print(f"wrote calibration_parameters.html, {len(spec['parameters'])} parameters")


if __name__ == "__main__":
    main()
