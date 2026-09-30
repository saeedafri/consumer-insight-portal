"""Plotly chart builders for CSI.

One builder per job:
    magnitude across items        -> horizontal_bar
    composition of a whole        -> donut (<= 5 slices, else horizontal_bar)
    polarity on an ordered scale  -> diverging_stack
    change over time              -> trend_line
    one headline number           -> stat_tile

Every chart ships a hover layer and — because three light-mode slots sit under
3:1 contrast — either direct labels or an accompanying table (`show_table`).
Never a dual-axis chart: two measures of different scale get two charts.
"""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .theme import (
    BRAND_RED, DIVERGING, GRID, INK_MUTED, INK_PRIMARY, INK_SECONDARY,
    SEQUENTIAL_RED, base_layout, color_map, fold_to_other,
)


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def horizontal_bar(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str = "",
    color: str = BRAND_RED,
    base_n: Optional[int] = None,
    max_items: int = 20,
) -> go.Figure:
    """Magnitude across named items. Sorted descending, direct-labelled."""
    d = df.dropna(subset=[value_col]).sort_values(value_col, ascending=True).tail(max_items)
    fig = go.Figure(
        go.Bar(
            x=d[value_col], y=d[label_col], orientation="h",
            marker={"color": color, "line": {"width": 0}},
            text=[_pct(v) for v in d[value_col]],
            textposition="outside",
            textfont={"color": INK_SECONDARY, "size": 11},
            hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>",
            cliponaxis=False,
        )
    )
    layout = base_layout(title, height=max(260, 26 * len(d) + 110))
    layout["xaxis"].update({"tickformat": ".0%", "range": [0, min(1.0, float(d[value_col].max()) * 1.22)]})
    layout["yaxis"].update({"automargin": True, "showgrid": False})
    layout["margin"]["l"] = 8
    fig.update_layout(**layout)
    if base_n:
        # A percentage without its base is not a number an analyst can defend,
        # so it goes on the axis where it cannot be cropped out of a screenshot.
        fig.update_layout(xaxis_title=f"Base: n={base_n}",
                          xaxis_title_font={"size": 11, "color": INK_MUTED})
        fig.update_layout(margin={**fig.layout.margin.to_plotly_json(), "b": 52})
    return fig


def grouped_bar(
    df: pd.DataFrame, label_col: str, value_col: str, series_col: str,
    title: str = "", entity_order: Optional[Sequence[str]] = None,
) -> go.Figure:
    """Same measure compared across a few segments. Colour follows the entity."""
    entities = list(entity_order) if entity_order else sorted(df[series_col].unique())
    cmap = color_map(entities)
    fig = go.Figure()
    for name in entities:
        sub = df[df[series_col] == name]
        if sub.empty:
            continue
        fig.add_bar(
            name=name, x=sub[label_col], y=sub[value_col],
            marker={"color": cmap[name], "line": {"width": 1, "color": "#ffffff"}},
            hovertemplate=f"<b>{name}</b><br>%{{x}}<br>%{{y:.1%}}<extra></extra>",
        )
    layout = base_layout(title)
    layout["yaxis"].update({"tickformat": ".0%"})
    layout["xaxis"].update({"showgrid": False, "automargin": True})
    layout["barmode"] = "group"
    fig.update_layout(**layout)
    return fig


def donut(
    df: pd.DataFrame, label_col: str, value_col: str, title: str = "",
    center_text: str = "",
) -> go.Figure:
    """Composition of a whole. Only for <= 5 slices — beyond that use a bar."""
    items = fold_to_other(list(zip(df[label_col], df[value_col])), cap=5)
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    cmap = color_map(labels)
    fig = go.Figure(
        go.Pie(
            labels=labels, values=values, hole=0.58, sort=False,
            marker={"colors": [cmap[l] for l in labels],
                    "line": {"color": "#ffffff", "width": 2}},
            textinfo="label+percent", textposition="outside",
            textfont={"color": INK_SECONDARY, "size": 11},
            hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
        )
    )
    layout = base_layout(title, height=400)
    # every slice is labelled on the ring; a legend only collides with the title
    layout["showlegend"] = False
    layout["margin"] = {**layout.get("margin", {}), "l": 70, "r": 70}   # room for outside labels
    fig.update_layout(**layout)
    if center_text:
        fig.add_annotation(
            text=center_text, x=0.5, y=0.5, showarrow=False,
            font={"size": 22, "color": INK_PRIMARY},
        )
    return fig


def diverging_stack(
    df: pd.DataFrame, label_col: str, value_col: str, scale_col: str,
    scale_order: Sequence[str], title: str = "",
) -> go.Figure:
    """Ordered-scale polarity (much worse .. much better) as a 100% stack.

    Two hues plus a neutral midpoint, drawn straight from the diverging ramp so
    the middle of the scale is grey, never a third hue.
    """
    n = len(scale_order)
    idx = [round(i * (len(DIVERGING) - 1) / max(n - 1, 1)) for i in range(n)]
    colors = {name: DIVERGING[idx[i]] for i, name in enumerate(scale_order)}
    fig = go.Figure()
    for name in scale_order:
        sub = df[df[scale_col] == name]
        if sub.empty:
            continue
        fig.add_bar(
            name=name, y=sub[label_col], x=sub[value_col], orientation="h",
            marker={"color": colors[name], "line": {"color": "#ffffff", "width": 2}},
            hovertemplate=f"<b>{name}</b><br>%{{y}}<br>%{{x:.1%}}<extra></extra>",
        )
    layout = base_layout(title, height=max(260, 34 * df[label_col].nunique() + 120))
    layout["barmode"] = "stack"
    layout["xaxis"].update({"tickformat": ".0%", "range": [0, 1]})
    layout["yaxis"].update({"automargin": True, "showgrid": False})
    fig.update_layout(**layout)
    return fig


def trend_line(
    df: pd.DataFrame, x_col: str, value_col: str, series_col: Optional[str] = None,
    title: str = "", entity_order: Optional[Sequence[str]] = None,
) -> go.Figure:
    """Wave-over-wave change. 2px lines, >=8px markers, crosshair hover."""
    fig = go.Figure()
    if series_col:
        entities = list(entity_order) if entity_order else sorted(df[series_col].unique())
        cmap = color_map(entities)
        for name in entities:
            sub = df[df[series_col] == name].sort_values(x_col)
            if sub.empty:
                continue
            fig.add_scatter(
                x=sub[x_col], y=sub[value_col], name=name, mode="lines+markers",
                line={"color": cmap[name], "width": 2},
                marker={"size": 8, "color": cmap[name],
                        "line": {"color": "#ffffff", "width": 2}},
                hovertemplate=f"<b>{name}</b><br>%{{x}}<br>%{{y:.1%}}<extra></extra>",
            )
    else:
        d = df.sort_values(x_col)
        fig.add_scatter(
            x=d[x_col], y=d[value_col], mode="lines+markers",
            line={"color": BRAND_RED, "width": 2},
            marker={"size": 8, "color": BRAND_RED, "line": {"color": "#ffffff", "width": 2}},
            hovertemplate="%{x}<br>%{y:.1%}<extra></extra>",
        )
    layout = base_layout(title)
    layout["yaxis"].update({"tickformat": ".0%"})
    layout["xaxis"].update({"showgrid": False})
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return fig


def heatmap(
    df: pd.DataFrame, x_col: str, y_col: str, value_col: str, title: str = ""
) -> go.Figure:
    """Question x segment magnitude grid. Single-hue sequential ramp."""
    pivot = df.pivot_table(index=y_col, columns=x_col, values=value_col, aggfunc="mean")
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values, x=list(pivot.columns), y=list(pivot.index),
            colorscale=[[i / (len(SEQUENTIAL_RED) - 1), c] for i, c in enumerate(SEQUENTIAL_RED)],
            hovertemplate="<b>%{y}</b><br>%{x}<br>%{z:.1%}<extra></extra>",
            colorbar={"tickformat": ".0%", "outlinewidth": 0, "thickness": 12},
            xgap=2, ygap=2,
        )
    )
    layout = base_layout(title, height=max(300, 28 * len(pivot.index) + 140))
    layout["xaxis"].update({"showgrid": False, "automargin": True})
    layout["yaxis"].update({"showgrid": False, "automargin": True})
    fig.update_layout(**layout)
    return fig


def stat_tile(label: str, value: str, caption: str = "") -> None:
    """One headline number. No plot, so no hover layer needed."""
    st.markdown(
        f"""
        <div style="border:1px solid {GRID};border-radius:10px;padding:14px 16px;background:#fff;">
          <div style="font-size:12px;color:{INK_SECONDARY};letter-spacing:.02em;">{label}</div>
          <div style="font-size:28px;font-weight:600;color:{INK_PRIMARY};line-height:1.25;">{value}</div>
          <div style="font-size:11px;color:{INK_MUTED};">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_table(df: pd.DataFrame, label: str = "View the data") -> None:
    """The table view every chart on this page is required to offer."""
    with st.expander(label):
        st.dataframe(df, width="stretch", hide_index=True)
