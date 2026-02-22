"""
Infosys Cobalt — Migration Analyzer
=====================================================
• All outputs dynamically computed from user inputs
• ZERO data stored, cached, or persisted on server
• Session data lives ONLY in browser memory
• Export generates fresh Excel/CSV on-the-fly, then discards
• Streaming results — each server appears as it completes
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io, os, datetime
from openpyxl.styles import Font, PatternFill, Alignment
from typing import Dict, List

try:
    import markdown as md_lib
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

from pricing_engine import (
    calculate_all_outputs, AWS_REGIONS, AZURE_REGIONS,
    check_aws_connectivity, check_azure_connectivity, check_anthropic_connectivity,
    set_aws_credentials,
)
from recommendation_engine import get_ai_recommendation, get_batch_ai_summary

# Enhancement modules — optional imports for graceful degradation
try:
    from validation import validate_server_inputs, validate_bulk_dataframe
    HAS_VALIDATION = True
except ImportError:
    HAS_VALIDATION = False

try:
    from scenario_engine import (
        run_sensitivity_analysis, calculate_roi_breakeven,
        project_costs, generate_wave_plan,
    )
    HAS_SCENARIOS = True
except ImportError:
    HAS_SCENARIOS = False

try:
    from currency_converter import (
        get_supported_currencies, get_symbol, get_multiplier,
        fetch_live_rates, CURRENCY_SYMBOLS, FALLBACK_RATES,
    )
    HAS_CURRENCY = True
except ImportError:
    HAS_CURRENCY = False
    CURRENCY_SYMBOLS = {"USD": "$"}
    FALLBACK_RATES = {"USD": 1.0}

try:
    from auth import AuthManager, render_login_page, ai_rate_limiter
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False

try:
    from audit_logger import AuditLogger
    HAS_AUDIT = True
except ImportError:
    HAS_AUDIT = False

try:
    from discovery import discover_matilda_api, discover_matilda_file
    HAS_DISCOVERY = True
except ImportError:
    HAS_DISCOVERY = False

try:
    from monitoring import metrics
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False

try:
    from pricing_cache import pricing_cache
    HAS_PRICING_CACHE = True
except ImportError:
    HAS_PRICING_CACHE = False

try:
    from pdf_report import generate_pdf_report
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from run_history import RunHistory
    HAS_HISTORY = True
except ImportError:
    HAS_HISTORY = False

try:
    from retry_utils import get_circuit_breaker_status
    HAS_RETRY = True
except ImportError:
    HAS_RETRY = False

try:
    from async_processor import BatchProcessor
    HAS_ASYNC = True
except ImportError:
    HAS_ASYNC = False


def render_ai_analysis(text: str, title: str = "Claude AI Analysis"):
    """Render AI markdown response as a beautifully formatted card."""
    if HAS_MARKDOWN:
        html_content = md_lib.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    else:
        # Fallback: basic conversion
        import re
        html_content = text
        html_content = re.sub(r'^### (.+)$', r'<h5>\1</h5>', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
        html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
        html_content = html_content.replace('\n\n', '<br><br>').replace('\n', '<br>')
    st.markdown(f'''<div class="ai-box">
        <h4 style="margin:0 0 .3rem 0;">AI Analysis &mdash; {title}</h4>
        <div class="ai-subtitle">AI-generated analysis &mdash; verify figures against computed data above</div>
        {html_content}
    </div>''', unsafe_allow_html=True)


def _paginated_dataframe(df, key_prefix, page_size=100, height_cap=500):
    """Display a DataFrame with pagination controls for large datasets.

    For datasets <= page_size rows, displays normally (no pagination overhead).
    For larger datasets, shows page navigation with configurable rows-per-page.
    """
    total_rows = len(df)
    if total_rows <= page_size:
        st.dataframe(df, use_container_width=True,
                      height=min(height_cap, 50 + total_rows * 35))
        return

    # ── Pagination controls ──
    c_rpp, c_page, c_info, c_jump = st.columns([1, 1, 2, 1])
    with c_rpp:
        rpp = st.selectbox("Rows / page", [50, 100, 200, 500],
                           index=[50, 100, 200, 500].index(page_size)
                           if page_size in [50, 100, 200, 500] else 1,
                           key=f"{key_prefix}_rpp")
    total_pages = max(1, (total_rows + rpp - 1) // rpp)
    with c_page:
        page = st.number_input("Page", min_value=1, max_value=total_pages,
                               value=1, step=1, key=f"{key_prefix}_pg")
    start = (page - 1) * rpp
    end = min(start + rpp, total_rows)
    with c_info:
        st.markdown(f"<br><span style='color:#8B98A8;'>Rows **{start + 1:,}**–**{end:,}** of "
                    f"**{total_rows:,}** &nbsp;|&nbsp; Page {page} of {total_pages}</span>",
                    unsafe_allow_html=True)
    with c_jump:
        if total_pages > 10:
            jump = st.selectbox("Jump to", ["First", "Last"],
                                key=f"{key_prefix}_jmp", label_visibility="collapsed")
            if jump == "Last" and page != total_pages:
                st.session_state[f"{key_prefix}_pg"] = total_pages
                st.rerun()
            elif jump == "First" and page != 1:
                st.session_state[f"{key_prefix}_pg"] = 1
                st.rerun()

    # ── Display page slice ──
    page_df = df.iloc[start:end].reset_index(drop=True)
    st.dataframe(page_df, use_container_width=True,
                  height=min(height_cap, 50 + len(page_df) * 35))


# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Infosys Cobalt — Migration Analyzer", page_icon="💎",
                   layout="wide", initial_sidebar_state="expanded")

# ─── Custom CSS — Dark Enterprise Theme ─────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    :root {
        --primary:#4A9EFF; --primary-light:#1A2D4A; --primary-dark:#7FBFFF;
        --accent:#4A9EFF; --surface:#141922; --surface2:#1A1F2E; --surface3:#222836;
        --danger:#FF6B6B; --warn:#FFB347; --success:#4ADE80; --info:#4A9EFF;
        --text:#E0E6ED; --text-secondary:#8B98A8; --text-muted:#5E6B7A;
        --border:#2A3142; --border-light:#232A3A;
    }
    .stApp { font-family:'Inter',system-ui,-apple-system,sans-serif; }
    /* Scrollbar */
    ::-webkit-scrollbar { background: #0E1117; width: 8px; }
    ::-webkit-scrollbar-thumb { background: #2A3142; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #3A4558; }
    /* Header */
    .main-header { background:var(--surface); padding:1.8rem 2.2rem; border-radius:12px; margin-bottom:1rem;
        border:1px solid var(--border); border-bottom:3px solid var(--primary); }
    .main-header h1 { font-size:1.75rem; font-weight:700; color:var(--text); margin:0 0 .25rem 0; letter-spacing:-0.3px; }
    .main-header p { color:var(--text-secondary); font-size:0.92rem; margin:0; }
    /* Compliance banner */
    .compliance-banner { background:var(--primary-light); border:1px solid #2A4060;
        border-radius:8px; padding:0.7rem 1.2rem; margin-bottom:1rem; display:flex; align-items:center; gap:0.8rem; }
    .compliance-banner .icon { font-size:1.2rem; }
    .compliance-banner .text { color:var(--primary-dark); font-size:0.82rem; font-weight:500; }
    /* Metric cards */
    .metric-card { background:var(--surface); padding:1.1rem 1.4rem; border-radius:10px;
        border:1px solid var(--border); border-left:4px solid var(--primary); margin-bottom:0.7rem;
        box-shadow:0 2px 6px rgba(0,0,0,0.2); }
    .metric-card .label { color:var(--text-muted); font-size:0.72rem; text-transform:uppercase;
        letter-spacing:0.8px; font-weight:600; margin-bottom:4px; }
    .metric-card .value { color:var(--text); font-size:1.4rem; font-weight:700;
        font-family:'IBM Plex Mono',monospace; }
    .metric-card .sub { color:var(--primary); font-size:0.8rem; margin-top:2px; font-weight:500; }
    .metric-red { border-left-color:var(--danger)!important; }
    .metric-red .sub { color:var(--danger); }
    .metric-blue { border-left-color:var(--info)!important; }
    .metric-blue .sub { color:var(--info); }
    .metric-yellow { border-left-color:var(--warn)!important; }
    .metric-yellow .sub { color:var(--warn); }
    /* Section headers */
    .section-header { font-size:0.82rem; font-weight:700; color:var(--primary); padding-bottom:0.5rem;
        border-bottom:2px solid var(--border); margin:1.5rem 0 1rem 0; text-transform:uppercase; letter-spacing:1.2px; }
    /* Output tables */
    .output-table { background:var(--surface); border-radius:10px; overflow:hidden; margin-bottom:1rem;
        border:1px solid var(--border); }
    .output-table table { width:100%; border-collapse:collapse; }
    .output-table th { background:var(--surface2); color:var(--primary); padding:.65rem 1rem;
        text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:0.8px; font-weight:600; }
    .output-table td { padding:.55rem 1rem; color:var(--text); border-bottom:1px solid var(--border);
        font-family:'IBM Plex Mono',monospace; font-size:.85rem; }
    .output-table tr:last-child td { border-bottom:none; }
    .output-table tr:hover td { background:var(--surface2); }
    /* AI analysis box */
    .ai-box { background:var(--surface); border:1px solid var(--border); border-left:4px solid var(--primary);
        border-radius:10px; padding:1.8rem 2rem; margin:1.2rem 0; box-shadow:0 2px 6px rgba(0,0,0,0.2); }
    .ai-box h4 { color:var(--primary); margin:0 0 .3rem 0; font-size:1.1rem; }
    .ai-box .ai-subtitle { color:var(--text-muted); font-size:.8rem; margin-bottom:1rem;
        padding-bottom:.6rem; border-bottom:1px solid var(--border); }
    .ai-box h5 { color:var(--primary-dark); margin:1.2rem 0 .4rem 0;
        border-bottom:1px solid var(--border); padding-bottom:.3rem; font-size:.95rem; }
    .ai-box p { color:var(--text); line-height:1.65; margin:0.4rem 0; }
    .ai-box ul, .ai-box ol { color:var(--text); padding-left:1.4rem; }
    .ai-box li { margin:0.3rem 0; line-height:1.55; }
    .ai-box strong { color:var(--primary-dark); }
    .ai-box code { background:var(--primary-light); color:var(--primary); padding:1px 5px; border-radius:3px; font-size:.85rem; }
    .ai-box table { width:100%; border-collapse:collapse; margin:.6rem 0; }
    .ai-box table th { background:var(--surface2); color:var(--primary); padding:.5rem .8rem; text-align:left;
        border-bottom:2px solid var(--border); font-size:.78rem; font-weight:600; }
    .ai-box table td { padding:.4rem .8rem; border-bottom:1px solid var(--border); color:var(--text);
        font-size:.82rem; }
    .ai-box table tr:hover td { background:var(--surface2); }
    .ai-box hr { border:none; border-top:1px solid var(--border); margin:1rem 0; }
    /* Badges */
    .badge { display:inline-block; padding:.2rem .6rem; border-radius:20px; font-size:.73rem; font-weight:600; }
    .badge-live { background:#0D2E1A; color:var(--success); border:1px solid #1A5C33; }
    .badge-ref { background:var(--primary-light); color:var(--primary); border:1px solid #2A4060; }
    /* Server card */
    .server-card { background:var(--surface); border-radius:10px; padding:1rem 1.2rem; margin:.6rem 0;
        border:1px solid var(--border); border-left:3px solid var(--primary); }
    .server-card .sname { color:var(--text); font-weight:700; font-size:1rem; }
    .server-card .sdetail { color:var(--text-secondary); font-size:.82rem; margin-top:4px; }
    /* Cost breakdown */
    .cost-breakdown { background:var(--surface2); border-radius:8px; padding:1rem 1.2rem; margin:.5rem 0;
        font-size:.85rem; border:1px solid var(--border); }
    .cost-breakdown .cb-row { display:flex; justify-content:space-between; padding:3px 0; color:var(--text-secondary); }
    .cost-breakdown .cb-total { border-top:2px solid var(--border); margin-top:6px; padding-top:6px;
        font-weight:700; color:var(--text); }
    /* Connectivity indicators */
    .conn-indicator { display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:8px;
        margin:4px 0; font-size:.82rem; }
    .conn-ok { background:#0D2E1A; border:1px solid #1A5C33; color:var(--success); }
    .conn-err { background:#2E0D0D; border:1px solid #5C1A1A; color:var(--danger); }
    .conn-warn { background:#2E2A0D; border:1px solid #5C4D1A; color:var(--warn); }
    .conn-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
    .conn-dot-ok { background:var(--success); }
    .conn-dot-err { background:var(--danger); }
    .conn-dot-warn { background:var(--warn); }
    .source-tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:.72rem;
        background:var(--primary-light); color:var(--primary); border:1px solid #2A4060; margin:2px 0; }
    .method-box { background:var(--surface); border-radius:10px; padding:1.2rem; margin:.8rem 0;
        border:1px solid var(--border); font-size:.85rem; }
    /* Streamlit overrides for enterprise look */
    .stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:2px solid var(--border); }
    .stTabs [data-baseweb="tab"] { font-weight:600; font-size:.85rem; letter-spacing:0.2px;
        padding:0.7rem 1.4rem; color:var(--text-secondary); }
    .stTabs [aria-selected="true"] { color:var(--primary); border-bottom:3px solid var(--primary); }
    div[data-testid="stExpander"] { border:1px solid var(--border); border-radius:8px; }
    div[data-testid="stExpander"] summary { font-weight:600; color:var(--text); }
</style>
""", unsafe_allow_html=True)

# ─── RBAC Authentication Gate ────────────────────────────────────────────────
if HAS_AUTH:
    # Initialize auth manager once
    if "_auth_mgr" not in st.session_state:
        st.session_state["_auth_mgr"] = AuthManager()
    _auth = st.session_state["_auth_mgr"]

    # Check if already logged in and session still valid
    _user = st.session_state.get("_auth_user")
    if _user and not _auth.is_session_valid(_user):
        st.session_state.pop("_auth_user", None)
        _user = None

    if not _user:
        _user = render_login_page(st)
        if not _user:
            st.stop()

    # Logged-in user info for sidebar display
    _current_user = st.session_state.get("_auth_user", {})
    _current_role = _current_user.get("role", "viewer")
    _current_perms = _current_user.get("permissions", [])

    def _has_perm(perm: str) -> bool:
        return perm in _current_perms
else:
    # No auth module — full access
    _current_user = {"username": "local", "role": "admin", "display_name": "Local User",
                     "permissions": ["view_dashboard", "analyze_servers", "export_data",
                                     "ai_analysis", "manage_users", "view_audit_log",
                                     "bulk_upload", "scenario_analysis", "auto_discovery"]}
    _current_role = "admin"
    _current_perms = _current_user["permissions"]

    def _has_perm(perm: str) -> bool:
        return True

st.markdown("""
<div class="main-header">
    <h1>Infosys Cobalt &mdash; Migration Analyzer</h1>
    <p>Enterprise Right-Sizing &bull; Real-Time Pricing &bull; AI Recommendations &mdash; AWS, Azure &amp; Azure Local</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="compliance-banner">
    <div class="icon">&#x1F512;</div>
    <div class="text">COMPLIANCE MODE &mdash; Zero data persistence. All data computed in-memory,
    never stored. Session discarded on close. Export generates fresh files on-the-fly.</div>
</div>
""", unsafe_allow_html=True)

# ─── On-Prem Cost Methodology Guidance (always visible) ─────────────────────
with st.expander("📖 How On-Premises / Data Center Costs Are Calculated — Industry-Sourced Rates", expanded=False):
    st.markdown("""
All on-prem costs are derived from **published vendor pricing and industry benchmarks**, not generic estimates.
Each server's annual TCO is calculated as a sum of 7 components:
""")
    meth_c1, meth_c2 = st.columns(2)
    with meth_c1:
        st.markdown("""
##### 🖥️ Hardware Costs (amortized over 5-year lifecycle)

| Component | Rate | Source |
|-----------|------|--------|
| **Compute** | `$130/vCPU/yr` | Dell PowerEdge R760 (2×Xeon 5th Gen, 64-core) base ~$10K-$15K. Amortized over 5 years → $125-$187/vCPU/yr. Source: [dell.com/poweredge-r760](https://dell.com/poweredge-r760), TerraZone 5-Year TCO (2025) |
| **Memory** | `$10/GB/yr` | DDR5 64GB ECC RDIMM at enterprise volume $240-$615/module. Amortized 5 years. Source: Counterpoint Research DRAM Report 2025, Samsung DDR5 pricing |
| **Storage** | `$0.08/GB/yr` | Blended 70/30 SSD/HDD enterprise mix. NVMe SSD: $0.10-$0.25/GB, HDD: $0.02-$0.04/GB. Amortized 5 years |

##### ⚡ Power & Cooling (Dynamic Calculation)

```
Power Cost = vCPUs × 25W × PUE × 8,760 hrs × $/kWh
```

| Parameter | Value | Source |
|-----------|-------|--------|
| Per-vCPU power draw | `25W` | Intel Xeon 4th/5th Gen typical under mixed workload |
| PUE (Power Usage Effectiveness) | `1.55` | Uptime Institute Global Data Center Survey 2024 (industry average; hyperscale ~1.2, enterprise ~1.5-1.8) |
| Electricity rate | `$0.12/kWh` | US Energy Information Administration (EIA) industrial average 2024 |
""")
    with meth_c2:
        st.markdown("""
##### 🏢 Facility & Operations

| Component | Rate | Source |
|-----------|------|--------|
| **Facility / Rack** | `$1,200/server/yr` | Colocation $1K-$2.5K/rack/mo, 42U rack shared across 10-20 servers. Source: ENCOR Advisors & Brightlio Colocation Pricing Guide (2025) |
| **Admin & Labor** | `$1,500/server/yr` | 1 SysAdmin per 50-100 servers @ $80K-$120K salary. Includes patching, monitoring, incident response. Source: Gartner IT staffing benchmarks, Sherweb TCO Analysis |

##### 📜 OS Licensing (Per vCPU/Month)

| OS | Rate | Source |
|----|------|--------|
| Windows Server 2025 Std | `$5.50/vCPU/mo` | Dell PowerEdge R760 configurator: $2,135/16-core → $133/core/yr |
| Red Hat Enterprise Linux | `$3.00/vCPU/mo` | RHEL Premium 2-socket: $1,430/yr normalized |
| SUSE Linux Enterprise | `$2.50/vCPU/mo` | SLES enterprise subscription pricing |
| Ubuntu / Debian / Amazon Linux | `$0` | Open source — no licensing cost |

##### ⚠️ What's NOT Included (Conservative Estimate)
Network equipment, backup/DR infrastructure, security hardware, compliance audits, insurance, spare parts inventory.
*Including these would add ~15-30% to on-prem costs.*

##### 📅 Rates Last Verified: Q4 2025
""")
    st.caption("💡 **Tip:** To customize rates (e.g., your actual electricity cost or PUE), edit the constants in `pricing_engine.py → compute_on_prem()`.")

with st.expander("🔷 Azure Local (formerly Azure Stack HCI) — Hybrid Pricing Methodology", expanded=False):
    st.markdown("""
Azure Local extends Azure to your **own on-premises hardware** with Azure Arc management, billed per physical core through your Azure subscription.
The tool calculates **3 scenarios** per server:
""")
    al1, al2 = st.columns(2)
    with al1:
        st.markdown("""
##### 💰 Azure Local Service Fees

| Scenario | Rate | What's Included |
|----------|------|-----------------|
| **Host Fee Only** (Linux guests) | `$10/physical core/mo` | Azure Local host service, Azure Arc management, AKS (2402+) |
| **Host + Windows Server Subscription** | `$23.30/physical core/mo` | Host fee + unlimited Windows Server guest licensing rights |
| **Azure Hybrid Benefit** | `$0/mo` | WS Datacenter w/ active Software Assurance waives both host and WS subscription fees |

##### 📐 How It's Calculated
```
Azure Local Annual = On-Prem HW & Ops (excl. OS licensing)
                   + Azure Local Service Fee × 12 months
```
- Hardware, power, facility, and labor costs are **identical** to the on-prem model (same physical servers)
- OS licensing is **replaced** by the Azure Local service fee / WS subscription
""")
    with al2:
        st.markdown("""
##### 📋 Key Facts
- **Billing:** Per physical processor core, daily basis (no hyper-threading in count)
- **Free trial:** 60 days after registration
- **AKS:** Included at no extra charge (release 2402+, effective Jan 2025)
- **vCPU proxy:** Tool uses vCPU count as proxy for physical cores (noted in output)
- **OEM licensing:** Alternative — pre-installed license valid for hardware lifetime (via OEM partner)

##### 🔗 Source
[Azure Local Pricing](https://azure.microsoft.com/en-us/pricing/details/azure-local/) (azure.microsoft.com)
[Azure Local Licensing Explained](https://www.techielass.com/azure-local-licensing-explained/) (techielass.com, Feb 2025)
[Microsoft Q&A — Azure Stack HCI Billing](https://learn.microsoft.com/en-us/answers/questions/1001165/) (learn.microsoft.com)

##### 📅 Rates Last Verified: Q1 2025
""")
    st.caption("💡 **Note:** Azure Hybrid Benefit requires Windows Server Datacenter licenses with active Software Assurance. Consult your Microsoft Licensing Solution Provider (LSP) for eligibility.")

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # User info and logout
    if HAS_AUTH and _current_user.get("username") != "local":
        _role_label = _auth.get_role_label(_current_role) if HAS_AUTH else _current_role
        st.markdown(f"**{_current_user.get('display_name', 'User')}** &nbsp; `{_role_label}`")
        if st.button("Logout", key="logout_btn"):
            st.session_state.pop("_auth_user", None)
            st.rerun()
        st.markdown("---")
    st.markdown("### Configuration")
    st.markdown("---")
    st.markdown("**Claude AI**")
    _secrets_key = ""
    try:
        _secrets_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    if not _secrets_key:
        _secrets_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if _secrets_key:
        api_key = _secrets_key
        st.success("API key loaded from secrets", icon="✅")
    else:
        api_key = st.text_input("Anthropic API Key", type="password",
                                help="Or add ANTHROPIC_API_KEY to .streamlit/secrets.toml")
        if not api_key:
            st.caption("Add to `secrets.toml` for auto-load")

    st.markdown("---")
    st.markdown("**AWS Pricing API**")
    _aws_access = ""
    _aws_secret = ""
    try:
        _aws_access = st.secrets.get("AWS_ACCESS_KEY_ID", "")
        _aws_secret = st.secrets.get("AWS_SECRET_ACCESS_KEY", "")
    except Exception:
        pass
    if not _aws_access:
        _aws_access = os.environ.get("AWS_ACCESS_KEY_ID", "")
    if not _aws_secret:
        _aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    if _aws_access and _aws_secret:
        aws_access_key = _aws_access
        aws_secret_key = _aws_secret
        st.success("AWS credentials loaded", icon="✅")
    else:
        aws_access_key = st.text_input("AWS Access Key ID", type="password",
                                       help="For live EC2/RDS pricing. Add to secrets.toml for auto-load")
        aws_secret_key = st.text_input("AWS Secret Access Key", type="password",
                                       help="Required for AWS Pricing API")
        if not aws_access_key:
            st.caption("Optional — uses reference catalog without keys")

    # Wire credentials into pricing engine (session-only, never persisted)
    if aws_access_key and aws_secret_key:
        set_aws_credentials(aws_access_key, aws_secret_key)

    st.markdown("---")
    st.markdown("**📊 Display**")
    show_charts = st.toggle("Show Charts", value=True)
    show_ai = st.toggle("AI Recommendations", value=True)
    show_enhanced = st.toggle("Enhanced Analysis", value=True, help="Network, DR/Backup, Storage Tiers, Serverless")
    show_budget = st.toggle("Budget-Grade Analysis", value=False, help="Support plans, migration labor, confidence ranges, multi-year TCO")
    if show_budget:
        budget_support_tier = st.selectbox("Support Plan",
            ["business", "enterprise", "developer", "none"],
            index=0, help="AWS: Business/Enterprise/Developer | Azure: Standard/Professional Direct")
        budget_years = st.slider("Budget Projection (years)", 1, 5, 3)
    else:
        budget_support_tier = "business"
        budget_years = 3
    # Enhanced currency support with 20 currencies
    currency_options = ["USD ($)", "CAD (C$)", "EUR (€)", "GBP (£)", "AUD (A$)",
                        "JPY (¥)", "INR (₹)", "SGD (S$)", "CHF (CHF)",
                        "SEK (kr)", "NZD (NZ$)", "BRL (R$)", "MXN (MX$)",
                        "KRW (₩)", "HKD (HK$)", "AED (AED)", "ZAR (R)"]
    currency = st.selectbox("Currency", currency_options)
    currency_code = currency.split(" ")[0]
    # Try live rates, fallback to static
    if HAS_CURRENCY:
        _rates, _rates_live, _rates_msg = fetch_live_rates()
        cmult = get_multiplier(currency_code, _rates)
        csym = get_symbol(currency_code)
    else:
        cmult = 1.0
        csym = "$"
    st.markdown("---")
    st.markdown("**🔒 Compliance**")
    st.caption("✅ Zero server-side data storage\n✅ In-memory computation only\n✅ Session cleared on browser close\n✅ Export generates fresh file\n✅ API key via secrets.toml (encrypted)")

    # ── CONNECTION STATUS INDICATORS ──
    st.markdown("---")
    st.markdown("**🔌 API Connections**")

    # Re-check when credentials change (track previous state)
    _curr_aws_key = aws_access_key[:8] if aws_access_key else ""
    _needs_recheck = (
        "_conn_checked" not in st.session_state
        or st.session_state.get("_prev_aws_key", "") != _curr_aws_key
        or st.session_state.get("_prev_api_key", "") != (api_key[:8] if api_key else "")
    )
    if _needs_recheck:
        st.session_state["_conn_aws"] = check_aws_connectivity()
        st.session_state["_conn_azure"] = check_azure_connectivity()
        st.session_state["_conn_anthropic"] = check_anthropic_connectivity(api_key)
        st.session_state["_prev_aws_key"] = _curr_aws_key
        st.session_state["_prev_api_key"] = api_key[:8] if api_key else ""
        st.session_state["_conn_checked"] = True

    aws_ok, aws_msg = st.session_state["_conn_aws"]
    az_ok, az_msg = st.session_state["_conn_azure"]
    anth_ok, anth_msg = st.session_state["_conn_anthropic"]

    def conn_html(name, ok, msg, icon, badge_text=""):
        cls = "conn-ok" if ok else "conn-err"
        dot = "conn-dot-ok" if ok else "conn-dot-err"
        status = "Connected" if ok else "Offline"
        badge = f' <span class="badge {"badge-live" if "Live" in badge_text else "badge-ref"}">{badge_text}</span>' if badge_text else ""
        return f'<div class="conn-indicator {cls}"><span class="conn-dot {dot}"></span><strong>{icon} {name}</strong> — {status}{badge}</div>'

    # AWS badge shows Live API vs Reference Catalog
    aws_badge = ""
    if aws_ok:
        aws_badge = "Live API" if "live" in aws_msg.lower() or "boto3" in aws_msg.lower() else "Reference"

    st.markdown(conn_html("AWS", aws_ok, aws_msg, "🟠", aws_badge), unsafe_allow_html=True)
    st.markdown(conn_html("Azure", az_ok, az_msg, "🔵", "Live API" if az_ok else ""), unsafe_allow_html=True)
    st.markdown(conn_html("Azure Local", az_ok, "Uses Azure API" if az_ok else az_msg, "🔷"), unsafe_allow_html=True)
    st.markdown(conn_html("Anthropic", anth_ok, anth_msg, "🟣"), unsafe_allow_html=True)

    with st.expander("ℹ️ Connection details", expanded=False):
        st.caption(f"**AWS:** {aws_msg}")
        st.caption(f"**Azure:** {az_msg}")
        st.caption(f"**Azure Local:** Uses Azure Retail Prices API (same connection as Azure)")
        st.caption(f"**Anthropic:** {anth_msg}")

    if st.button("🔄 Refresh Connections", use_container_width=True, key="refresh_conn"):
        st.session_state.pop("_conn_checked", None)
        st.rerun()
    if st.button("🗑️ Clear Session Now", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ─── Helpers ─────────────────────────────────────────────────────────────────
def fp(val):
    return f"{csym}{val * cmult:,.2f}"

def mc(label, value, sub="", css=""):
    st.markdown(f'<div class="metric-card {css}"><div class="label">{label}</div>'
                f'<div class="value">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)

def sf(val, default=0):
    try: return float(val)
    except: return default

def build_inputs(row: dict) -> Dict:
    return {
        "cloud_provider": str(row.get("Cloud Provider", "AWS")),
        "cloud_region": str(row.get("Cloud Region", "US East (N. Virginia)")),
        "host_name": str(row.get("Host Name", "")),
        "ip_address": str(row.get("IP Address", "")),
        "platform": str(row.get("Platform", "Linux")),
        "operating_system": str(row.get("Operating System", "Linux")),
        "environment": str(row.get("Environment", "Production")),
        "server_type": str(row.get("Server Type", "Application")),
        "os_eol_status": str(row.get("OS EOL Status", "No")),
        "migration_type": str(row.get("Migration Type", "Rehost")),
        "databases_caches": str(row.get("Databases/Caches", "None")),
        "app_services": str(row.get("AppServices", "")),
        "instance_usage": str(row.get("InstanceUsage", "24x7")),
        "vcpu_count": sf(row.get("VCPUCount", 2)),
        "avg_cpu_usage": sf(row.get("AvgCPUUsage (%tage)", 50)),
        "memory_gb": sf(row.get("Memory(GB)", 8)),
        "avg_memory_usage": sf(row.get("Avg Memory (%tage)", 50)),
        "total_storage_gb": sf(row.get("Total Storage(GB)", 100)),
        "storage_usage_pct": sf(row.get("Storage Usage (%)", 60)),
        "avg_network_throughput": sf(row.get("Average Network Throughput (Mbps)", 100)),
        "total_network_throughput": sf(row.get("Total Network Throughput (Mbps)", 1000)),
        "avg_disk_iops": sf(row.get("Average Disk IOPS", 500)),
        # Budget-grade parameters (injected from sidebar)
        "support_tier": budget_support_tier,
        "budget_years": budget_years,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT ROW BUILDER — Maps internal keys to exact column names
# ═══════════════════════════════════════════════════════════════════════════════
def build_output_row(inp: Dict, out: Dict) -> Dict:
    """Build one output row with exact user-specified column names."""
    return {
        "Host Name": inp.get("host_name", ""),
        "Cloud Provider": inp.get("cloud_provider", ""),
        "Region": inp.get("cloud_region", ""),
        "Right Sizing Based On - CPU": out["right_sizing_cpu"],
        "Right Sizing Based On - Memory": out["right_sizing_memory"],
        "Right Sizing Based On - Storage": out["right_sizing_storage"],
        "IAAS On Demand Price ($)": round(out["iaas_on_demand_price"] * cmult, 2),
        "IAAS Reserved 1 Year Price ($)": round(out["iaas_reserved_1yr_price"] * cmult, 2),
        "IAAS Reserved 3 Year Price ($)": round(out["iaas_reserved_3yr_price"] * cmult, 2),
        "IAAS Licensing Price ($)": round(out["iaas_licensing_price"] * cmult, 2),
        "Recomm. Instance Type": out["recomm_instance_type"],
        "Recomm. vCPU": out["recomm_vcpu"],
        "Recomm. Memory": out["recomm_memory"],
        "Recomm. Storage Type": out["recomm_storage_type"],
        "IAAS Recommended On Demand Price ($)": round(out["iaas_rec_on_demand"] * cmult, 2),
        "IAAS Recommended 1 Year Price ($)": round(out["iaas_rec_reserved_1yr"] * cmult, 2),
        "IAAS Recommended 3 Year Price ($)": round(out["iaas_rec_reserved_3yr"] * cmult, 2),
        "IAAS Recommended Licensing Price ($)": round(out["iaas_rec_licensing"] * cmult, 2),
        "Recommended Storage (GB)": out["rec_storage_gb"],
        "Recommended Storage Price ($)": round(out["rec_storage_price"] * cmult, 2),
        "PAAS Service": out["paas_service"],
        "PAAS Recommended Instance Type": out["paas_instance_type"],
        "PAAS Recomm. Service": out["paas_service_name"],
        "PAAS Recomm. CPU": out["paas_vcpu"],
        "PAAS Recomm. Memory": out.get("paas_memory", ""),
        "PAAS Recomm. Storage": out["paas_storage"],
        "PAAS Recomm. Storage Price ($)": round(out["paas_storage_price"] * cmult, 2),
        "PAAS Recommended On Demand Price ($)": round(out["paas_on_demand"] * cmult, 2),
        "PAAS Recommended 1 Year Price ($)": round(out["paas_reserved_1yr"] * cmult, 2),
        "PAAS Recommended 3 Year Price ($)": round(out["paas_reserved_3yr"] * cmult, 2),
        "PAAS Recommended Service Licensing Price ($)": round(out["paas_licensing"] * cmult, 2),
        "AWS Annual (3yr RI) ($)": round(out["cross_provider"]["AWS"]["annual_3yr_ri"] * cmult, 2),
        "AWS Instance Type": out["cross_provider"]["AWS"]["instance_type"],
        "Azure Annual (3yr RI) ($)": round(out["cross_provider"]["Azure"]["annual_3yr_ri"] * cmult, 2),
        "Azure Instance Type": out["cross_provider"]["Azure"]["instance_type"],
        "Azure Local Host Fee ($/mo)": round(out["azure_local"]["host_fee_monthly"] * cmult, 2),
        "Azure Local WS Subscription ($/mo)": round(out["azure_local"]["ws_sub_monthly"] * cmult, 2),
        "Azure Local Linux Annual ($)": round(out["azure_local"]["linux_total_annual"] * cmult, 2),
        "Azure Local Windows Annual ($)": round(out["azure_local"]["windows_total_annual"] * cmult, 2),
        "Azure Local AHB Annual ($)": round(out["azure_local"]["ahb_total_annual"] * cmult, 2),
        "On-Prem Yearly Cost ($)": round(out["on_prem_yearly_cost"] * cmult, 2),
        "DB Licensing ($/yr)": round(out.get("db_licensing_annual", 0) * cmult, 2),
        "DB License Type": out.get("db_licensing_name", "None"),
        "DR Strategy": out.get("_dr_strategy", "pilot_light"),
        "Target Operating System": out["target_operating_system"],
        # Enhanced cost columns
        "Network Egress ($/mo)": round(out.get("network_costs", {}).get("total_monthly", 0) * cmult, 2),
        "DR+Backup ($/mo)": round(out.get("dr_backup_costs", {}).get("combined_monthly", 0) * cmult, 2),
        "Storage Savings ($/mo)": round(out.get("storage_tiers", {}).get("savings_monthly", 0) * cmult, 2),
        "Container Option ($/mo)": round(out.get("modern_options", {}).get("container", {}).get("monthly_cost", 0) * cmult, 2),
        "Serverless Option ($/mo)": round(out.get("modern_options", {}).get("serverless", {}).get("monthly_cost", 0) * cmult, 2) if out.get("modern_options", {}).get("serverless", {}).get("suitable") else 0,
        "Modern Recommended": out.get("modern_options", {}).get("recommended", "N/A"),
        # PaaS Annual Total
        "PAAS Annual (3yr RI) ($)": round((out["paas_reserved_3yr"] + out["paas_licensing"] + out["paas_storage_price"]) * 12 * cmult, 2),
        # Migration Transfer (one-time)
        "Migration Transfer (GB)": round(out.get("migration_transfer", {}).get("data_to_transfer_gb", 0), 2),
        "Migration Transfer Method": out.get("migration_transfer", {}).get("recommended", {}).get("method", "N/A"),
        "Migration Transfer Cost ($)": round(out.get("migration_transfer", {}).get("recommended", {}).get("cost", 0) * cmult, 2),
        # All-In Cloud Annual (IaaS + Network + DR/Backup)
        "AWS All-In Annual ($)": round((out["cross_provider"]["AWS"]["annual_3yr_ri"] + out.get("network_costs", {}).get("total_annual", 0) + out.get("dr_backup_costs", {}).get("combined_annual", 0)) * cmult, 2),
        "Azure All-In Annual ($)": round((out["cross_provider"]["Azure"]["annual_3yr_ri"] + out.get("network_costs", {}).get("total_annual", 0) + out.get("dr_backup_costs", {}).get("combined_annual", 0)) * cmult, 2),
        # Budget-Grade columns
        "Support Plan ($/yr)": round(out.get("budget_support", {}).get("annual_cost", 0) * cmult, 2),
        "Migration Labor ($)": round(out.get("budget_migration_labor", {}).get("migration_labor", 0) * cmult, 2),
        "Migration Testing ($)": round(out.get("budget_migration_labor", {}).get("testing_validation", 0) * cmult, 2),
        "Parallel Run ($)": round(out.get("budget_migration_labor", {}).get("parallel_run", 0) * cmult, 2),
        "Total One-Time ($)": round(out.get("budget_total_one_time", 0) * cmult, 2),
        "AWS Budget All-In ($/yr)": round(out.get("budget_aws_all_in_annual", 0) * cmult, 2),
        "Azure Budget All-In ($/yr)": round(out.get("budget_azure_all_in_annual", 0) * cmult, 2),
        "AWS Low P10 ($/yr)": round(out.get("budget_aws_confidence", {}).get("low_annual", 0) * cmult, 2),
        "AWS Expected+Contingency ($/yr)": round(out.get("budget_aws_confidence", {}).get("budget_annual", 0) * cmult, 2),
        "AWS High P90 ($/yr)": round(out.get("budget_aws_confidence", {}).get("high_annual", 0) * cmult, 2),
        "Azure Low P10 ($/yr)": round(out.get("budget_azure_confidence", {}).get("low_annual", 0) * cmult, 2),
        "Azure Expected+Contingency ($/yr)": round(out.get("budget_azure_confidence", {}).get("budget_annual", 0) * cmult, 2),
        "Azure High P90 ($/yr)": round(out.get("budget_azure_confidence", {}).get("high_annual", 0) * cmult, 2),
        "Budget Best Cloud": out.get("budget_best_cloud", ""),
        "Break-Even Year": out.get("budget_summary", {}).get("breakeven_year", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SERVER CARD — Renders a single server's results inline (streaming display)
# ═══════════════════════════════════════════════════════════════════════════════
def render_server_card(inp: Dict, out: Dict, idx: int):
    """Compact card for one server — shown during streaming analysis."""
    host = inp.get("host_name", f"Server-{idx}")
    cloud = inp.get("cloud_provider", "")
    region = inp.get("cloud_region", "")
    is_azl = cloud == "Azure Local"
    if is_azl:
        azl_cost = out.get("azure_local", {}).get("recommended_annual", 0)
        savings = out["on_prem_yearly_cost"] - azl_cost
        sav_label = "vs On-Prem"
    else:
        savings = out["on_prem_yearly_cost"] - (out["iaas_rec_reserved_3yr"] + out["iaas_rec_licensing"] + out["rec_storage_price"]) * 12
        sav_label = "vs On-Prem"
    sav_pct = (savings / max(1, out["on_prem_yearly_cost"])) * 100

    with st.expander(f"✅ **{host}** — {cloud} {region} | Instance: `{out['recomm_instance_type']}` | "
                     f"{'↓' if savings > 0 else '↑'} {fp(abs(savings))}/yr ({abs(sav_pct):.0f}%) {sav_label}", expanded=(idx < 3)):
        xp = out.get("cross_provider", {})
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            mc("Right-Sized", f"{out['right_sizing_cpu']} vCPU / {out['right_sizing_memory']} GB",
               f"Storage: {out['right_sizing_storage']} GB")
        with c2:
            aws_a = xp.get("AWS", {}).get("annual_3yr_ri", 0)
            mc("AWS (3yr RI)", fp(aws_a) + "/yr",
               xp.get("AWS", {}).get("instance_type", ""))
        with c3:
            az_a = xp.get("Azure", {}).get("annual_3yr_ri", 0)
            mc("Azure (3yr RI)", fp(az_a) + "/yr",
               xp.get("Azure", {}).get("instance_type", ""), "metric-blue")
        with c4:
            azl = out.get("azure_local", {})
            mc("Azure Local", fp(azl.get('recommended_annual', 0)) + "/yr",
               azl.get('recommended_label', ''), "metric-blue")
        with c5:
            mc("On-Prem Yearly", fp(out['on_prem_yearly_cost']),
               f"Target: {out['target_operating_system']}", "metric-red")
        with c6:
            mc("PaaS 3yr RI", fp(out['paas_reserved_3yr']) + "/mo",
               out['paas_service_name'], "metric-yellow")

        # On-Prem cost breakdown
        bk = out.get("on_prem_breakdown", {})
        if bk:
            st.markdown(f"""<div class="cost-breakdown">
                <strong style="color:var(--accent);">📊 Data Center Cost Breakdown (Industry-Sourced)</strong>
                <div class="cb-row"><span>🖥️ Compute ({int(float(inp.get('vcpu_count',0)))} vCPU × $130/yr)</span><span>${bk.get('hw_compute',0):,.2f}</span></div>
                <div class="cb-row"><span>🧠 Memory ({float(inp.get('memory_gb',0))}GB × $10/yr)</span><span>${bk.get('hw_memory',0):,.2f}</span></div>
                <div class="cb-row"><span>💾 Storage ({float(inp.get('total_storage_gb',0))}GB × $0.08/yr)</span><span>${bk.get('hw_storage',0):,.2f}</span></div>
                <div class="cb-row"><span>⚡ Power ({bk.get('server_watts',0):.0f}W × PUE {bk.get('pue',1.55)} × ${bk.get('electricity_rate',0.12)}/kWh)</span><span>${bk.get('power_cooling',0):,.2f}</span></div>
                <div class="cb-row"><span>🏢 Facility/Rack (colocation share)</span><span>${bk.get('facility',0):,.2f}</span></div>
                <div class="cb-row"><span>👷 Admin & Labor</span><span>${bk.get('admin_labor',0):,.2f}</span></div>
                <div class="cb-row"><span>📜 OS ({bk.get('licensing_name', 'Linux')})</span><span>${bk.get('annual_licensing',0):,.2f}</span></div>
                <div class="cb-row"><span>🗄️ DB License ({bk.get('db_licensing_name', 'None')})</span><span>${bk.get('db_licensing_annual',0):,.2f}</span></div>
                <div class="cb-row cb-total"><span>Total Annual On-Prem Cost</span><span>${out['on_prem_yearly_cost']:,.2f}</span></div>
            </div>""", unsafe_allow_html=True)

        # Azure Local breakdown
        azl = out.get("azure_local", {})
        if azl:
            st.markdown(f"""<div class="cost-breakdown">
                <strong style="color:var(--primary);">Azure Local (Hybrid) — 3 Scenarios</strong>
                <div class="cb-row"><span>🐧 Linux (Host $10/core/mo × {int(float(inp.get('vcpu_count',0)))})</span><span>${azl.get('linux_total_annual',0):,.2f}/yr</span></div>
                <div class="cb-row"><span>🪟 Windows (Host+WS $23.30/core/mo × {int(float(inp.get('vcpu_count',0)))})</span><span>${azl.get('windows_total_annual',0):,.2f}/yr</span></div>
                <div class="cb-row"><span>💎 Azure Hybrid Benefit (SA waiver)</span><span>${azl.get('ahb_total_annual',0):,.2f}/yr</span></div>
            </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL / CSV GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════
def generate_excel(results: List[Dict]) -> bytes:
    """Pandas bulk write for speed. In-memory only."""
    buf = io.BytesIO()

    # Build DataFrames with exact column names
    inp_rows = [{
        "Cloud Provider": r["inputs"].get("cloud_provider", ""), "Cloud Region": r["inputs"].get("cloud_region", ""),
        "Host Name": r["inputs"].get("host_name", ""), "IP Address": r["inputs"].get("ip_address", ""),
        "Platform": r["inputs"].get("platform", ""), "Operating System": r["inputs"].get("operating_system", ""),
        "Environment": r["inputs"].get("environment", ""), "Server Type": r["inputs"].get("server_type", ""),
        "OS EOL Status": r["inputs"].get("os_eol_status", ""), "Migration Type": r["inputs"].get("migration_type", ""),
        "Databases/Caches": r["inputs"].get("databases_caches", ""), "AppServices": r["inputs"].get("app_services", ""),
        "InstanceUsage": r["inputs"].get("instance_usage", ""), "VCPUCount": r["inputs"].get("vcpu_count", ""),
        "AvgCPUUsage (%)": r["inputs"].get("avg_cpu_usage", ""), "Memory (GB)": r["inputs"].get("memory_gb", ""),
        "Avg Memory (%)": r["inputs"].get("avg_memory_usage", ""),
        "Total Storage (GB)": r["inputs"].get("total_storage_gb", ""),
        "Storage Usage (%)": r["inputs"].get("storage_usage_pct", ""),
        "Avg Network (Mbps)": r["inputs"].get("avg_network_throughput", ""),
        "Total Network (Mbps)": r["inputs"].get("total_network_throughput", ""),
        "Avg Disk IOPS": r["inputs"].get("avg_disk_iops", ""),
    } for r in results]

    out_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]

    sum_rows = []
    for r in results:
        o = r["outputs"]
        op = o["on_prem_yearly_cost"]
        iaas_3y = (o["iaas_rec_reserved_3yr"] + o["iaas_rec_licensing"] + o["rec_storage_price"]) * 12
        paas_3y = (o["paas_reserved_3yr"] + o["paas_licensing"] + o["paas_storage_price"]) * 12
        aws_ann = o["cross_provider"]["AWS"]["annual_3yr_ri"]
        az_ann = o["cross_provider"]["Azure"]["annual_3yr_ri"]
        best_cloud = min(aws_ann, az_ann)
        sav = op - best_cloud
        bk = o.get("on_prem_breakdown", {})
        azl_d = o.get("azure_local", {})
        sum_rows.append({
            "Host": r["inputs"]["host_name"],
            "Cloud Provider": r["inputs"].get("cloud_provider", ""),
            "On-Prem Annual ($)": round(op, 2),
            "  Hardware (Compute+Mem+Stor)": round(bk.get("hw_total", 0), 2),
            "  Power & Cooling": round(bk.get("power_cooling", 0), 2),
            "  Facility/Rack": round(bk.get("facility", 0), 2),
            "  Admin/Labor": round(bk.get("admin_labor", 0), 2),
            "  OS Licensing": round(bk.get("annual_licensing", 0), 2),
            "  DB Licensing": round(bk.get("db_licensing_annual", 0), 2),
            "AWS Annual (3yr RI) ($)": round(aws_ann, 2),
            "AWS Instance": o["cross_provider"]["AWS"]["instance_type"],
            "Azure Annual (3yr RI) ($)": round(az_ann, 2),
            "Azure Instance": o["cross_provider"]["Azure"]["instance_type"],
            "PaaS 3yr RI Annual ($)": round(paas_3y, 2),
            "Azure Local Linux Annual ($)": round(azl_d.get("linux_total_annual", 0), 2),
            "Azure Local Windows Annual ($)": round(azl_d.get("windows_total_annual", 0), 2),
            "Azure Local AHB Annual ($)": round(azl_d.get("ahb_total_annual", 0), 2),
            "Best Cloud Savings ($)": round(sav, 2),
            "Savings %": round((sav / op * 100) if op > 0 else 0, 1),
        })

    # Budget Summary rows (if budget data is available)
    budget_rows = []
    if results and results[0]["outputs"].get("budget_support"):
        for r in results:
            o = r["outputs"]
            budget_rows.append({
                "Host": r["inputs"]["host_name"],
                "Cloud Provider": r["inputs"].get("cloud_provider", ""),
                "Support Plan ($/yr)": round(o.get("budget_support", {}).get("annual_cost", 0), 2),
                "Migration Labor ($)": round(o.get("budget_migration_labor", {}).get("migration_labor", 0), 2),
                "Testing ($)": round(o.get("budget_migration_labor", {}).get("testing_validation", 0), 2),
                "Training ($)": round(o.get("budget_migration_labor", {}).get("training", 0), 2),
                "Parallel Run ($)": round(o.get("budget_migration_labor", {}).get("parallel_run", 0), 2),
                "Total One-Time ($)": round(o.get("budget_total_one_time", 0), 2),
                "AWS Budget All-In ($/yr)": round(o.get("budget_aws_all_in_annual", 0), 2),
                "Azure Budget All-In ($/yr)": round(o.get("budget_azure_all_in_annual", 0), 2),
                "AWS Low P10 ($/yr)": round(o.get("budget_aws_confidence", {}).get("low_annual", 0), 2),
                "AWS Budget P50+10% ($/yr)": round(o.get("budget_aws_confidence", {}).get("budget_annual", 0), 2),
                "AWS High P90 ($/yr)": round(o.get("budget_aws_confidence", {}).get("high_annual", 0), 2),
                "Azure Low P10 ($/yr)": round(o.get("budget_azure_confidence", {}).get("low_annual", 0), 2),
                "Azure Budget P50+10% ($/yr)": round(o.get("budget_azure_confidence", {}).get("budget_annual", 0), 2),
                "Azure High P90 ($/yr)": round(o.get("budget_azure_confidence", {}).get("high_annual", 0), 2),
                "Best Cloud": o.get("budget_best_cloud", ""),
                "Break-Even Year": o.get("budget_summary", {}).get("breakeven_year", ""),
            })

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(inp_rows).to_excel(writer, sheet_name="Input Data", index=False)
        pd.DataFrame(out_rows).to_excel(writer, sheet_name="Output — Dynamic", index=False)
        pd.DataFrame(sum_rows).to_excel(writer, sheet_name="Cost Summary", index=False)
        if budget_rows:
            pd.DataFrame(budget_rows).to_excel(writer, sheet_name="Budget Summary", index=False)

        notices = [
            "COMPLIANCE & DATA HANDLING NOTICE", "",
            f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
            "1. ZERO DATA PERSISTENCE: All data computed in-memory. Nothing stored.", "",
            "ON-PREM COST METHODOLOGY (Industry-Sourced Rates, 5-Year Amortization):",
            "  Hardware Compute: $130/vCPU/yr — Dell PowerEdge R760 (dell.com), 5-yr amortization",
            "  Hardware Memory: $10/GB/yr — DDR5 ECC RDIMM enterprise (Counterpoint Research 2025)",
            "  Hardware Storage: $0.08/GB/yr — Blended 70/30 SSD/HDD enterprise mix",
            "  Power & Cooling: vCPU × 25W × PUE(1.55) × 8,760hrs × $0.12/kWh",
            "    — PUE: US DOE/LBNL 2024 Data Center Energy Usage Report",
            "    — Electricity: US EIA industrial average (eia.gov)",
            "  Facility/Rack: $1,200/server/yr — ENCOR Advisors, Brightlio Colocation Guide (2025)",
            "  Admin/Labor: $1,500/server/yr — Gartner IT staffing benchmarks",
            "  OS Licensing: Windows $5.50/vCPU/mo, RHEL $3.00, SUSE $2.50 — Dell configurator (dell.com)",
            "  DB Licensing: Oracle $9,975/vCPU/yr, SQL Server Ent $3,400/vCPU/yr, Std $890/vCPU/yr,",
            "    MongoDB $10,000/server/yr, Redis $5,000/server/yr, MySQL/PostgreSQL/MariaDB $0 (open source)", "",
            "CLOUD PRICING: Azure Retail Prices API (live) + AWS reference catalog (fallback).", "",
            "AZURE LOCAL (formerly Azure Stack HCI) PRICING:",
            "  Host Service Fee: $10/physical core/month — azure.microsoft.com/pricing/details/azure-local/",
            "  Windows Server Subscription: $23.30/physical core/month (incl. unlimited WS guest licensing)",
            "  Azure Hybrid Benefit: WS Datacenter w/ Software Assurance waives host + WS subscription fees",
            "  AKS on Azure Local: included at no extra charge (2402+ release, effective Jan 2025)",
            "  60-day free trial after registration", "",
            "DISCLAIMER: Indicative pricing. Verify with official cloud calculators.", "",
            "BUDGET-GRADE METHODOLOGY:",
            "  Support Plans: AWS Business (tiered 10%/7%/5%/3%) — aws.amazon.com/premiumsupport/pricing/",
            "    Azure Standard $100/mo — azure.microsoft.com/en-us/support/plans/",
            "  Migration Labor: $5K-$25K/server base (Gartner Migration TCO, AWS MAP, Azure Migrate)",
            "    Complexity surcharges: DB Server 1.5x, Mail 1.3x, File 1.2x, Oracle 3.0x, SQL Server 2.0x",
            "  Testing/QA: 15-20% of labor cost by migration type",
            "  Training: $3,500/person × 0.1 allocation per server",
            "  Parallel Run: 2 months on-prem (Production), 1 month (non-Production)",
            "  Confidence Ranges: P10 (-15%), P50 (base), P90 (+25%) — Gartner, McKinsey",
            "  Contingency: 10% of expected (P50) — industry standard budget reserve",
            "  Price Trends: Cloud -5%/yr, On-prem HW +3%/yr, Power +4%/yr, Labor +5%/yr",
        ]
        pd.DataFrame({"Notice": notices}).to_excel(writer, sheet_name="Compliance Notice", index=False, header=False)

        wb = writer.book
        hf = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        hfill = PatternFill("solid", fgColor="1B4F72")
        sheet_names = ["Input Data", "Output — Dynamic", "Cost Summary"]
        if budget_rows:
            sheet_names.append("Budget Summary")
        for ws_name in sheet_names:
            ws = wb[ws_name]
            for cell in ws[1]:
                cell.font = hf; cell.fill = hfill
                cell.alignment = Alignment(horizontal="center", wrap_text=True)
            ws.freeze_panes = "A2"
            for col in ws.columns:
                mx = max(len(str(c.value or "")) for c in list(col)[:min(20, len(list(col)))])
                ws.column_dimensions[col[0].column_letter].width = min(mx + 4, 32)

    buf.seek(0)
    return buf.getvalue()


def generate_csv(results: List[Dict]) -> str:
    """CSV in-memory. Nothing stored."""
    rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
    return pd.DataFrame(rows).to_csv(index=False)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE SERVER DISPLAY (Manual Input tab)
# ═══════════════════════════════════════════════════════════════════════════════
def render_single_output(inputs: Dict, outputs: Dict):
    src = outputs.get("_pricing_source", "reference_catalog")
    badge = "badge-live" if "live" in src else "badge-ref"
    label = "LIVE API" if "live" in src else "REFERENCE"
    provider = outputs.get("_cloud_provider", "AWS")
    st.markdown(f'<span class="badge {badge}">● {label} PRICING</span>', unsafe_allow_html=True)

    # Azure Local primary recommendation when selected as provider
    if provider == "Azure Local":
        azl = outputs.get("azure_local", {})
        st.markdown('<div class="section-header">🔷 Azure Local — Primary Recommendation</div>', unsafe_allow_html=True)
        st.success("**Azure Local** selected — your servers stay on-prem with Azure Arc management. "
                   "IaaS/PaaS pricing below shows Azure cloud equivalent for comparison.")
        al1, al2, al3, al4 = st.columns(4)
        with al1:
            mc("Azure Local (Recommended)", fp(azl.get('recommended_annual', 0)) + "/yr",
               azl.get('recommended_label', ''), "metric-blue")
        with al2:
            mc("Linux Scenario", fp(azl.get('linux_total_annual', 0)) + "/yr",
               f"Host: ${azl.get('host_fee_per_core_mo', 10)}/core/mo")
        with al3:
            mc("Windows Scenario", fp(azl.get('windows_total_annual', 0)) + "/yr",
               f"Host+WS: ${azl.get('ws_sub_per_core_mo', 23.3)}/core/mo", "metric-blue")
        with al4:
            mc("Azure Hybrid Benefit", fp(azl.get('ahb_total_annual', 0)) + "/yr",
               "WS Datacenter w/ SA", "metric-yellow")
        st.markdown("---")

    # Right-Sizing
    st.markdown('<div class="section-header">📐 Right-Sizing</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        orig = int(float(inputs.get("vcpu_count", 0)))
        red = int((1 - outputs["right_sizing_cpu"] / max(1, orig)) * 100) if outputs["right_sizing_cpu"] < orig else 0
        mc("Right Sizing Based On - CPU", f"{outputs['right_sizing_cpu']} vCPU",
           f"{orig} → {outputs['right_sizing_cpu']} ({red}% reduction)" if red > 0 else "No reduction needed")
    with c2:
        mc("Right Sizing Based On - Memory", f"{outputs['right_sizing_memory']} GB",
           f"{inputs['memory_gb']} → {outputs['right_sizing_memory']} GB", "metric-blue")
    with c3:
        mc("Right Sizing Based On - Storage", f"{outputs['right_sizing_storage']} GB",
           f"{inputs['total_storage_gb']} → {outputs['right_sizing_storage']} GB", "metric-yellow")

    # IaaS
    st.markdown('<div class="section-header">💰 IaaS Pricing</div>', unsafe_allow_html=True)
    ca, cb = st.columns(2)
    with ca:
        st.markdown("**Current-Size**")
        st.markdown(f"""<div class="output-table"><table>
            <tr><th>Model</th><th>Monthly</th></tr>
            <tr><td>IAAS On Demand Price</td><td>{fp(outputs['iaas_on_demand_price'])}</td></tr>
            <tr><td>IAAS Reserved 1 Year Price</td><td>{fp(outputs['iaas_reserved_1yr_price'])}</td></tr>
            <tr><td>IAAS Reserved 3 Year Price</td><td>{fp(outputs['iaas_reserved_3yr_price'])}</td></tr>
            <tr><td>IAAS Licensing Price</td><td>{fp(outputs['iaas_licensing_price'])}</td></tr>
        </table></div>""", unsafe_allow_html=True)
    with cb:
        st.markdown(f"**Recommended: `{outputs['recomm_instance_type']}`** ({outputs['recomm_vcpu']} vCPU / {outputs['recomm_memory']} GB)")
        st.markdown(f"""<div class="output-table"><table>
            <tr><th>Model</th><th>Monthly</th></tr>
            <tr><td>IAAS Recommended On Demand Price</td><td>{fp(outputs['iaas_rec_on_demand'])}</td></tr>
            <tr><td>IAAS Recommended 1 Year Price</td><td>{fp(outputs['iaas_rec_reserved_1yr'])}</td></tr>
            <tr><td>IAAS Recommended 3 Year Price</td><td>{fp(outputs['iaas_rec_reserved_3yr'])}</td></tr>
            <tr><td>IAAS Recommended Licensing Price</td><td>{fp(outputs['iaas_rec_licensing'])}</td></tr>
            <tr><td>Recommended Storage ({outputs['recomm_storage_type']})</td><td>{outputs['rec_storage_gb']} GB @ {fp(outputs['rec_storage_price'])}/mo</td></tr>
        </table></div>""", unsafe_allow_html=True)

    # PaaS
    st.markdown('<div class="section-header">🔧 PaaS</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="output-table"><table>
        <tr><th>Field</th><th>Value</th></tr>
        <tr><td>PAAS Service</td><td>{outputs['paas_service']}</td></tr>
        <tr><td>PAAS Recomm. Service</td><td>{outputs['paas_service_name']}</td></tr>
        <tr><td>PAAS Recommended Instance Type</td><td>{outputs['paas_instance_type']}</td></tr>
        <tr><td>PAAS Recomm. CPU</td><td>{outputs['paas_vcpu']}</td></tr>
        <tr><td>PAAS Recomm. Memory</td><td>{outputs.get('paas_memory', 'N/A')}</td></tr>
        <tr><td>PAAS Recomm. Storage</td><td>{outputs['paas_storage']} GB</td></tr>
        <tr><td>PAAS Recomm. Storage Price</td><td>{fp(outputs['paas_storage_price'])}/mo</td></tr>
        <tr><td>PAAS Recommended On Demand Price</td><td>{fp(outputs['paas_on_demand'])}/mo</td></tr>
        <tr><td>PAAS Recommended 1 Year Price</td><td>{fp(outputs['paas_reserved_1yr'])}/mo</td></tr>
        <tr><td>PAAS Recommended 3 Year Price</td><td>{fp(outputs['paas_reserved_3yr'])}/mo</td></tr>
        <tr><td>PAAS Recommended Service Licensing Price</td><td>{fp(outputs['paas_licensing'])}/mo</td></tr>
    </table></div>""", unsafe_allow_html=True)

    # Azure Local (hybrid option)
    azl = outputs.get("azure_local", {})
    if azl:
        st.markdown('<div class="section-header">🔷 Azure Local (Hybrid On-Prem + Azure Management)</div>', unsafe_allow_html=True)
        st.caption("Azure Local (formerly Azure Stack HCI) extends Azure to your on-premises hardware — "
                   "same hardware costs but with Azure Arc management, billed per physical core/month.")
        al1, al2, al3 = st.columns(3)
        with al1:
            mc("Linux Guest", fp(azl['linux_total_annual']) + "/yr",
               f"Host fee: {fp(azl['host_fee_monthly'])}/mo ({int(float(inputs.get('vcpu_count',0)))} cores × ${azl['host_fee_per_core_mo']}/core)")
        with al2:
            mc("Windows Guest", fp(azl['windows_total_annual']) + "/yr",
               f"Host + WS Sub: {fp(azl['ws_sub_monthly'])}/mo ({int(float(inputs.get('vcpu_count',0)))} cores × ${azl['ws_sub_per_core_mo']}/core)", "metric-blue")
        with al3:
            mc("Azure Hybrid Benefit", fp(azl['ahb_total_annual']) + "/yr",
               "WS Datacenter w/ SA — fees waived", "metric-yellow")

        st.markdown(f"""<div class="output-table"><table>
            <tr><th>Scenario</th><th>Service Fee/mo</th><th>HW + Ops/yr</th><th>Total Annual</th></tr>
            <tr><td>🐧 Linux (Host Fee Only)</td><td>{fp(azl['host_fee_monthly'])}</td><td>{fp(azl['hw_and_ops_annual'])}</td><td><strong>{fp(azl['linux_total_annual'])}</strong></td></tr>
            <tr><td>🪟 Windows (Host + WS Subscription)</td><td>{fp(azl['ws_sub_monthly'])}</td><td>{fp(azl['hw_and_ops_annual'])}</td><td><strong>{fp(azl['windows_total_annual'])}</strong></td></tr>
            <tr><td>💎 Azure Hybrid Benefit (SA)</td><td>{csym}0.00</td><td>{fp(azl['hw_and_ops_annual'])}</td><td><strong>{fp(azl['ahb_total_annual'])}</strong></td></tr>
        </table></div>""", unsafe_allow_html=True)
        st.caption(f"ℹ️ {azl.get('physical_cores_note', '')} "
                   f"Source: {azl.get('source', 'azure.microsoft.com')}")

    # On-Prem with full breakdown + methodology
    st.markdown('<div class="section-header">🏢 On-Prem / Data Center Cost (Industry-Sourced)</div>', unsafe_allow_html=True)
    bk = outputs.get("on_prem_breakdown", {})
    t1, t2 = st.columns([2, 1])
    with t1:
        if bk:
            sources = bk.get("sources", {})
            st.markdown(f"""<div class="cost-breakdown">
                <strong style="color:var(--accent);">📊 Annual TCO Breakdown — Industry-Sourced Rates</strong>
                <div class="cb-row"><span>🖥️ Hardware Compute ({int(float(inputs.get('vcpu_count',0)))} vCPU × $130/yr amortized)</span><span>${bk['hw_compute']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('compute','Dell PowerEdge R760, 5-yr lifecycle')}</div>
                <div class="cb-row"><span>🧠 Hardware Memory ({float(inputs.get('memory_gb',0))} GB × $10/yr amortized)</span><span>${bk['hw_memory']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('memory','DDR5 RDIMM enterprise pricing')}</div>
                <div class="cb-row"><span>💾 Hardware Storage ({float(inputs.get('total_storage_gb',0))} GB × $0.08/yr blended SSD/HDD)</span><span>${bk['hw_storage']:,.2f}</span></div>
                <div class="cb-row" style="font-weight:600; border-top:1px solid var(--border); padding-top:4px; color:var(--text);">
                    <span>Hardware Subtotal</span><span>${bk['hw_total']:,.2f}</span></div>
                <div class="cb-row"><span>⚡ Power & Cooling ({bk.get('server_watts',0):.0f}W × PUE {bk.get('pue',1.55)} × {bk.get('power_kwh_yr',0):,.0f} kWh/yr × ${bk.get('electricity_rate',0.12)}/kWh)</span><span>${bk['power_cooling']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('power','US DOE 2024 Report, EIA')}</div>
                <div class="cb-row"><span>🏢 Facility / Colocation Rack Share</span><span>${bk['facility']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('facility','ENCOR Advisors, Brightlio 2025')}</div>
                <div class="cb-row"><span>👷 Admin & Labor Overhead (SysAdmin allocation)</span><span>${bk['admin_labor']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('labor','Gartner benchmarks, Sherweb TCO')}</div>
                <div class="cb-row"><span>📜 OS Licensing ({bk.get('licensing_name','Linux')})</span><span>${bk['annual_licensing']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('licensing','Dell configurator pricing')}</div>
                <div class="cb-row"><span>🗄️ DB Software ({bk.get('db_licensing_name','None')})</span><span>${bk.get('db_licensing_annual',0):,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#5E6B7A;">↳ {sources.get('db_licensing','Oracle/MS/MongoDB/Redis official price lists')}</div>
                <div class="cb-row cb-total"><span>On-Prem Yearly Cost</span><span>${outputs['on_prem_yearly_cost']:,.2f}</span></div>
            </div>""", unsafe_allow_html=True)
    with t2:
        mc("On-Prem Yearly Cost", fp(outputs['on_prem_yearly_cost']), "", "metric-red")
        xp = outputs.get("cross_provider", {})
        aws_ann = xp.get("AWS", {}).get("annual_3yr_ri", 0)
        az_ann = xp.get("Azure", {}).get("annual_3yr_ri", 0)
        mc("AWS Annual (3yr RI)", fp(aws_ann),
           f"Instance: {xp.get('AWS', {}).get('instance_type', '')}")
        mc("Azure Annual (3yr RI)", fp(az_ann),
           f"Instance: {xp.get('Azure', {}).get('instance_type', '')}", "metric-blue")
        azl_r = outputs.get("azure_local", {})
        mc("Azure Local Annual", fp(azl_r.get('recommended_annual', 0)),
           azl_r.get('recommended_label', ''), "metric-blue")
        best_cloud = min(aws_ann, az_ann)
        savings = outputs['on_prem_yearly_cost'] - best_cloud
        mc("Best Cloud Savings", fp(abs(savings)),
           f"{'↓' if savings > 0 else '↑'} {abs(savings / max(1, outputs['on_prem_yearly_cost']) * 100):.1f}%",
           "" if savings > 0 else "metric-red")

    st.info(f"🎯 **Target Operating System:** {outputs['target_operating_system']}")
    st.caption("📖 For rate sources and assumptions, expand **'How On-Premises Costs Are Calculated'** at the top of the page.")

    # Charts
    if show_charts:
        st.markdown('<div class="section-header">📈 Visual Analytics</div>', unsafe_allow_html=True)
        ch1, ch2 = st.columns(2)
        with ch1:
            fig = go.Figure()
            cats = ["On-Demand", "1-Year RI", "3-Year RI"]
            fig.add_trace(go.Bar(name="Current IaaS", x=cats,
                y=[outputs['iaas_on_demand_price']*cmult, outputs['iaas_reserved_1yr_price']*cmult, outputs['iaas_reserved_3yr_price']*cmult],
                marker_color="#FF6B6B"))
            fig.add_trace(go.Bar(name="Right-Sized IaaS", x=cats,
                y=[outputs['iaas_rec_on_demand']*cmult, outputs['iaas_rec_reserved_1yr']*cmult, outputs['iaas_rec_reserved_3yr']*cmult],
                marker_color="#4ADE80"))
            fig.add_trace(go.Bar(name="PaaS", x=cats,
                y=[outputs['paas_on_demand']*cmult, outputs['paas_reserved_1yr']*cmult, outputs['paas_reserved_3yr']*cmult],
                marker_color="#4A9EFF"))
            fig.update_layout(title="Monthly Cost Comparison", barmode="group", template="plotly_dark",
                paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED", height=420)
            st.plotly_chart(fig, use_container_width=True)
        with ch2:
            fig_g = make_subplots(rows=1, cols=3, specs=[[{"type":"indicator"}]*3],
                                  subplot_titles=["CPU", "Memory", "Storage"])
            for i, (v, col) in enumerate([(float(inputs['avg_cpu_usage']), "#4ADE80"),
                                           (float(inputs['avg_memory_usage']), "#4A9EFF"),
                                           (float(inputs['storage_usage_pct']), "#FFB347")]):
                fig_g.add_trace(go.Indicator(mode="gauge+number", value=v,
                    gauge=dict(axis=dict(range=[0,100]), bar=dict(color=col), bgcolor="#1A1F2E"),
                    number=dict(suffix="%")), row=1, col=i+1)
            fig_g.update_layout(template="plotly_dark", height=350, paper_bgcolor="#141922", font_color="#E0E6ED")
            st.plotly_chart(fig_g, use_container_width=True)

    # ── ENHANCED ANALYSIS SECTIONS ────────────────────────────────────────
    if show_enhanced:
        net = outputs.get("network_costs", {})
        drb = outputs.get("dr_backup_costs", {})
        st_tiers = outputs.get("storage_tiers", {})
        modern = outputs.get("modern_options", {})

        # Network Costs
        if net and net.get("total_monthly", 0) > 0:
            st.markdown('<div class="section-header">🌐 Network & Egress Costs</div>', unsafe_allow_html=True)
            nc1, nc2, nc3 = st.columns(3)
            with nc1:
                mc("Egress Cost", fp(net.get("egress", {}).get("monthly_cost", 0)) + "/mo",
                   f"~{net.get('estimated_egress_gb_month', 0):.0f} GB/mo egress")
            with nc2:
                mc("VPN/Connectivity", fp(net.get("vpn", {}).get("monthly_cost", 0)) + "/mo",
                   net.get("vpn", {}).get("type", ""), "metric-blue")
            with nc3:
                mc("Total Network", fp(net.get("total_monthly", 0)) + "/mo",
                   fp(net.get("total_annual", 0)) + "/yr", "metric-yellow")

        # DR & Backup
        if drb and drb.get("combined_monthly", 0) > 0:
            st.markdown('<div class="section-header">🛡️ DR & Backup Costs</div>', unsafe_allow_html=True)
            dr1, dr2, dr3 = st.columns(3)
            with dr1:
                mc("Backup", fp(drb.get("backup", {}).get("total_monthly", 0)) + "/mo",
                   f"{drb.get('backup', {}).get('total_backup_storage_gb', 0):.0f} GB stored")
            with dr2:
                dr_data = drb.get("dr", {})
                mc("Disaster Recovery", fp(dr_data.get("total_monthly", 0)) + "/mo",
                   f"{dr_data.get('strategy_label', 'Pilot Light')} (RTO: {dr_data.get('rto', 'N/A')})", "metric-blue")
            with dr3:
                mc("Combined DR+Backup", fp(drb.get("combined_monthly", 0)) + "/mo",
                   fp(drb.get("combined_annual", 0)) + "/yr", "metric-red")

        # Storage Tier Optimization
        if st_tiers and st_tiers.get("savings_pct", 0) > 0:
            st.markdown('<div class="section-header">💾 Storage Tier Optimization</div>', unsafe_allow_html=True)
            so1, so2 = st.columns(2)
            with so1:
                mc("Current (Single Tier)", fp(st_tiers.get("single_tier_monthly", 0)) + "/mo",
                   "All storage on hot tier", "metric-red")
            with so2:
                mc("Optimized (Tiered)", fp(st_tiers.get("optimized_monthly", 0)) + "/mo",
                   f"Save {st_tiers.get('savings_pct', 0):.0f}% ({fp(st_tiers.get('savings_monthly', 0))}/mo)")
            st.caption(st_tiers.get("recommendation", ""))

        # Serverless/Container Options
        if modern and modern.get("recommended", "N/A") != "N/A":
            st.markdown('<div class="section-header">🚀 Modern Deployment Options</div>', unsafe_allow_html=True)
            sl = modern.get("serverless", {})
            ct = modern.get("container", {})
            mo1, mo2, mo3 = st.columns(3)
            with mo1:
                if sl.get("suitable"):
                    mc("Serverless", fp(sl.get("monthly_cost", 0)) + "/mo",
                       f"{sl.get('service', '')} | {sl.get('estimated_requests_month', 0):,.0f} req/mo")
                else:
                    mc("Serverless", "N/A", sl.get("reason", "Not suitable"), "metric-red")
            with mo2:
                mc("Container", fp(ct.get("monthly_cost", 0)) + "/mo",
                   f"{ct.get('service', '')} | {ct.get('container_vcpu', 0)} vCPU", "metric-blue")
            with mo3:
                mc("Recommended", fp(modern.get("recommended_monthly", 0)) + "/mo",
                   modern.get("recommended", ""), "metric-yellow")

        # Migration Transfer Cost (one-time)
        mig_t = outputs.get("migration_transfer", {})
        if mig_t and mig_t.get("data_to_transfer_gb", 0) > 0:
            st.markdown('<div class="section-header">📦 Migration Data Transfer</div>', unsafe_allow_html=True)
            rec_method = mig_t.get("recommended", {})
            mt1, mt2 = st.columns(2)
            with mt1:
                mc("Data to Transfer", f"{mig_t['data_to_transfer_gb']:,.0f} GB",
                   "Used storage from current servers")
            with mt2:
                mc("Transfer Method", rec_method.get("method", "Internet"),
                   f"Cost: {fp(rec_method.get('cost', 0))} | ~{rec_method.get('estimated_hours', 0):.0f} hrs",
                   "metric-blue")
            if rec_method.get("note"):
                st.caption(f"ℹ️ {rec_method['note']}")

        # All-In Cloud Annual Summary
        net_annual = outputs.get("network_costs", {}).get("total_annual", 0)
        drb_annual = outputs.get("dr_backup_costs", {}).get("combined_annual", 0)
        xp = outputs.get("cross_provider", {})
        aws_iaas = xp.get("AWS", {}).get("annual_3yr_ri", 0)
        az_iaas = xp.get("Azure", {}).get("annual_3yr_ri", 0)
        aws_all_in = aws_iaas + net_annual + drb_annual
        az_all_in = az_iaas + net_annual + drb_annual

        st.markdown('<div class="section-header">📋 All-In Cloud Annual (IaaS + Network + DR/Backup)</div>', unsafe_allow_html=True)
        ai1, ai2, ai3, ai4 = st.columns(4)
        with ai1:
            mc("AWS All-In Annual", fp(aws_all_in),
               f"IaaS: {fp(aws_iaas)} + Net: {fp(net_annual)} + DR: {fp(drb_annual)}")
        with ai2:
            mc("Azure All-In Annual", fp(az_all_in),
               f"IaaS: {fp(az_iaas)} + Net: {fp(net_annual)} + DR: {fp(drb_annual)}", "metric-blue")
        with ai3:
            mc("On-Prem Annual", fp(outputs['on_prem_yearly_cost']),
               "Excludes network/DR (conservative)", "metric-red")
        with ai4:
            best_all_in = min(aws_all_in, az_all_in)
            savings_all_in = outputs['on_prem_yearly_cost'] - best_all_in
            mc("All-In Savings", fp(abs(savings_all_in)),
               f"{'↓' if savings_all_in > 0 else '↑'} vs On-Prem (conservative)",
               "" if savings_all_in > 0 else "metric-red")

    # ── BUDGET-GRADE SECTION (guarded by sidebar toggle) ──────────────────
    if show_budget and outputs.get("budget_support"):
        st.markdown('<div class="section-header">💼 Budget-Grade Analysis</div>', unsafe_allow_html=True)

        # Support Plan Costs
        sup = outputs.get("budget_support", {})
        su1, su2, su3 = st.columns(3)
        with su1:
            mc("Support Plan", sup.get("support_tier", "N/A").title(),
               f"{fp(sup.get('annual_cost', 0))}/yr ({sup.get('pct_of_spend', 0):.1f}% of spend)")
        with su2:
            aws_sup = outputs.get("cross_provider", {}).get("AWS", {}).get("support", {})
            mc("AWS Support", fp(aws_sup.get("annual_cost", 0)) + "/yr",
               f"{aws_sup.get('support_tier', 'business').title()} tier")
        with su3:
            az_sup = outputs.get("cross_provider", {}).get("Azure", {}).get("support", {})
            mc("Azure Support", fp(az_sup.get("annual_cost", 0)) + "/yr",
               f"{az_sup.get('support_tier', 'standard').title()} tier", "metric-blue")

        # Migration One-Time Costs
        st.markdown('<div class="section-header">🔧 Migration One-Time Costs</div>', unsafe_allow_html=True)
        mig = outputs.get("budget_migration_labor", {})
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            mc("Migration Labor", fp(mig.get("migration_labor", 0)),
               f"~{mig.get('estimated_duration_weeks', 0):.0f} weeks")
        with m2:
            mc("Testing/QA", fp(mig.get("testing_validation", 0)),
               f"{mig.get('complexity_factors', {}).get('server_type_mult', 1):.1f}x complexity")
        with m3:
            mc("Training", fp(mig.get("training", 0)),
               "$3,500/person prorated")
        with m4:
            mc("Parallel Run", fp(mig.get("parallel_run", 0)),
               "On-prem during cutover")
        with m5:
            mc("Total One-Time", fp(outputs.get("budget_total_one_time", 0)),
               "Labor + Testing + Training + Transfer", "metric-yellow")

        # Confidence Ranges
        st.markdown('<div class="section-header">🎯 Confidence Ranges (Annual)</div>', unsafe_allow_html=True)
        best_cloud = outputs.get("budget_best_cloud", "AWS")
        best_conf = outputs.get(f"budget_{best_cloud.lower()}_confidence", {})
        cr1, cr2, cr3, cr4 = st.columns(4)
        with cr1:
            mc(f"{best_cloud} Low (P10)", fp(best_conf.get("low_annual", 0)) + "/yr",
               "Best case: EDP discounts, spot")
        with cr2:
            mc(f"{best_cloud} Expected (P50)", fp(best_conf.get("expected_annual", 0)) + "/yr",
               "Base calculation (3yr RI)")
        with cr3:
            mc(f"{best_cloud} High (P90)", fp(best_conf.get("high_annual", 0)) + "/yr",
               "Worst case: overflows, growth", "metric-red")
        with cr4:
            mc("Budget (P50 + 10%)", fp(best_conf.get("budget_annual", 0)) + "/yr",
               f"Incl. {fp(best_conf.get('contingency_amount', 0))} contingency", "metric-yellow")

        # Multi-Year Budget Projection
        bs = outputs.get("budget_summary", {})
        if bs:
            yrs = bs.get("projection_years", 3)
            st.markdown(f'<div class="section-header">📅 {yrs}-Year Budget Projection</div>', unsafe_allow_html=True)

            bp1, bp2, bp3, bp4 = st.columns(4)
            with bp1:
                mc("Year 0 (Migration)", fp(bs["year_0"]["total"]),
                   f"One-time: {fp(bs['year_0']['migration_one_time'])} + Cloud: {fp(bs['year_0']['cloud_prorated'])}", "metric-yellow")
            with bp2:
                mc(f"{yrs}-Year Cloud Total", fp(bs["total_cloud_n_year"]),
                   f"Incl. Year 0 migration + {yrs} years run rate")
            with bp3:
                mc(f"{yrs}-Year On-Prem Total", fp(bs["total_on_prem_n_year"]),
                   "With inflation (HW +3%, power +4%, labor +5%/yr)", "metric-red")
            with bp4:
                be = bs.get("breakeven_year")
                be_label = f"Year {be}" if be else "Year 0"
                mc(f"{yrs}-Year Savings", fp(bs["total_savings_n_year"]),
                   f"Break-even: {be_label}", "" if bs["total_savings_n_year"] > 0 else "metric-red")

            # Year-by-year table
            with st.expander(f"📊 Year-by-Year Breakdown ({yrs} years)", expanded=False):
                import pandas as _pd
                yr_data = []
                yr_data.append({
                    "Year": "Year 0", "Cloud Total": fp(bs["year_0"]["total"]),
                    "On-Prem Total": fp(bs["year_0"]["on_prem_prorated"]),
                    "Annual Savings": fp(bs["year_0"]["on_prem_prorated"] - bs["year_0"]["total"]),
                    "Cumulative Cloud": fp(bs["year_0"]["total"]),
                    "Cumulative On-Prem": fp(bs["year_0"]["on_prem_prorated"]),
                    "Cumulative Savings": fp(bs["year_0"]["on_prem_prorated"] - bs["year_0"]["total"]),
                })
                for yr in bs.get("yearly", []):
                    yr_data.append({
                        "Year": f"Year {yr['year']}",
                        "Cloud Total": fp(yr["total_cloud"]),
                        "On-Prem Total": fp(yr["on_prem_projected"]),
                        "Annual Savings": fp(yr["annual_savings"]),
                        "Cumulative Cloud": fp(yr["cumulative_cloud"]),
                        "Cumulative On-Prem": fp(yr["cumulative_on_prem"]),
                        "Cumulative Savings": fp(yr["cumulative_savings"]),
                    })
                st.dataframe(_pd.DataFrame(yr_data), use_container_width=True, hide_index=True)

        st.caption(f"📋 Sources: AWS Premium Support (aws.amazon.com/premiumsupport/pricing/) | "
                   f"Azure Support Plans (azure.microsoft.com/en-us/support/plans/) | "
                   f"Gartner Migration TCO | Cloud price trends: -5%/yr (historical)")


# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZE SESSION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
audit = AuditLogger(st.session_state) if HAS_AUDIT else None
run_hist = RunHistory(st.session_state) if HAS_HISTORY else None


# ═══════════════════════════════════════════════════════════════════════════════
# TABS — Now with enhanced features
# ═══════════════════════════════════════════════════════════════════════════════
tab_upload, tab_manual, tab_results, tab_scenarios, tab_discovery, tab_monitor = st.tabs([
    "📁 Upload File", "✏️ Manual Input", "📊 Batch Results",
    "🔄 Scenarios & Projections", "🔍 Matilda Discovery", "📡 Monitoring"
])

# ── TAB 1: UPLOAD with STREAMING RESULTS ─────────────────────────────────────
with tab_upload:
    st.markdown('<div class="section-header">📁 Upload Server Inventory</div>', unsafe_allow_html=True)
    cu1, cu2 = st.columns([2, 1])
    with cu1:
        uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"],
            help="File processed in-memory only. Never stored.")
    with cu2:
        st.markdown("**Required columns:**")
        st.caption("Cloud Provider, Cloud Region, Host Name, IP Address, Platform, Operating System, "
                   "Environment, Server Type, OS EOL Status, Migration Type, Databases/Caches, "
                   "AppServices, InstanceUsage, VCPUCount, AvgCPUUsage (%tage), Memory(GB), "
                   "Avg Memory (%tage), Total Storage(GB), Storage Usage (%), "
                   "Average Network Throughput (Mbps), Total Network Throughput (Mbps), Average Disk IOPS")
        st.caption("💡 **Cloud Provider** accepts: `AWS`, `Azure`, or `Azure Local`. "
                   "Azure Local uses Azure regions and adds hybrid on-prem + Azure Arc pricing.")

    tpl = pd.DataFrame(columns=[
        "Cloud Provider", "Cloud Region", "Host Name", "IP Address", "Platform",
        "Operating System", "Environment", "Server Type", "OS EOL Status",
        "Migration Type", "Databases/Caches", "AppServices", "InstanceUsage",
        "VCPUCount", "AvgCPUUsage (%tage)", "Memory(GB)", "Avg Memory (%tage)",
        "Total Storage(GB)", "Storage Usage (%)", "Average Network Throughput (Mbps)",
        "Total Network Throughput (Mbps)", "Average Disk IOPS"])
    st.download_button("📥 Download Empty Template (CSV)", tpl.to_csv(index=False), "migration_template.csv", "text/csv")

    if uploaded:
        try:
            df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
            n_rows = len(df)
            st.success(f"✅ Loaded **{n_rows} servers** (in-memory only, not stored)")

            # ── ENHANCED: Bulk data validation ──
            if HAS_VALIDATION:
                validation = validate_bulk_dataframe(df)
                if not validation.is_valid:
                    for err in validation.errors:
                        st.error(err)
                if validation.warnings:
                    with st.expander(f"⚠️ {len(validation.warnings)} validation warning(s)", expanded=False):
                        for warn in validation.warnings:
                            st.warning(warn)

            if n_rows > 1000:
                st.warning(f"⚡ **Large dataset ({n_rows:,} rows).** Catalog pricing used for bulk. "
                           f"Estimated: ~{n_rows * 4 / 1000:.0f}s compute.")

            with st.expander("📋 Preview Input Data", expanded=False):
                _paginated_dataframe(df, "input_preview", page_size=100, height_cap=300)

            _can_analyze = _has_perm("analyze_servers")
            if not _can_analyze:
                st.warning("Your role does not have permission to analyze servers. Contact an admin.")
            if st.button("🚀 Analyze All Servers (Streaming)", type="primary", key="batch_go", disabled=not _can_analyze):
                results = []
                _batch_errors = []

                # Progress bar
                prog = st.progress(0, text="Starting analysis…")

                # Streaming table placeholder
                st.markdown('<div class="section-header">📊 Results — Streaming Live</div>', unsafe_allow_html=True)
                table_placeholder = st.empty()
                cards_container = st.container()

                # Build all inputs first
                all_inputs = [build_inputs(row.to_dict()) for _, row in df.iterrows()]

                # Use parallel processing for large batches (>5 servers)
                if HAS_ASYNC and n_rows > 5:
                    processor = BatchProcessor(max_workers=4, chunk_size=10)

                    def _progress_cb(done, total, hostname, result):
                        prog.progress(done / total,
                                      text=f"Server {done}/{total}: **{hostname}** → `{result['outputs']['recomm_instance_type']}`")

                    results, _batch_errors = processor.process_batch(
                        all_inputs, calculate_all_outputs,
                        progress_callback=_progress_cb,
                    )
                    # Update table after parallel run
                    if results:
                        display_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
                        table_placeholder.dataframe(
                            pd.DataFrame(display_rows),
                            use_container_width=True,
                            height=min(400, 40 + len(results) * 35))
                    # Show first 10 server cards
                    for idx, r in enumerate(results[:10]):
                        with cards_container:
                            render_server_card(r["inputs"], r["outputs"], idx + 1)
                else:
                    # Sequential processing (small batches or async unavailable)
                    for inp in all_inputs:
                        out = calculate_all_outputs(inp)
                        results.append({"inputs": inp, "outputs": out})

                        done = len(results)
                        prog.progress(done / n_rows,
                                      text=f"Server {done}/{n_rows}: **{inp.get('host_name', '')}** → `{out['recomm_instance_type']}`")

                        if done % 5 == 0 or done == n_rows or done <= 10:
                            display_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
                            table_placeholder.dataframe(
                                pd.DataFrame(display_rows),
                                use_container_width=True,
                                height=min(400, 40 + done * 35))

                        if done <= 10 or done == n_rows:
                            with cards_container:
                                render_server_card(inp, out, done)

                st.session_state["_batch"] = results
                prog.empty()
                _err_msg = f" ({len(_batch_errors)} errors)" if _batch_errors else ""
                st.success(f"✅ **{len(results):,} servers** analyzed{_err_msg}! Results below and in **📊 Batch Results** tab.")
                if _batch_errors:
                    with st.expander(f"⚠️ {len(_batch_errors)} servers failed", expanded=False):
                        for err in _batch_errors:
                            st.error(f"**{err['inputs'].get('host_name', 'Unknown')}**: {err['error']}")

                # Final export buttons right here
                st.markdown('<div class="section-header">📥 Export</div>', unsafe_allow_html=True)
                ex1, ex2 = st.columns(2)
                with ex1:
                    st.download_button("📥 Download CSV", generate_csv(results),
                        f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="up_csv")
                with ex2:
                    st.download_button("📥 Download Excel", generate_excel(results),
                        f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="up_xlsx")
        except Exception as e:
            st.error(f"Error: {e}")


# ── TAB 2: MANUAL ───────────────────────────────────────────────────────────
with tab_manual:
    st.markdown('<div class="section-header">✏️ Manual Server Input</div>', unsafe_allow_html=True)
    st.markdown("##### 🖥️ Infrastructure")
    c1, c2, c3, c4 = st.columns(4)
    with c1: m_cloud = st.selectbox("Cloud Provider", ["AWS", "Azure", "Azure Local"], key="mc")
    with c2:
        if m_cloud == "AWS":
            regs = list(AWS_REGIONS.keys())
        else:  # Azure or Azure Local both use Azure regions
            regs = list(AZURE_REGIONS.keys())
        m_region = st.selectbox("Cloud Region", regs, key="mr")
    with c3: m_host = st.text_input("Host Name", placeholder="e.g. web-prod-01", key="mh")
    with c4: m_ip = st.text_input("IP Address", placeholder="e.g. 10.0.1.100", key="mi")

    c5, c6, c7, c8 = st.columns(4)
    with c5: m_plat = st.selectbox("Platform", ["Linux","Windows","VMware","Hyper-V","Physical"], key="mp")
    with c6: m_os = st.selectbox("Operating System", [
        "Ubuntu 22.04","Ubuntu 20.04","Amazon Linux 2","Amazon Linux 2023","Red Hat Enterprise Linux 8",
        "Red Hat Enterprise Linux 9","CentOS 7","CentOS 8","SUSE Linux Enterprise 15",
        "Windows Server 2022","Windows Server 2019","Windows Server 2016","Debian 11","Debian 12"], key="mo")
    with c7: m_env = st.selectbox("Environment", ["Production","Staging","Development","Testing","DR","QA"], key="me")
    with c8: m_st = st.selectbox("Server Type", [
        "Web Server","Application Server","Database Server","Cache Server","File Server",
        "Mail Server","API Gateway","Load Balancer","Monitoring","CI/CD"], key="ms")

    c9, c10, c11, c12 = st.columns(4)
    with c9: m_eol = st.selectbox("OS EOL Status", ["No","Yes - EOL","Yes - Extended Support"], key="meol")
    with c10: m_mig = st.selectbox("Migration Type", [
        "Rehost (Lift & Shift)","Replatform","Refactor","Repurchase","Retire","Retain"], key="mmig")
    with c11: m_db = st.selectbox("Databases/Caches", [
        "None","MySQL","PostgreSQL","Oracle","SQL Server","MongoDB","Redis","Memcached","MariaDB","DynamoDB","Cassandra"], key="mdb")
    with c12: m_app = st.text_input("App Services", placeholder="Apache, Node.js", key="mapp")

    st.markdown("---")
    st.markdown("##### 📊 Resource Metrics")
    r1, r2, r3 = st.columns(3)
    with r1:
        m_usage = st.selectbox("Instance Usage", ["24x7","Business Hours","On-Demand","Scheduled"], key="mu")
        m_vcpu = st.number_input("vCPU Count", 1, 128, 4, key="mv")
        m_acpu = st.slider("Avg CPU (%)", 0, 100, 45, key="mac")
    with r2:
        m_mem = st.number_input("Memory (GB)", 1, 1024, 16, key="mm")
        m_amem = st.slider("Avg Memory (%)", 0, 100, 55, key="mam")
        m_stor = st.number_input("Total Storage (GB)", 10, 65536, 200, key="mst")
    with r3:
        m_spct = st.slider("Storage Usage (%)", 0, 100, 60, key="msp")
        m_net = st.number_input("Avg Network (Mbps)", 0, 100000, 150, key="mn")
        m_tnet = st.number_input("Total Network (Mbps)", 0, 100000, 2000, key="mtn")
    m_iops = st.number_input("Average Disk IOPS", 0, 500000, 800, key="mio")

    st.markdown("---")

    if st.button("🚀 Analyze & Calculate", type="primary", use_container_width=True, key="go_manual"):
        inp = {
            "cloud_provider": m_cloud, "cloud_region": m_region, "host_name": m_host, "ip_address": m_ip,
            "platform": m_plat, "operating_system": m_os, "environment": m_env, "server_type": m_st,
            "os_eol_status": m_eol, "migration_type": m_mig.split(" (")[0] if " (" in m_mig else m_mig,
            "databases_caches": m_db, "app_services": m_app, "instance_usage": m_usage,
            "vcpu_count": m_vcpu, "avg_cpu_usage": m_acpu, "memory_gb": m_mem, "avg_memory_usage": m_amem,
            "total_storage_gb": m_stor, "storage_usage_pct": m_spct,
            "avg_network_throughput": m_net, "total_network_throughput": m_tnet, "avg_disk_iops": m_iops,
            "support_tier": budget_support_tier, "budget_years": budget_years,
        }
        # ── ENHANCED: Input validation ──
        _valid = True
        if HAS_VALIDATION:
            validation = validate_server_inputs(inp)
            if validation.warnings:
                for w in validation.warnings:
                    st.warning(w)
            if not validation.is_valid:
                _valid = False
                for e in validation.errors:
                    st.error(e)
        if _valid:
            with st.spinner("Computing…"):
                import time as _t; _start = _t.time()
                out = calculate_all_outputs(inp)
                if HAS_MONITORING:
                    metrics.record_timing("analysis.single", (_t.time() - _start) * 1000)
                    metrics.increment_counter("analysis.total_servers")
            if audit:
                audit.log_analysis("user", "analyst", 1, m_cloud, "manual")
            st.session_state["_m_inp"] = inp
            st.session_state["_m_out"] = out

    if "_m_out" in st.session_state:
        inp, out = st.session_state["_m_inp"], st.session_state["_m_out"]
        render_single_output(inp, out)

        if show_ai and api_key and _has_perm("ai_analysis"):
            st.markdown('<div class="section-header">🤖 AI Migration Analysis</div>', unsafe_allow_html=True)
            st.caption("AI analyzes sizing, PaaS vs IaaS, cost optimization, migration gaps, and risk assessment")
            if st.button("🧠 Generate AI Analysis (Sizing + PaaS/IaaS + Gaps)", type="primary", key="ai_m"):
                # Rate limit AI calls
                _ai_allowed = True
                if HAS_AUTH:
                    _ai_allowed, _ai_remaining = ai_rate_limiter.check_limit(
                        _current_user.get("username", "anon"))
                if not _ai_allowed:
                    st.warning("⏳ AI rate limit reached (10 calls/hour). Please wait before trying again.")
                else:
                    with st.spinner("Claude analyzing sizing, PaaS/IaaS fit, cost optimization, gaps, and migration strategy…"):
                        rec = get_ai_recommendation(inp, out, api_key)
                    render_ai_analysis(rec, "Server Migration Analysis")
        elif show_ai and not api_key:
            st.info("💡 Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` or enter in sidebar.")
        elif show_ai and not _has_perm("ai_analysis"):
            st.info("🔒 AI analysis requires Analyst or Admin role.")

        st.markdown('<div class="section-header">📥 Export</div>', unsafe_allow_html=True)
        if not _has_perm("export_data"):
            st.info("🔒 Export requires Viewer, Analyst, or Admin role.")
        else:
            results = [{"inputs": inp, "outputs": out}]
            ce1, ce2, ce3 = st.columns(3)
            with ce1:
                st.download_button("📥 Download Excel", generate_excel(results),
                    f"{inp.get('host_name','server')}_analysis.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with ce2:
                st.download_button("📥 Download CSV", generate_csv(results),
                    f"{inp.get('host_name','server')}_analysis.csv", "text/csv")
            if HAS_PDF:
                with ce3:
                    pdf_data = generate_pdf_report(results, currency_symbol=csym, currency_multiplier=cmult)
                    st.download_button("📥 Download PDF", pdf_data,
                        f"{inp.get('host_name','server')}_report.pdf", "application/pdf", key="pdf_single")


# ── TAB 3: BATCH RESULTS ────────────────────────────────────────────────────
with tab_results:
    if "_batch" not in st.session_state:
        st.info("📁 Upload a file and click **Analyze All Servers** to see batch results here.")
    else:
        results = st.session_state["_batch"]
        n = len(results)

        # ── EXECUTIVE SUMMARY ──────────────────────────────────────────────
        st.markdown('<div class="section-header">📊 Executive Summary</div>', unsafe_allow_html=True)

        t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
        t_aws = sum(r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"] for r in results)
        t_az = sum(r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"] for r in results)
        t_azl = sum(r["outputs"].get("azure_local", {}).get("recommended_annual", 0) for r in results)
        t_net = sum(r["outputs"].get("network_costs", {}).get("total_annual", 0) for r in results)
        t_drb = sum(r["outputs"].get("dr_backup_costs", {}).get("combined_annual", 0) for r in results)
        t_cont = sum(r["outputs"].get("modern_options", {}).get("container", {}).get("monthly_cost", 0) * 12 for r in results)
        t_best = min(t_aws, t_az)
        t_sav = t_op - t_best

        # Row 1: Core cost comparison
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        with s1: mc("Total Servers", f"{n:,}")
        with s2: mc("On-Prem Annual", fp(t_op), "Current TCO", "metric-red")
        with s3: mc("AWS Annual (3yr)", fp(t_aws), "IaaS Optimized")
        with s4: mc("Azure Annual (3yr)", fp(t_az), "IaaS Optimized", "metric-blue")
        with s5: mc("Azure Local Annual", fp(t_azl), "Hybrid", "metric-blue")
        with s6: mc("Best Cloud Savings", fp(abs(t_sav)), f"{abs(t_sav/max(1,t_op)*100):.1f}%", "" if t_sav > 0 else "metric-red")

        # Row 2: All-In Cloud Annual (IaaS + Network + DR/Backup)
        if show_enhanced:
            t_aws_all_in = t_aws + t_net + t_drb
            t_az_all_in = t_az + t_net + t_drb
            t_best_all_in = min(t_aws_all_in, t_az_all_in)
            t_sav_all_in = t_op - t_best_all_in
            t_mig_transfer = sum(r["outputs"].get("migration_transfer", {}).get("recommended", {}).get("cost", 0) for r in results)

            ai1, ai2, ai3, ai4 = st.columns(4)
            with ai1: mc("AWS All-In Annual", fp(t_aws_all_in), "IaaS + Network + DR/Backup")
            with ai2: mc("Azure All-In Annual", fp(t_az_all_in), "IaaS + Network + DR/Backup", "metric-blue")
            with ai3: mc("All-In Savings", fp(abs(t_sav_all_in)),
                         f"{abs(t_sav_all_in/max(1,t_op)*100):.1f}% vs On-Prem", "" if t_sav_all_in > 0 else "metric-red")
            with ai4: mc("Migration Transfer", fp(t_mig_transfer), "One-time cost", "metric-yellow")

        # Row 3: Enhanced cost breakdowns
        if show_enhanced:
            e1, e2, e3, e4 = st.columns(4)
            with e1: mc("Network/Egress", fp(t_net) + "/yr", f"{n:,} servers total")
            with e2: mc("DR + Backup", fp(t_drb) + "/yr", "All environments")
            with e3: mc("Container Option", fp(t_cont) + "/yr", "EKS/AKS/Fargate")
            with e4:
                t_stor_sav = sum(r["outputs"].get("storage_tiers", {}).get("savings_monthly", 0) * 12 for r in results)
                mc("Storage Optimization", fp(t_stor_sav) + "/yr savings", "Tiered storage")

        # Row 4: Budget-Grade executive summary
        if show_budget:
            t_support = sum(r["outputs"].get("budget_support", {}).get("annual_cost", 0) for r in results)
            t_mig_labor = sum(r["outputs"].get("budget_total_one_time", 0) for r in results)
            t_aws_budget = sum(r["outputs"].get("budget_aws_all_in_annual", 0) for r in results)
            t_az_budget = sum(r["outputs"].get("budget_azure_all_in_annual", 0) for r in results)
            t_aws_low = sum(r["outputs"].get("budget_aws_confidence", {}).get("low_annual", 0) for r in results)
            t_aws_high = sum(r["outputs"].get("budget_aws_confidence", {}).get("high_annual", 0) for r in results)
            t_az_low = sum(r["outputs"].get("budget_azure_confidence", {}).get("low_annual", 0) for r in results)
            t_az_high = sum(r["outputs"].get("budget_azure_confidence", {}).get("high_annual", 0) for r in results)

            st.markdown("---")
            st.markdown('<div class="section-header">💼 Budget-Grade Portfolio Summary</div>', unsafe_allow_html=True)
            bi1, bi2, bi3, bi4, bi5 = st.columns(5)
            with bi1: mc("Support Plans", fp(t_support) + "/yr", "All servers combined")
            with bi2: mc("Migration One-Time", fp(t_mig_labor), "Labor + Testing + Transfer", "metric-yellow")
            with bi3: mc("AWS Budget All-In", fp(t_aws_budget) + "/yr", f"Range: {fp(t_aws_low)} - {fp(t_aws_high)}")
            with bi4: mc("Azure Budget All-In", fp(t_az_budget) + "/yr", f"Range: {fp(t_az_low)} - {fp(t_az_high)}", "metric-blue")
            with bi5:
                best_budget = min(t_aws_budget, t_az_budget)
                budget_sav = t_op - best_budget
                mc("Budget Savings", fp(abs(budget_sav)) + "/yr",
                   f"{abs(budget_sav/max(1,t_op)*100):.1f}% vs On-Prem (incl. support)",
                   "" if budget_sav > 0 else "metric-red")

        # On-Prem methodology (collapsed)
        with st.expander("📊 On-Prem Cost Methodology — Industry-Sourced Rates", expanded=False):
            st.markdown("""
            #### How On-Premises / Data Center Costs Are Calculated

            All rates are sourced from vendor pricing pages and industry benchmarks — not generic estimates.
            Costs represent **annual Total Cost of Ownership (TCO)** per server, amortized over a **5-year lifecycle**.

            | Component | Rate | Source |
            |-----------|------|--------|
            | **Hardware — Compute** | `$130/vCPU/yr` | Dell PowerEdge R760 (2×Xeon, 64-core) ~$10K-$15K, 5-yr amortization |
            | **Hardware — Memory** | `$10/GB/yr` | DDR5 64GB ECC RDIMM enterprise volume pricing, 5-yr amortization |
            | **Hardware — Storage** | `$0.08/GB/yr` | Blended 70/30 SSD/HDD enterprise mix, 5-yr amortization |
            | **Power & Cooling** | Dynamic | `vCPU × 25W × PUE(1.55) × 8,760hrs × $0.12/kWh` — US DOE/LBNL 2024 |
            | **Facility / Rack** | `$1,200/server/yr` | Colocation $1K-$2.5K/rack/mo, 42U rack shared |
            | **Admin & Labor** | `$1,500/server/yr` | 1 SysAdmin per 50-100 servers @ $80K-$120K salary |
            | **OS Licensing** | Per vCPU/mo | Win: $5.50, RHEL: $3.00, SUSE: $2.50, Linux: $0 |
            | **DB Licensing** | Per vCPU/yr or flat | Oracle: $9,975/vCPU/yr, SQL Server Ent: $3,400, Std: $890; MongoDB: $10K/srv, Redis: $5K/srv |

            #### 🔷 Azure Local (Hybrid Option)
            - **Host fee:** $10/physical core/month (Linux guests)
            - **Windows subscription:** $23.30/physical core/month
            - **Azure Hybrid Benefit:** WS Datacenter w/ SA waives all fees
            """)

        # ── BREAKDOWN BY DIMENSION ─────────────────────────────────────────
        st.markdown('<div class="section-header">📋 Portfolio Breakdown</div>', unsafe_allow_html=True)

        # Build a lightweight summary DataFrame once (not the full 30+ column table)
        _summary_rows = []
        for r in results:
            inp, out = r["inputs"], r["outputs"]
            _savings = out["on_prem_yearly_cost"] - min(
                out["cross_provider"]["AWS"]["annual_3yr_ri"],
                out["cross_provider"]["Azure"]["annual_3yr_ri"])
            _net_yr = out.get("network_costs", {}).get("total_annual", 0)
            _drb_yr = out.get("dr_backup_costs", {}).get("combined_annual", 0)
            _aws_yr = out["cross_provider"]["AWS"]["annual_3yr_ri"]
            _az_yr = out["cross_provider"]["Azure"]["annual_3yr_ri"]
            _summary_rows.append({
                "Host Name": inp.get("host_name", ""),
                "Environment": inp.get("environment", ""),
                "Server Type": inp.get("server_type", ""),
                "Platform": inp.get("platform", ""),
                "Cloud Provider": inp.get("cloud_provider", ""),
                "Family": out.get("_instance_family", "general"),
                "vCPU": out["right_sizing_cpu"],
                "Memory (GB)": out["right_sizing_memory"],
                "Storage (GB)": out["right_sizing_storage"],
                "Instance Type": out["recomm_instance_type"],
                f"On-Prem ({csym}/yr)": round(out["on_prem_yearly_cost"] * cmult, 2),
                f"AWS ({csym}/yr)": round(_aws_yr * cmult, 2),
                f"Azure ({csym}/yr)": round(_az_yr * cmult, 2),
                f"Azure Local ({csym}/yr)": round(out.get("azure_local", {}).get("recommended_annual", 0) * cmult, 2),
                f"Savings ({csym}/yr)": round(_savings * cmult, 2),
                f"Network ({csym}/mo)": round(out.get("network_costs", {}).get("total_monthly", 0) * cmult, 2),
                f"DR+Backup ({csym}/mo)": round(out.get("dr_backup_costs", {}).get("combined_monthly", 0) * cmult, 2),
                f"Container ({csym}/mo)": round(out.get("modern_options", {}).get("container", {}).get("monthly_cost", 0) * cmult, 2),
                f"AWS All-In ({csym}/yr)": round((_aws_yr + _net_yr + _drb_yr) * cmult, 2),
                f"Azure All-In ({csym}/yr)": round((_az_yr + _net_yr + _drb_yr) * cmult, 2),
                "Modern Recommended": out.get("modern_options", {}).get("recommended", "N/A"),
            })
        df_summary = pd.DataFrame(_summary_rows)

        # Aggregated views as sub-tabs
        view_mode = st.radio("View", ["By Environment", "By Server Type", "By Workload Family",
                                       "Top Savings", "Top Costs", "Search Servers"],
                             horizontal=True, key="batch_view")

        def _agg_table(group_col):
            """Build aggregated cost table grouped by a column."""
            agg = df_summary.groupby(group_col).agg(
                Servers=("Host Name", "count"),
                **{f"On-Prem ({csym}/yr)": (f"On-Prem ({csym}/yr)", "sum"),
                   f"AWS ({csym}/yr)": (f"AWS ({csym}/yr)", "sum"),
                   f"Azure ({csym}/yr)": (f"Azure ({csym}/yr)", "sum"),
                   f"Savings ({csym}/yr)": (f"Savings ({csym}/yr)", "sum"),
                   f"AWS All-In ({csym}/yr)": (f"AWS All-In ({csym}/yr)", "sum"),
                   f"Azure All-In ({csym}/yr)": (f"Azure All-In ({csym}/yr)", "sum"),
                   f"Network ({csym}/mo)": (f"Network ({csym}/mo)", "sum"),
                   f"DR+Backup ({csym}/mo)": (f"DR+Backup ({csym}/mo)", "sum"),
                   f"Container ({csym}/mo)": (f"Container ({csym}/mo)", "sum")},
            ).reset_index()
            for col in agg.columns:
                if agg[col].dtype in ["float64", "float32"]:
                    agg[col] = agg[col].round(2)
            return agg

        if view_mode == "By Environment":
            agg_df = _agg_table("Environment")
            st.dataframe(agg_df, use_container_width=True, height=min(400, 50 + len(agg_df) * 35))
            # Drill-down: click environment to see servers
            sel_env = st.selectbox("Drill into environment", ["All"] + sorted(df_summary["Environment"].unique().tolist()), key="drill_env")
            if sel_env != "All":
                filtered = df_summary[df_summary["Environment"] == sel_env]
                st.caption(f"Showing {len(filtered):,} servers in **{sel_env}**")
                _paginated_dataframe(filtered, "drill_env_tbl", page_size=100, height_cap=400)

        elif view_mode == "By Server Type":
            agg_df = _agg_table("Server Type")
            st.dataframe(agg_df, use_container_width=True, height=min(400, 50 + len(agg_df) * 35))
            sel_type = st.selectbox("Drill into server type", ["All"] + sorted(df_summary["Server Type"].unique().tolist()), key="drill_type")
            if sel_type != "All":
                filtered = df_summary[df_summary["Server Type"] == sel_type]
                st.caption(f"Showing {len(filtered):,} **{sel_type}** servers")
                _paginated_dataframe(filtered, "drill_type_tbl", page_size=100, height_cap=400)

        elif view_mode == "By Workload Family":
            agg_df = _agg_table("Family")
            st.dataframe(agg_df, use_container_width=True, height=min(400, 50 + len(agg_df) * 35))
            sel_fam = st.selectbox("Drill into family", ["All"] + sorted(df_summary["Family"].unique().tolist()), key="drill_fam")
            if sel_fam != "All":
                filtered = df_summary[df_summary["Family"] == sel_fam]
                st.caption(f"Showing {len(filtered):,} **{sel_fam}** workloads")
                _paginated_dataframe(filtered, "drill_fam_tbl", page_size=100, height_cap=400)

        elif view_mode == "Top Savings":
            st.caption(f"Top 50 servers with highest annual savings (of {n:,} total)")
            top_sav = df_summary.nlargest(50, f"Savings ({csym}/yr)")
            st.dataframe(top_sav, use_container_width=True, height=min(500, 50 + 50 * 35))

        elif view_mode == "Top Costs":
            st.caption(f"Top 50 most expensive servers by on-prem cost (of {n:,} total)")
            top_cost = df_summary.nlargest(50, f"On-Prem ({csym}/yr)")
            st.dataframe(top_cost, use_container_width=True, height=min(500, 50 + 50 * 35))

        elif view_mode == "Search Servers":
            search_q = st.text_input("Search by hostname, IP, or instance type", key="batch_search", placeholder="e.g. prod-web, 10.0.1")
            if search_q:
                mask = df_summary.apply(lambda row: search_q.lower() in str(row.values).lower(), axis=1)
                matched = df_summary[mask]
                st.caption(f"Found **{len(matched):,}** matches for \"{search_q}\"")
                _paginated_dataframe(matched, "search_tbl", page_size=100, height_cap=500)
            else:
                st.caption(f"Enter a search term to filter {n:,} servers. Or use the views above to browse by group.")

        # ── CHARTS ──────────────────────────────────────────────────────────
        if show_charts:
            st.markdown('<div class="section-header">📈 Portfolio Analytics</div>', unsafe_allow_html=True)
            ch1, ch2 = st.columns(2)

            with ch1:
                # Cost comparison by environment (aggregated — scales to any size)
                env_costs = df_summary.groupby("Environment").agg({
                    f"On-Prem ({csym}/yr)": "sum", f"AWS ({csym}/yr)": "sum",
                    f"Azure ({csym}/yr)": "sum"}).reset_index()
                fig_env = go.Figure()
                fig_env.add_trace(go.Bar(name="On-Prem", x=env_costs["Environment"],
                    y=env_costs[f"On-Prem ({csym}/yr)"], marker_color="#FF6B6B"))
                fig_env.add_trace(go.Bar(name="AWS (3yr RI)", x=env_costs["Environment"],
                    y=env_costs[f"AWS ({csym}/yr)"], marker_color="#E8850C"))
                fig_env.add_trace(go.Bar(name="Azure (3yr RI)", x=env_costs["Environment"],
                    y=env_costs[f"Azure ({csym}/yr)"], marker_color="#4A9EFF"))
                fig_env.update_layout(title="Annual Cost by Environment", barmode="group",
                    template="plotly_dark", height=400,
                    paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED")
                st.plotly_chart(fig_env, use_container_width=True)

            with ch2:
                # Workload family distribution
                fams = df_summary["Family"].value_counts()
                fig_fam = go.Figure(data=[go.Pie(labels=fams.index.tolist(), values=fams.values.tolist(),
                    marker_colors=["#4A9EFF","#4ADE80","#FFB347","#FF6B6B","#A78BFA"], hole=0.4)])
                fig_fam.update_layout(title=f"Workload Families ({n:,} servers)",
                    template="plotly_dark", height=400,
                    paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED")
                st.plotly_chart(fig_fam, use_container_width=True)

            ch3, ch4 = st.columns(2)
            with ch3:
                # Savings distribution histogram
                fig_h = go.Figure(data=[go.Histogram(
                    x=df_summary[f"Savings ({csym}/yr)"].tolist(), nbinsx=min(50, max(10, n // 100)),
                    marker_color="#4ADE80")])
                fig_h.update_layout(title=f"Savings Distribution ({n:,} servers)",
                    xaxis_title=f"Annual Savings ({csym})", yaxis_title="Server Count",
                    template="plotly_dark", height=350,
                    paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED")
                st.plotly_chart(fig_h, use_container_width=True)

            with ch4:
                # Cost by server type
                type_costs = df_summary.groupby("Server Type")[f"Savings ({csym}/yr)"].sum().sort_values(ascending=False)
                fig_t = go.Figure(data=[go.Bar(x=type_costs.index.tolist(), y=type_costs.values.tolist(),
                    marker_color="#4A9EFF")])
                fig_t.update_layout(title="Total Savings by Server Type",
                    yaxis_title=f"Savings ({csym}/yr)", template="plotly_dark", height=350,
                    paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED")
                st.plotly_chart(fig_t, use_container_width=True)

        # ── AI STRATEGY ─────────────────────────────────────────────────────
        if show_ai and api_key and _has_perm("ai_analysis"):
            st.markdown('<div class="section-header">🤖 AI Portfolio Strategy</div>', unsafe_allow_html=True)
            st.caption("AI analyzes sizing optimization, PaaS vs IaaS for each workload, migration gaps, wave planning, and financial projections")
            if st.button("🧠 Generate Executive Decision Brief (Sizing + PaaS/IaaS + Gaps)", type="primary", key="ai_b"):
                _ai_allowed = True
                if HAS_AUTH:
                    _ai_allowed, _ai_remaining = ai_rate_limiter.check_limit(
                        _current_user.get("username", "anon"))
                if not _ai_allowed:
                    st.warning("⏳ AI rate limit reached (10 calls/hour). Please wait before trying again.")
                else:
                    with st.spinner("Claude analyzing portfolio: sizing, PaaS/IaaS, gaps, wave plan, risk register, 3-year projection…"):
                        s = get_batch_ai_summary(results, api_key)
                    render_ai_analysis(s, "Executive Portfolio Analysis")

        # ── WAVE PLAN & ROI ─────────────────────────────────────────────────
        if show_enhanced and HAS_SCENARIOS:
            st.markdown('<div class="section-header">📋 Migration Wave Plan</div>', unsafe_allow_html=True)
            wave_plan = generate_wave_plan(results)
            for wave_key in ["wave_1", "wave_2", "wave_3", "wave_4"]:
                wave = wave_plan["waves"][wave_key]
                with st.expander(
                    f"**{wave['name']}** ({wave['timeline']}) — {wave['count']:,} servers "
                    f"| Savings: {fp(wave['total_savings'])}/yr",
                    expanded=(wave_key == "wave_1")
                ):
                    st.caption(f"Criteria: {wave['criteria']}")
                    if wave["servers"]:
                        wdf = pd.DataFrame(wave["servers"])[["host_name", "environment", "server_type",
                                                              "migration_type", "on_prem_cost", "cloud_cost"]]
                        wdf.columns = ["Host", "Env", "Type", "Migration", "On-Prem/yr", "Cloud/yr"]
                        st.dataframe(wdf, use_container_width=True, height=min(250, 35 + len(wave["servers"]) * 35))
                    else:
                        st.caption("No servers assigned to this wave.")

            st.markdown('<div class="section-header">📈 Portfolio ROI & Break-Even</div>', unsafe_allow_html=True)
            roi = calculate_roi_breakeven(t_op, t_best, server_count=n)
            roi1, roi2, roi3, roi4 = st.columns(4)
            with roi1: mc("Migration Investment", fp(roi["migration_cost"]), f"{n:,} servers")
            with roi2: mc("Monthly Savings", fp(roi["monthly_savings"]), "After migration")
            with roi3:
                be = roi.get("breakeven_months")
                mc("Break-Even", f"{be} months" if be else "N/A", "Cloud costs more" if not be else "")
            with roi4: mc("3-Year Savings", fp(roi["three_year_savings"]), f"ROI: {roi.get('three_year_roi_pct', 0):.0f}%")

        # ── SNAPSHOT ────────────────────────────────────────────────────────
        if run_hist:
            with st.expander("💾 Save Snapshot for Comparison", expanded=False):
                snap_label = st.text_input("Snapshot label", value=f"Analysis {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", key="snap_label")
                if st.button("Save Snapshot", key="save_snap"):
                    snap_id = run_hist.save_snapshot(snap_label, results)
                    st.success(f"Snapshot saved: **{snap_label}** (ID: {snap_id})")

        # ── FULL TABLE (collapsed for large datasets) ───────────────────────
        with st.expander(f"📋 Full Output Table ({n:,} rows × {len(build_output_row(results[0]['inputs'], results[0]['outputs']))} columns)", expanded=(n <= 100)):
            out_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
            _paginated_dataframe(pd.DataFrame(out_rows), "full_tbl", page_size=100, height_cap=500)

        # ── EXPORT ──────────────────────────────────────────────────────────
        st.markdown('<div class="section-header">📥 Export Portfolio</div>', unsafe_allow_html=True)
        if n > 1000:
            st.info(f"💡 **{n:,} rows**: CSV recommended (~1-2s). Excel may take ~{n*2//1000}s.")
        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            st.download_button(f"📥 CSV {'(Recommended)' if n > 1000 else ''}", generate_csv(results),
                f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="b_csv")
        with ex2:
            if n > 5000:
                if st.button(f"⚙️ Generate Excel ({n:,} rows)", key="gen_xlsx"):
                    with st.spinner(f"Generating Excel…"):
                        xlsx_data = generate_excel(results)
                    st.download_button("📥 Download Excel", xlsx_data,
                        f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx")
            else:
                st.download_button("📥 Excel", generate_excel(results),
                    f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="b_xlsx")
        if HAS_PDF:
            with ex3:
                pdf_data = generate_pdf_report(results, currency_symbol=csym, currency_multiplier=cmult)
                st.download_button("📥 PDF Report", pdf_data,
                    f"migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    "application/pdf", key="b_pdf")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: SCENARIOS & PROJECTIONS (requires scenario_engine, run_history)
# ══════════════════════════════════════════════════════════════════════════════
with tab_scenarios:
  if not _has_perm("scenario_analysis"):
    st.info("🔒 Scenario analysis requires Analyst or Admin role.")
  elif not HAS_SCENARIOS:
    st.info("Scenarios module not available. Ensure `scenario_engine.py` and `run_history.py` are deployed.")
  else:
    st.markdown('<div class="section-header">🔄 Scenario Analysis & Financial Projections</div>', unsafe_allow_html=True)

    # ── What-If Sensitivity Analysis ──
    st.markdown("#### 📊 What-If Sensitivity Analysis")
    if "_m_out" in st.session_state:
        inp_s, out_s = st.session_state["_m_inp"], st.session_state["_m_out"]
        st.info(f"Running sensitivity for: **{inp_s.get('host_name', 'Manual Server')}**")

        if st.button("Run Sensitivity Analysis", type="primary", key="run_sensitivity"):
            with st.spinner("Computing scenarios..."):
                sensitivity = run_sensitivity_analysis(inp_s, out_s, calculate_all_outputs)

            for var, data in sensitivity.items():
                with st.expander(f"**{var}** (base: {data['base_value']})", expanded=False):
                    rows = []
                    for s in data["scenarios"]:
                        rows.append({
                            "Variation": f"{s['variation_pct']:+d}%",
                            "Value": s["new_value"],
                            "Instance": s["instance_type"],
                            f"AWS Annual ({csym})": round(s["aws_annual"] * cmult, 2),
                            f"Azure Annual ({csym})": round(s["azure_annual"] * cmult, 2),
                            f"On-Prem Annual ({csym})": round(s["on_prem_annual"] * cmult, 2),
                        })
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.caption("Analyze a server in **Manual Input** tab first to run sensitivity analysis.")

    st.markdown("---")

    # ── Cost Projections ──
    st.markdown("#### 📈 3-5 Year Cost Projection")
    if "_m_out" in st.session_state:
        inp_p, out_p = st.session_state["_m_inp"], st.session_state["_m_out"]
        proj_years = st.slider("Projection years", 3, 7, 5, key="proj_yr")

        best_cloud = min(
            out_p["cross_provider"]["AWS"]["annual_3yr_ri"],
            out_p["cross_provider"]["Azure"]["annual_3yr_ri"],
        )
        roi = calculate_roi_breakeven(
            out_p["on_prem_yearly_cost"], best_cloud,
            inp_p.get("migration_type", "Rehost"),
            inp_p.get("databases_caches", "None"),
        )
        projection = project_costs(
            out_p["on_prem_yearly_cost"], best_cloud,
            out_p.get("on_prem_breakdown", {}),
            years=proj_years, migration_cost=roi["migration_cost"],
        )

        # Projection chart
        fig_proj = go.Figure()
        years = [p["year"] for p in projection["on_prem"]]
        fig_proj.add_trace(go.Scatter(
            x=years, y=[p["annual_cost"] * cmult for p in projection["on_prem"]],
            name="On-Premises", mode="lines+markers", line=dict(color="#FF6B6B", width=3),
        ))
        fig_proj.add_trace(go.Scatter(
            x=years, y=[p["annual_cost"] * cmult for p in projection["cloud"]],
            name="Cloud", mode="lines+markers", line=dict(color="#4A9EFF", width=3),
        ))
        fig_proj.update_layout(
            title=f"{proj_years}-Year Cost Projection",
            xaxis_title="Year", yaxis_title=f"Annual Cost ({csym})",
            template="plotly_dark", height=400,
            paper_bgcolor="#141922", plot_bgcolor="#1A1F2E", font_color="#E0E6ED",
        )
        st.plotly_chart(fig_proj, use_container_width=True)

        # ROI metrics
        r1, r2, r3 = st.columns(3)
        with r1:
            mc("Migration Cost", fp(roi["migration_cost"]),
               f"Break-even: {roi.get('breakeven_months', 'N/A')} months")
        with r2:
            mc(f"{proj_years}-Year Total Savings", fp(projection["total_savings"]),
               f"{projection['total_savings_pct']:.1f}% cheaper than on-prem")
        with r3:
            mc("3-Year ROI", f"{roi.get('three_year_roi_pct', 0):.0f}%",
               fp(roi.get("three_year_savings", 0)) + " net savings")
    else:
        st.caption("Analyze a server in **Manual Input** tab first.")

    st.markdown("---")

    # ── Historical Comparison ──
    st.markdown("#### 🕐 Historical Run Comparison")
    snapshots = run_hist.get_snapshots() if run_hist else []
    if len(snapshots) >= 2:
        snap_labels = {s["id"]: f"{s['label']} ({s['timestamp'][:16]})" for s in snapshots}
        sc1, sc2 = st.columns(2)
        with sc1:
            snap_a = st.selectbox("Snapshot A", list(snap_labels.keys()),
                                  format_func=lambda x: snap_labels[x], key="snap_a")
        with sc2:
            snap_b = st.selectbox("Snapshot B", list(snap_labels.keys()),
                                  format_func=lambda x: snap_labels[x], index=1, key="snap_b")
        if snap_a != snap_b and st.button("Compare Snapshots", key="compare_snap"):
            comparison = run_hist.compare_snapshots(snap_a, snap_b)
            if comparison:
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    mc("Servers Changed", str(comparison["server_count"]["changed"]),
                       f"Added: {comparison['server_count']['added']} | Removed: {comparison['server_count']['removed']}")
                with cc2:
                    d = comparison["totals"]["savings"]
                    mc("Savings Delta", fp(d["delta"]),
                       f"{d['delta_pct']:+.1f}%", "" if d["delta"] >= 0 else "metric-red")
                with cc3:
                    d = comparison["totals"]["on_prem"]
                    mc("On-Prem Delta", fp(d["delta"]),
                       f"{d['delta_pct']:+.1f}%")
    elif len(snapshots) == 1:
        st.caption("Save at least 2 snapshots from **Batch Results** to compare.")
    else:
        st.caption("No snapshots saved yet. Run a batch analysis and save a snapshot.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: AUTO-DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════
with tab_discovery:
  if not _has_perm("auto_discovery"):
    st.info("🔒 Auto-discovery requires Admin role.")
  elif not HAS_DISCOVERY:
    st.info("Discovery module not available. Ensure `discovery.py` is deployed.")
  else:
    st.markdown('<div class="section-header">🔍 Matilda Server Discovery</div>', unsafe_allow_html=True)
    st.caption("Import server inventory from Matilda via API or file export.")

    disc_method = st.radio("Import Method", ["Matilda API", "Matilda File Export"],
                           horizontal=True, key="disc_method")

    if disc_method == "Matilda API":
        st.markdown("##### Connect to Matilda API")
        mc1, mc2 = st.columns(2)
        with mc1:
            mat_url = st.text_input("Matilda URL", placeholder="https://matilda.example.com",
                                    key="disc_mat_url")
            mat_key = st.text_input("API Key", type="password", key="disc_mat_key")
        with mc2:
            mat_env = st.selectbox("Filter by Environment",
                                   ["All", "Production", "Development", "Staging", "Testing", "DR", "UAT"],
                                   key="disc_mat_env")
            mat_limit = st.number_input("Max servers", 100, 50000, 10000, step=500, key="disc_mat_limit")

        if st.button("Discover from Matilda", type="primary", key="disc_mat_go"):
            if not mat_url or not mat_key:
                st.error("Please provide Matilda URL and API Key.")
            else:
                filters = {}
                if mat_env != "All":
                    filters["environment"] = mat_env
                with st.spinner(f"Querying Matilda API (limit: {mat_limit:,})..."):
                    result = discover_matilda_api(mat_url, mat_key,
                                                  filters=filters, limit=mat_limit)
                if result.success:
                    st.success(result.message)
                    if result.servers:
                        df_disc = pd.DataFrame(result.servers)
                        display_cols = [c for c in df_disc.columns if not c.startswith("_")]
                        _n = len(df_disc)
                        st.caption(f"Showing preview of {min(100, _n):,} of {_n:,} servers")
                        st.dataframe(df_disc[display_cols].head(100), use_container_width=True, height=350)
                        st.session_state["_discovered"] = result.servers
                else:
                    st.error(result.message)
                    for err in result.errors:
                        st.error(err)

    else:  # Matilda File Export
        st.markdown("##### Upload Matilda Export")
        st.caption("Supports CSV, Excel (.xlsx), and JSON files exported from Matilda. "
                   "Column names are auto-mapped.")
        mat_file = st.file_uploader("Upload Matilda export file",
                                     type=["csv", "xlsx", "xls", "json"],
                                     key="disc_mat_file")
        if mat_file:
            with st.spinner(f"Importing {mat_file.name}..."):
                result = discover_matilda_file(mat_file, mat_file.name)
            if result.success:
                st.success(result.message)
                if result.servers:
                    df_disc = pd.DataFrame(result.servers)
                    display_cols = [c for c in df_disc.columns if not c.startswith("_")]
                    _n = len(df_disc)
                    st.caption(f"Showing preview of {min(100, _n):,} of {_n:,} servers")
                    st.dataframe(df_disc[display_cols].head(100), use_container_width=True, height=350)
                    st.session_state["_discovered"] = result.servers
            else:
                st.error(result.message)
                for err in result.errors:
                    st.error(err)

    # Use discovered servers
    if "_discovered" in st.session_state:
        st.markdown("---")
        disc_servers = st.session_state["_discovered"]
        _dn = len(disc_servers)
        st.success(f"**{_dn:,} servers** imported from Matilda (in-memory only)")

        # Quick summary of discovered inventory
        df_summary = pd.DataFrame(disc_servers)
        ds1, ds2, ds3, ds4 = st.columns(4)
        with ds1:
            mc("Total Servers", f"{_dn:,}")
        with ds2:
            _envs = df_summary["Environment"].value_counts()
            mc("Environments", str(len(_envs)), _envs.index[0] if len(_envs) else "")
        with ds3:
            _plats = df_summary["Platform"].value_counts()
            mc("Platforms", ", ".join(f"{k}: {v}" for k, v in _plats.items()))
        with ds4:
            _vcpu_total = df_summary["VCPUCount"].sum()
            mc("Total vCPUs", f"{int(_vcpu_total):,}")

        if st.button("Use for Analysis", type="primary", key="analyze_disc"):
            st.session_state["_disc_for_upload"] = disc_servers
            st.success("Servers loaded. Switch to **Upload File** tab — they'll be available as a pre-loaded dataset.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: MONITORING & HEALTH
# ══════════════════════════════════════════════════════════════════════════════
with tab_monitor:
  if not (HAS_MONITORING and HAS_RETRY and HAS_PRICING_CACHE):
    st.info("Monitoring modules not fully available. Ensure `monitoring.py`, `retry_utils.py`, and `pricing_cache.py` are deployed.")
  else:
    st.markdown('<div class="section-header">📡 Application Monitoring</div>', unsafe_allow_html=True)

    # Health status
    health = metrics.get_health_status()
    h_color = {"healthy": "", "degraded": "metric-yellow", "unhealthy": "metric-red"}
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        mc("Status", health["status"].upper(), f"Error rate: {health['error_rate']}%",
           h_color.get(health["status"], ""))
    with h2:
        mc("Uptime", health["uptime"], "Since session start")
    with h3:
        mc("Total Operations", str(health["total_operations"]))
    with h4:
        mc("Active Alerts", str(health["active_alerts"]),
           "" if health["active_alerts"] == 0 else "Check below", "metric-red" if health["active_alerts"] > 0 else "")

    # Circuit breaker status
    st.markdown("##### Circuit Breaker Status")
    cb_status = get_circuit_breaker_status()
    cb_cols = st.columns(len(cb_status))
    for i, (name, status) in enumerate(cb_status.items()):
        with cb_cols[i]:
            state = status["state"]
            is_ok = status["is_available"]
            mc(name.replace("_", " ").title(),
               state.upper(),
               f"Failures: {status['failures']}/{status['threshold']}",
               "" if is_ok else "metric-red")

    # Cache stats
    st.markdown("##### Pricing Cache")
    cache_stats = pricing_cache.get_stats()
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1:
        mc("Cache Size", f"{cache_stats['active']}/{cache_stats['max_size']}")
    with cs2:
        mc("Hit Rate", f"{cache_stats['hit_rate_pct']}%",
           f"Hits: {cache_stats['hits']} | Misses: {cache_stats['misses']}")
    with cs3:
        mc("Evictions", str(cache_stats["evictions"]))
    with cs4:
        if st.button("Clear Cache", key="clear_cache"):
            pricing_cache.invalidate()
            st.success("Cache cleared")
            st.rerun()

    # Performance metrics
    dashboard = metrics.get_dashboard()
    st.markdown("##### API Performance")
    api_data = dashboard.get("api_metrics", {})
    for api_name, stats in api_data.items():
        if stats["count"] > 0:
            st.caption(f"**{api_name}**: {stats['count']} calls | "
                       f"Avg: {stats['avg']:.0f}ms | P95: {stats['p95']:.0f}ms | "
                       f"Last: {stats['last']:.0f}ms")

    # Analysis metrics
    st.markdown("##### Analysis Throughput")
    an_data = dashboard.get("analysis_metrics", {})
    am1, am2 = st.columns(2)
    with am1:
        mc("Total Servers Analyzed", str(an_data.get("total_analyzed", 0)))
    with am2:
        single_stats = an_data.get("single_server", {})
        mc("Avg Analysis Time", f"{single_stats.get('avg', 0):.0f}ms" if single_stats.get("count", 0) > 0 else "N/A")

    # Audit log
    st.markdown("##### Audit Log")
    audit_summary = audit.get_summary()
    if audit_summary["total_events"] > 0:
        st.caption(f"Total events: {audit_summary['total_events']} | "
                   f"Categories: {', '.join(f'{k}: {v}' for k, v in audit_summary.get('by_category', {}).items())}")
        with st.expander("View Audit Entries", expanded=False):
            entries = audit.get_entries(limit=50)
            if entries:
                st.dataframe(pd.DataFrame(entries), use_container_width=True, height=300)

        ae1, ae2 = st.columns(2)
        with ae1:
            st.download_button("📥 Export Audit CSV", audit.export_csv(),
                               "audit_log.csv", "text/csv", key="audit_csv")
        with ae2:
            st.download_button("📥 Export Audit JSON", audit.export_json(),
                               "audit_log.json", "application/json", key="audit_json")
    else:
        st.caption("No audit events recorded in this session.")
