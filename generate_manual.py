"""
Generate Infosys Cobalt — Migration Analyzer User Manual (Word DOCX)
=====================================================================
Creates a professionally formatted Word document with all tool features,
pricing methodology, rate tables, and user guidance.

Usage:
    python generate_manual.py
"""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import datetime
import os

# ─── Styling constants ────────────────────────────────────────────────────────
INFOSYS_BLUE = RGBColor(0x00, 0x6F, 0xBA)  # Infosys brand blue
DARK_BG = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT = RGBColor(0x4A, 0x9E, 0xFF)
HEADING_COLOR = RGBColor(0x00, 0x3F, 0x72)
TABLE_HEADER_BG = "003F72"
TABLE_ALT_BG = "F0F4F8"
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)


def set_cell_shading(cell, color_hex):
    """Apply background shading to a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def add_table_borders(table):
    """Add borders to all cells in a table."""
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else parse_xml(f'<w:tblPr {nsdecls("w")}/>')
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        '  <w:top w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '  <w:left w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '  <w:right w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="B0B0B0"/>'
        '</w:tblBorders>'
    )
    tblPr.append(borders)


def style_header_row(row, color_hex=TABLE_HEADER_BG):
    """Style the header row of a table with dark background and white text."""
    for cell in row.cells:
        set_cell_shading(cell, color_hex)
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = WHITE
                run.font.bold = True
                run.font.size = Pt(9)


def add_styled_table(doc, headers, rows, col_widths=None):
    """Create a formatted table with header styling and alternating row colors."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    add_table_borders(table)

    # Header row
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_header_row(table.rows[0])

    # Data rows
    for r_idx, row_data in enumerate(rows):
        for c_idx, val in enumerate(row_data):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = str(val)
            cell.paragraphs[0].style = doc.styles['Normal']
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(9)
        if r_idx % 2 == 1:
            for cell in table.rows[r_idx + 1].cells:
                set_cell_shading(cell, TABLE_ALT_BG)

    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)

    return table


def add_heading_styled(doc, text, level=1):
    """Add a heading with Infosys blue color."""
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        run.font.color.rgb = HEADING_COLOR
    return heading


def add_bullet(doc, text, bold_prefix=""):
    """Add a bullet point with optional bold prefix."""
    p = doc.add_paragraph(style='List Bullet')
    if bold_prefix:
        run = p.add_run(bold_prefix)
        run.bold = True
        p.add_run(f" {text}")
    else:
        p.add_run(text)
    return p


def add_note_box(doc, text, prefix="Note:"):
    """Add a styled note/tip paragraph."""
    p = doc.add_paragraph()
    run = p.add_run(f"{prefix} ")
    run.bold = True
    run.font.color.rgb = INFOSYS_BLUE
    p.add_run(text)
    p.paragraph_format.left_indent = Cm(1)
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DOCUMENT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_manual():
    doc = Document()

    # ── Page setup ────────────────────────────────────────────────────────────
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

    # ── Default font ──────────────────────────────────────────────────────────
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(10)
    font.color.rgb = BLACK

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1: COVER PAGE
    # ══════════════════════════════════════════════════════════════════════════
    for _ in range(6):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Infosys Cobalt")
    run.font.size = Pt(36)
    run.font.color.rgb = INFOSYS_BLUE
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Migration Analyzer")
    run.font.size = Pt(28)
    run.font.color.rgb = HEADING_COLOR
    run.bold = True

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("User Manual & Pricing Methodology Reference")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Version 2.0  |  {datetime.date.today().strftime('%B %Y')}")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Budget-Grade Cloud Cost Analysis")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS (Manual)
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "Table of Contents", level=1)

    toc_items = [
        "1.  Executive Overview",
        "2.  Getting Started",
        "3.  Tab 1: Upload File (Batch Analysis)",
        "4.  Tab 2: Manual Input (Single Server)",
        "5.  Understanding the Output",
        "6.  Budget-Grade Analysis",
        "7.  AI-Powered Recommendations",
        "8.  Tab 3: Batch Results & Portfolio View",
        "9.  Tab 4: Scenarios & Projections",
        "10. Tab 5: Matilda Discovery Integration",
        "11. Tab 6: Monitoring & Health",
        "12. Pricing Methodology",
        "13. Supported Currencies",
        "14. RBAC & Permissions",
        "15. Compliance & Data Handling",
        "Appendix A: Required CSV Columns",
        "Appendix B: Rate Sources & References",
    ]
    for item in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(1)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2: EXECUTIVE OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "1. Executive Overview", level=1)

    doc.add_paragraph(
        "The Infosys Cobalt Migration Analyzer is a budget-grade cloud cost analysis tool that "
        "evaluates on-premises workloads and provides comprehensive cost comparisons across "
        "AWS, Azure, Azure Local (hybrid), and on-premises infrastructure. Every computation "
        "is performed dynamically at runtime with zero data persistence."
    )

    add_heading_styled(doc, "Key Capabilities", level=2)
    capabilities = [
        ("Multi-Cloud Comparison:", "Side-by-side AWS, Azure, Azure Local, and on-premises cost analysis for every server"),
        ("Intelligent Right-Sizing:", "Automatically recommends optimal vCPU, memory, and storage based on actual utilization (CPU/memory/IOPS)"),
        ("Budget-Grade Pricing:", "Support plan costs, migration labor estimates, confidence ranges (P10/P50/P90), contingency buffers, and multi-year TCO projections"),
        ("8-Component On-Prem TCO:", "Hardware compute, memory, storage, power & cooling, facility, admin labor, OS licensing, and database software licensing"),
        ("Live Pricing APIs:", "Real-time pricing from Azure Retail Prices API and AWS Pricing API (with fallback to reference catalog)"),
        ("AI-Powered Analysis:", "Claude AI provides natural-language recommendations, risk assessment, and migration strategy guidance"),
        ("PaaS & Serverless:", "Automatic PaaS service mapping, serverless (Lambda/Functions) and container (Fargate/Container Apps) cost estimates"),
        ("DR & Backup:", "Auto-selected disaster recovery strategy with backup cost modeling per server type"),
        ("Network & Egress:", "Tiered egress pricing, VPN, load balancer, NAT gateway, and inter-region transfer costs"),
        ("Storage Tier Optimization:", "Hot/warm/cool/archive tier recommendations with savings analysis"),
        ("20 Currencies:", "Live exchange rate conversion for global teams"),
        ("RBAC:", "Role-based access control (Admin, Analyst, Viewer) with session-based authentication"),
    ]
    for bold_text, desc in capabilities:
        add_bullet(doc, desc, bold_text)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3: GETTING STARTED
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "2. Getting Started", level=1)

    add_heading_styled(doc, "Login", level=2)
    doc.add_paragraph(
        "The tool requires authentication before access. The login page displays the "
        "Infosys Cobalt logo with a centered sign-in form."
    )
    add_styled_table(doc,
        ["Username", "Password", "Role"],
        [
            ["admin", "admin123", "Administrator"],
            ["analyst", "analyst123", "Analyst"],
            ["viewer", "viewer123", "Viewer"],
        ],
        col_widths=[2.0, 2.0, 2.5]
    )
    doc.add_paragraph()
    add_note_box(doc, "In production deployments, replace default credentials with your organization's identity provider.", "Security:")

    add_heading_styled(doc, "Sidebar Configuration", level=2)
    doc.add_paragraph("The left sidebar contains all global configuration options:")

    config_items = [
        ("Claude AI API Key:", "Enter your Anthropic API key for AI-powered recommendations. Can also be set in .streamlit/secrets.toml for auto-loading."),
        ("AWS Pricing API:", "Optional AWS Access Key ID and Secret Access Key for live EC2/RDS pricing. Without these, the tool uses a reference catalog with verified pricing."),
        ("Display Toggles:", "Show Charts, AI Recommendations, Enhanced Analysis (network/DR/storage/serverless), and Budget-Grade Analysis."),
        ("Budget-Grade Options:", "When enabled: Support Plan tier (Business/Enterprise/Developer/None) and Budget Projection years (1-5)."),
        ("Currency:", "Select from 17 supported currencies. Live exchange rates are fetched automatically with fallback to static rates."),
        ("API Connections:", "Status indicators show connectivity to AWS, Azure, Azure Local, and Anthropic APIs."),
    ]
    for bold_text, desc in config_items:
        add_bullet(doc, desc, bold_text)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4: TAB 1 — UPLOAD FILE
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "3. Tab 1: Upload File (Batch Analysis)", level=1)

    doc.add_paragraph(
        "Upload a CSV or Excel file containing your server inventory for batch analysis. "
        "Each row represents one server. The tool validates all columns and provides "
        "real-time streaming results as each server is analyzed."
    )

    add_heading_styled(doc, "Workflow", level=2)
    steps = [
        "Download the template CSV using the 'Download Template' button",
        "Fill in your server inventory data (see Appendix A for column definitions)",
        "Upload the file using the file uploader (CSV or Excel)",
        "The tool validates all rows and reports any errors",
        "Click 'Analyze All Servers' to start batch processing",
        "Results stream in real-time — each server card appears as analysis completes",
        "View portfolio-level Batch Results in Tab 3",
        "Export results to Excel with all cost breakdowns",
    ]
    for i, step in enumerate(steps, 1):
        p = doc.add_paragraph(f"{i}. {step}")
        p.paragraph_format.left_indent = Cm(1)

    add_heading_styled(doc, "Pagination", level=2)
    doc.add_paragraph(
        "For large uploads, results are paginated at 25 servers per page. Navigation "
        "controls appear at the bottom of the results. Streaming display shows a progress "
        "bar and timing information during analysis."
    )

    add_note_box(doc, "The tool processes servers sequentially to maintain streaming display. A batch of 100 servers typically completes in 2-5 minutes depending on API response times.", "Performance:")

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5: TAB 2 — MANUAL INPUT
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "4. Tab 2: Manual Input (Single Server)", level=1)

    doc.add_paragraph(
        "Analyze a single server by filling in the form fields. All fields have sensible "
        "defaults. After clicking 'Analyze Server', the full detailed output is displayed "
        "inline with all cost breakdowns."
    )

    add_heading_styled(doc, "Form Fields", level=2)

    form_fields = [
        ["Host Name", "Text", "Server hostname or identifier", "e.g., web-prod-01"],
        ["IP Address", "Text", "Server IP address", "e.g., 10.0.1.50"],
        ["Cloud Provider", "Dropdown", "Target cloud: AWS, Azure, Azure Local", "AWS"],
        ["Cloud Region", "Dropdown", "Target region (12 AWS + 12 Azure regions)", "US East (N. Virginia)"],
        ["Platform", "Dropdown", "OS platform family", "Linux"],
        ["Operating System", "Dropdown", "Specific OS version", "Linux, Windows Server 2019, RHEL, etc."],
        ["Environment", "Dropdown", "Deployment environment", "Production, Development, Testing, QA, Staging, DR"],
        ["Server Type", "Dropdown", "Workload type", "Application, Web, Database, File, Mail, API Gateway, Cache, LB, CI/CD, Monitoring"],
        ["OS EOL Status", "Dropdown", "End-of-life status", "No, Yes (EOL)"],
        ["Migration Type", "Dropdown", "6Rs migration strategy", "Rehost, Replatform, Refactor, Repurchase, Retire, Retain"],
        ["Databases/Caches", "Dropdown", "Database engines running", "None, MySQL, PostgreSQL, SQL Server, Oracle, MongoDB, Redis, etc."],
        ["Instance Usage", "Dropdown", "Usage pattern", "24x7, Business Hours, On-Demand, Scheduled"],
        ["vCPU Count", "Number", "Current virtual CPU count", "1-128"],
        ["Avg CPU Usage (%)", "Slider", "Average CPU utilization", "0-100%"],
        ["Memory (GB)", "Number", "Total memory allocated", "1-1024 GB"],
        ["Avg Memory Usage (%)", "Slider", "Average memory utilization", "0-100%"],
        ["Total Storage (GB)", "Number", "Total disk capacity", "10-65,536 GB"],
        ["Storage Usage (%)", "Slider", "Percentage of storage used", "0-100%"],
        ["Avg Network Throughput", "Number", "Average network throughput (Mbps)", "0-10,000"],
        ["Total Network Throughput", "Number", "Peak network throughput (Mbps)", "0-100,000"],
        ["Avg Disk IOPS", "Number", "Average disk I/O operations", "0-500,000"],
    ]

    add_styled_table(doc,
        ["Field", "Type", "Description", "Values / Range"],
        form_fields,
        col_widths=[1.5, 0.8, 2.5, 1.7]
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6: UNDERSTANDING THE OUTPUT
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "5. Understanding the Output", level=1)

    doc.add_paragraph(
        "Each analyzed server produces a comprehensive output card with multiple sections. "
        "The output is organized into logical groups for easy reading."
    )

    add_heading_styled(doc, "Right-Sizing Results", level=2)
    doc.add_paragraph(
        "The tool automatically right-sizes compute, memory, and storage based on actual "
        "utilization with a 30% headroom buffer:"
    )
    doc.add_paragraph("   Right-Sized vCPU = Current vCPU x (Avg Usage / 100) x 1.3, rounded up to nearest standard size")
    doc.add_paragraph("   Right-Sized Memory = Current Memory x (Avg Usage / 100) x 1.3, rounded up")
    doc.add_paragraph("   Right-Sized Storage = Current Storage x (Usage % / 100) x 1.4, minimum 20 GB")

    add_heading_styled(doc, "IaaS Pricing (Current & Recommended)", level=2)
    doc.add_paragraph(
        "Shows On-Demand, 1-Year Reserved Instance, and 3-Year Reserved Instance pricing "
        "for both the current-size VM and the right-sized recommendation. RI discounts: "
        "1-Year ~40% off On-Demand, 3-Year ~60% off On-Demand."
    )

    add_heading_styled(doc, "Cross-Provider Comparison", level=2)
    doc.add_paragraph(
        "Regardless of which cloud provider was selected, the output always shows side-by-side "
        "annual costs (3yr RI) for AWS, Azure, Azure Local, and On-Premises. This allows "
        "informed comparison without re-running the analysis."
    )

    add_heading_styled(doc, "PaaS Recommendation", level=2)
    doc.add_paragraph(
        "The tool maps each server's workload type and database to the appropriate PaaS "
        "service. Database servers get mapped to managed database services (RDS, Azure SQL, etc.). "
        "Non-database servers get mapped to compute PaaS (App Runner, App Service, etc.) "
        "with a 30% PaaS platform markup over IaaS general pricing."
    )

    add_heading_styled(doc, "On-Premises Cost Breakdown (8 Components)", level=2)
    doc.add_paragraph(
        "The on-prem TCO is calculated from 8 industry-sourced components (see Section 12 "
        "for detailed rates and sources):"
    )
    components = [
        "Hardware Compute — $130/vCPU/year (Dell PowerEdge, 5yr amortization)",
        "Hardware Memory — $10/GB/year (DDR5 RDIMM, 5yr amortization)",
        "Hardware Storage — $0.08/GB/year (blended SSD/HDD)",
        "Power & Cooling — Dynamic: vCPU x 25W x PUE(1.55) x 8,760hrs x $0.12/kWh",
        "Facility/Rack Space — $1,200/server/year (colocation)",
        "Admin & Labor — $1,500/server/year (sysadmin allocation)",
        "OS Licensing — Windows $5.50/vCPU/mo, RHEL $3.00, SUSE $2.50, Linux $0",
        "DB Software Licensing — Oracle $9,975/vCPU/yr, SQL Server Ent $3,400, Std $890, MongoDB $10K/server, Redis $5K/server",
    ]
    for c in components:
        add_bullet(doc, c)

    add_heading_styled(doc, "Enhanced Analysis (when enabled)", level=2)
    enhanced = [
        ("Network & Egress:", "Tiered egress pricing, VPN, load balancer, NAT gateway costs"),
        ("DR & Backup:", "Auto-selected DR strategy (backup_restore / pilot_light / warm_standby / multi_site) with backup storage costs"),
        ("Storage Tier Optimization:", "Hot/warm/cool/archive distribution with savings analysis"),
        ("Serverless & Container:", "Lambda/Functions and Fargate/Container Apps cost estimates"),
        ("Migration Transfer:", "One-time data transfer cost (Internet / DataSync / Data Box / Snowball)"),
        ("All-In Annual:", "IaaS + Network + DR/Backup combined annual cost per cloud"),
    ]
    for bold_text, desc in enhanced:
        add_bullet(doc, desc, bold_text)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7: BUDGET-GRADE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "6. Budget-Grade Analysis", level=1)

    doc.add_paragraph(
        "When the Budget-Grade Analysis toggle is enabled in the sidebar, the tool calculates "
        "additional costs that are critical for budget planning and financial approvals. "
        "These include support plans, migration labor, confidence ranges, and multi-year projections."
    )

    add_heading_styled(doc, "Support Plan Costs", level=2)
    doc.add_paragraph("Cloud vendor support is a recurring operational cost. The tool calculates support costs based on the selected tier:")

    add_heading_styled(doc, "AWS Support Plans", level=3)
    add_styled_table(doc,
        ["Tier", "Rate", "Minimum", "Source"],
        [
            ["Business", "10% of first $10K + 7% next $10K + 5% next $60K + 3% over $80K", "N/A", "aws.amazon.com/premiumsupport/pricing/"],
            ["Enterprise", "15% of monthly spend", "$15,000/mo", "aws.amazon.com/premiumsupport/pricing/"],
            ["Developer", "3% of monthly spend", "$29/mo", "aws.amazon.com/premiumsupport/pricing/"],
            ["None", "$0", "$0", "-"],
        ],
        col_widths=[1.2, 2.8, 1.0, 1.5]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Azure Support Plans", level=3)
    add_styled_table(doc,
        ["Tier", "Rate", "Source"],
        [
            ["Standard", "$100/month flat", "azure.microsoft.com/en-us/support/plans/"],
            ["Professional Direct", "$1,000/month flat", "azure.microsoft.com/en-us/support/plans/"],
            ["None", "$0", "-"],
        ],
        col_widths=[2.0, 2.0, 2.5]
    )

    add_heading_styled(doc, "Migration Labor Costs (One-Time)", level=2)
    doc.add_paragraph(
        "Migration labor is a significant one-time cost. The tool estimates labor, testing, "
        "training, and parallel-run costs based on the 6Rs migration strategy, server complexity, "
        "database complexity, and server size."
    )

    add_heading_styled(doc, "Base Labor Rates by Migration Strategy", level=3)
    add_styled_table(doc,
        ["Strategy", "Base Labor", "Testing %", "Duration"],
        [
            ["Rehost (Lift & Shift)", "$5,000", "15%", "1 week"],
            ["Replatform", "$12,000", "18%", "3 weeks"],
            ["Refactor", "$25,000", "20%", "8 weeks"],
            ["Repurchase", "$8,000", "15%", "4 weeks"],
            ["Retire", "$1,000", "5%", "0.5 weeks"],
            ["Retain", "$0", "0%", "0 weeks"],
        ],
        col_widths=[2.0, 1.5, 1.0, 1.5]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Server Complexity Surcharges", level=3)
    add_styled_table(doc,
        ["Server Type", "Multiplier", "Rationale"],
        [
            ["Database Server", "1.5x", "Schema migration, data validation, failover testing"],
            ["Mail Server", "1.3x", "MX records, mail flow testing, compliance"],
            ["File Server", "1.2x", "Permission migration, large data volumes"],
            ["Application Server", "1.0x", "Baseline complexity"],
            ["Web Server", "0.8x", "Stateless, simpler migration"],
            ["API Gateway", "0.8x", "Configuration-driven"],
            ["Cache Server", "0.7x", "Ephemeral, rebuild from scratch"],
            ["Load Balancer", "0.6x", "Configuration only"],
            ["Monitoring / CI/CD", "0.5x", "Re-deploy from templates"],
        ],
        col_widths=[1.8, 1.2, 3.5]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Database Complexity Multipliers", level=3)
    add_styled_table(doc,
        ["Database", "Multiplier", "Notes"],
        [
            ["Oracle", "3.0x", "Complex licensing, schema conversion, stored procedures"],
            ["Cassandra", "2.0x", "Distributed, multi-node coordination"],
            ["SQL Server", "2.0x", "SSIS/SSRS/SSAS packages, linked servers"],
            ["MongoDB", "1.8x", "Schema design differences, aggregation pipelines"],
            ["MySQL / PostgreSQL / MariaDB", "1.5x", "Standard relational migration"],
            ["DynamoDB", "1.3x", "NoSQL, partition key design"],
            ["Redis", "1.2x", "In-memory, quick rebuild"],
            ["Memcached", "1.1x", "Ephemeral cache"],
            ["None", "1.0x", "No database migration"],
        ],
        col_widths=[2.0, 1.2, 3.3]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Size Multipliers", level=3)
    doc.add_paragraph("Large servers incur additional migration complexity:")
    add_styled_table(doc,
        ["Condition", "Additional Multiplier"],
        [
            ["> 16 vCPU", "+20%"],
            ["> 32 vCPU", "+50%"],
            ["> 2 TB storage", "+30%"],
            ["> 10 TB storage", "+50%"],
        ],
        col_widths=[3.0, 3.0]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Additional One-Time Costs", level=3)
    add_bullet(doc, "Training: $350 per server ($3,500 per team member x 0.1 allocation per server)", "Training:")
    add_bullet(doc, "Production servers run both environments for 2 months; non-production for 1 month", "Parallel Run:")
    add_bullet(doc, "Based on data volume: Internet (<100GB), DataSync/Data Box (100GB-10TB), Snowball/Data Box (>10TB)", "Data Transfer:")

    add_heading_styled(doc, "Confidence Ranges", level=2)
    doc.add_paragraph(
        "Following Gartner/McKinsey methodology, the tool provides budget confidence bands:"
    )
    add_styled_table(doc,
        ["Percentile", "Adjustment", "Assumptions"],
        [
            ["P10 (Low)", "-15%", "Negotiated EDP/ELA discounts, full right-sizing, spot/preemptible usage"],
            ["P50 (Expected)", "Base", "Base calculation with 3yr RI pricing and recommended right-sizing"],
            ["P90 (High)", "+25%", "On-demand overflow, 15% data growth, unexpected egress, learning curve waste"],
            ["Contingency", "+10% of P50", "Gartner/McKinsey standard budget buffer"],
        ],
        col_widths=[1.5, 1.2, 3.8]
    )

    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("Budget Annual = P50 (Expected) + 10% Contingency")
    run.bold = True

    add_heading_styled(doc, "Multi-Year TCO Projection", level=2)
    doc.add_paragraph(
        "The tool projects costs over 1-5 years using industry-standard price trends:"
    )
    add_styled_table(doc,
        ["Cost Component", "Annual Trend", "Source"],
        [
            ["Cloud compute/network/DR", "-5% per year", "Historical cloud price reductions"],
            ["On-prem hardware", "+3% per year", "Hardware refresh inflation"],
            ["On-prem power & cooling", "+4% per year", "US DOE electricity trend data"],
            ["On-prem admin labor", "+5% per year", "US BLS labor cost inflation"],
            ["On-prem licensing", "+3% per year", "Vendor price increase patterns"],
            ["Cloud support", "Flat (contractual)", "Support is contract-based"],
        ],
        col_widths=[2.5, 1.5, 2.5]
    )

    doc.add_paragraph()
    doc.add_paragraph(
        "The projection includes Year 0 (migration year) with one-time migration costs "
        "plus 6 months of prorated cloud run-rate. Break-even year is identified when "
        "cumulative cloud costs (including migration) become less than cumulative on-premises costs."
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8: AI RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "7. AI-Powered Recommendations", level=1)

    doc.add_paragraph(
        "When enabled and an Anthropic API key is configured, the tool uses Claude AI "
        "(claude-sonnet-4) to generate natural-language analysis for each server and batch summaries."
    )

    add_heading_styled(doc, "Single Server Analysis", level=2)
    doc.add_paragraph("The AI receives the full cost breakdown and provides:")
    items = [
        "Migration strategy recommendation with rationale",
        "Cost optimization opportunities (RI, Spot, rightsizing)",
        "Risk assessment (EOL OS, database complexity, data gravity)",
        "Timeline recommendation and sequencing advice",
        "Budget-grade insights (when enabled) including migration ROI and break-even analysis",
    ]
    for item in items:
        add_bullet(doc, item)

    add_heading_styled(doc, "Batch Portfolio Summary", level=2)
    doc.add_paragraph("For batch analysis, the AI receives aggregated portfolio metrics and provides:")
    items = [
        "Executive summary with total savings and recommendation",
        "Portfolio risk heat-map (high/medium/low complexity servers)",
        "Migration wave planning recommendations",
        "Budget-grade financial projections with confidence ranges",
        "Quick wins identification (highest savings, lowest complexity)",
    ]
    for item in items:
        add_bullet(doc, item)

    add_heading_styled(doc, "Rate Limiting", level=2)
    doc.add_paragraph(
        "AI calls are rate-limited to 10 calls per hour per session to manage API costs. "
        "The rate limit counter is displayed in the sidebar when approaching the limit."
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 9: TAB 3 — BATCH RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "8. Tab 3: Batch Results & Portfolio View", level=1)

    doc.add_paragraph(
        "After batch analysis completes, Tab 3 provides executive-level portfolio views."
    )

    add_heading_styled(doc, "Executive Summary", level=2)
    summary_items = [
        ("Total Servers Analyzed:", "Count of all servers in the batch"),
        ("Total On-Prem Cost:", "Sum of all on-premises annual costs"),
        ("Best Cloud Cost:", "Sum of cheapest cloud option per server (AWS or Azure 3yr RI)"),
        ("Total Annual Savings:", "Difference between on-prem and best cloud"),
        ("Savings Percentage:", "Portfolio-level savings as percentage of on-prem"),
    ]
    for bold, desc in summary_items:
        add_bullet(doc, desc, bold)

    add_heading_styled(doc, "Enhanced Portfolio Rows (when enabled)", level=2)
    enhanced_rows = [
        "Network egress totals across all servers",
        "DR + Backup combined annual cost",
        "Storage tier optimization savings",
        "Container and serverless option totals",
        "All-In annual (IaaS + Network + DR) per cloud",
        "Budget support plan totals, migration labor totals",
        "Budget all-in with confidence ranges",
    ]
    for item in enhanced_rows:
        add_bullet(doc, item)

    add_heading_styled(doc, "Charts", level=2)
    doc.add_paragraph(
        "Interactive Plotly charts show: (1) Multi-cloud cost comparison bar chart, "
        "(2) On-prem cost breakdown, and (3) Server-by-server comparison."
    )

    add_heading_styled(doc, "Export", level=2)
    doc.add_paragraph(
        "Download results as a multi-sheet Excel workbook containing: Server Inputs, "
        "Analysis Results, Detailed Breakdown, and Budget Summary sheets. A compliance "
        "notice is included documenting all rate sources and methodology."
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 10: TAB 4 — SCENARIOS & PROJECTIONS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "9. Tab 4: Scenarios & Projections", level=1)

    doc.add_paragraph(
        "This tab provides what-if analysis, multi-year cost projections, ROI break-even "
        "calculations, and migration wave planning."
    )

    add_heading_styled(doc, "Sensitivity Analysis", level=2)
    doc.add_paragraph(
        "Vary input parameters (vCPU, CPU usage, memory, memory usage, storage, IOPS) by "
        "-30%, -15%, +15%, +30% and see the impact on AWS, Azure, and on-prem costs. "
        "Helps identify which variables most affect the migration business case."
    )

    add_heading_styled(doc, "Cost Projections (1-5 Years)", level=2)
    doc.add_paragraph(
        "Projects cloud and on-prem costs forward using the price trends described in "
        "Section 6. Includes cumulative cost comparison and savings trajectory."
    )

    add_heading_styled(doc, "ROI & Break-Even", level=2)
    doc.add_paragraph(
        "Calculates months to break-even after migration investment, monthly and annual "
        "savings, and 3-year ROI percentage."
    )

    add_heading_styled(doc, "Migration Wave Plan", level=2)
    add_styled_table(doc,
        ["Wave", "Name", "Timeline", "Criteria"],
        [
            ["Wave 1", "Quick Wins", "Month 1-2", "Dev/test, no DB, Rehost strategy"],
            ["Wave 2", "Core Migration", "Month 3-6", "Production apps, medium complexity"],
            ["Wave 3", "Complex Workloads", "Month 6-12", "Database servers, stateful, EOL OS"],
            ["Wave 4", "Optimization", "Month 12-18", "Refactor/PaaS candidates, fine-tuning"],
        ],
        col_widths=[0.8, 1.5, 1.2, 3.0]
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 11: TAB 5 — MATILDA DISCOVERY
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "10. Tab 5: Matilda Discovery Integration", level=1)

    doc.add_paragraph(
        "The tool integrates with Matilda Cloud's auto-discovery platform to import "
        "server inventory automatically."
    )

    add_heading_styled(doc, "API Import", level=2)
    doc.add_paragraph(
        "Enter your Matilda API URL and API Key to fetch discovered servers. The tool "
        "automatically maps Matilda's discovery fields to the required CSV column format."
    )

    add_heading_styled(doc, "File Import", level=2)
    doc.add_paragraph(
        "Upload a Matilda discovery export file (CSV/Excel). The tool maps Matilda column "
        "names (e.g., 'cpuCount' -> 'VCPUCount', 'memoryGB' -> 'Memory(GB)') and fills "
        "in defaults for any missing fields."
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 12: TAB 6 — MONITORING
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "11. Tab 6: Monitoring & Health", level=1)

    doc.add_paragraph(
        "The monitoring tab provides operational visibility into the tool's health and performance."
    )

    sections = [
        ("System Health:", "API latency, error rates, uptime metrics for AWS, Azure, and Anthropic endpoints"),
        ("Circuit Breakers:", "Shows open/closed status for each API. Circuit breakers prevent cascading failures by temporarily stopping calls to failing APIs"),
        ("Pricing Cache:", "Cache hit/miss rates, entry count, TTL settings. Cache reduces API calls and improves response times"),
        ("Audit Log:", "Searchable log of all analysis operations with timestamps, user, and action details"),
        ("Rate Limits:", "Current usage against rate limits for API calls, analyses, exports, and AI requests"),
    ]
    for bold, desc in sections:
        add_bullet(doc, desc, bold)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 13: PRICING METHODOLOGY (the big one)
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "12. Pricing Methodology", level=1)

    doc.add_paragraph(
        "This section documents all pricing rates, formulas, and sources used by the tool. "
        "All rates are verifiable against the cited vendor URLs."
    )

    # ── On-Prem Rates ──
    add_heading_styled(doc, "On-Premises Data Center TCO Rates", level=2)
    add_styled_table(doc,
        ["Component", "Rate", "Basis", "Source"],
        [
            ["Hardware Compute", "$130/vCPU/year", "Dell PowerEdge R760, 5yr amortization", "dell.com/poweredge-r760"],
            ["Hardware Memory", "$10/GB/year", "DDR5 RDIMM enterprise, 5yr amortization", "Counterpoint Research 2025, NetworkWorld"],
            ["Hardware Storage", "$0.08/GB/year", "Blended 70/30 SSD/HDD", "Industry standard"],
            ["Power & Cooling", "25W/vCPU x PUE 1.55 x $0.12/kWh", "Dynamic per server", "US DOE 2024, EIA (eia.gov)"],
            ["Facility/Rack", "$1,200/server/year", "Colocation rack share", "ENCOR Advisors, Brightlio 2025"],
            ["Admin Labor", "$1,500/server/year", "SysAdmin allocation (1:50-100)", "Gartner, Sherweb TCO"],
            ["OS: Windows", "$5.50/vCPU/month", "WS 2025 Std, $2,135/16-core", "Dell configurator"],
            ["OS: RHEL", "$3.00/vCPU/month", "RHEL Premium 2-socket", "Dell configurator"],
            ["OS: SUSE", "$2.50/vCPU/month", "SUSE Enterprise", "Dell configurator"],
            ["OS: Linux", "$0", "Open source", "-"],
        ],
        col_widths=[1.5, 1.8, 1.7, 1.5]
    )

    doc.add_paragraph()
    # ── DB Licensing ──
    add_heading_styled(doc, "Database Software Licensing (On-Prem)", level=2)
    add_styled_table(doc,
        ["Database", "Rate", "Model", "Source"],
        [
            ["Oracle Enterprise", "$9,975/vCPU/year", "$47,500/proc, x86 factor 0.5, 5yr + 22% support", "oracle.com/contracts"],
            ["SQL Server Enterprise", "$3,400/vCPU/year", "$15,123/2-core, 5yr + 25% SA", "microsoft.com/licensing"],
            ["SQL Server Standard", "$890/vCPU/year", "$3,945/2-core, 5yr + 25% SA", "microsoft.com/licensing"],
            ["MongoDB Enterprise", "$10,000/server/year", "Flat rate", "mongodb.com/pricing"],
            ["Redis Enterprise", "$5,000/server/year", "Flat rate", "redis.com/pricing"],
            ["MySQL / PostgreSQL", "$0", "Open source", "-"],
            ["MariaDB", "$0", "Open source", "-"],
            ["Memcached / Cassandra", "$0", "Open source", "-"],
        ],
        col_widths=[1.8, 1.5, 1.7, 1.5]
    )

    doc.add_paragraph()
    # ── Cloud VM Pricing ──
    add_heading_styled(doc, "Cloud VM Pricing", level=2)
    doc.add_paragraph(
        "The tool uses a priority pricing pipeline: (1) Live API pricing when available, "
        "(2) Reference catalog as fallback. All prices are US East baseline with regional "
        "multipliers applied."
    )

    add_heading_styled(doc, "Regional Multipliers", level=3)
    add_styled_table(doc,
        ["Region", "AWS Multiplier", "Azure Multiplier"],
        [
            ["US East (Virginia/Ohio)", "1.00x", "1.00x"],
            ["US West (Oregon/WA)", "1.00x", "1.00x"],
            ["US West (N. California)", "1.08x", "-"],
            ["Canada Central", "1.04x", "1.04x"],
            ["EU Ireland / N. Europe", "1.05x", "1.05x"],
            ["EU Frankfurt / W. Europe", "1.08x", "1.08x"],
            ["UK South", "1.07x", "1.07x"],
            ["Singapore / SE Asia", "1.06x", "1.06x"],
            ["Australia East / Sydney", "1.10x", "1.10x"],
            ["Japan East / Tokyo", "1.12x", "1.12x"],
            ["India (Mumbai/Central)", "0.95x", "0.95x"],
        ],
        col_widths=[2.5, 1.8, 2.2]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "RI Discount Modeling", level=3)
    add_styled_table(doc,
        ["Commitment", "Discount vs On-Demand"],
        [
            ["On-Demand", "0% (baseline)"],
            ["1-Year Reserved Instance", "~40% discount"],
            ["3-Year Reserved Instance", "~60% discount"],
        ],
        col_widths=[3.0, 3.5]
    )

    doc.add_paragraph()
    # ── Storage Pricing ──
    add_heading_styled(doc, "Cloud Storage Pricing (per GB/month)", level=2)
    add_styled_table(doc,
        ["Type", "AWS Rate", "Azure Rate", "Auto-Selection Criteria"],
        [
            ["gp3 / Premium SSD", "$0.08", "$0.132", "Default / IOPS > 3,000"],
            ["io1/io2 / Ultra Disk", "$0.125", "$0.165", "IOPS > 16,000 (AWS) / > 10,000 (Azure)"],
            ["st1 / Standard HDD", "$0.045", "$0.04", "Storage > 500 GB, low IOPS"],
            ["Standard SSD", "-", "$0.075", "Azure default for moderate IOPS"],
        ],
        col_widths=[1.8, 1.2, 1.2, 2.3]
    )

    doc.add_paragraph()
    # ── Network/Egress ──
    add_heading_styled(doc, "Network & Egress Pricing", level=2)

    add_heading_styled(doc, "Egress Tiers", level=3)
    add_styled_table(doc,
        ["Tier", "AWS Rate", "Azure Rate"],
        [
            ["First 1 GB (AWS) / 5 GB (Azure)", "Free", "Free"],
            ["Up to 10 TB", "$0.09/GB", "$0.087/GB"],
            ["10-50 TB", "$0.085/GB", "$0.083/GB"],
            ["50-150 TB", "$0.07/GB", "$0.07/GB"],
            ["150+ TB", "$0.05/GB", "$0.05/GB"],
        ],
        col_widths=[2.5, 1.8, 2.2]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "VPN & Private Connectivity", level=3)
    add_styled_table(doc,
        ["Service", "AWS", "Azure"],
        [
            ["Site-to-Site VPN", "$36.50/connection/mo", "$26 (Basic) — $184 (Standard)"],
            ["Dedicated Connection", "$220/mo (1Gbps Direct Connect)", "$218/mo (1Gbps ExpressRoute)"],
            ["10 Gbps Connection", "$1,650/mo", "$3,500/mo"],
            ["Transit/Peering", "$36/attachment/mo", "$0.01/GB (VNet peering)"],
            ["NAT Gateway", "$0.045/GB processed (AWS only)", "N/A"],
        ],
        col_widths=[1.8, 2.5, 2.2]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Load Balancer Costs", level=3)
    add_styled_table(doc,
        ["Component", "AWS", "Azure"],
        [
            ["Base hourly", "$0.0225/hr (ALB/NLB)", "$0.025/hr (Standard)"],
            ["Per-unit charge", "$0.008/LCU-hr (ALB)", "$10/rule/mo (after 5 free)"],
            ["Data processing", "Included in LCU", "$0.005/GB"],
        ],
        col_widths=[1.8, 2.5, 2.2]
    )

    doc.add_paragraph()
    # ── DR & Backup ──
    add_heading_styled(doc, "DR & Backup Pricing", level=2)

    add_heading_styled(doc, "Backup Storage Rates", level=3)
    add_styled_table(doc,
        ["Service", "AWS Rate", "Azure Rate"],
        [
            ["Snapshot/VM Backup", "$0.05/GB-month", "$0.025/GB (LRS), $0.05/GB (GRS)"],
            ["Cold/Archive", "$0.01/GB (Backup cold)", "$0.002/GB (Archive tier)"],
            ["DB Backup", "$0.095/GB (RDS)", "$0.095/GB (SQL)"],
            ["VM Instance Fee", "N/A", "$10/protected VM/month"],
        ],
        col_widths=[1.8, 2.5, 2.2]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "DR Strategy Costs", level=3)
    add_styled_table(doc,
        ["Strategy", "Compute Cost", "RTO", "RPO", "Auto-Selected For"],
        [
            ["Backup & Restore", "0% of prod compute", "4-24 hours", "Last backup", "Web, API, Cache, LB, Monitoring, CI/CD"],
            ["Pilot Light", "10% of prod compute", "10-30 min", "Minutes", "Application Server"],
            ["Warm Standby", "30% of prod compute", "Minutes", "Seconds", "Database, File, Mail Server"],
            ["Multi-Site", "100% of prod compute", "Near-zero", "Near-zero", "Manually selected only"],
        ],
        col_widths=[1.2, 1.3, 1.0, 1.0, 2.0]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "DR Service Fees", level=3)
    add_styled_table(doc,
        ["Service", "Rate"],
        [
            ["AWS Elastic DR", "$0.028/instance/hour (~$20.44/month)"],
            ["Azure Site Recovery", "$25/protected instance/month"],
        ],
        col_widths=[3.0, 3.5]
    )

    doc.add_paragraph()
    # ── Storage Tiers ──
    add_heading_styled(doc, "Storage Tier Optimization", level=2)
    doc.add_paragraph(
        "The tool recommends distributing storage across hot/warm/cool/archive tiers "
        "based on access patterns (IOPS), server type, and database presence."
    )

    add_heading_styled(doc, "AWS Storage Tiers (per GB/month)", level=3)
    add_styled_table(doc,
        ["Tier", "Disk (EBS)", "Object (S3)", "Service Name"],
        [
            ["Hot", "$0.08", "$0.023", "gp3 / S3 Standard"],
            ["Warm", "$0.045", "$0.0125", "st1 / S3 Infrequent Access"],
            ["Cool", "$0.015", "$0.004", "sc1 / S3 Glacier Instant Retrieval"],
            ["Archive", "N/A", "$0.00099", "S3 Glacier Deep Archive"],
        ],
        col_widths=[0.8, 1.2, 1.5, 3.0]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Azure Storage Tiers (per GB/month)", level=3)
    add_styled_table(doc,
        ["Tier", "Disk", "Blob", "Service Name"],
        [
            ["Hot", "$0.132", "$0.0184", "Premium SSD / Hot Blob"],
            ["Warm", "$0.075", "$0.01", "Standard SSD / Cool Blob"],
            ["Cool", "$0.04", "$0.0036", "Standard HDD / Cold Blob"],
            ["Archive", "N/A", "$0.002", "Archive Blob"],
        ],
        col_widths=[0.8, 1.2, 1.5, 3.0]
    )

    doc.add_paragraph()
    # ── Serverless & Container ──
    add_heading_styled(doc, "Serverless & Container Pricing", level=2)

    add_heading_styled(doc, "Serverless (Lambda / Azure Functions)", level=3)
    add_styled_table(doc,
        ["Component", "AWS Lambda", "Azure Functions"],
        [
            ["Per million requests", "$0.20", "$0.20"],
            ["Per GB-second", "$0.0000166667", "$0.000016"],
            ["Free tier requests", "1,000,000/month", "1,000,000/month"],
            ["Free tier compute", "400,000 GB-seconds", "400,000 GB-seconds"],
        ],
        col_widths=[2.0, 2.2, 2.3]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Container (Fargate / Container Apps)", level=3)
    add_styled_table(doc,
        ["Component", "AWS Fargate", "Azure Container Apps"],
        [
            ["vCPU cost", "$0.04048/vCPU-hour", "$0.000024/vCPU-second"],
            ["Memory cost", "$0.004445/GB-hour", "$0.000003/GB-second"],
            ["Spot discount", "70%", "N/A"],
            ["Kubernetes mgmt", "$73/mo (EKS cluster)", "Free (AKS), $73/mo SLA option"],
        ],
        col_widths=[1.8, 2.3, 2.4]
    )

    doc.add_paragraph()
    # ── PaaS Mapping ──
    add_heading_styled(doc, "PaaS Service Mapping", level=2)
    doc.add_paragraph("The tool automatically maps workloads to the appropriate PaaS service:")

    add_heading_styled(doc, "Database PaaS Mapping", level=3)
    add_styled_table(doc,
        ["Database", "AWS PaaS", "Azure PaaS"],
        [
            ["PostgreSQL", "Aurora PostgreSQL", "Azure DB for PostgreSQL"],
            ["MySQL / MariaDB", "Aurora MySQL", "Azure DB for MySQL"],
            ["SQL Server", "RDS for SQL Server", "Azure SQL Database"],
            ["Oracle", "RDS for Oracle", "Azure DB for PostgreSQL*"],
            ["MongoDB", "Amazon DocumentDB", "Cosmos DB (MongoDB API)"],
            ["Redis", "ElastiCache Redis", "Azure Cache for Redis"],
            ["Memcached", "ElastiCache Memcached", "Azure Cache for Redis"],
            ["DynamoDB", "Amazon DynamoDB", "-"],
            ["Cassandra", "Amazon Keyspaces", "Cosmos DB (Cassandra API)"],
        ],
        col_widths=[1.5, 2.3, 2.7]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Non-Database PaaS Mapping", level=3)
    add_styled_table(doc,
        ["Server Type", "AWS PaaS", "Azure PaaS"],
        [
            ["Web Server", "AWS App Runner", "Azure App Service"],
            ["Application Server", "AWS Elastic Beanstalk", "Azure App Service"],
            ["API Gateway", "Amazon API Gateway", "Azure API Management"],
            ["Cache Server", "Amazon ElastiCache", "Azure Cache for Redis"],
            ["File Server", "Amazon EFS", "Azure Files"],
            ["Mail Server", "Amazon SES + WorkMail", "Microsoft 365 (Exchange Online)"],
            ["Load Balancer", "Elastic Load Balancing (ALB)", "Azure Application Gateway"],
            ["Monitoring", "Amazon CloudWatch", "Azure Monitor"],
            ["CI/CD", "AWS CodePipeline", "Azure Pipelines (DevOps)"],
        ],
        col_widths=[1.5, 2.3, 2.7]
    )

    doc.add_paragraph()
    # ── Azure Local ──
    add_heading_styled(doc, "Azure Local (Hybrid) Pricing", level=2)
    add_styled_table(doc,
        ["Scenario", "Rate", "What's Included"],
        [
            ["Linux Guest (Host Fee)", "$10/physical core/month", "Azure Local host service, Azure Arc, AKS"],
            ["Windows Guest", "$23.30/physical core/month", "Host fee + unlimited WS guest licensing"],
            ["Azure Hybrid Benefit", "$0/month", "WS Datacenter w/ SA waives all fees"],
            ["WS 2025 PAYG (Azure Arc)", "$33.58/physical core/month", "Pay-as-you-go via Azure Arc"],
        ],
        col_widths=[2.0, 2.0, 2.5]
    )

    doc.add_paragraph()
    doc.add_paragraph("Source: azure.microsoft.com/en-us/pricing/details/azure-local/")

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 14: SUPPORTED CURRENCIES
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "13. Supported Currencies", level=1)

    doc.add_paragraph(
        "The tool supports 17 currencies with live exchange rate fetching (fallback to "
        "static rates when offline). All costs are calculated in USD and converted at display time."
    )

    add_styled_table(doc,
        ["Code", "Currency", "Symbol"],
        [
            ["USD", "US Dollar", "$"],
            ["CAD", "Canadian Dollar", "C$"],
            ["EUR", "Euro", "\u20ac"],
            ["GBP", "British Pound", "\u00a3"],
            ["AUD", "Australian Dollar", "A$"],
            ["JPY", "Japanese Yen", "\u00a5"],
            ["INR", "Indian Rupee", "\u20b9"],
            ["SGD", "Singapore Dollar", "S$"],
            ["CHF", "Swiss Franc", "CHF"],
            ["SEK", "Swedish Krona", "kr"],
            ["NZD", "New Zealand Dollar", "NZ$"],
            ["BRL", "Brazilian Real", "R$"],
            ["MXN", "Mexican Peso", "MX$"],
            ["KRW", "South Korean Won", "\u20a9"],
            ["HKD", "Hong Kong Dollar", "HK$"],
            ["AED", "UAE Dirham", "AED"],
            ["ZAR", "South African Rand", "R"],
        ],
        col_widths=[1.0, 2.5, 1.0]
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 15: RBAC & PERMISSIONS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "14. RBAC & Permissions", level=1)

    doc.add_paragraph(
        "The tool implements role-based access control with three roles. Authentication "
        "uses SHA-256 hashed passwords with session-based tokens."
    )

    add_styled_table(doc,
        ["Permission", "Admin", "Analyst", "Viewer"],
        [
            ["View Dashboard", "Yes", "Yes", "Yes"],
            ["Analyze Servers", "Yes", "Yes", "No"],
            ["Export Data", "Yes", "Yes", "Yes"],
            ["AI Analysis", "Yes", "Yes", "No"],
            ["Bulk Upload", "Yes", "Yes", "No"],
            ["Scenario Analysis", "Yes", "Yes", "No"],
            ["Auto Discovery", "Yes", "No", "No"],
            ["Manage Users", "Yes", "No", "No"],
            ["View Audit Log", "Yes", "No", "No"],
        ],
        col_widths=[2.0, 1.2, 1.2, 1.2]
    )

    doc.add_paragraph()
    add_heading_styled(doc, "Session Security", level=2)
    security_items = [
        ("Session Timeout:", "60 minutes of inactivity"),
        ("Login Attempts:", "5 failed attempts trigger 15-minute lockout"),
        ("Session Token:", "64-character hex token generated per login"),
        ("Rate Limits:", "API: 100/hr, Analysis: 50/hr, Export: 20/hr, AI: 10/hr"),
    ]
    for bold, desc in security_items:
        add_bullet(doc, desc, bold)

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 16: COMPLIANCE & DATA HANDLING
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "15. Compliance & Data Handling", level=1)

    doc.add_paragraph(
        "The tool is designed with a zero-persistence architecture to meet enterprise "
        "compliance requirements."
    )

    compliance_items = [
        ("Zero Server-Side Storage:", "No data is stored, cached, or persisted on the server. All computations happen in-memory at runtime."),
        ("Session-Only Data:", "All session data (inputs, results, API keys) lives only in the browser's session state and is cleared when the browser tab closes."),
        ("No Database:", "The tool has no database backend. There are no tables, no schemas, no data at rest."),
        ("Ephemeral Exports:", "Excel/CSV exports are generated on-the-fly in memory and immediately discarded after download."),
        ("API Key Security:", "Anthropic and AWS API keys can be stored in .streamlit/secrets.toml (encrypted) or entered per-session. Keys are never logged or persisted."),
        ("Audit Logging:", "When enabled, audit logs are held in session memory only and are lost on session end."),
        ("Pricing Cache:", "Optional in-memory cache (TTL: 30 minutes) for API responses. Cleared on session end."),
    ]
    for bold, desc in compliance_items:
        add_bullet(doc, desc, bold)

    add_heading_styled(doc, "Export Freshness", level=2)
    doc.add_paragraph(
        "Every export contains a compliance notice documenting: (1) all rate sources with URLs, "
        "(2) the date/time of generation, (3) methodology descriptions for on-prem, cloud, "
        "network, DR, storage, serverless, PaaS, budget, and support plan calculations."
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # APPENDIX A: REQUIRED CSV COLUMNS
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "Appendix A: Required CSV Columns", level=1)

    doc.add_paragraph(
        "The following columns are expected in the CSV/Excel upload file. Download the "
        "template from the Upload File tab for a pre-formatted file."
    )

    csv_columns = [
        ["Cloud Provider", "Target cloud", "AWS, Azure, Azure Local", "AWS"],
        ["Cloud Region", "Target region", "See region lists in sidebar", "US East (N. Virginia)"],
        ["Host Name", "Server identifier", "Any text", "web-prod-01"],
        ["IP Address", "Server IP", "IPv4 address", "10.0.1.50"],
        ["Platform", "OS platform", "Linux, Windows", "Linux"],
        ["Operating System", "Specific OS", "Linux, RHEL, Windows Server 2019, etc.", "Linux"],
        ["Environment", "Deployment env", "Production, Development, Testing, QA, Staging, DR", "Production"],
        ["Server Type", "Workload type", "Application, Web Server, Database Server, etc.", "Application"],
        ["OS EOL Status", "End-of-life flag", "No, Yes (EOL)", "No"],
        ["Migration Type", "6Rs strategy", "Rehost, Replatform, Refactor, Repurchase, Retire, Retain", "Rehost"],
        ["Databases/Caches", "DB engines", "None, MySQL, PostgreSQL, SQL Server, Oracle, MongoDB, Redis, etc.", "None"],
        ["AppServices", "App services", "Any text", ""],
        ["InstanceUsage", "Usage pattern", "24x7, Business Hours, On-Demand, Scheduled", "24x7"],
        ["VCPUCount", "vCPU count", "Integer (1-128)", "4"],
        ["AvgCPUUsage (%tage)", "CPU utilization", "0-100", "50"],
        ["Memory(GB)", "Memory in GB", "1-1024", "8"],
        ["Avg Memory (%tage)", "Memory utilization", "0-100", "50"],
        ["Total Storage(GB)", "Disk capacity", "10-65536", "200"],
        ["Storage Usage (%)", "Storage used", "0-100", "60"],
        ["Average Network Throughput (Mbps)", "Avg network", "0-10000", "100"],
        ["Total Network Throughput (Mbps)", "Peak network", "0-100000", "1000"],
        ["Average Disk IOPS", "Avg IOPS", "0-500000", "500"],
    ]

    add_styled_table(doc,
        ["Column Name", "Description", "Valid Values", "Default"],
        csv_columns,
        col_widths=[2.0, 1.2, 1.8, 1.5]
    )

    doc.add_page_break()

    # ══════════════════════════════════════════════════════════════════════════
    # APPENDIX B: RATE SOURCES
    # ══════════════════════════════════════════════════════════════════════════
    add_heading_styled(doc, "Appendix B: Rate Sources & References", level=1)

    doc.add_paragraph(
        "All pricing rates used in the tool are sourced from official vendor documentation. "
        "Below is the complete list of sources by category."
    )

    sources = [
        ["On-Prem Hardware", "Dell PowerEdge R760/R770 configurator", "dell.com/poweredge-r760"],
        ["On-Prem Memory", "DDR5 RDIMM pricing", "Counterpoint Research 2025, NetworkWorld Nov 2025"],
        ["On-Prem Power", "US DOE 2024 Data Center Energy Report", "energy.gov, eia.gov"],
        ["On-Prem Facility", "Colocation pricing guides", "ENCOR Advisors, Brightlio 2025"],
        ["On-Prem Labor", "IT staffing benchmarks", "Gartner, Sherweb TCO Analysis"],
        ["DB: Oracle", "Oracle Technology Global Price List", "oracle.com/contracts"],
        ["DB: SQL Server", "Microsoft Volume Licensing", "microsoft.com/licensing"],
        ["DB: MongoDB", "MongoDB Enterprise Advanced pricing", "mongodb.com/pricing"],
        ["DB: Redis", "Redis Enterprise pricing", "redis.com/pricing"],
        ["AWS EC2", "EC2 On-Demand pricing", "aws.amazon.com/ec2/pricing/on-demand/"],
        ["AWS S3", "S3 pricing", "aws.amazon.com/s3/pricing/"],
        ["AWS EBS", "EBS pricing", "aws.amazon.com/ebs/pricing/"],
        ["AWS Egress", "Data transfer pricing", "aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer"],
        ["AWS Support", "Premium support pricing", "aws.amazon.com/premiumsupport/pricing/"],
        ["AWS DR", "Elastic Disaster Recovery pricing", "aws.amazon.com/disaster-recovery/pricing/"],
        ["AWS Backup", "AWS Backup pricing", "aws.amazon.com/backup/pricing/"],
        ["AWS Lambda", "Lambda pricing", "aws.amazon.com/lambda/pricing/"],
        ["AWS Fargate", "Fargate pricing", "aws.amazon.com/fargate/pricing/"],
        ["AWS EKS", "EKS pricing", "aws.amazon.com/eks/pricing/"],
        ["Azure VMs", "Azure Retail Prices API (live)", "prices.azure.com/api/retail/prices"],
        ["Azure Blob", "Blob Storage pricing", "azure.microsoft.com/pricing/details/storage/blobs/"],
        ["Azure Disk", "Managed Disks pricing", "azure.microsoft.com/pricing/details/managed-disks/"],
        ["Azure Egress", "Bandwidth pricing", "azure.microsoft.com/pricing/details/bandwidth/"],
        ["Azure Support", "Support plans", "azure.microsoft.com/support/plans/"],
        ["Azure Site Recovery", "Site Recovery pricing", "azure.microsoft.com/pricing/details/site-recovery/"],
        ["Azure Backup", "Backup pricing", "azure.microsoft.com/pricing/details/backup/"],
        ["Azure Functions", "Functions pricing", "azure.microsoft.com/pricing/details/functions/"],
        ["Azure Containers", "Container Apps pricing", "azure.microsoft.com/pricing/details/container-apps/"],
        ["Azure AKS", "AKS pricing", "azure.microsoft.com/pricing/details/kubernetes-service/"],
        ["Azure Local", "Azure Local pricing", "azure.microsoft.com/pricing/details/azure-local/"],
        ["Migration Benchmarks", "Migration TCO benchmarks", "Gartner, AWS MAP, Azure Migrate"],
        ["Confidence Ranges", "Budget methodology", "Gartner, McKinsey cloud migration reports"],
    ]

    add_styled_table(doc,
        ["Category", "Description", "Source URL / Reference"],
        sources,
        col_widths=[1.5, 2.0, 3.0]
    )

    doc.add_paragraph()
    doc.add_paragraph()

    # ── Footer ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("— End of Document —")
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    run.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | Infosys Cobalt Migration Analyzer v2.0")
    run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    run.font.size = Pt(8)

    # ── Save ──────────────────────────────────────────────────────────────────
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "Infosys_Cobalt_Migration_Analyzer_Manual.docx")
    doc.save(output_path)
    print(f"\nManual generated successfully!")
    print(f"  Path: {output_path}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")
    return output_path


if __name__ == "__main__":
    generate_manual()
