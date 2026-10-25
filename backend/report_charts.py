"""Static A4 report charts from frozen, previously verified aggregate evidence.

Presentation only: never query/recalculate a dataset, invent a trend or silently
use per-record scatter coordinates in PDF/HTML reports. Both renderers consume
the same bounded numeric points, labels and visible source limitations.
"""
from __future__ import annotations

from html import escape
import math

from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle
from reportlab.lib import colors

SUPPORTED = {"bar": 12, "histogram": 24, "line": 18}


def visual_spec(chart: dict | None) -> dict | None:
    """Return a bounded plot projection, or abstain for unsupported charts."""
    if not isinstance(chart, dict):
        return None
    kind = chart.get("type")
    if kind not in SUPPORTED or not isinstance(chart.get("data"), list):
        return None
    points = []
    for item in chart["data"][:SUPPORTED[kind]]:
        if not isinstance(item, dict):
            return None
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        label = item.get("label")
        if not isinstance(label, str):
            return None
        # Category values are saved chart aggregates, never source-record IDs.
        points.append({"label": label[:90], "value": float(value)})
    if not points:
        return None
    # Never treat a cropped representation as the full population or groups.
    limited = len(chart["data"]) > len(points) or bool(chart.get("truncated")) or bool(chart.get("sampled"))
    note = chart.get("note", "")
    if not isinstance(note, str):
        note = ""
    if limited:
        note += (" " if note else "") + "Visual shows a bounded subset of saved chart groups; see verified table and provenance."
    return {
        "type": kind,
        "x": str(chart.get("x") or "")[:90],
        "y": str(chart.get("y") or "")[:90],
        "aggregation": str(chart.get("aggregation") or "")[:30],
        "data": points,
        "limited": limited,
        "note": note[:600],
    }


def _domain(spec: dict) -> tuple[float, float]:
    vals = [point["value"] for point in spec["data"]]
    low, high = min(0.0, min(vals)), max(0.0, max(vals))
    if low == high:
        return (low - 1.0, high + 1.0)
    return low, high


def _number(number: float) -> str:
    return format(number, ".5g")


def _x_indices(spec: dict) -> set[int]:
    n = len(spec["data"])
    if spec["type"] == "histogram":
        return {0, n-1}
    if n <= 6:
        return set(range(n))
    return {0, n//3, (2*n)//3, n-1}


def html_chart(spec: dict) -> str:
    """Accessible self-contained SVG: inline, without browser/network scripts."""
    width, height = 620, 238
    left, right, bottom, top = 68.0, 605.0, 50.0, 18.0
    plot_w, plot_h = right-left, height-bottom-top
    low, high = _domain(spec)
    y = lambda val: bottom + (val-low)/(high-low)*plot_h
    baseline = y(0.0)
    n = len(spec["data"])
    step = plot_w / n
    axis = escape(spec["y"] or ("Frequency" if spec["type"] == "histogram" else spec["aggregation"] or "Value"))
    group = escape(spec["x"] or "Group")
    result = [f'<figure class="verified-chart"><svg viewBox="0 0 {width} {height}" role="img" '
              f'aria-label="Saved {escape(spec["type"])} chart. {n} plotted aggregate values, '
              f'version-linked values listed in the evidence table.">',
              '<rect x="0" y="0" width="620" height="238" rx="10" fill="#fafbfe"/>']
    for tick in sorted(set([low, 0.0, high])):
        ordinate = height - y(tick)
        result.append(f'<line x1="{left}" y1="{ordinate:.2f}" x2="{right}" y2="{ordinate:.2f}" '
                      'stroke="#dae0ef" stroke-width="1"/>')
        result.append(f'<text x="{left-8}" y="{ordinate+4:.2f}" text-anchor="end" '
                      f'font-size="11" fill="#566581">{escape(_number(tick))}</text>')
    for i, point in enumerate(spec["data"]):
        val, name = point["value"], point["label"]
        px = left + step*(i+.5)
        yp = height-y(val)
        desc = escape(f'{name}: {_number(val)}')
        if spec["type"] == "line":
            if i:
                prev = spec["data"][i-1]
                result.append(f'<line x1="{left+step*(i-.5):.2f}" y1="{height-y(prev["value"]):.2f}" '
                              f'x2="{px:.2f}" y2="{yp:.2f}" stroke="#4936af" stroke-width="2.5"/>')
            result.append(f'<circle cx="{px:.2f}" cy="{yp:.2f}" r="3.5" fill="#087e8b"><title>{desc}</title></circle>')
        else:
            bar_w = step*(.96 if spec["type"] == "histogram" else .68)
            top_y = min(yp, height-baseline)
            rect_h = max(1.0, abs(yp-(height-baseline)))
            result.append(f'<rect x="{px-bar_w/2:.2f}" y="{top_y:.2f}" width="{bar_w:.2f}" '
                          f'height="{rect_h:.2f}" fill="#087e8b"><title>{desc}</title></rect>')
        if i in _x_indices(spec):
            label = name if len(name) <= 14 else name[:11] + "…"
            result.append(f'<text x="{px:.2f}" y="{height-25}" text-anchor="middle" '
                          f'font-size="10" fill="#485673">{escape(label)}</text>')
    result.append(f'<text x="{(left+right)/2:.2f}" y="{height-5}" text-anchor="middle" '
                  f'font-size="11" fill="#28364e">{group}</text>')
    result.append(f'<text x="8" y="12" font-size="11" fill="#28364e">{axis}</text></svg>')
    result.append('<figcaption>Static visualization of saved aggregate values. '
                  'The accompanying evidence table contains the recorded numbers.')
    if spec["note"]:
        result.append(' '+escape(spec["note"]))
    result.append('</figcaption></figure>')
    return "".join(result)


def pdf_chart(spec: dict, width: float = 500.0) -> Drawing:
    """ReportLab vector plot; same projection and scaling as the HTML exhibit."""
    height = 220.0
    d = Drawing(width, height)
    left, right, bottom, top = 54.0, width-13.0, 45.0, 17.0
    plot_w, plot_h = right-left, height-bottom-top
    low, high = _domain(spec)
    y = lambda val: bottom + (val-low)/(high-low)*plot_h
    baseline = y(0.0)
    d.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#fafbfe"), strokeColor=None))
    for tick in sorted(set([low, 0.0, high])):
        yy = y(tick)
        d.add(Line(left, yy, right, yy, strokeColor=colors.HexColor("#dbe1ee"), strokeWidth=.65))
        d.add(String(left-6, yy-3, _number(tick), textAnchor="end", fontSize=7.5,
                     fillColor=colors.HexColor("#566581")))
    n = len(spec["data"])
    step = plot_w/n
    for i, point in enumerate(spec["data"]):
        x = left+step*(i+.5)
        ordinate = y(point["value"])
        if spec["type"] == "line":
            if i:
                prev = spec["data"][i-1]
                d.add(Line(left+step*(i-.5), y(prev["value"]), x, ordinate,
                           strokeColor=colors.HexColor("#4936af"), strokeWidth=2))
            d.add(Circle(x, ordinate, 2.8, fillColor=colors.HexColor("#087e8b"), strokeColor=None))
        else:
            bar_w = step*(.96 if spec["type"] == "histogram" else .68)
            d.add(Rect(x-bar_w/2, min(ordinate, baseline), bar_w,
                       max(1, abs(ordinate-baseline)),
                       fillColor=colors.HexColor("#087e8b"), strokeColor=None))
        if i in _x_indices(spec):
            label = point["label"]
            if len(label)>12:
                label = label[:10]+"..."
            d.add(String(x, 25, label, fontSize=7, textAnchor="middle",
                         fillColor=colors.HexColor("#485673")))
    d.add(String((left+right)/2, 7, spec["x"][:65] or "Group",
                 textAnchor="middle", fontSize=8, fillColor=colors.HexColor("#28364e")))
    d.add(String(5, height-12, (spec["y"] or ("Frequency" if spec["type"] == "histogram"
                                            else spec["aggregation"] or "Value"))[:50],
                 fontSize=8, fillColor=colors.HexColor("#28364e")))
    return d
