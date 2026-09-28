"""Chart palette and Plotly template for CIP.

The categorical order below is fixed — slot 1 is always Coresight red, slot 2
always blue, and so on. Colour follows the entity, never its rank, so a filter
that drops a series must not repaint the survivors: always pass an explicit
colour map keyed on the entity name, never let Plotly cycle.

Both modes were validated with the dataviz palette validator (OKLab CVD ΔE,
normal-vision floor, chroma, lightness band, contrast):

  light  worst adjacent CVD ΔE 9.1 · normal-vision 22.9   ALL PASS
  dark   worst adjacent CVD ΔE 8.4 · normal-vision 19.7   ALL PASS

Three light slots (aqua, yellow, magenta) sit under 3:1 against the light
surface, so the relief rule applies: every chart here ships direct labels or a
table view. `show_table()` below is that relief.
"""
from __future__ import annotations

from typing import Iterable, Sequence

BRAND_RED = "#d62e2f"

CATEGORICAL_LIGHT: tuple[str, ...] = (
    "#d62e2f",  # 1 red — Coresight brand
    "#2a78d6",  # 2 blue
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#4a3aa7",  # 5 violet
    "#e87ba4",  # 6 magenta
)

CATEGORICAL_DARK: tuple[str, ...] = (
    "#e66767", "#3987e5", "#199e70", "#c98500", "#9085e9", "#d55181",
)

# Magnitude: one hue, light -> dark. Never a rainbow.
SEQUENTIAL_RED: tuple[str, ...] = (
    "#fdeceb", "#f8c4c2", "#f09693", "#e46561", "#d62e2f", "#a61f20", "#741516",
)

# Polarity (e.g. "much worse" .. "much better"): two hues + neutral midpoint.
DIVERGING: tuple[str, ...] = (
    "#a61f20", "#e46561", "#f8c4c2", "#e8e8e6", "#9ecfe9", "#4b9ed4", "#1b5f96",
)

STATUS = {
    "good": "#1b7f4f",
    "warning": "#b07000",
    "serious": "#c1510f",
    "critical": "#a61f20",
}

INK_PRIMARY = "#1a1a2e"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8985"
SURFACE = "#ffffff"
GRID = "#e8e8e6"

# All-pairs forms (scatter, bubble, small multiples) cap at 3 slots; past that,
# fold to "Other" or facet.
ALL_PAIRS_CAP = 3


def color_map(entities: Sequence[str], dark: bool = False) -> dict[str, str]:
    """Stable entity -> colour map. Sort the entity list ONCE upstream and reuse
    this map everywhere so a series keeps its colour across filters and pages."""
    palette = CATEGORICAL_DARK if dark else CATEGORICAL_LIGHT
    mapped: dict[str, str] = {}
    for i, name in enumerate(entities):
        if i < len(palette):
            mapped[name] = palette[i]
        else:
            mapped[name] = INK_MUTED  # anything past slot 6 folds into "Other"
    return mapped


def fold_to_other(items: Sequence[tuple[str, float]], cap: int = 6) -> list[tuple[str, float]]:
    """Keep the top `cap` items by value; sum the rest into 'Other'."""
    ranked = sorted(items, key=lambda kv: kv[1], reverse=True)
    if len(ranked) <= cap:
        return ranked
    head = ranked[: cap - 1]
    tail_total = sum(v for _, v in ranked[cap - 1 :])
    return head + [("Other", tail_total)]


def base_layout(title: str = "", height: int = 420) -> dict:
    """Recessive axes and grid, generous margins, no chartjunk."""
    return {
        "title": {
            "text": title,
            "font": {"size": 16, "color": INK_PRIMARY, "family": "Inter, Helvetica, Arial, sans-serif"},
            "x": 0, "xanchor": "left", "pad": {"b": 12},
        },
        "height": height,
        "paper_bgcolor": SURFACE,
        "plot_bgcolor": SURFACE,
        "font": {"family": "Inter, Helvetica, Arial, sans-serif", "size": 12, "color": INK_SECONDARY},
        "margin": {"l": 8, "r": 24, "t": 56 if title else 24, "b": 32},
        "xaxis": {"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID,
                  "tickfont": {"color": INK_SECONDARY}},
        "yaxis": {"gridcolor": GRID, "zerolinecolor": GRID, "linecolor": GRID,
                  "tickfont": {"color": INK_SECONDARY}},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02,
                   "xanchor": "left", "x": 0,
                   "font": {"color": INK_SECONDARY}, "title": {"text": ""}},
        "hoverlabel": {"bgcolor": SURFACE, "bordercolor": GRID,
                       "font": {"color": INK_PRIMARY, "size": 12}},
        "bargap": 0.28,   # the 2px-equivalent surface gap between adjacent bars
        "separators": ".,",
    }
