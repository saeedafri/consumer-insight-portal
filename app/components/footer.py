"""Coresight footer — the same furniture as the Market Data Portal."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

_FOOTER_CSS = """
<style>
.csi-footer {
  background: #2d2a29; color: #cfcdca;
  width: 100vw; margin-left: calc(-50vw + 50%); margin-right: calc(-50vw + 50%);
  margin-top: 56px; padding: 34px 0 22px 0;
  font-family: 'Inter', sans-serif; font-size: 13px; line-height: 1.7;
}
.csi-footer-inner {
  max-width: 1440px; margin: 0 auto; padding: 0 40px;
  display: flex; gap: 56px; flex-wrap: wrap;
}
.csi-footer h4 {
  color: #fff; font-size: 13px; font-weight: 600; margin: 0 0 10px 0;
  letter-spacing: .04em; text-transform: uppercase;
}
.csi-footer a { color: #cfcdca; text-decoration: none; }
.csi-footer a:hover { color: #fff; text-decoration: underline; }
.csi-footer-col { min-width: 190px; }
.csi-footer-brand { max-width: 330px; }
.csi-footer-brand img { width: 150px; margin-bottom: 12px; display: block; }
.csi-footer-bottom {
  max-width: 1440px; margin: 26px auto 0 auto; padding: 16px 40px 0 40px;
  border-top: 1px solid #45413f; color: #97948f; font-size: 12px;
  display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap;
}
@media (max-width: 900px) {
  .csi-footer-inner { gap: 28px; }
}
</style>
"""

LOGO = ("https://production-wordpress-cdn-dpa0g9bzd7b3h7gy.z03.azurefd.net"
        "/wp-content/uploads/2023/12/coresight-logo.png")


def render_footer(data_note: str = "") -> None:
    """Footer with the methodology note the research team needs on every page."""
    year = datetime.now().year
    note = data_note or (
        "Figures are computed on each question's own answering base. "
        "Most of this questionnaire is routed, so bases differ by question."
    )
    st.markdown(
        _FOOTER_CSS
        + f"""
<div class="csi-footer">
  <div class="csi-footer-inner">
    <div class="csi-footer-col csi-footer-brand">
      <img src="{LOGO}" alt="Coresight Research">
      <div>Consumer Insight Portal — survey analytics on the CSI tables in
      <code style="color:#e0ded9">dwh_stg</code>.</div>
    </div>
    <div class="csi-footer-col">
      <h4>Portal</h4>
      <div><a href="/" target="_self">Overview</a></div>
      <div><a href="/questions" target="_self">Questions</a></div>
      <div><a href="/analysis" target="_self">Analysis Builder</a></div>
      <div><a href="/crosstabs" target="_self">Cross-tabs</a></div>
    </div>
    <div class="csi-footer-col">
      <h4>Data</h4>
      <div><a href="/trends" target="_self">Trends</a></div>
      <div><a href="/data-health" target="_self">Data health</a></div>
      <div><a href="https://se1.decipherinc.com" target="_blank" rel="noopener">Forsta Surveys ↗</a></div>
    </div>
    <div class="csi-footer-col" style="max-width:320px">
      <h4>Reading the numbers</h4>
      <div>{note}</div>
    </div>
  </div>
  <div class="csi-footer-bottom">
    <div>© {year} Coresight Research. Internal use only — client-confidential survey data.</div>
    <div>Source: Forsta Surveys · se1.decipherinc.com</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
