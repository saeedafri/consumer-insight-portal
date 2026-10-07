"""Sign in.

Reached by `require_auth` when a page is opened without a live session. Which
method appears depends on AUTH_PROVIDER — see docs/08-authentication.md.
"""
from __future__ import annotations

import time

import streamlit as st

from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config

render_header("", "", config.environment.value.upper())
page_title("Sign in", "Coresight Consumer Insight Portal")

mode = auth.provider()

if auth.is_authenticated():
    user = auth.current_user()
    st.success(f"Signed in as **{user.email if user else 'local-dev'}**.")
    if st.button("Continue to the portal", type="primary"):
        st.switch_page("pages/1_Overview.py")
    st.stop()

left, right = st.columns([3, 2])

with left:
    if mode == "oidc":
        st.markdown(
            "Sign in with your Coresight account. You will be redirected to the "
            "identity provider and returned here."
        )
        st.link_button("Continue with Coresight SSO",
                       f"{auth._env('IDP_BASE_URL')}/oauth/authorize", type="primary")
        st.caption(
            "If this does not complete, the redirect URI registered with the IdP "
            "probably does not match this host. `docs/08-authentication.md` lists "
            "what IT needs to register."
        )
    elif mode == "local":
        with st.form("csi_login"):
            email = st.text_input("Work email", placeholder="you@coresight.com")
            passphrase = st.text_input("Portal passphrase", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            good, message = auth.sign_in_local(email, passphrase)
            if good:
                # The session cookie is written by a browser component rendered in
                # this run; navigating at once discards it before it executes and
                # the user is signed out on the next page load.
                # ponytail: fixed pause; a server-set cookie would remove it
                time.sleep(1.0)
                st.switch_page("pages/1_Overview.py")
            else:
                st.error(message)
    else:
        st.warning(
            "**Authentication is switched off.** Anyone who can reach this host "
            "can read the survey microdata. That is acceptable on a laptop and "
            "nowhere else — set `AUTH_PROVIDER=local` (or `oidc`) before this "
            "goes on a shared server."
        )
        if st.button("Continue without signing in", type="primary"):
            st.switch_page("pages/1_Overview.py")

with right:
    st.markdown(
        """
        <div style="background:#fafafa;border:1px solid #e8e8e6;border-radius:10px;
                    padding:16px 18px;font-size:13px;color:#52514e;line-height:1.7">
          <strong style="color:#1a1a2e">What is behind this login</strong><br>
          Respondent-level consumer survey data — about 400 interviews per weekly wave,
          demographics, and every answer given.<br><br>
          It is client-confidential and not anonymised beyond the panel's own
          identifiers, so access is per person and every sign-in is recorded in
          <code>cip_auth_session</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )

render_footer()
