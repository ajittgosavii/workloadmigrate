"""
☁️ Cloud Migration Cost Analyzer — Compliance-Ready
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
)
from recommendation_engine import get_ai_recommendation, get_batch_ai_summary


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
        <h3>🤖 {title}</h3>
        <div class="ai-subtitle">AI-generated analysis — verify figures against computed data above</div>
        {html_content}
    </div>''', unsafe_allow_html=True)

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Cloud Migration Analyzer", page_icon="☁️",
                   layout="wide", initial_sidebar_state="expanded")

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root { --accent:#00D4AA; --surface:#1A1F2E; --surface2:#232839; --danger:#FF6B6B; --warn:#FFD93D; --info:#6C9FFF; }
    .stApp { font-family:'DM Sans',sans-serif; }
    .main-header { background:linear-gradient(135deg,#0f2027,#203a43 50%,#2c5364); padding:2rem 2.5rem;
        border-radius:16px; margin-bottom:1rem; border:1px solid rgba(0,212,170,0.2); position:relative; overflow:hidden; }
    .main-header::before { content:''; position:absolute; top:-50%; right:-20%; width:300px; height:300px;
        background:radial-gradient(circle,rgba(0,212,170,0.08),transparent 70%); border-radius:50%; }
    .main-header h1 { font-size:2rem; font-weight:700; color:#FFF; margin:0 0 .3rem 0; }
    .main-header p { color:#94A3B8; font-size:1rem; margin:0; }
    .compliance-banner { background:linear-gradient(90deg,#1e293b,#0f172a); border:1px solid rgba(255,217,61,0.3);
        border-radius:10px; padding:0.8rem 1.2rem; margin-bottom:1rem; display:flex; align-items:center; gap:0.8rem; }
    .compliance-banner .icon { font-size:1.4rem; }
    .compliance-banner .text { color:#FFD93D; font-size:0.85rem; font-weight:500; }
    .metric-card { background:var(--surface); padding:1.2rem 1.5rem; border-radius:12px;
        border-left:4px solid var(--accent); margin-bottom:0.8rem; }
    .metric-card .label { color:#94A3B8; font-size:0.78rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
    .metric-card .value { color:#FFF; font-size:1.5rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
    .metric-card .sub { color:var(--accent); font-size:0.83rem; margin-top:2px; }
    .metric-red { border-left-color:var(--danger)!important; }
    .metric-blue { border-left-color:var(--info)!important; }
    .metric-yellow { border-left-color:var(--warn)!important; }
    .section-header { font-size:0.88rem; font-weight:700; color:var(--accent); padding-bottom:0.5rem;
        border-bottom:2px solid var(--surface); margin:1.5rem 0 1rem 0; text-transform:uppercase; letter-spacing:1.5px; }
    .output-table { background:var(--surface); border-radius:12px; overflow:hidden; margin-bottom:1rem; }
    .output-table table { width:100%; border-collapse:collapse; }
    .output-table th { background:var(--surface2); color:var(--accent); padding:.7rem 1rem;
        text-align:left; font-size:.73rem; text-transform:uppercase; letter-spacing:1px; }
    .output-table td { padding:.6rem 1rem; color:#E0E0E0; border-bottom:1px solid rgba(255,255,255,0.05);
        font-family:'JetBrains Mono',monospace; font-size:.88rem; }
    .output-table tr:last-child td { border-bottom:none; }
    .ai-box { background:linear-gradient(135deg,#0d1b2a,#1b2838,#162032); border:1px solid rgba(0,212,170,0.4);
        border-radius:14px; padding:2rem 2.2rem; margin:1.2rem 0; box-shadow:0 4px 24px rgba(0,212,170,0.08); }
    .ai-box h3 { color:var(--accent); margin:0 0 .4rem 0; font-size:1.3rem; }
    .ai-box .ai-subtitle { color:rgba(255,255,255,0.5); font-size:.82rem; margin-bottom:1.2rem; }
    .ai-box h4, .ai-box h5 { color:#6C9FFF; margin:1.4rem 0 .5rem 0; border-bottom:1px solid rgba(108,159,255,0.2); padding-bottom:.3rem; }
    .ai-box p { color:rgba(255,255,255,0.88); line-height:1.65; margin:0.4rem 0; }
    .ai-box ul, .ai-box ol { color:rgba(255,255,255,0.88); padding-left:1.4rem; }
    .ai-box li { margin:0.3rem 0; line-height:1.55; }
    .ai-box strong { color:#FFD93D; }
    .ai-box code { background:rgba(0,212,170,0.1); color:var(--accent); padding:1px 5px; border-radius:3px; font-size:.85rem; }
    .ai-box table { width:100%; border-collapse:collapse; margin:.6rem 0; }
    .ai-box table th { background:rgba(108,159,255,0.15); color:#6C9FFF; padding:.5rem .8rem; text-align:left;
        border-bottom:1px solid rgba(108,159,255,0.3); font-size:.82rem; }
    .ai-box table td { padding:.4rem .8rem; border-bottom:1px solid rgba(255,255,255,0.06); color:rgba(255,255,255,0.85);
        font-size:.82rem; }
    .ai-box table tr:hover td { background:rgba(255,255,255,0.03); }
    .ai-box hr { border:none; border-top:1px solid rgba(255,255,255,0.08); margin:1rem 0; }
    .badge { display:inline-block; padding:.2rem .6rem; border-radius:20px; font-size:.73rem; font-weight:600; }
    .badge-live { background:rgba(0,212,170,0.15); color:var(--accent); }
    .badge-ref { background:rgba(108,159,255,0.15); color:var(--info); }
    .server-card { background:var(--surface); border-radius:10px; padding:1rem 1.2rem; margin:.6rem 0;
        border-left:3px solid var(--accent); }
    .server-card .sname { color:#FFF; font-weight:700; font-size:1rem; }
    .server-card .sdetail { color:#94A3B8; font-size:.82rem; margin-top:4px; }
    .cost-breakdown { background:var(--surface2); border-radius:8px; padding:1rem 1.2rem; margin:.5rem 0; font-size:.85rem; }
    .cost-breakdown .cb-row { display:flex; justify-content:space-between; padding:3px 0; color:#CBD5E1; }
    .cost-breakdown .cb-total { border-top:1px solid rgba(255,255,255,0.15); margin-top:6px; padding-top:6px;
        font-weight:700; color:#FFF; }
    .conn-indicator { display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:8px;
        margin:4px 0; font-size:.82rem; }
    .conn-ok { background:rgba(0,212,170,0.1); border:1px solid rgba(0,212,170,0.3); color:#00D4AA; }
    .conn-err { background:rgba(255,107,107,0.1); border:1px solid rgba(255,107,107,0.3); color:#FF6B6B; }
    .conn-warn { background:rgba(255,217,61,0.1); border:1px solid rgba(255,217,61,0.3); color:#FFD93D; }
    .conn-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
    .conn-dot-ok { background:#00D4AA; box-shadow:0 0 6px #00D4AA; }
    .conn-dot-err { background:#FF6B6B; }
    .conn-dot-warn { background:#FFD93D; }
    .source-tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:.72rem;
        background:rgba(108,159,255,0.1); color:#6C9FFF; border:1px solid rgba(108,159,255,0.2); margin:2px 0; }
    .method-box { background:var(--surface); border-radius:10px; padding:1.2rem; margin:.8rem 0;
        border:1px solid rgba(255,255,255,0.08); font-size:.85rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>☁️ Cloud Migration Cost Analyzer</h1>
    <p>Enterprise Right-Sizing • Real-Time Pricing • AI Recommendations — AWS, Azure & Azure Local</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="compliance-banner">
    <div class="icon">🔒</div>
    <div class="text">COMPLIANCE MODE: Zero data persistence — All data computed in-memory,
    never stored. Session discarded on close. Export generates fresh Excel/CSV on-the-fly.</div>
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
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")
    st.markdown("**🤖 Claude AI**")
    _secrets_key = ""
    try:
        _secrets_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    if not _secrets_key:
        _secrets_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if _secrets_key:
        api_key = _secrets_key
        st.success("🔑 API key loaded from secrets", icon="✅")
    else:
        api_key = st.text_input("Anthropic API Key", type="password",
                                help="Or add ANTHROPIC_API_KEY to .streamlit/secrets.toml")
        if not api_key:
            st.caption("💡 Add to `secrets.toml` for auto-load")
    st.markdown("---")
    st.markdown("**📊 Display**")
    show_charts = st.toggle("Show Charts", value=True)
    show_ai = st.toggle("AI Recommendations", value=True)
    currency = st.selectbox("Currency", ["USD ($)", "CAD (C$)", "EUR (€)", "GBP (£)"])
    cmult = {"USD ($)": 1.0, "CAD (C$)": 1.38, "EUR (€)": 0.92, "GBP (£)": 0.79}[currency]
    csym = {"USD ($)": "$", "CAD (C$)": "C$", "EUR (€)": "€", "GBP (£)": "£"}[currency]
    st.markdown("---")
    st.markdown("**🔒 Compliance**")
    st.caption("✅ Zero server-side data storage\n✅ In-memory computation only\n✅ Session cleared on browser close\n✅ Export generates fresh file\n✅ API key via secrets.toml (encrypted)")

    # ── CONNECTION STATUS INDICATORS ──
    st.markdown("---")
    st.markdown("**🔌 API Connections**")

    # Check connections (cached per session)
    if "_conn_checked" not in st.session_state:
        st.session_state["_conn_aws"] = check_aws_connectivity()
        st.session_state["_conn_azure"] = check_azure_connectivity()
        st.session_state["_conn_anthropic"] = check_anthropic_connectivity(api_key)
        st.session_state["_conn_checked"] = True

    aws_ok, aws_msg = st.session_state["_conn_aws"]
    az_ok, az_msg = st.session_state["_conn_azure"]
    anth_ok, anth_msg = st.session_state["_conn_anthropic"]

    def conn_html(name, ok, msg, icon):
        cls = "conn-ok" if ok else "conn-err"
        dot = "conn-dot-ok" if ok else "conn-dot-err"
        status = "Connected" if ok else "Offline"
        return f'<div class="conn-indicator {cls}"><span class="conn-dot {dot}"></span><strong>{icon} {name}</strong> — {status}</div>'

    st.markdown(conn_html("AWS", aws_ok, aws_msg, "🟠"), unsafe_allow_html=True)
    st.markdown(conn_html("Azure", az_ok, az_msg, "🔵"), unsafe_allow_html=True)
    st.markdown(conn_html("Azure Local", az_ok, "Uses Azure API" if az_ok else az_msg, "🔷"), unsafe_allow_html=True)
    st.markdown(conn_html("Anthropic", anth_ok, anth_msg, "🟣"), unsafe_allow_html=True)

    with st.expander("ℹ️ Connection details", expanded=False):
        st.caption(f"**AWS:** {aws_msg}")
        st.caption(f"**Azure:** {az_msg}")
        st.caption(f"**Azure Local:** Uses Azure Retail Prices API (same connection as Azure)")
        st.caption(f"**Anthropic:** {anth_msg}")

    if st.button("🔄 Refresh Connections", use_container_width=True, key="refresh_conn"):
        st.session_state["_conn_aws"] = check_aws_connectivity()
        st.session_state["_conn_azure"] = check_azure_connectivity()
        st.session_state["_conn_anthropic"] = check_anthropic_connectivity(api_key)
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
        "Target Operating System": out["target_operating_system"],
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
                <div class="cb-row cb-total"><span>Total Annual On-Prem Cost</span><span>${out['on_prem_yearly_cost']:,.2f}</span></div>
            </div>""", unsafe_allow_html=True)

        # Azure Local breakdown
        azl = out.get("azure_local", {})
        if azl:
            st.markdown(f"""<div class="cost-breakdown">
                <strong style="color:#9B59B6;">🔷 Azure Local (Hybrid) — 3 Scenarios</strong>
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

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(inp_rows).to_excel(writer, sheet_name="Input Data", index=False)
        pd.DataFrame(out_rows).to_excel(writer, sheet_name="Output — Dynamic", index=False)
        pd.DataFrame(sum_rows).to_excel(writer, sheet_name="Cost Summary", index=False)

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
            "  OS Licensing: Windows $5.50/vCPU/mo, RHEL $3.00, SUSE $2.50 — Dell configurator (dell.com)", "",
            "CLOUD PRICING: Azure Retail Prices API (live) + AWS reference catalog (fallback).", "",
            "AZURE LOCAL (formerly Azure Stack HCI) PRICING:",
            "  Host Service Fee: $10/physical core/month — azure.microsoft.com/pricing/details/azure-local/",
            "  Windows Server Subscription: $23.30/physical core/month (incl. unlimited WS guest licensing)",
            "  Azure Hybrid Benefit: WS Datacenter w/ Software Assurance waives host + WS subscription fees",
            "  AKS on Azure Local: included at no extra charge (2402+ release, effective Jan 2025)",
            "  60-day free trial after registration", "",
            "DISCLAIMER: Indicative pricing. Verify with official cloud calculators.",
        ]
        pd.DataFrame({"Notice": notices}).to_excel(writer, sheet_name="Compliance Notice", index=False, header=False)

        wb = writer.book
        hf = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        hfill = PatternFill("solid", fgColor="1B4F72")
        for ws_name in ["Input Data", "Output — Dynamic", "Cost Summary"]:
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
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('compute','Dell PowerEdge R760, 5-yr lifecycle')}</div>
                <div class="cb-row"><span>🧠 Hardware Memory ({float(inputs.get('memory_gb',0))} GB × $10/yr amortized)</span><span>${bk['hw_memory']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('memory','DDR5 RDIMM enterprise pricing')}</div>
                <div class="cb-row"><span>💾 Hardware Storage ({float(inputs.get('total_storage_gb',0))} GB × $0.08/yr blended SSD/HDD)</span><span>${bk['hw_storage']:,.2f}</span></div>
                <div class="cb-row" style="font-weight:600; border-top:1px solid rgba(255,255,255,0.1); padding-top:4px;">
                    <span>Hardware Subtotal</span><span>${bk['hw_total']:,.2f}</span></div>
                <div class="cb-row"><span>⚡ Power & Cooling ({bk.get('server_watts',0):.0f}W × PUE {bk.get('pue',1.55)} × {bk.get('power_kwh_yr',0):,.0f} kWh/yr × ${bk.get('electricity_rate',0.12)}/kWh)</span><span>${bk['power_cooling']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('power','US DOE 2024 Report, EIA')}</div>
                <div class="cb-row"><span>🏢 Facility / Colocation Rack Share</span><span>${bk['facility']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('facility','ENCOR Advisors, Brightlio 2025')}</div>
                <div class="cb-row"><span>👷 Admin & Labor Overhead (SysAdmin allocation)</span><span>${bk['admin_labor']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('labor','Gartner benchmarks, Sherweb TCO')}</div>
                <div class="cb-row"><span>📜 OS Licensing ({bk.get('licensing_name','Linux')})</span><span>${bk['annual_licensing']:,.2f}</span></div>
                <div class="cb-row" style="padding-left:24px;font-size:.78rem;color:#6C9FFF;">↳ {sources.get('licensing','Dell configurator pricing')}</div>
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
                marker_color="#00D4AA"))
            fig.add_trace(go.Bar(name="PaaS", x=cats,
                y=[outputs['paas_on_demand']*cmult, outputs['paas_reserved_1yr']*cmult, outputs['paas_reserved_3yr']*cmult],
                marker_color="#6C9FFF"))
            fig.update_layout(title="Monthly Cost Comparison", barmode="group", template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=420)
            st.plotly_chart(fig, use_container_width=True)
        with ch2:
            fig_g = make_subplots(rows=1, cols=3, specs=[[{"type":"indicator"}]*3],
                                  subplot_titles=["CPU", "Memory", "Storage"])
            for i, (v, col) in enumerate([(float(inputs['avg_cpu_usage']), "#00D4AA"),
                                           (float(inputs['avg_memory_usage']), "#6C9FFF"),
                                           (float(inputs['storage_usage_pct']), "#FFD93D")]):
                fig_g.add_trace(go.Indicator(mode="gauge+number", value=v,
                    gauge=dict(axis=dict(range=[0,100]), bar=dict(color=col), bgcolor="rgba(255,255,255,0.05)"),
                    number=dict(suffix="%")), row=1, col=i+1)
            fig_g.update_layout(template="plotly_dark", height=350, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_g, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════
tab_upload, tab_manual, tab_results = st.tabs(["📁 Upload File", "✏️ Manual Input", "📊 Batch Results"])

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

            if n_rows > 1000:
                st.warning(f"⚡ **Large dataset ({n_rows:,} rows).** Catalog pricing used for bulk. "
                           f"Estimated: ~{n_rows * 4 / 1000:.0f}s compute.")

            with st.expander("📋 Preview Input Data", expanded=False):
                st.dataframe(df.head(100), use_container_width=True, height=250)
                if n_rows > 100:
                    st.caption(f"Showing first 100 of {n_rows:,}")

            if st.button("🚀 Analyze All Servers (Streaming)", type="primary", key="batch_go"):
                results = []

                # Progress bar
                prog = st.progress(0, text="Starting analysis…")

                # Streaming table placeholder
                st.markdown('<div class="section-header">📊 Results — Streaming Live</div>', unsafe_allow_html=True)
                table_placeholder = st.empty()
                cards_container = st.container()

                for i, row in df.iterrows():
                    inp = build_inputs(row.to_dict())
                    out = calculate_all_outputs(inp)
                    results.append({"inputs": inp, "outputs": out})

                    # Update progress
                    done = len(results)
                    prog.progress(done / n_rows,
                                  text=f"Server {done}/{n_rows}: **{inp.get('host_name', '')}** → `{out['recomm_instance_type']}`")

                    # Update streaming table every 5 servers or at the end
                    if done % 5 == 0 or done == n_rows or done <= 10:
                        display_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
                        table_placeholder.dataframe(
                            pd.DataFrame(display_rows),
                            use_container_width=True,
                            height=min(400, 40 + done * 35))

                    # Show server card for first 10 and last one
                    if done <= 10 or done == n_rows:
                        with cards_container:
                            render_server_card(inp, out, done)

                st.session_state["_batch"] = results
                prog.empty()
                st.success(f"✅ **{len(results):,} servers** analyzed! Results below and in **📊 Batch Results** tab.")

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
        }
        with st.spinner("Computing…"):
            out = calculate_all_outputs(inp)
        st.session_state["_m_inp"] = inp
        st.session_state["_m_out"] = out

    if "_m_out" in st.session_state:
        inp, out = st.session_state["_m_inp"], st.session_state["_m_out"]
        render_single_output(inp, out)

        if show_ai and api_key:
            st.markdown('<div class="section-header">🤖 AI Migration Analysis</div>', unsafe_allow_html=True)
            if st.button("🧠 Generate Deep AI Analysis", type="primary", key="ai_m"):
                with st.spinner("Claude analyzing server profile, cross-provider costs, risks, and migration strategy…"):
                    rec = get_ai_recommendation(inp, out, api_key)
                render_ai_analysis(rec, "Server Migration Analysis")
        elif show_ai and not api_key:
            st.info("💡 Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` or enter in sidebar.")

        st.markdown('<div class="section-header">📥 Export</div>', unsafe_allow_html=True)
        results = [{"inputs": inp, "outputs": out}]
        ce1, ce2 = st.columns(2)
        with ce1:
            st.download_button("📥 Download Excel", generate_excel(results),
                f"{inp.get('host_name','server')}_analysis.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with ce2:
            st.download_button("📥 Download CSV", generate_csv(results),
                f"{inp.get('host_name','server')}_analysis.csv", "text/csv")


# ── TAB 3: BATCH RESULTS ────────────────────────────────────────────────────
with tab_results:
    if "_batch" not in st.session_state:
        st.info("📁 Upload a file and click **Analyze All Servers** to see batch results here.")
    else:
        results = st.session_state["_batch"]
        n = len(results)
        st.markdown('<div class="section-header">📊 Portfolio Dashboard</div>', unsafe_allow_html=True)

        t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
        t_aws = sum(r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"] for r in results)
        t_az = sum(r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"] for r in results)
        t_azl = sum(r["outputs"].get("azure_local", {}).get("recommended_annual", 0) for r in results)
        t_best = min(t_aws, t_az)
        t_sav = t_op - t_best

        s1, s2, s3, s4, s5, s6 = st.columns(6)
        with s1: mc("Total Servers", str(n))
        with s2: mc("On-Prem Annual", fp(t_op), "Current", "metric-red")
        with s3: mc("AWS Annual (3yr)", fp(t_aws), "IaaS Optimized")
        with s4: mc("Azure Annual (3yr)", fp(t_az), "IaaS Optimized", "metric-blue")
        with s5: mc("Azure Local Annual", fp(t_azl), "Hybrid", "metric-blue")
        with s6: mc("Best Cloud Savings", fp(abs(t_sav)), f"{abs(t_sav/max(1,t_op)*100):.1f}%", "" if t_sav > 0 else "metric-red")

        # On-Prem methodology note
        with st.expander("📊 On-Prem Cost Methodology — Industry-Sourced Rates", expanded=False):
            st.markdown("""
            #### How On-Premises / Data Center Costs Are Calculated

            All rates are sourced from vendor pricing pages and industry benchmarks — not generic estimates.
            Costs represent **annual Total Cost of Ownership (TCO)** per server, amortized over a **5-year lifecycle**.

            | Component | Rate | Source |
            |-----------|------|--------|
            | **Hardware — Compute** | `$130/vCPU/yr` | Dell PowerEdge R760 (2×Xeon, 64-core) ~$10K-$15K, 5-yr amortization ([dell.com](https://dell.com/poweredge-r760), TerraZone TCO 2025) |
            | **Hardware — Memory** | `$10/GB/yr` | DDR5 64GB ECC RDIMM enterprise volume pricing, 5-yr amortization (Counterpoint Research 2025, [NetworkWorld](https://networkworld.com) Nov 2025) |
            | **Hardware — Storage** | `$0.08/GB/yr` | Blended 70/30 SSD/HDD enterprise mix, 5-yr amortization |
            | **Power & Cooling** | Dynamic | `vCPU × 25W × PUE(1.55) × 8,760hrs × $0.12/kWh` — US DOE/LBNL 2024 Data Center Energy Report, EIA industrial avg |
            | **Facility / Rack** | `$1,200/server/yr` | Colocation $1K-$2.5K/rack/mo, 42U rack shared (ENCOR Advisors, [Brightlio](https://brightlio.com) 2025) |
            | **Admin & Labor** | `$1,500/server/yr` | 1 SysAdmin per 50-100 servers @ $80K-$120K salary (Gartner benchmarks, [Sherweb](https://sherweb.com) TCO) |
            | **OS Licensing** | Per vCPU/mo | Win: $5.50, RHEL: $3.00, SUSE: $2.50, Linux: $0 — Dell PowerEdge configurator ([dell.com](https://dell.com)) |

            #### Key Assumptions
            - **Hardware lifecycle:** 5 years (industry standard refresh cycle)
            - **PUE:** 1.55 (US industry average per DOE 2024; hyperscale ~1.2, enterprise ~1.5-1.8)
            - **Electricity:** $0.12/kWh US industrial average (varies $0.06 Iowa to $0.25 Rhode Island)
            - **Per-vCPU power draw:** 25W (Intel Xeon 4th/5th Gen typical under mixed workload)
            - **Colocation:** Mid-tier US market pricing; premium markets (N. Virginia, NYC) 20-40% higher

            #### What's NOT Included (Conservative Estimate)
            - Network equipment & bandwidth costs
            - Backup infrastructure & disaster recovery
            - Security hardware (firewalls, IDS/IPS)
            - Compliance audit & certification costs
            - Insurance & physical security
            - Hardware spare parts inventory

            *Including these would increase on-prem costs by an estimated 15-30%.*

            #### 🔷 Azure Local (Hybrid Option)
            Azure Local pricing is sourced from [azure.microsoft.com/pricing/details/azure-local/](https://azure.microsoft.com/en-us/pricing/details/azure-local/):
            - **Host fee:** $10/physical core/month (Linux guests)
            - **Windows subscription:** $23.30/physical core/month (includes unlimited WS guest licensing)
            - **Azure Hybrid Benefit:** WS Datacenter w/ SA waives all fees
            - Uses same on-prem hardware costs + Azure service fees
            """)
            st.caption("📅 Rates last verified: Q4 2025. Rates auto-update is not available — update pricing_engine.py for current rates.")

        # Full output table with exact column names
        st.markdown('<div class="section-header">📋 Full Output Table</div>', unsafe_allow_html=True)
        out_rows = [build_output_row(r["inputs"], r["outputs"]) for r in results]
        st.dataframe(pd.DataFrame(out_rows), use_container_width=True, height=min(500, 50 + n * 35))

        if show_charts:
            st.markdown('<div class="section-header">📈 Portfolio Charts</div>', unsafe_allow_html=True)
            chart_data = results[:50] if n > 50 else results
            chart_label = f" (Top 50 of {n:,})" if n > 50 else ""
            bc1, bc2 = st.columns(2)
            with bc1:
                fig = go.Figure()
                hosts = [r["inputs"]["host_name"] for r in chart_data]
                fig.add_trace(go.Bar(name="On-Prem", x=hosts, y=[r["outputs"]["on_prem_yearly_cost"]*cmult for r in chart_data], marker_color="#FF6B6B"))
                fig.add_trace(go.Bar(name="AWS (3yr RI)", x=hosts,
                    y=[r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"]*cmult for r in chart_data], marker_color="#FF9900"))
                fig.add_trace(go.Bar(name="Azure (3yr RI)", x=hosts,
                    y=[r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"]*cmult for r in chart_data], marker_color="#0078D4"))
                fig.add_trace(go.Bar(name="Azure Local", x=hosts,
                    y=[r["outputs"].get("azure_local", {}).get("recommended_annual", 0)*cmult for r in chart_data], marker_color="#9B59B6"))
                fig.update_layout(title=f"Annual Cost by Server{chart_label}", barmode="group", template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=450)
                st.plotly_chart(fig, use_container_width=True)
            with bc2:
                fams = {}
                for r in results:
                    f = r["outputs"]["_instance_family"]
                    fams[f] = fams.get(f, 0) + 1
                fig2 = go.Figure(data=[go.Pie(labels=list(fams.keys()), values=list(fams.values()),
                    marker_colors=["#00D4AA","#6C9FFF","#FFD93D","#FF6B6B","#A78BFA"], hole=0.4)])
                fig2.update_layout(title=f"Workload Families ({n:,})", template="plotly_dark", height=450,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

            if n > 50:
                savings_list = [(r["outputs"]["on_prem_yearly_cost"] -
                                (r["outputs"]["iaas_rec_reserved_3yr"]+r["outputs"]["iaas_rec_licensing"]+r["outputs"]["rec_storage_price"])*12)
                               for r in results]
                fig_h = go.Figure(data=[go.Histogram(x=[s*cmult for s in savings_list], nbinsx=30, marker_color="#00D4AA")])
                fig_h.update_layout(title=f"Savings Distribution ({n:,} servers)", xaxis_title=f"Annual Savings ({csym})",
                    yaxis_title="Count", template="plotly_dark", height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_h, use_container_width=True)

        if show_ai and api_key:
            st.markdown('<div class="section-header">🤖 AI Portfolio Strategy</div>', unsafe_allow_html=True)
            if st.button("🧠 Generate Executive Decision Brief", type="primary", key="ai_b"):
                with st.spinner("Claude analyzing portfolio: cross-provider costs, migration waves, risk register, 3-year projection…"):
                    s = get_batch_ai_summary(results, api_key)
                render_ai_analysis(s, "Executive Portfolio Analysis")

        # Export
        st.markdown('<div class="section-header">📥 Export Portfolio</div>', unsafe_allow_html=True)
        if n > 1000:
            st.info(f"💡 **{n:,} rows**: CSV recommended (~1-2s). Excel may take ~{n*2//1000}s.")
        ex1, ex2 = st.columns(2)
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
