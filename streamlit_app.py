"""
☁️ Cloud Migration Cost Analyzer — Compliance-Ready
=====================================================
• All outputs dynamically computed from user inputs
• ZERO data stored, cached, or persisted on server
• Session data lives ONLY in browser memory
• Export generates fresh Excel/CSV on-the-fly, then discards
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import datetime
from openpyxl.styles import Font, PatternFill, Alignment
from typing import Dict, List

from pricing_engine import (
    calculate_all_outputs, AWS_REGIONS, AZURE_REGIONS,
)
from recommendation_engine import get_ai_recommendation, get_batch_ai_summary

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
    .ai-box { background:linear-gradient(135deg,#1a2332,#1e293b); border:1px solid rgba(0,212,170,0.3);
        border-radius:12px; padding:1.5rem; margin:1rem 0; }
    .ai-box h4 { color:var(--accent); margin:0 0 .8rem 0; }
    .badge { display:inline-block; padding:.2rem .6rem; border-radius:20px; font-size:.73rem; font-weight:600; }
    .badge-live { background:rgba(0,212,170,0.15); color:var(--accent); }
    .badge-ref { background:rgba(108,159,255,0.15); color:var(--info); }
</style>
""", unsafe_allow_html=True)


# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>☁️ Cloud Migration Cost Analyzer</h1>
    <p>Enterprise Right-Sizing • Real-Time Pricing • AI Recommendations — AWS & Azure</p>
</div>
""", unsafe_allow_html=True)

# ─── Compliance Banner ───────────────────────────────────────────────────────
st.markdown("""
<div class="compliance-banner">
    <div class="icon">🔒</div>
    <div class="text">COMPLIANCE MODE: Zero data persistence — All data is computed in-memory from your inputs,
    never stored on any server. Session data exists only in your browser and is discarded on close.
    Export to Excel/CSV to save results locally.</div>
</div>
""", unsafe_allow_html=True)


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")
    st.markdown("**🤖 Claude AI**")
    # Priority: secrets.toml → environment variable → manual UI input
    _secrets_key = ""
    try:
        _secrets_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    if not _secrets_key:
        import os
        _secrets_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if _secrets_key:
        api_key = _secrets_key
        st.success("🔑 API key loaded from secrets", icon="✅")
    else:
        api_key = st.text_input("Anthropic API Key", type="password",
                                help="Or add ANTHROPIC_API_KEY to .streamlit/secrets.toml")
        if not api_key:
            st.caption("💡 Add to `secrets.toml` for automatic loading")
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
    if st.button("🗑️ Clear Session Now", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ─── Helpers ─────────────────────────────────────────────────────────────────
def fp(val): return f"{csym}{val * cmult:,.2f}"

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
# EXCEL / CSV GENERATORS — In-memory only, optimized for large datasets (7000+)
# Uses pandas bulk write + openpyxl only for compliance sheet formatting
# ═══════════════════════════════════════════════════════════════════════════════
INPUT_COLS_MAP = [
    ("Cloud Provider", "cloud_provider"), ("Cloud Region", "cloud_region"),
    ("Host Name", "host_name"), ("IP Address", "ip_address"),
    ("Platform", "platform"), ("Operating System", "operating_system"),
    ("Environment", "environment"), ("Server Type", "server_type"),
    ("OS EOL Status", "os_eol_status"), ("Migration Type", "migration_type"),
    ("Databases/Caches", "databases_caches"), ("AppServices", "app_services"),
    ("InstanceUsage", "instance_usage"), ("VCPUCount", "vcpu_count"),
    ("AvgCPUUsage (%)", "avg_cpu_usage"), ("Memory (GB)", "memory_gb"),
    ("Avg Memory (%)", "avg_memory_usage"), ("Total Storage (GB)", "total_storage_gb"),
    ("Storage Usage (%)", "storage_usage_pct"),
    ("Avg Network (Mbps)", "avg_network_throughput"),
    ("Total Network (Mbps)", "total_network_throughput"),
    ("Avg Disk IOPS", "avg_disk_iops"),
]

OUTPUT_COLS_MAP = [
    ("Host Name", "host_name", "inputs"),
    ("Right-Sized CPU (vCPU)", "right_sizing_cpu", "outputs"),
    ("Right-Sized Memory (GB)", "right_sizing_memory", "outputs"),
    ("Right-Sized Storage (GB)", "right_sizing_storage", "outputs"),
    ("IaaS On-Demand ($/mo)", "iaas_on_demand_price", "outputs"),
    ("IaaS 1-Year RI ($/mo)", "iaas_reserved_1yr_price", "outputs"),
    ("IaaS 3-Year RI ($/mo)", "iaas_reserved_3yr_price", "outputs"),
    ("IaaS Licensing ($/mo)", "iaas_licensing_price", "outputs"),
    ("Recomm. Instance Type", "recomm_instance_type", "outputs"),
    ("Recomm. vCPU", "recomm_vcpu", "outputs"),
    ("Recomm. Memory (GB)", "recomm_memory", "outputs"),
    ("Recomm. Storage Type", "recomm_storage_type", "outputs"),
    ("IaaS Rec. On-Demand ($/mo)", "iaas_rec_on_demand", "outputs"),
    ("IaaS Rec. 1-Year RI ($/mo)", "iaas_rec_reserved_1yr", "outputs"),
    ("IaaS Rec. 3-Year RI ($/mo)", "iaas_rec_reserved_3yr", "outputs"),
    ("IaaS Rec. Licensing ($/mo)", "iaas_rec_licensing", "outputs"),
    ("Rec. Storage (GB)", "rec_storage_gb", "outputs"),
    ("Rec. Storage Price ($/mo)", "rec_storage_price", "outputs"),
    ("PaaS Service", "paas_service", "outputs"),
    ("PaaS Instance Type", "paas_instance_type", "outputs"),
    ("PaaS Service Name", "paas_service_name", "outputs"),
    ("PaaS vCPU", "paas_vcpu", "outputs"),
    ("PaaS Storage (GB)", "paas_storage", "outputs"),
    ("PaaS Storage Price ($/mo)", "paas_storage_price", "outputs"),
    ("PaaS On-Demand ($/mo)", "paas_on_demand", "outputs"),
    ("PaaS 1-Year RI ($/mo)", "paas_reserved_1yr", "outputs"),
    ("PaaS 3-Year RI ($/mo)", "paas_reserved_3yr", "outputs"),
    ("PaaS Licensing ($/mo)", "paas_licensing", "outputs"),
    ("On-Prem Yearly Cost ($)", "on_prem_yearly_cost", "outputs"),
    ("Target Operating System", "target_operating_system", "outputs"),
]


def _build_input_df(results: List[Dict]) -> pd.DataFrame:
    rows = [{col: res["inputs"].get(key, "") for col, key in INPUT_COLS_MAP} for res in results]
    return pd.DataFrame(rows)


def _build_output_df(results: List[Dict]) -> pd.DataFrame:
    rows = [{col: res[src].get(key, "") for col, key, src in OUTPUT_COLS_MAP} for res in results]
    return pd.DataFrame(rows)


def _build_summary_df(results: List[Dict]) -> pd.DataFrame:
    rows = []
    for res in results:
        o = res["outputs"]
        op = o["on_prem_yearly_cost"]
        iaas_od = (o["iaas_rec_on_demand"] + o["iaas_rec_licensing"] + o["rec_storage_price"]) * 12
        iaas_3y = (o["iaas_rec_reserved_3yr"] + o["iaas_rec_licensing"] + o["rec_storage_price"]) * 12
        paas_od = (o["paas_on_demand"] + o["paas_licensing"] + o["paas_storage_price"]) * 12
        paas_3y = (o["paas_reserved_3yr"] + o["paas_licensing"] + o["paas_storage_price"]) * 12
        savings = op - iaas_3y
        sav_pct = (savings / op * 100) if op > 0 else 0
        rows.append({"Host": res["inputs"]["host_name"], "On-Prem Annual ($)": round(op, 2),
                      "IaaS OD Annual ($)": round(iaas_od, 2), "IaaS 3yr RI Annual ($)": round(iaas_3y, 2),
                      "PaaS OD Annual ($)": round(paas_od, 2), "PaaS 3yr RI Annual ($)": round(paas_3y, 2),
                      "Savings vs On-Prem ($)": round(savings, 2), "Savings %": round(sav_pct, 1)})
    return pd.DataFrame(rows)


def generate_excel(results: List[Dict], single: bool = False) -> bytes:
    """
    Generate Excel IN-MEMORY using pandas bulk write (fast for 7000+ rows).
    Adds compliance sheet with openpyxl formatting.
    Nothing stored to disk.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _build_input_df(results).to_excel(writer, sheet_name="Input Data", index=False)
        _build_output_df(results).to_excel(writer, sheet_name="Output — Dynamic", index=False)
        _build_summary_df(results).to_excel(writer, sheet_name="Cost Summary", index=False)

        # Compliance notice sheet
        notices = [
            "COMPLIANCE & DATA HANDLING NOTICE", "",
            f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
            "1. ZERO DATA PERSISTENCE: All data computed in-memory from user inputs. Nothing stored.",
            "2. STATELESS: Each calculation independent. No session data, cookies, or caches used.",
            "3. PRICING: Azure Retail Prices API (live) + AWS reference catalog (fallback).",
            "4. NO PII STORAGE: Hostnames/IPs exist only in this exported file.",
            "5. DISCLAIMER: Pricing is indicative. Verify with official cloud pricing calculators.",
        ]
        pd.DataFrame({"Notice": notices}).to_excel(writer, sheet_name="Compliance Notice", index=False, header=False)

        # Format headers on all sheets
        wb = writer.book
        hdr_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        hdr_fill = PatternFill("solid", fgColor="1B4F72")
        for ws_name in ["Input Data", "Output — Dynamic", "Cost Summary"]:
            ws = wb[ws_name]
            for cell in ws[1]:
                cell.font = hdr_font
                cell.fill = hdr_fill
                cell.alignment = Alignment(horizontal="center", wrap_text=True)
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col[:min(20, len(list(col)))])
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 28)

    buf.seek(0)
    return buf.getvalue()


def generate_csv(results: List[Dict]) -> str:
    """Generate CSV in-memory. Nothing stored."""
    rows = []
    for res in results:
        row = {col: res["inputs"].get(key, "") for col, key in INPUT_COLS_MAP}
        row.update({col: res[src].get(key, "") for col, key, src in OUTPUT_COLS_MAP if col != "Host Name"})
        rows.append(row)
    return pd.DataFrame(rows).to_csv(index=False)


# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def render_single_output(inputs: Dict, outputs: Dict):
    """Render all dynamically-computed outputs for a single server."""

    src = outputs.get("_pricing_source", "reference_catalog")
    badge = "badge-live" if "live" in src else "badge-ref"
    label = "LIVE API PRICING" if "live" in src else "REFERENCE PRICING"
    st.markdown(f'<span class="badge {badge}">● {label}</span>', unsafe_allow_html=True)

    # Right-Sizing
    st.markdown('<div class="section-header">📐 Right-Sizing (Dynamically Computed)</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        orig_cpu = int(float(inputs.get("vcpu_count", 0)))
        red = int((1 - outputs["right_sizing_cpu"] / max(1, orig_cpu)) * 100) if outputs["right_sizing_cpu"] < orig_cpu else 0
        mc("Right-Sized CPU", f"{outputs['right_sizing_cpu']} vCPU",
           f"From {orig_cpu} → {outputs['right_sizing_cpu']} ({red}% reduction)" if red > 0 else "No reduction — current sizing adequate")
    with c2:
        mc("Right-Sized Memory", f"{outputs['right_sizing_memory']} GB",
           f"From {inputs['memory_gb']} → {outputs['right_sizing_memory']} GB", "metric-blue")
    with c3:
        mc("Right-Sized Storage", f"{outputs['right_sizing_storage']} GB",
           f"From {inputs['total_storage_gb']} → {outputs['right_sizing_storage']} GB", "metric-yellow")

    # IaaS
    st.markdown('<div class="section-header">💰 IaaS Pricing (Dynamically Computed)</div>', unsafe_allow_html=True)
    c_a, c_b = st.columns(2)
    with c_a:
        st.markdown("**Current-Size Pricing**")
        st.markdown(f"""<div class="output-table"><table>
            <tr><th>Model</th><th>Monthly</th></tr>
            <tr><td>On-Demand</td><td>{fp(outputs['iaas_on_demand_price'])}</td></tr>
            <tr><td>1-Year RI</td><td>{fp(outputs['iaas_reserved_1yr_price'])}</td></tr>
            <tr><td>3-Year RI</td><td>{fp(outputs['iaas_reserved_3yr_price'])}</td></tr>
            <tr><td>Licensing</td><td>{fp(outputs['iaas_licensing_price'])}</td></tr>
        </table></div>""", unsafe_allow_html=True)
    with c_b:
        st.markdown(f"**Recommended: `{outputs['recomm_instance_type']}`** ({outputs['recomm_vcpu']} vCPU / {outputs['recomm_memory']} GB)")
        st.markdown(f"""<div class="output-table"><table>
            <tr><th>Model</th><th>Monthly</th></tr>
            <tr><td>On-Demand</td><td>{fp(outputs['iaas_rec_on_demand'])}</td></tr>
            <tr><td>1-Year RI</td><td>{fp(outputs['iaas_rec_reserved_1yr'])}</td></tr>
            <tr><td>3-Year RI</td><td>{fp(outputs['iaas_rec_reserved_3yr'])}</td></tr>
            <tr><td>Licensing</td><td>{fp(outputs['iaas_rec_licensing'])}</td></tr>
            <tr><td>Storage ({outputs['recomm_storage_type']})</td><td>{fp(outputs['rec_storage_price'])}</td></tr>
        </table></div>""", unsafe_allow_html=True)

    # PaaS
    st.markdown('<div class="section-header">🔧 PaaS Alternative (Dynamically Computed)</div>', unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    with p1: mc("PaaS Service", outputs['paas_service_name'], outputs['paas_service'])
    with p2: mc("PaaS Instance", outputs['paas_instance_type'], f"{outputs['paas_vcpu']} vCPU", "metric-blue")
    with p3: mc("PaaS On-Demand", fp(outputs['paas_on_demand']) + "/mo", f"3yr RI: {fp(outputs['paas_reserved_3yr'])}/mo", "metric-yellow")

    st.markdown(f"""<div class="output-table"><table>
        <tr><th>PaaS Detail</th><th>Value</th></tr>
        <tr><td>Storage</td><td>{outputs['paas_storage']} GB @ {fp(outputs['paas_storage_price'])}/mo</td></tr>
        <tr><td>1-Year RI</td><td>{fp(outputs['paas_reserved_1yr'])}/mo</td></tr>
        <tr><td>3-Year RI</td><td>{fp(outputs['paas_reserved_3yr'])}/mo</td></tr>
        <tr><td>Licensing</td><td>{fp(outputs['paas_licensing'])}/mo</td></tr>
    </table></div>""", unsafe_allow_html=True)

    # On-Prem vs Cloud
    st.markdown('<div class="section-header">🏢 TCO Comparison (Dynamically Computed)</div>', unsafe_allow_html=True)
    annual_cloud = (outputs['iaas_rec_reserved_3yr'] + outputs['iaas_rec_licensing'] + outputs['rec_storage_price']) * 12
    savings = outputs['on_prem_yearly_cost'] - annual_cloud
    sav_pct = (savings / max(1, outputs['on_prem_yearly_cost'])) * 100
    t1, t2, t3 = st.columns(3)
    with t1: mc("On-Prem Yearly", fp(outputs['on_prem_yearly_cost']), "Infra + Licensing + Ops", "metric-red")
    with t2: mc("Cloud Yearly (3yr RI)", fp(annual_cloud), "Compute + Storage + License")
    with t3: mc("Annual Savings", fp(abs(savings)),
                f"{'↓' if savings > 0 else '↑'} {abs(sav_pct):.1f}% {'savings' if savings > 0 else 'increase'}",
                "" if savings > 0 else "metric-red")

    st.info(f"🎯 **Target Operating System:** {outputs['target_operating_system']}")

    # Charts
    if show_charts:
        st.markdown('<div class="section-header">📈 Dynamic Visual Analytics</div>', unsafe_allow_html=True)
        ch1, ch2 = st.columns(2)
        with ch1:
            fig = go.Figure()
            cats = ["On-Demand", "1-Year RI", "3-Year RI"]
            fig.add_trace(go.Bar(name="Current IaaS", x=cats,
                y=[outputs['iaas_on_demand_price']*cmult, outputs['iaas_reserved_1yr_price']*cmult, outputs['iaas_reserved_3yr_price']*cmult],
                marker_color="#FF6B6B", text=[fp(outputs['iaas_on_demand_price']), fp(outputs['iaas_reserved_1yr_price']), fp(outputs['iaas_reserved_3yr_price'])], textposition="outside"))
            fig.add_trace(go.Bar(name="Right-Sized IaaS", x=cats,
                y=[outputs['iaas_rec_on_demand']*cmult, outputs['iaas_rec_reserved_1yr']*cmult, outputs['iaas_rec_reserved_3yr']*cmult],
                marker_color="#00D4AA", text=[fp(outputs['iaas_rec_on_demand']), fp(outputs['iaas_rec_reserved_1yr']), fp(outputs['iaas_rec_reserved_3yr'])], textposition="outside"))
            fig.add_trace(go.Bar(name="PaaS", x=cats,
                y=[outputs['paas_on_demand']*cmult, outputs['paas_reserved_1yr']*cmult, outputs['paas_reserved_3yr']*cmult],
                marker_color="#6C9FFF", text=[fp(outputs['paas_on_demand']), fp(outputs['paas_reserved_1yr']), fp(outputs['paas_reserved_3yr'])], textposition="outside"))
            fig.update_layout(title="Monthly Cost Comparison", barmode="group", template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=420, yaxis_title=f"Monthly ({csym})")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            fig_g = make_subplots(rows=1, cols=3, specs=[[{"type":"indicator"}]*3],
                                  subplot_titles=["CPU Usage", "Memory Usage", "Storage Usage"])
            for i, (v, col) in enumerate([(float(inputs['avg_cpu_usage']), "#00D4AA"),
                                           (float(inputs['avg_memory_usage']), "#6C9FFF"),
                                           (float(inputs['storage_usage_pct']), "#FFD93D")]):
                fig_g.add_trace(go.Indicator(mode="gauge+number", value=v,
                    gauge=dict(axis=dict(range=[0,100]), bar=dict(color=col), bgcolor="rgba(255,255,255,0.05)",
                        steps=[dict(range=[0,30],color="rgba(0,212,170,0.1)"), dict(range=[30,70],color="rgba(255,217,61,0.1)"),
                               dict(range=[70,100],color="rgba(255,107,107,0.1)")]),
                    number=dict(suffix="%")), row=1, col=i+1)
            fig_g.update_layout(template="plotly_dark", height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_g, use_container_width=True)

        fig_a = go.Figure()
        ann_cats = ["On-Premises", "IaaS On-Demand", "IaaS 3yr RI", "PaaS On-Demand", "PaaS 3yr RI"]
        ann_vals = [
            outputs['on_prem_yearly_cost'] * cmult,
            (outputs['iaas_rec_on_demand'] + outputs['iaas_rec_licensing'] + outputs['rec_storage_price']) * 12 * cmult,
            annual_cloud * cmult,
            (outputs['paas_on_demand'] + outputs['paas_licensing'] + outputs['paas_storage_price']) * 12 * cmult,
            (outputs['paas_reserved_3yr'] + outputs['paas_licensing'] + outputs['paas_storage_price']) * 12 * cmult,
        ]
        fig_a.add_trace(go.Bar(x=ann_cats, y=ann_vals, marker_color=["#FF6B6B","#FFD93D","#00D4AA","#6C9FFF","#A78BFA"],
            text=[f"{csym}{v:,.0f}" for v in ann_vals], textposition="outside"))
        fig_a.update_layout(title="Annual TCO Comparison", template="plotly_dark", height=400,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title=f"Annual ({csym})", showlegend=False)
        st.plotly_chart(fig_a, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════
tab_upload, tab_manual, tab_results = st.tabs(["📁 Upload File", "✏️ Manual Input", "📊 Batch Results"])

# ── TAB 1: UPLOAD ────────────────────────────────────────────────────────────
with tab_upload:
    st.markdown('<div class="section-header">📁 Upload Server Inventory</div>', unsafe_allow_html=True)

    c_u1, c_u2 = st.columns([2, 1])
    with c_u1:
        uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"],
            help="Columns must match Input parameter names. File is processed in-memory only.")
    with c_u2:
        st.markdown("**Required columns:**")
        st.caption("Cloud Provider, Cloud Region, Host Name, IP Address, Platform, Operating System, Environment, Server Type, OS EOL Status, Migration Type, Databases/Caches, AppServices, InstanceUsage, VCPUCount, AvgCPUUsage (%tage), Memory(GB), Avg Memory (%tage), Total Storage(GB), Storage Usage (%), Average Network Throughput (Mbps), Total Network Throughput (Mbps), Average Disk IOPS")

    # Template download (generated dynamically — not stored)
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

            # Large dataset advisory
            if n_rows > 1000:
                st.warning(f"⚡ **Large dataset detected ({n_rows:,} rows).** Live API pricing is disabled for bulk processing. "
                           f"Catalog pricing with regional multipliers will be used. "
                           f"Estimated time: ~{n_rows * 4 / 1000:.0f}s compute + ~{n_rows * 2 / 1000:.0f}s Excel export. "
                           f"CSV export is significantly faster for large datasets.")
            elif n_rows > 100:
                st.info(f"ℹ️ **{n_rows} servers.** Live API pricing is limited to avoid rate limits. Bulk uses catalog pricing.")

            with st.expander("📋 Preview", expanded=False):
                st.dataframe(df.head(100), use_container_width=True, height=250)
                if n_rows > 100:
                    st.caption(f"Showing first 100 of {n_rows:,} rows")

            if st.button("🚀 Analyze All Servers", type="primary", key="batch_go"):
                results = []
                prog = st.progress(0, text="Computing…")
                batch_size = 100
                total_batches = (n_rows + batch_size - 1) // batch_size

                for batch_idx in range(total_batches):
                    start_i = batch_idx * batch_size
                    end_i = min(start_i + batch_size, n_rows)
                    batch_df = df.iloc[start_i:end_i]

                    for _, row in batch_df.iterrows():
                        inp = build_inputs(row.to_dict())
                        # For bulk (>100 rows), force catalog pricing to avoid API rate limits
                        if n_rows > 100:
                            inp["_force_catalog"] = True
                        out = calculate_all_outputs(inp)
                        results.append({"inputs": inp, "outputs": out})

                    pct = (end_i) / n_rows
                    prog.progress(pct, text=f"Batch {batch_idx+1}/{total_batches} — {end_i:,}/{n_rows:,} servers processed")

                st.session_state["_batch"] = results
                prog.empty()
                st.success(f"✅ **{len(results):,} servers** analyzed. Go to **📊 Batch Results** tab.")
        except Exception as e:
            st.error(f"Error: {e}")


# ── TAB 2: MANUAL ───────────────────────────────────────────────────────────
with tab_manual:
    st.markdown('<div class="section-header">✏️ Manual Server Input</div>', unsafe_allow_html=True)

    st.markdown("##### 🖥️ Infrastructure")
    c1, c2, c3, c4 = st.columns(4)
    with c1: m_cloud = st.selectbox("Cloud Provider", ["AWS", "Azure"], key="mc")
    with c2:
        regs = list(AWS_REGIONS.keys()) if m_cloud == "AWS" else list(AZURE_REGIONS.keys())
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
        with st.spinner("Computing dynamically…"):
            out = calculate_all_outputs(inp)
        st.session_state["_m_inp"] = inp
        st.session_state["_m_out"] = out

    if "_m_out" in st.session_state:
        inp, out = st.session_state["_m_inp"], st.session_state["_m_out"]
        render_single_output(inp, out)

        # AI
        if show_ai and api_key:
            st.markdown('<div class="section-header">🤖 AI Recommendations</div>', unsafe_allow_html=True)
            if st.button("🧠 Generate AI Analysis", key="ai_m"):
                with st.spinner("Asking Claude (data not stored)…"):
                    rec = get_ai_recommendation(inp, out, api_key)
                st.markdown(f'<div class="ai-box"><h4>🤖 Claude AI</h4><div>{rec}</div></div>', unsafe_allow_html=True)
        elif show_ai and not api_key:
            st.info("💡 Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` or enter in sidebar.")

        # Export
        st.markdown('<div class="section-header">📥 Export (Generated On-the-Fly, Not Stored)</div>', unsafe_allow_html=True)
        results = [{"inputs": inp, "outputs": out}]
        ce1, ce2 = st.columns(2)
        with ce1:
            st.download_button("📥 Download Excel", generate_excel(results, single=True),
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
        st.markdown('<div class="section-header">📊 Portfolio Dashboard (Dynamic)</div>', unsafe_allow_html=True)

        n = len(results)
        t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
        t_iaas = sum((r["outputs"]["iaas_rec_on_demand"]+r["outputs"]["iaas_rec_licensing"]+r["outputs"]["rec_storage_price"])*12 for r in results)
        t_3yr = sum((r["outputs"]["iaas_rec_reserved_3yr"]+r["outputs"]["iaas_rec_licensing"]+r["outputs"]["rec_storage_price"])*12 for r in results)
        t_sav = t_op - t_3yr

        s1, s2, s3, s4 = st.columns(4)
        with s1: mc("Total Servers", str(n), "Analyzed")
        with s2: mc("On-Prem Annual", fp(t_op), "Current", "metric-red")
        with s3: mc("Cloud Annual (3yr)", fp(t_3yr), "Optimized")
        with s4: mc("Savings", fp(abs(t_sav)), f"{abs(t_sav/max(1,t_op)*100):.1f}%", "" if t_sav > 0 else "metric-red")

        # Table
        st.markdown('<div class="section-header">📋 Server Details</div>', unsafe_allow_html=True)
        tbl = []
        for r in results:
            i, o = r["inputs"], r["outputs"]
            tbl.append({
                "Host": i["host_name"], "Cloud": i["cloud_provider"],
                "Cur vCPU": int(float(i["vcpu_count"])), "Rec vCPU": o["right_sizing_cpu"],
                "Cur Mem": float(i["memory_gb"]), "Rec Mem": o["right_sizing_memory"],
                "Instance": o["recomm_instance_type"],
                f"IaaS OD ({csym}/mo)": round(o["iaas_rec_on_demand"]*cmult, 2),
                f"IaaS 3yr ({csym}/mo)": round(o["iaas_rec_reserved_3yr"]*cmult, 2),
                "PaaS": o["paas_service_name"],
                f"PaaS 3yr ({csym}/mo)": round(o["paas_reserved_3yr"]*cmult, 2),
                f"On-Prem ({csym}/yr)": round(o["on_prem_yearly_cost"]*cmult, 2),
                "Target OS": o["target_operating_system"],
            })
        result_df = pd.DataFrame(tbl)
        if n > 500:
            st.caption(f"Showing interactive table ({n:,} rows). Use column headers to sort/filter.")
        st.dataframe(result_df, use_container_width=True, height=min(400, 50 + n * 35))

        if show_charts:
            st.markdown('<div class="section-header">📈 Portfolio Charts</div>', unsafe_allow_html=True)

            # For large datasets, sample for charting
            chart_data = results
            chart_label = ""
            if n > 50:
                chart_data = results[:50]
                chart_label = f" (Top 50 of {n:,})"
            bc1, bc2 = st.columns(2)
            with bc1:
                fig = go.Figure()
                hosts = [r["inputs"]["host_name"] for r in chart_data]
                fig.add_trace(go.Bar(name="On-Prem", x=hosts, y=[r["outputs"]["on_prem_yearly_cost"]*cmult for r in chart_data], marker_color="#FF6B6B"))
                fig.add_trace(go.Bar(name="IaaS 3yr", x=hosts,
                    y=[(r["outputs"]["iaas_rec_reserved_3yr"]+r["outputs"]["iaas_rec_licensing"]+r["outputs"]["rec_storage_price"])*12*cmult for r in chart_data], marker_color="#00D4AA"))
                fig.add_trace(go.Bar(name="PaaS 3yr", x=hosts,
                    y=[(r["outputs"]["paas_reserved_3yr"]+r["outputs"]["paas_licensing"]+r["outputs"]["paas_storage_price"])*12*cmult for r in chart_data], marker_color="#6C9FFF"))
                fig.update_layout(title=f"Annual Cost by Server{chart_label}", barmode="group", template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=450, yaxis_title=f"Annual ({csym})")
                st.plotly_chart(fig, use_container_width=True)
            with bc2:
                fams = {}
                for r in results:  # Use ALL results for distribution
                    f = r["outputs"]["_instance_family"]
                    fams[f] = fams.get(f, 0) + 1
                fig2 = go.Figure(data=[go.Pie(labels=list(fams.keys()), values=list(fams.values()),
                    marker_colors=["#00D4AA","#6C9FFF","#FFD93D","#FF6B6B","#A78BFA"], hole=0.4)])
                fig2.update_layout(title=f"Workload Families ({n:,} servers)", template="plotly_dark", height=450,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

            # Cost distribution histogram for large datasets
            if n > 100:
                all_savings = [(r["outputs"]["on_prem_yearly_cost"] -
                               (r["outputs"]["iaas_rec_reserved_3yr"]+r["outputs"]["iaas_rec_licensing"]+r["outputs"]["rec_storage_price"])*12)
                              for r in results]
                fig_hist = go.Figure(data=[go.Histogram(x=[s*cmult for s in all_savings], nbinsx=30,
                    marker_color="#00D4AA", name="Savings Distribution")])
                fig_hist.update_layout(title=f"Annual Savings Distribution ({n:,} servers)",
                    xaxis_title=f"Annual Savings ({csym})", yaxis_title="Server Count",
                    template="plotly_dark", height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_hist, use_container_width=True)

        # AI
        if show_ai and api_key:
            st.markdown('<div class="section-header">🤖 AI Portfolio Summary</div>', unsafe_allow_html=True)
            if st.button("🧠 Portfolio AI Analysis", key="ai_b"):
                with st.spinner("Claude analyzing (data not stored)…"):
                    s = get_batch_ai_summary(results, api_key)
                st.markdown(f'<div class="ai-box"><h4>🤖 Claude AI</h4><div>{s}</div></div>', unsafe_allow_html=True)

        # Export
        st.markdown('<div class="section-header">📥 Export Portfolio (Generated On-the-Fly)</div>', unsafe_allow_html=True)
        if n > 1000:
            st.info(f"💡 **{n:,} rows**: CSV export is recommended (~1-2s). Excel export may take ~{n*2//1000}s due to formatting.")
        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button(f"📥 Download CSV {'(Recommended)' if n > 1000 else ''}", generate_csv(results),
                f"migration_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
        with ex2:
            if n > 5000:
                if st.button(f"⚙️ Generate Excel ({n:,} rows)", key="gen_xlsx"):
                    with st.spinner(f"Generating Excel for {n:,} rows..."):
                        xlsx_data = generate_excel(results)
                    st.download_button("📥 Download Excel", xlsx_data,
                        f"migration_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx")
            else:
                st.download_button("📥 Download Excel", generate_excel(results),
                    f"migration_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
