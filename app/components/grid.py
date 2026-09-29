"""Interactive tables.

AG Grid where it is installed — sortable, resizable, with the label column
pinned so it stays visible while an analyst scrolls a wide banner — and a
graceful fall back to `st.dataframe` where it is not, so a missing optional
dependency never takes a page down.
"""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import streamlit as st

try:
    from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder, JsCode
    HAS_AGGRID = True
except Exception:  # noqa: BLE001
    HAS_AGGRID = False
    JsCode = None  # type: ignore[assignment]

# Columns worth pinning to the left, in order of preference.
_PIN_PRIORITY = ("Answer", "Item", "Row", "Question", "Statement", "Segment", "Wave")

_PCT_FORMATTER = """
function(params) {
  if (params.value === null || params.value === undefined || params.value === '') return '';
  return (params.value * 100).toFixed(1) + '%';
}
"""

_THEME_CSS = {
    "--ag-font-family": "Inter, Helvetica, Arial, sans-serif",
    "--ag-font-size": "13px",
    "--ag-header-background-color": "#f0f0f0",
    "--ag-header-foreground-color": "#2d2a29",
    "--ag-odd-row-background-color": "#fafafa",
    "--ag-row-hover-color": "#fdeceb",
    "--ag-selected-row-background-color": "#fdeceb",
    "--ag-border-color": "#e0e0e0",
}


def _pin_column(df: pd.DataFrame) -> Optional[str]:
    for name in _PIN_PRIORITY:
        if name in df.columns:
            return name
    return df.columns[0] if len(df.columns) else None


def show(
    df: pd.DataFrame,
    percent_columns: Sequence[str] = ("%", "pct", "Share"),
    height: Optional[int] = None,
    key: str = "grid",
) -> None:
    """Render a table. Same call whether or not AG Grid is available."""
    if df is None or df.empty:
        st.info("Nothing to show for this selection.")
        return

    if not HAS_AGGRID:
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={
                c: st.column_config.NumberColumn(format="%.1f%%")
                for c in df.columns if str(c) in percent_columns
            },
        )
        st.caption("Install `streamlit-aggrid` for sortable, resizable columns.")
        return

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        sortable=True, filter=True, resizable=True, wrapText=True, autoHeight=False,
        cellStyle={"fontSize": "13px"},
    )
    pin = _pin_column(df)
    if pin:
        gb.configure_column(pin, pinned="left", minWidth=240,
                            cellStyle={"fontWeight": "500"})
    for col in df.columns:
        if str(col) in percent_columns:
            gb.configure_column(col, type=["numericColumn"], minWidth=110,
                                valueFormatter=JsCode(_PCT_FORMATTER))
        elif pd.api.types.is_numeric_dtype(df[col]):
            gb.configure_column(col, type=["numericColumn"], minWidth=100)
    gb.configure_grid_options(
        domLayout="normal",
        suppressFieldDotNotation=True,
        enableCellTextSelection=True,
        ensureDomOrder=True,
    )

    rows = len(df)
    AgGrid(
        df,
        gridOptions=gb.build(),
        height=height or min(620, 42 + 30 * min(rows, 18)),
        theme="balham",
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        custom_css={".ag-theme-balham": _THEME_CSS},
        key=key,
        reload_data=False,
        update_mode="NO_UPDATE",
    )
    st.caption(f"{rows:,} rows · click a header to sort, drag its edge to resize.")
