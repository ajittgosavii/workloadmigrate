"""
PDF Executive Report Generator — Detailed Budget-Grade Output
================================================================
Generates comprehensive PDF reports with 12 sections covering all
cost analysis, budget-grade data, and migration planning.

Report sections:
  1.  Cover Page & Portfolio Metrics
  2.  Executive Summary
  3.  Multi-Cloud Cost Comparison
  4.  On-Premises Cost Breakdown (8 components)
  5.  Enhanced Analysis (Network, DR, Storage, Serverless)
  6.  Budget-Grade Analysis (Support, Migration, Confidence, TCO)
  7.  PaaS & Modern Options
  8.  Server-by-Server Detail
  9.  Azure Local Comparison
  10. Migration Wave Plan
  11. AI Strategic Analysis
  12. Methodology & Rate Sources
"""

import io
from datetime import datetime
from typing import Dict, List, Optional

try:
    from scenario_engine import generate_wave_plan
    HAS_WAVE_PLAN = True
except ImportError:
    HAS_WAVE_PLAN = False


def generate_pdf_report(
    results: List[Dict],
    report_title: str = "Infosys Cobalt — Migration Analysis Report",
    currency_symbol: str = "$",
    currency_multiplier: float = 1.0,
    include_ai_analysis: Optional[str] = None,
) -> bytes:
    """
    Generate a comprehensive PDF report with 12 sections.

    Args:
        results: List of {"inputs": ..., "outputs": ...} dicts
        report_title: Report title
        currency_symbol: Currency symbol for formatting
        currency_multiplier: Currency conversion multiplier
        include_ai_analysis: Optional AI-generated analysis text

    Returns:
        PDF bytes ready for download
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor, black, white
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        return _generate_simple_pdf(results, report_title, currency_symbol, currency_multiplier)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6*inch,
                            bottomMargin=0.6*inch, leftMargin=0.65*inch,
                            rightMargin=0.65*inch)

    styles = getSampleStyleSheet()
    story = []

    # ── Custom styles ─────────────────────────────────────────────────────────
    BLUE = '#003F72'
    ACCENT = '#0078D4'
    LIGHT_BG = '#F2F8FD'
    GRAY = '#666666'

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=24, textColor=HexColor(ACCENT),
        spaceAfter=8, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=11, textColor=HexColor(GRAY),
        alignment=TA_CENTER, spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontSize=15, textColor=HexColor(BLUE),
        spaceBefore=16, spaceAfter=8,
        borderWidth=1, borderColor=HexColor(ACCENT),
        borderPadding=4,
    )
    subheading_style = ParagraphStyle(
        'SubHeading', parent=styles['Heading3'],
        fontSize=12, textColor=HexColor('#2C5364'),
        spaceBefore=10, spaceAfter=5,
    )
    body_style = ParagraphStyle(
        'CustomBody', parent=styles['Normal'],
        fontSize=9, leading=13,
    )
    small_style = ParagraphStyle(
        'Small', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=HexColor('#888888'),
    )
    disclaimer_style = ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontSize=7, textColor=HexColor('#999999'),
        leading=9, spaceBefore=10,
    )

    cs = currency_symbol
    cm = currency_multiplier

    def fp(val):
        """Format price."""
        return f"{cs}{val * cm:,.2f}"

    def fpk(val):
        """Format price in thousands."""
        v = val * cm
        if abs(v) >= 1_000_000:
            return f"{cs}{v/1_000_000:,.1f}M"
        if abs(v) >= 10_000:
            return f"{cs}{v/1_000:,.0f}K"
        return f"{cs}{v:,.2f}"

    def pct(num, den):
        """Safe percentage."""
        return f"{(num / max(1, den)) * 100:.1f}%"

    def _styled_table(data, col_widths, font_size=8):
        """Build a styled table with header row."""
        t = Table(data, colWidths=col_widths)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(BLUE)),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), font_size),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor(LIGHT_BG)]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

    # ══════════════════════════════════════════════════════════════════════════
    # AGGREGATE METRICS (calculated once, used across sections)
    # ══════════════════════════════════════════════════════════════════════════
    n = len(results)
    t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
    t_aws = sum(r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"] for r in results)
    t_az = sum(r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"] for r in results)
    t_azl = sum(r["outputs"].get("azure_local", {}).get("recommended_annual", 0) for r in results)
    t_paas = sum(r["outputs"].get("paas_annual_3yr_ri", 0) for r in results)
    t_best = min(t_aws, t_az)
    t_sav = t_op - t_best
    best_provider = "AWS" if t_aws <= t_az else "Azure"

    # Enhanced aggregates
    t_net_aws = sum(r["outputs"].get("network_costs", {}).get("total_annual", 0) for r in results)
    t_dr_aws = sum(r["outputs"].get("dr_backup_costs", {}).get("combined_annual", 0) for r in results)
    t_stor_sav = sum(r["outputs"].get("storage_tiers", {}).get("savings_monthly", 0) * 12 for r in results)

    # Budget aggregates
    t_support_aws = sum(r["outputs"].get("cross_provider", {}).get("AWS", {}).get("support", {}).get("annual_cost", 0) for r in results)
    t_support_az = sum(r["outputs"].get("cross_provider", {}).get("Azure", {}).get("support", {}).get("annual_cost", 0) for r in results)
    t_mig_labor = sum(r["outputs"].get("budget_migration_labor", {}).get("migration_labor", 0) for r in results)
    t_mig_testing = sum(r["outputs"].get("budget_migration_labor", {}).get("testing_validation", 0) for r in results)
    t_mig_training = sum(r["outputs"].get("budget_migration_labor", {}).get("training", 0) for r in results)
    t_mig_parallel = sum(r["outputs"].get("budget_migration_labor", {}).get("parallel_run", 0) for r in results)
    t_mig_total = sum(r["outputs"].get("budget_total_one_time", 0) for r in results)
    t_budget_aws = sum(r["outputs"].get("budget_aws_all_in_annual", 0) for r in results)
    t_budget_az = sum(r["outputs"].get("budget_azure_all_in_annual", 0) for r in results)

    # Confidence ranges (portfolio-level)
    t_aws_p10 = sum(r["outputs"].get("budget_aws_confidence", {}).get("low_annual", 0) for r in results)
    t_aws_p50 = sum(r["outputs"].get("budget_aws_confidence", {}).get("expected_annual", 0) for r in results)
    t_aws_p90 = sum(r["outputs"].get("budget_aws_confidence", {}).get("high_annual", 0) for r in results)
    t_aws_budget = sum(r["outputs"].get("budget_aws_confidence", {}).get("budget_annual", 0) for r in results)
    t_az_p10 = sum(r["outputs"].get("budget_azure_confidence", {}).get("low_annual", 0) for r in results)
    t_az_p50 = sum(r["outputs"].get("budget_azure_confidence", {}).get("expected_annual", 0) for r in results)
    t_az_p90 = sum(r["outputs"].get("budget_azure_confidence", {}).get("high_annual", 0) for r in results)
    t_az_budget = sum(r["outputs"].get("budget_azure_confidence", {}).get("budget_annual", 0) for r in results)

    # On-prem breakdown aggregates
    t_hw_compute = sum(r["outputs"].get("on_prem_breakdown", {}).get("hw_compute", 0) for r in results)
    t_hw_memory = sum(r["outputs"].get("on_prem_breakdown", {}).get("hw_memory", 0) for r in results)
    t_hw_storage = sum(r["outputs"].get("on_prem_breakdown", {}).get("hw_storage", 0) for r in results)
    t_power = sum(r["outputs"].get("on_prem_breakdown", {}).get("power_cooling", 0) for r in results)
    t_facility = sum(r["outputs"].get("on_prem_breakdown", {}).get("facility", 0) for r in results)
    t_labor = sum(r["outputs"].get("on_prem_breakdown", {}).get("admin_labor", 0) for r in results)
    t_os_lic = sum(r["outputs"].get("on_prem_breakdown", {}).get("annual_licensing", 0) for r in results)
    t_db_lic = sum(r["outputs"].get("on_prem_breakdown", {}).get("db_licensing_annual", 0) for r in results)

    # Azure Local aggregates
    t_azl_linux = sum(r["outputs"].get("azure_local", {}).get("linux_total_annual", 0) for r in results)
    t_azl_win = sum(r["outputs"].get("azure_local", {}).get("windows_total_annual", 0) for r in results)
    t_azl_ahb = sum(r["outputs"].get("azure_local", {}).get("ahb_total_annual", 0) for r in results)

    # All-In
    t_allin_aws = t_aws + t_net_aws + t_dr_aws
    t_allin_az = t_az + t_net_aws + t_dr_aws  # Same network/DR estimate

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1: COVER PAGE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 80))
    story.append(Paragraph(report_title, title_style))
    story.append(Paragraph(
        f"Budget-Grade Cloud Migration Analysis<br/>"
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}<br/>"
        f"Servers: {n} | Compliance: Zero Data Persistence",
        subtitle_style
    ))
    story.append(Spacer(1, 20))

    # Portfolio summary table
    cover_data = [
        ['Portfolio Metric', 'Value'],
        ['Total Servers Analyzed', str(n)],
        ['On-Premises Annual Cost', fp(t_op)],
        ['AWS Annual (3yr RI)', fp(t_aws)],
        ['Azure Annual (3yr RI)', fp(t_az)],
        ['Azure Local Annual', fp(t_azl)],
        ['Best Cloud Provider', best_provider],
        ['Annual Savings (IaaS only)', f"{fp(abs(t_sav))} ({pct(abs(t_sav), t_op)})"],
        ['', ''],
        ['AWS Budget All-In (w/ Support)', fp(t_budget_aws)],
        ['Azure Budget All-In (w/ Support)', fp(t_budget_az)],
        ['Total Migration One-Time Cost', fp(t_mig_total)],
        [f'{best_provider} Confidence: P10 (Low)', fp(t_aws_p10 if best_provider == "AWS" else t_az_p10)],
        [f'{best_provider} Confidence: P50 + Contingency', fp(t_aws_budget if best_provider == "AWS" else t_az_budget)],
        [f'{best_provider} Confidence: P90 (High)', fp(t_aws_p90 if best_provider == "AWS" else t_az_p90)],
    ]
    story.append(_styled_table(cover_data, [3.5*inch, 3*inch], font_size=9))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2: EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Executive Summary", heading_style))

    # Break-even summary
    breakeven_years = []
    for r in results:
        be = r["outputs"].get("budget_summary", {}).get("breakeven_year")
        if be:
            breakeven_years.append(be)
    avg_breakeven = f"Year {sum(breakeven_years) / len(breakeven_years):.1f}" if breakeven_years else "N/A"

    story.append(Paragraph(
        f"This analysis evaluates <b>{n} servers</b> for cloud migration across AWS, Azure, "
        f"and Azure Local (hybrid). The total on-premises annual cost is <b>{fp(t_op)}</b>.",
        body_style
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>IaaS-only savings:</b> Migrating to <b>{best_provider}</b> with 3-year reserved "
        f"instances yields <b>{fp(abs(t_sav))}</b> annual savings (<b>{pct(abs(t_sav), t_op)}</b> reduction).",
        body_style
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Budget All-In (IaaS + Network + DR + Support):</b> "
        f"AWS: <b>{fp(t_budget_aws)}</b>/yr | Azure: <b>{fp(t_budget_az)}</b>/yr. "
        f"Including 10% contingency, the budget recommendation for <b>{best_provider}</b> is "
        f"<b>{fp(t_aws_budget if best_provider == 'AWS' else t_az_budget)}</b>/yr.",
        body_style
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Migration investment:</b> Total one-time cost of <b>{fp(t_mig_total)}</b> "
        f"(labor + testing + training + parallel run + data transfer). "
        f"Average break-even: <b>{avg_breakeven}</b>.",
        body_style
    ))
    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3: MULTI-CLOUD COST COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Multi-Cloud Cost Comparison", heading_style))

    comp_data = [
        ['Provider', 'IaaS (3yr RI)', 'Network/yr', 'DR+Backup/yr', 'Support/yr', 'All-In/yr', 'Budget All-In/yr'],
        ['On-Premises', fp(t_op), '-', '-', '-', fp(t_op), fp(t_op)],
        ['AWS', fp(t_aws), fp(t_net_aws), fp(t_dr_aws), fp(t_support_aws), fp(t_allin_aws), fp(t_budget_aws)],
        ['Azure', fp(t_az), fp(t_net_aws), fp(t_dr_aws), fp(t_support_az), fp(t_allin_az), fp(t_budget_az)],
        ['Azure Local', fp(t_azl), '-', '-', '-', fp(t_azl), fp(t_azl)],
        ['PaaS (3yr RI)', fp(t_paas), '-', '-', '-', fp(t_paas), '-'],
    ]
    story.append(_styled_table(comp_data, [1.0*inch, 0.9*inch, 0.85*inch, 0.9*inch, 0.85*inch, 0.9*inch, 1.0*inch], font_size=7))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>All-In = IaaS + Network Egress + DR/Backup. Budget All-In adds Support Plan costs.</i>",
        small_style
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4: ON-PREMISES COST BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("3. On-Premises Cost Breakdown (8 Components)", heading_style))

    story.append(Paragraph(
        f"Total on-premises annual cost across {n} servers: <b>{fp(t_op)}</b>. "
        f"Breakdown by industry-sourced component:",
        body_style
    ))
    story.append(Spacer(1, 6))

    onprem_data = [
        ['Component', 'Annual Total', '% of Total', 'Rate'],
        ['Hardware Compute', fp(t_hw_compute), pct(t_hw_compute, t_op), '$130/vCPU/yr'],
        ['Hardware Memory', fp(t_hw_memory), pct(t_hw_memory, t_op), '$10/GB/yr'],
        ['Hardware Storage', fp(t_hw_storage), pct(t_hw_storage, t_op), '$0.08/GB/yr'],
        ['Power & Cooling', fp(t_power), pct(t_power, t_op), '25W/vCPU, PUE 1.55, $0.12/kWh'],
        ['Facility / Rack', fp(t_facility), pct(t_facility, t_op), '$1,200/server/yr'],
        ['Admin & Labor', fp(t_labor), pct(t_labor, t_op), '$1,500/server/yr'],
        ['OS Licensing', fp(t_os_lic), pct(t_os_lic, t_op), 'Win $5.50, RHEL $3, SUSE $2.50/vCPU/mo'],
        ['DB Licensing', fp(t_db_lic), pct(t_db_lic, t_op), 'Oracle $9,975, SQL Ent $3,400/vCPU/yr'],
        ['TOTAL', fp(t_op), '100%', ''],
    ]
    story.append(_styled_table(onprem_data, [1.4*inch, 1.2*inch, 0.8*inch, 3.1*inch], font_size=8))
    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5: ENHANCED ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Enhanced Analysis — Network, DR, Storage, Modern Options", heading_style))

    # Network
    story.append(Paragraph("<b>Network & Egress</b>", subheading_style))
    t_egress_mo = sum(r["outputs"].get("network_costs", {}).get("egress", {}).get("monthly_cost", 0) for r in results)
    t_vpn_mo = sum(r["outputs"].get("network_costs", {}).get("vpn", {}).get("monthly_cost", 0) for r in results)
    t_lb_mo = sum(r["outputs"].get("network_costs", {}).get("load_balancer", {}).get("monthly_cost", 0) for r in results)

    net_data = [
        ['Component', 'Monthly', 'Annual'],
        ['Data Egress', fp(t_egress_mo), fp(t_egress_mo * 12)],
        ['VPN / Connectivity', fp(t_vpn_mo), fp(t_vpn_mo * 12)],
        ['Load Balancers', fp(t_lb_mo), fp(t_lb_mo * 12)],
        ['Total Network', fp(t_net_aws / 12), fp(t_net_aws)],
    ]
    story.append(_styled_table(net_data, [2.5*inch, 1.8*inch, 2.2*inch], font_size=8))
    story.append(Spacer(1, 8))

    # DR & Backup
    story.append(Paragraph("<b>DR & Backup</b>", subheading_style))
    t_backup_mo = sum(r["outputs"].get("dr_backup_costs", {}).get("backup", {}).get("total_monthly", 0) for r in results)
    t_dr_mo = sum(r["outputs"].get("dr_backup_costs", {}).get("dr", {}).get("total_monthly", 0) for r in results)

    # DR strategy distribution
    dr_strategies = {}
    for r in results:
        strat = r["outputs"].get("_dr_strategy", "pilot_light")
        dr_strategies[strat] = dr_strategies.get(strat, 0) + 1
    dr_strat_text = ", ".join(f"{k}: {v}" for k, v in sorted(dr_strategies.items(), key=lambda x: -x[1]))

    dr_data = [
        ['Component', 'Monthly', 'Annual'],
        ['Backup Storage', fp(t_backup_mo), fp(t_backup_mo * 12)],
        ['DR Compute + Services', fp(t_dr_mo), fp(t_dr_mo * 12)],
        ['Total DR + Backup', fp((t_backup_mo + t_dr_mo)), fp(t_dr_aws)],
    ]
    story.append(_styled_table(dr_data, [2.5*inch, 1.8*inch, 2.2*inch], font_size=8))
    story.append(Paragraph(f"<i>DR Strategy Mix: {dr_strat_text}</i>", small_style))
    story.append(Spacer(1, 8))

    # Storage Optimization
    story.append(Paragraph("<b>Storage Tier Optimization</b>", subheading_style))
    story.append(Paragraph(
        f"By distributing storage across hot/warm/cool/archive tiers, estimated annual savings: "
        f"<b>{fp(t_stor_sav)}</b>.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Serverless & Container
    story.append(Paragraph("<b>Serverless & Container Options</b>", subheading_style))
    sl_suitable = sum(1 for r in results if r["outputs"].get("modern_options", {}).get("serverless", {}).get("suitable"))
    ct_total = sum(r["outputs"].get("modern_options", {}).get("container", {}).get("monthly_cost", 0) for r in results)
    sl_total = sum(r["outputs"].get("modern_options", {}).get("serverless", {}).get("monthly_cost", 0)
                   for r in results if r["outputs"].get("modern_options", {}).get("serverless", {}).get("suitable"))

    modern_data = [
        ['Option', 'Eligible Servers', 'Monthly Cost', 'Annual Cost'],
        ['Serverless (Lambda/Functions)', str(sl_suitable), fp(sl_total), fp(sl_total * 12)],
        ['Container (Fargate/Container Apps)', str(n), fp(ct_total), fp(ct_total * 12)],
    ]
    story.append(_styled_table(modern_data, [2.2*inch, 1.2*inch, 1.5*inch, 1.6*inch], font_size=8))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6: BUDGET-GRADE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Budget-Grade Analysis", heading_style))

    # Support Plans
    story.append(Paragraph("<b>Cloud Support Plan Costs</b>", subheading_style))
    support_data = [
        ['Provider', 'Support Tier', 'Annual Cost', '% of IaaS Spend'],
        ['AWS', 'Business (tiered)', fp(t_support_aws), pct(t_support_aws, t_aws)],
        ['Azure', 'Standard ($100/mo)', fp(t_support_az), pct(t_support_az, t_az)],
    ]
    story.append(_styled_table(support_data, [1.2*inch, 1.8*inch, 1.5*inch, 2.0*inch], font_size=8))
    story.append(Spacer(1, 8))

    # Migration Labor
    story.append(Paragraph("<b>Migration One-Time Costs</b>", subheading_style))
    mig_data = [
        ['Component', 'Total', 'Per Server Avg'],
        ['Migration Labor', fp(t_mig_labor), fp(t_mig_labor / max(1, n))],
        ['Testing & Validation', fp(t_mig_testing), fp(t_mig_testing / max(1, n))],
        ['Training', fp(t_mig_training), fp(t_mig_training / max(1, n))],
        ['Parallel Run (on-prem during cutover)', fp(t_mig_parallel), fp(t_mig_parallel / max(1, n))],
        ['Data Transfer', fp(t_mig_total - t_mig_labor - t_mig_testing - t_mig_training - t_mig_parallel), '-'],
        ['TOTAL ONE-TIME', fp(t_mig_total), fp(t_mig_total / max(1, n))],
    ]
    story.append(_styled_table(mig_data, [2.8*inch, 1.8*inch, 1.9*inch], font_size=8))
    story.append(Spacer(1, 8))

    # Confidence Ranges
    story.append(Paragraph("<b>Confidence Ranges (Gartner/McKinsey Methodology)</b>", subheading_style))
    conf_data = [
        ['Percentile', 'AWS Annual', 'Azure Annual', 'Description'],
        ['P10 (Low, -15%)', fp(t_aws_p10), fp(t_az_p10), 'Negotiated discounts, full right-sizing, spot usage'],
        ['P50 (Expected)', fp(t_aws_p50), fp(t_az_p50), 'Base 3yr RI + right-sizing'],
        ['P50 + Contingency (+10%)', fp(t_aws_budget), fp(t_az_budget), 'Budget recommendation (Gartner standard)'],
        ['P90 (High, +25%)', fp(t_aws_p90), fp(t_az_p90), 'On-demand overflow, data growth, learning curve'],
    ]
    story.append(_styled_table(conf_data, [1.4*inch, 1.2*inch, 1.2*inch, 2.7*inch], font_size=7))
    story.append(Spacer(1, 8))

    # Multi-Year Projection (aggregate from first result's budget_summary if available)
    story.append(Paragraph("<b>Multi-Year TCO Projection</b>", subheading_style))
    # Build aggregate year-by-year from individual results
    max_years = max((r["outputs"].get("budget_summary", {}).get("projection_years", 0) for r in results), default=3)
    if max_years > 0:
        proj_header = ['Year', f'{best_provider} Cloud', 'On-Prem Projected', 'Annual Savings', 'Cumulative Savings']
        proj_rows = [proj_header]

        # Year 0
        y0_cloud = sum(r["outputs"].get("budget_summary", {}).get("year_0", {}).get("total", 0) for r in results)
        y0_op = sum(r["outputs"].get("budget_summary", {}).get("year_0", {}).get("on_prem_prorated", 0) for r in results)
        proj_rows.append(['Year 0 (Migration)', fp(y0_cloud), fp(y0_op), '-', '-'])

        for yr_idx in range(max_years):
            yr_cloud = 0
            yr_op = 0
            cum_cloud = 0
            cum_op = 0
            for r in results:
                yearly = r["outputs"].get("budget_summary", {}).get("yearly", [])
                if yr_idx < len(yearly):
                    yr_cloud += yearly[yr_idx].get("total_cloud", 0)
                    yr_op += yearly[yr_idx].get("on_prem_projected", 0)
                    cum_cloud += yearly[yr_idx].get("cumulative_cloud", 0)
                    cum_op += yearly[yr_idx].get("cumulative_on_prem", 0)
            yr_sav = yr_op - yr_cloud
            cum_sav = cum_op - cum_cloud
            proj_rows.append([
                f'Year {yr_idx + 1}', fp(yr_cloud), fp(yr_op),
                fp(yr_sav), fp(cum_sav),
            ])

        story.append(_styled_table(proj_rows, [1.2*inch, 1.4*inch, 1.4*inch, 1.2*inch, 1.3*inch], font_size=8))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<i>Trends: Cloud -5%/yr, On-prem HW +3%/yr, Power +4%/yr, Labor +5%/yr, Licensing +3%/yr. "
            f"Average break-even: {avg_breakeven}.</i>",
            small_style
        ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7: PaaS & MODERN OPTIONS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. PaaS & Modern Deployment Options", heading_style))

    story.append(Paragraph(
        f"PaaS annual cost (3yr RI): <b>{fp(t_paas)}</b> vs IaaS ({best_provider}): <b>{fp(t_best)}</b>. "
        f"PaaS includes managed services with built-in HA, patching, and scaling.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Top PaaS mappings
    paas_data = [['Host', 'Server Type', 'Database', 'PaaS Service', 'PaaS Annual']]
    for r in results[:20]:
        inp, out = r["inputs"], r["outputs"]
        paas_data.append([
            inp.get("host_name", "N/A")[:18],
            inp.get("server_type", "")[:15],
            inp.get("databases_caches", "None")[:12],
            out.get("paas_service_name", "N/A")[:20],
            fp(out.get("paas_annual_3yr_ri", 0)),
        ])
    if len(results) > 20:
        paas_data.append(['...', f'+{len(results)-20} more', '', '', ''])

    story.append(_styled_table(paas_data, [1.2*inch, 1.1*inch, 1.0*inch, 1.5*inch, 1.2*inch], font_size=7))
    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8: SERVER-BY-SERVER DETAIL
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Server-by-Server Analysis", heading_style))

    srv_header = ['Host', 'Type', 'Env', 'vCPU/Mem', 'On-Prem/yr', 'AWS All-In', 'Azure All-In', 'Budget Best', 'Savings']
    srv_rows = [srv_header]

    for r in results[:50]:
        inp, out = r["inputs"], r["outputs"]
        op = out["on_prem_yearly_cost"]
        aws_ai = out.get("budget_aws_all_in_annual", out["cross_provider"]["AWS"]["annual_3yr_ri"])
        az_ai = out.get("budget_azure_all_in_annual", out["cross_provider"]["Azure"]["annual_3yr_ri"])
        best_c = min(aws_ai, az_ai)
        sav = op - best_c
        best_lbl = "AWS" if aws_ai <= az_ai else "Azure"

        srv_rows.append([
            inp.get("host_name", "N/A")[:14],
            inp.get("server_type", "")[:10],
            inp.get("environment", "")[:6],
            f"{out['right_sizing_cpu']}v/{out['right_sizing_memory']}G",
            fpk(op),
            fpk(aws_ai),
            fpk(az_ai),
            best_lbl,
            f"{fpk(sav)} ({pct(sav, op)})",
        ])

    story.append(_styled_table(srv_rows,
        [0.9*inch, 0.7*inch, 0.5*inch, 0.65*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.6*inch, 1.0*inch],
        font_size=6))

    if n > 50:
        story.append(Paragraph(
            f"<i>Showing first 50 of {n} servers. Full data in Excel export.</i>",
            small_style
        ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 9: AZURE LOCAL COMPARISON
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("8. Azure Local (Hybrid) Comparison", heading_style))

    story.append(Paragraph(
        "Azure Local extends Azure to on-premises hardware with Azure Arc management, "
        "billed per physical core. Three scenarios per server:",
        body_style
    ))
    story.append(Spacer(1, 6))

    azl_data = [
        ['Scenario', 'Portfolio Annual', 'vs On-Prem', 'Rate'],
        ['Linux (Host Fee Only)', fp(t_azl_linux), fp(t_op - t_azl_linux), '$10/core/mo'],
        ['Windows (Host + WS Sub)', fp(t_azl_win), fp(t_op - t_azl_win), '$23.30/core/mo'],
        ['Azure Hybrid Benefit (SA)', fp(t_azl_ahb), fp(t_op - t_azl_ahb), '$0/mo (waived)'],
        ['On-Premises (for reference)', fp(t_op), '-', '-'],
    ]
    story.append(_styled_table(azl_data, [2.0*inch, 1.5*inch, 1.5*inch, 1.5*inch], font_size=8))
    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 10: MIGRATION WAVE PLAN
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("9. Migration Wave Plan", heading_style))

    if HAS_WAVE_PLAN:
        try:
            wave_result = generate_wave_plan(results)
            waves = wave_result.get("waves", {})

            wave_data = [['Wave', 'Name', 'Timeline', 'Servers', 'On-Prem/yr', 'Cloud/yr', 'Savings']]
            for wk in ["wave_1", "wave_2", "wave_3", "wave_4"]:
                w = waves.get(wk, {})
                wave_data.append([
                    wk.replace("_", " ").title(),
                    w.get("name", ""),
                    w.get("timeline", ""),
                    str(w.get("count", 0)),
                    fpk(w.get("total_on_prem", 0)),
                    fpk(w.get("total_cloud", 0)),
                    fpk(w.get("total_savings", 0)),
                ])
            wave_data.append([
                'TOTAL', '', 'Month 1-18', str(n),
                fpk(t_op), fpk(t_best), fpk(t_sav),
            ])

            story.append(_styled_table(wave_data,
                [0.7*inch, 1.1*inch, 0.9*inch, 0.6*inch, 1.0*inch, 1.0*inch, 1.0*inch], font_size=8))
        except Exception:
            story.append(Paragraph("Wave plan generation not available.", body_style))
    else:
        wave_data = [
            ['Wave', 'Name', 'Timeline', 'Criteria'],
            ['Wave 1', 'Quick Wins', 'Month 1-2', 'Dev/test, no DB, Rehost'],
            ['Wave 2', 'Core Migration', 'Month 3-6', 'Production apps, medium complexity'],
            ['Wave 3', 'Complex Workloads', 'Month 6-12', 'Database servers, stateful, EOL OS'],
            ['Wave 4', 'Optimization', 'Month 12-18', 'Refactor/PaaS candidates'],
        ]
        story.append(_styled_table(wave_data, [0.8*inch, 1.5*inch, 1.2*inch, 3.0*inch], font_size=8))

    story.append(Spacer(1, 12))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 11: AI STRATEGIC ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    if include_ai_analysis:
        story.append(PageBreak())
        story.append(Paragraph("10. AI Strategic Analysis", heading_style))
        story.append(Paragraph(
            "<i>Generated by Claude AI (claude-sonnet-4) based on full cost analysis data.</i>",
            small_style
        ))
        story.append(Spacer(1, 8))
        for line in include_ai_analysis.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
            elif line.startswith('###'):
                story.append(Paragraph(line.replace('### ', '').replace('###', ''), subheading_style))
            elif line.startswith('##'):
                story.append(Paragraph(line.replace('## ', '').replace('##', ''), subheading_style))
            elif line.startswith('**') and line.endswith('**'):
                story.append(Paragraph(f"<b>{line.strip('*')}</b>", body_style))
            elif line.startswith('- ') or line.startswith('* '):
                story.append(Paragraph(f"&nbsp;&nbsp;&bull; {line[2:]}", body_style))
            elif line:
                # Escape XML entities
                safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_line, body_style))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 12: METHODOLOGY & SOURCES
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    sec_num = "11" if include_ai_analysis else "10"
    story.append(Paragraph(f"{sec_num}. Methodology & Rate Sources", heading_style))

    # On-prem rates table
    story.append(Paragraph("<b>On-Premises Data Center TCO Rates</b>", subheading_style))
    meth_onprem = [
        ['Component', 'Rate', 'Source'],
        ['Hardware Compute', '$130/vCPU/yr', 'Dell PowerEdge R760, 5yr amortization'],
        ['Hardware Memory', '$10/GB/yr', 'DDR5 RDIMM enterprise (Counterpoint 2025)'],
        ['Hardware Storage', '$0.08/GB/yr', 'Blended 70/30 SSD/HDD'],
        ['Power & Cooling', '25W/vCPU x PUE 1.55 x $0.12/kWh', 'US DOE 2024, EIA (eia.gov)'],
        ['Facility/Rack', '$1,200/server/yr', 'ENCOR Advisors, Brightlio 2025'],
        ['Admin Labor', '$1,500/server/yr', 'Gartner, Sherweb TCO'],
        ['OS: Windows', '$5.50/vCPU/mo', 'Dell configurator (WS 2025 Std)'],
        ['OS: RHEL', '$3.00/vCPU/mo', 'Dell configurator'],
        ['DB: Oracle', '$9,975/vCPU/yr', 'oracle.com/contracts'],
        ['DB: SQL Server Ent', '$3,400/vCPU/yr', 'microsoft.com/licensing'],
        ['DB: SQL Server Std', '$890/vCPU/yr', 'microsoft.com/licensing'],
        ['DB: MongoDB Ent', '$10,000/server/yr', 'mongodb.com/pricing'],
        ['DB: Redis Ent', '$5,000/server/yr', 'redis.com/pricing'],
    ]
    story.append(_styled_table(meth_onprem, [1.5*inch, 1.8*inch, 3.2*inch], font_size=7))
    story.append(Spacer(1, 8))

    # Cloud pricing approach
    story.append(Paragraph("<b>Cloud Pricing Approach</b>", subheading_style))
    story.append(Paragraph(
        "1. <b>Azure:</b> Live pricing from Azure Retail Prices API (prices.azure.com)<br/>"
        "2. <b>AWS:</b> Live pricing from AWS Pricing API (boto3, if credentials provided) or reference catalog<br/>"
        "3. <b>RI Discounts:</b> 1yr = 40% off On-Demand, 3yr = 60% off On-Demand<br/>"
        "4. <b>Right-Sizing:</b> Actual usage x 1.3 headroom, rounded to nearest standard VM size<br/>"
        "5. <b>Regional Multipliers:</b> Applied per region (e.g., Tokyo +12%, India -5%)",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Budget methodology
    story.append(Paragraph("<b>Budget-Grade Methodology</b>", subheading_style))
    story.append(Paragraph(
        "<b>Support Plans:</b> AWS Business (tiered 10%/7%/5%/3%), Azure Standard ($100/mo flat)<br/>"
        "<b>Migration Labor:</b> Base rates by 6Rs strategy x server complexity x DB complexity x size multiplier<br/>"
        "<b>Confidence Ranges:</b> P10 (-15%), P50 (base), P90 (+25%), Contingency +10% (Gartner/McKinsey)<br/>"
        "<b>Multi-Year Trends:</b> Cloud -5%/yr, On-prem HW +3%, Power +4%, Labor +5%, Licensing +3%<br/>"
        "<b>Break-Even:</b> Year when cumulative cloud costs (incl. migration) &lt; cumulative on-prem",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Key sources
    story.append(Paragraph("<b>Key Rate Sources</b>", subheading_style))
    sources_data = [
        ['Category', 'Source'],
        ['AWS EC2/EBS/S3', 'aws.amazon.com/ec2/pricing/, aws.amazon.com/ebs/pricing/'],
        ['AWS Support', 'aws.amazon.com/premiumsupport/pricing/'],
        ['AWS DR/Backup', 'aws.amazon.com/disaster-recovery/pricing/, aws.amazon.com/backup/pricing/'],
        ['AWS Lambda/Fargate', 'aws.amazon.com/lambda/pricing/, aws.amazon.com/fargate/pricing/'],
        ['Azure VMs/Storage', 'prices.azure.com/api/retail/prices (Live API)'],
        ['Azure Support', 'azure.microsoft.com/support/plans/'],
        ['Azure DR/Backup', 'azure.microsoft.com/pricing/details/site-recovery/'],
        ['Azure Local', 'azure.microsoft.com/pricing/details/azure-local/'],
        ['On-Prem Hardware', 'dell.com/poweredge-r760'],
        ['Power/PUE', 'US DOE 2024 Data Center Energy Report, EIA (eia.gov)'],
        ['Facility', 'ENCOR Advisors, Brightlio Colocation Pricing 2025'],
        ['Migration Benchmarks', 'Gartner Migration TCO, AWS MAP, Azure Migrate'],
    ]
    story.append(_styled_table(sources_data, [1.8*inch, 4.7*inch], font_size=7))
    story.append(Spacer(1, 8))

    # Compliance
    story.append(Paragraph("<b>Compliance & Data Handling</b>", subheading_style))
    story.append(Paragraph(
        "All data computed in-memory at runtime. Zero server-side persistence. "
        "Session data cleared on browser close. Export generated fresh on-the-fly.",
        body_style
    ))

    # Disclaimer
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "DISCLAIMER: This report provides indicative, budget-grade pricing based on published rates "
        "and industry benchmarks. Actual costs may vary based on specific configurations, "
        "negotiated enterprise agreements (EDP/ELA), usage patterns, and regional factors. "
        "Confidence ranges (P10-P90) reflect typical variance observed in cloud migration projects. "
        "Verify all figures with official cloud pricing calculators and your account team before "
        "making procurement decisions. All rates sourced from vendor documentation as of Q1 2025.",
        disclaimer_style
    ))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Infosys Cobalt — Migration Analyzer v2.0 | "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Zero Data Persistence",
        disclaimer_style
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def _generate_simple_pdf(results, title, cs, cm):
    """Fallback PDF generation without reportlab (plain text PDF)."""
    n = len(results)
    t_op = sum(r["outputs"]["on_prem_yearly_cost"] for r in results)
    t_aws = sum(r["outputs"]["cross_provider"]["AWS"]["annual_3yr_ri"] for r in results)
    t_az = sum(r["outputs"]["cross_provider"]["Azure"]["annual_3yr_ri"] for r in results)

    content = f"""{title}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Servers: {n}

COST COMPARISON
On-Premises:    {cs}{t_op * cm:,.2f}/yr
AWS (3yr RI):   {cs}{t_aws * cm:,.2f}/yr
Azure (3yr RI): {cs}{t_az * cm:,.2f}/yr

Note: Install reportlab for formatted PDF reports.
pip install reportlab
"""
    return content.encode('utf-8')
