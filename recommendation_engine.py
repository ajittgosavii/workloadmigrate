"""
AI Recommendation Engine — Stateless
======================================
Uses Claude API for deep, decision-grade migration analysis.
NO data is stored, cached, or persisted. Each call is independent.

Three functions:
  1. get_ai_recommendation() — Single server deep-dive (sizing, PaaS/IaaS, risks, gaps)
  2. get_batch_ai_summary() — Portfolio executive brief with decision matrix
  3. get_ai_gap_analysis()  — Proactive gap identification for migration planning
"""

import json
from typing import Dict, List, Optional


def _format_enhanced_costs(outputs: Dict) -> str:
    """Format enhanced cost modules data for AI prompt context."""
    parts = []

    # Network costs
    net = outputs.get("network_costs", {})
    if net:
        parts.append(f"""NETWORK COSTS:
  Egress: ${net.get('egress_monthly', 0):,.2f}/mo | VPN: ${net.get('vpn_monthly', 0):,.2f}/mo
  Load Balancer: ${net.get('lb_monthly', 0):,.2f}/mo | NAT Gateway: ${net.get('nat_monthly', 0):,.2f}/mo
  Total Network: ${net.get('total_monthly', 0):,.2f}/mo (${net.get('total_annual', 0):,.2f}/yr)""")

    # DR + Backup
    dr = outputs.get("dr_backup_costs", {})
    if dr:
        parts.append(f"""DR & BACKUP COSTS:
  Backup: ${dr.get('backup_monthly', 0):,.2f}/mo ({dr.get('backup_strategy', 'N/A')})
  DR: ${dr.get('dr_monthly', 0):,.2f}/mo ({dr.get('dr_strategy', 'N/A')})
  Combined: ${dr.get('combined_monthly', 0):,.2f}/mo (${dr.get('combined_annual', 0):,.2f}/yr)""")

    # Storage optimization
    stor = outputs.get("storage_tiers", {})
    if stor:
        parts.append(f"""STORAGE TIER OPTIMIZATION:
  Used Storage: {stor.get('used_storage_gb', 0):.0f} GB
  Single-Tier (all hot): ${stor.get('single_tier_monthly', 0):,.2f}/mo
  Optimized (tiered): ${stor.get('optimized_monthly', 0):,.2f}/mo
  Savings: ${stor.get('savings_monthly', 0):,.2f}/mo ({stor.get('savings_pct', 0):.0f}%)""")

    # Modern deployment options
    mod = outputs.get("modern_options", {})
    if mod:
        sl = mod.get("serverless", {})
        ct = mod.get("container", {})
        parts.append(f"""MODERN DEPLOYMENT OPTIONS:
  Serverless: {"$" + f"{sl.get('monthly_cost', 0):,.2f}/mo" if sl.get('suitable') else "Not suitable — " + sl.get('reason', 'N/A')}
  Container (On-Demand): ${ct.get('monthly_cost', 0):,.2f}/mo ({ct.get('container_vcpu', 0)} vCPU / {ct.get('container_memory_gb', 0)} GB)
  Container (Spot): ${mod.get('container_spot', {}).get('monthly_cost', 0):,.2f}/mo
  Recommended: {mod.get('recommended', 'N/A')}""")

    # Migration transfer
    mig = outputs.get("migration_transfer", {})
    if mig:
        rec = mig.get("recommended", {})
        parts.append(f"""MIGRATION DATA TRANSFER:
  Data to Transfer: {mig.get('data_to_transfer_gb', 0):.0f} GB
  Method: {rec.get('method', 'N/A')} | Cost: ${rec.get('cost', 0):,.2f}
  Duration: {rec.get('duration', 'N/A')}""")

    # Budget-grade costs
    bsup = outputs.get("budget_support", {})
    bmig = outputs.get("budget_migration_labor", {})
    aws_conf = outputs.get("budget_aws_confidence", {})
    az_conf = outputs.get("budget_azure_confidence", {})
    if bsup or bmig:
        parts.append(f"""BUDGET-GRADE COSTS:
  Support Plan: ${bsup.get('annual_cost', 0):,.2f}/yr ({bsup.get('support_tier', 'N/A')})
  Migration Labor: ${bmig.get('migration_labor', 0):,.2f} | Testing: ${bmig.get('testing_validation', 0):,.2f}
  Training: ${bmig.get('training', 0):,.2f} | Parallel Run: ${bmig.get('parallel_run', 0):,.2f}
  Total One-Time: ${outputs.get('budget_total_one_time', 0):,.2f}
  AWS Budget All-In: ${outputs.get('budget_aws_all_in_annual', 0):,.2f}/yr (IaaS+Net+DR+Support)
  Azure Budget All-In: ${outputs.get('budget_azure_all_in_annual', 0):,.2f}/yr (IaaS+Net+DR+Support)
  AWS Confidence: Low ${aws_conf.get('low_annual', 0):,.2f} | Budget ${aws_conf.get('budget_annual', 0):,.2f} | High ${aws_conf.get('high_annual', 0):,.2f}
  Azure Confidence: Low ${az_conf.get('low_annual', 0):,.2f} | Budget ${az_conf.get('budget_annual', 0):,.2f} | High ${az_conf.get('high_annual', 0):,.2f}
  Break-Even Year: {outputs.get('budget_summary', {}).get('breakeven_year', 'N/A')}""")

    return "\n\n".join(parts) if parts else "Enhanced cost modules not available."


def get_ai_recommendation(inputs: Dict, outputs: Dict, api_key: str) -> Optional[str]:
    """Stateless: Deep per-server migration analysis. Nothing is stored."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        xp = outputs.get("cross_provider", {})
        azl = outputs.get("azure_local", {})
        bk = outputs.get("on_prem_breakdown", {})
        aws_ann = xp.get("AWS", {}).get("annual_3yr_ri", 0)
        az_ann = xp.get("Azure", {}).get("annual_3yr_ri", 0)
        enhanced_costs = _format_enhanced_costs(outputs)

        # All-In costs (IaaS + Network + DR/Backup)
        net_annual = outputs.get("network_costs", {}).get("total_annual", 0)
        dr_annual = outputs.get("dr_backup_costs", {}).get("combined_annual", 0)
        aws_all_in = aws_ann + net_annual + dr_annual
        az_all_in = az_ann + net_annual + dr_annual
        paas_annual = (outputs.get("paas_reserved_3yr", 0) + outputs.get("paas_licensing", 0) + outputs.get("paas_storage_price", 0)) * 12

        prompt = f"""You are a senior cloud architect and financial analyst preparing a migration decision brief for an enterprise Architecture Review Board (ARB). Produce a thorough, data-driven analysis.

SERVER PROFILE:
  Host: {inputs.get('host_name','N/A')}
  Platform: {inputs.get('platform','N/A')} / OS: {inputs.get('operating_system','N/A')}
  Environment: {inputs.get('environment','N/A')} | Type: {inputs.get('server_type','N/A')}
  OS EOL Status: {inputs.get('os_eol_status','N/A')}
  Proposed Migration: {inputs.get('migration_type','N/A')}
  Databases/Caches: {inputs.get('databases_caches','None')}
  DB License Cost (On-Prem): ${outputs.get('db_licensing_annual', 0):,.2f}/yr ({outputs.get('db_licensing_name', 'None')})
  App Services: {inputs.get('app_services','None')}

RESOURCE UTILIZATION:
  vCPU: {inputs.get('vcpu_count',0)} cores @ {inputs.get('avg_cpu_usage',0)}% avg
  Memory: {inputs.get('memory_gb',0)} GB @ {inputs.get('avg_memory_usage',0)}% avg
  Storage: {inputs.get('total_storage_gb',0)} GB @ {inputs.get('storage_usage_pct',0)}% used
  IOPS: {inputs.get('avg_disk_iops',0)}
  Network: {inputs.get('avg_network_throughput',0)} Mbps avg / {inputs.get('total_network_throughput',0)} Mbps total
  Usage Pattern: {inputs.get('instance_usage','24x7')}

RIGHT-SIZING RESULTS:
  Original to Right-Sized: {inputs.get('vcpu_count',0)} to {outputs.get('right_sizing_cpu','N/A')} vCPU | {inputs.get('memory_gb',0)} to {outputs.get('right_sizing_memory','N/A')} GB
  Storage: {inputs.get('total_storage_gb',0)} to {outputs.get('right_sizing_storage','N/A')} GB
  Instance Family: {outputs.get('_instance_family', 'general')} | DR Strategy: {outputs.get('_dr_strategy', 'pilot_light')}

CROSS-PROVIDER COST COMPARISON (Annual, 3yr Reserved):
  AWS:         ${aws_ann:>12,.2f}/yr  Instance: {xp.get('AWS',{}).get('instance_type','N/A')} ({xp.get('AWS',{}).get('vcpu',0)} vCPU / {xp.get('AWS',{}).get('memory',0)} GB)
  Azure:       ${az_ann:>12,.2f}/yr  Instance: {xp.get('Azure',{}).get('instance_type','N/A')} ({xp.get('Azure',{}).get('vcpu',0)} vCPU / {xp.get('Azure',{}).get('memory',0)} GB)
  Azure Local: ${azl.get('recommended_annual',0):>12,.2f}/yr  Scenario: {azl.get('recommended_label','N/A')}
    Linux: ${azl.get('linux_total_annual',0):,.2f}  |  Windows: ${azl.get('windows_total_annual',0):,.2f}  |  AHB: ${azl.get('ahb_total_annual',0):,.2f}
  On-Premises: ${outputs.get('on_prem_yearly_cost',0):>12,.2f}/yr
    Hardware: ${bk.get('hw_total',0):,.2f} | Power: ${bk.get('power_cooling',0):,.2f} | Facility: ${bk.get('facility',0):,.2f} | Labor: ${bk.get('admin_labor',0):,.2f} | OS License: ${bk.get('annual_licensing',0):,.2f} | DB License: ${bk.get('db_licensing_annual',0):,.2f}

ALL-IN CLOUD ANNUAL (IaaS + Network + DR/Backup):
  AWS All-In:   ${aws_all_in:>12,.2f}/yr
  Azure All-In: ${az_all_in:>12,.2f}/yr

PaaS OPTION:
  Service: {outputs.get('paas_service_name','N/A')} ({outputs.get('paas_instance_type','N/A')})
  PaaS On-Demand: ${outputs.get('paas_on_demand',0):,.2f}/mo | PaaS 3yr: ${outputs.get('paas_reserved_3yr',0):,.2f}/mo
  PaaS Annual (3yr RI): ${paas_annual:,.2f}/yr

{enhanced_costs}

ANALYSIS REQUIRED — Produce a STRUCTURED decision brief with these exact sections. Use real $ amounts and % throughout. Be specific to THIS server's data.

### EXECUTIVE RECOMMENDATION
State the recommended path (AWS/Azure/Azure Local/On-Prem/PaaS) with the strongest financial and technical justification. Name the specific instance and annual cost. 2-3 sentences.

### SIZING RECOMMENDATION
Detailed right-sizing analysis for this specific server:
- **Current state**: Analyze the {inputs.get('avg_cpu_usage',0)}% CPU / {inputs.get('avg_memory_usage',0)}% memory utilization — is this over-provisioned, under-provisioned, or right-sized?
- **Optimal size**: Recommend the exact instance type and size for EACH cloud provider. Explain why.
- **Burstable vs Fixed**: Should this use burstable (T-series/B-series) or fixed (M-series/D-series) instances? Base this on the usage pattern ({inputs.get('instance_usage','24x7')}) and CPU% profile.
- **Memory-to-CPU ratio**: Is the workload CPU-bound or memory-bound? Recommend the right instance family (general/compute/memory-optimized).
- **Storage tier**: What storage type is optimal for {inputs.get('avg_disk_iops',0)} IOPS? (gp3/io2/Standard SSD/Premium SSD)
- **Quantify savings**: Show $ saved from right-sizing vs current-size pricing.

### PaaS vs IaaS DECISION
Make a clear recommendation for this specific server — should it go PaaS or IaaS?
- **PaaS suitability score** (1-10): Rate how well this workload fits PaaS. Consider:
  - Server type: {inputs.get('server_type','N/A')} — is this a PaaS-native workload?
  - Databases: {inputs.get('databases_caches','None')} — managed DB services available?
  - App services: {inputs.get('app_services','None')} — containerizable? serverless-compatible?
  - State: Is this stateful or stateless?
- **PaaS recommendation**: If PaaS, name the exact service (e.g., Azure App Service P2v3, AWS RDS db.r6g.xlarge, Azure SQL Managed Instance)
- **IaaS justification**: If IaaS, explain why PaaS isn't suitable for this workload
- **Hybrid option**: Could parts run on PaaS while others stay IaaS? (e.g., DB on managed service, app on VM)
- **Cost comparison**: PaaS ${paas_annual:,.2f}/yr vs AWS IaaS ${aws_ann:,.2f}/yr vs Azure IaaS ${az_ann:,.2f}/yr

### COST DECISION MATRIX
Create a comparison table showing each option's annual cost, all-in annual cost (including network/DR/backup), savings vs on-prem, and a 1-line verdict:
- AWS IaaS (3yr RI) — All-In: ${aws_all_in:,.2f}
- Azure IaaS (3yr RI) — All-In: ${az_all_in:,.2f}
- Azure Local (recommended scenario)
- PaaS (3yr RI)
- Stay On-Prem

### MIGRATION STRATEGY
- Recommended migration approach for this specific workload type ({inputs.get('server_type','N/A')})
- If databases are involved ({inputs.get('databases_caches','None')}), address data migration complexity
- Downtime requirements and rollback plan considerations
- Dependencies and sequencing

### GAPS & MISSING CONSIDERATIONS
Proactively identify what might be MISSING from this migration plan:
- **Licensing gaps**: DB licensing detected: {outputs.get('db_licensing_name', 'None')}. Are there additional application licenses (SAP, middleware) not captured? BYOL opportunities for {inputs.get('databases_caches','None')}?
- **Network dependencies**: Inter-server communication, latency requirements between this server and others
- **Security requirements**: Compliance frameworks (SOC2, HIPAA, PCI-DSS) that affect placement
- **Data residency**: Any geographic or regulatory constraints on where data can be hosted?
- **Operational readiness**: Team skills gap for the recommended cloud platform? Training needed?
- **Hidden costs**: Monitoring, logging, WAF, DDoS protection, DNS hosting
- **Performance testing**: Load testing needed before cutover? Benchmark requirements?
- **Backup/DR validation**: Is the current DR strategy adequate for cloud?

### RISK ASSESSMENT
- Technical risks specific to this migration (OS compatibility, EOL status: {inputs.get('os_eol_status','N/A')})
- Performance risks (IOPS: {inputs.get('avg_disk_iops',0)}, network: {inputs.get('avg_network_throughput',0)} Mbps)
- Compliance / licensing risks
- Operational risks during transition

### BUDGET-GRADE TCO PROJECTION
Use the CALCULATED budget data (not estimates):
- Migration one-time: ${outputs.get('budget_total_one_time', 0):,.2f} (labor + testing + training + parallel run + data transfer)
- Budget All-In Annual ({outputs.get('budget_best_cloud', 'N/A')}): ${outputs.get(f"budget_{outputs.get('budget_best_cloud', 'aws').lower()}_all_in_annual", 0):,.2f}/yr (IaaS + Network + DR + Support)
- Confidence range: Low ${outputs.get(f"budget_{outputs.get('budget_best_cloud', 'aws').lower()}_confidence", {{}}).get('low_annual', 0):,.2f} to High ${outputs.get(f"budget_{outputs.get('budget_best_cloud', 'aws').lower()}_confidence", {{}}).get('high_annual', 0):,.2f}
- Budget with 10% contingency: ${outputs.get(f"budget_{outputs.get('budget_best_cloud', 'aws').lower()}_confidence", {{}}).get('budget_annual', 0):,.2f}/yr
- Break-even: Year {outputs.get('budget_summary', {{}}).get('breakeven_year', 'N/A')}
- Present a 3-year total: Cloud vs On-Prem cumulative (including Year 0 migration)

Be concrete, use actual $ figures from the data, and make clear recommendations. Never say "it depends" — commit to a recommendation."""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3500,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except ImportError:
        return "Install anthropic SDK: `pip install anthropic`"
    except Exception as e:
        return f"AI unavailable: {str(e)}"


def get_batch_ai_summary(all_results: List[Dict], api_key: str) -> Optional[str]:
    """Stateless: Deep portfolio analysis for decision-makers. Nothing is stored."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        n = len(all_results)
        t_op = sum(r["outputs"].get("on_prem_yearly_cost", 0) for r in all_results)
        t_aws = sum(r["outputs"].get("cross_provider", {}).get("AWS", {}).get("annual_3yr_ri", 0) for r in all_results)
        t_az = sum(r["outputs"].get("cross_provider", {}).get("Azure", {}).get("annual_3yr_ri", 0) for r in all_results)
        t_azl = sum(r["outputs"].get("azure_local", {}).get("recommended_annual", 0) for r in all_results)
        t_paas = sum((r["outputs"].get("paas_reserved_3yr", 0) + r["outputs"].get("paas_licensing", 0) + r["outputs"].get("paas_storage_price", 0)) * 12 for r in all_results)
        t_net = sum(r["outputs"].get("network_costs", {}).get("total_annual", 0) for r in all_results)
        t_dr = sum(r["outputs"].get("dr_backup_costs", {}).get("combined_annual", 0) for r in all_results)
        t_stor_save = sum(r["outputs"].get("storage_tiers", {}).get("savings_monthly", 0) * 12 for r in all_results)
        t_db_lic = sum(r["outputs"].get("db_licensing_annual", 0) for r in all_results)

        # Budget-grade aggregates
        t_support = sum(r["outputs"].get("budget_support", {}).get("annual_cost", 0) for r in all_results)
        t_mig_labor = sum(r["outputs"].get("budget_total_one_time", 0) for r in all_results)
        t_aws_budget = sum(r["outputs"].get("budget_aws_all_in_annual", 0) for r in all_results)
        t_az_budget = sum(r["outputs"].get("budget_azure_all_in_annual", 0) for r in all_results)

        # All-In
        t_aws_allin = t_aws + t_net + t_dr
        t_az_allin = t_az + t_net + t_dr

        # Per-cloud breakdown
        clouds, oses, fams, envs, stype, dbs = {}, {}, {}, {}, {}, {}
        eols = {}
        high_cpu, low_cpu, high_mem, low_mem = [], [], [], []
        top_spenders, top_savers = [], []
        paas_candidates = []
        serverless_candidates = []
        sizing_details = []

        for r in all_results:
            inp, out = r["inputs"], r["outputs"]
            host = inp.get("host_name", "?")
            c = out.get("_cloud_provider", "?")
            clouds[c] = clouds.get(c, 0) + 1
            o = inp.get("operating_system", "?")
            oses[o] = oses.get(o, 0) + 1
            f = out.get("_instance_family", "?")
            fams[f] = fams.get(f, 0) + 1
            e = inp.get("environment", "?")
            envs[e] = envs.get(e, 0) + 1
            s = inp.get("server_type", "?")
            stype[s] = stype.get(s, 0) + 1
            eol = inp.get("os_eol_status", "No")
            if "Yes" in str(eol):
                eols[host] = eol
            db = inp.get("databases_caches", "None")
            db_lic = out.get("db_licensing_annual", 0)
            if db and db != "None":
                dbs[host] = f"{db} (${db_lic:,.0f}/yr license)" if db_lic > 0 else db

            cpu = float(inp.get("avg_cpu_usage", 50))
            mem = float(inp.get("avg_memory_usage", 50))
            if cpu > 80: high_cpu.append(f"{host} ({cpu:.0f}%)")
            if cpu < 20: low_cpu.append(f"{host} ({cpu:.0f}%)")
            if mem > 80: high_mem.append(f"{host} ({mem:.0f}%)")
            if mem < 20: low_mem.append(f"{host} ({mem:.0f}%)")

            op = out.get("on_prem_yearly_cost", 0)
            aws_a = out.get("cross_provider", {}).get("AWS", {}).get("annual_3yr_ri", 0)
            az_a = out.get("cross_provider", {}).get("Azure", {}).get("annual_3yr_ri", 0)
            best = min(aws_a, az_a)
            sav = op - best
            top_spenders.append((host, op))
            top_savers.append((host, sav, op, best, "AWS" if aws_a <= az_a else "Azure"))

            # Sizing analysis
            orig_cpu = float(inp.get("vcpu_count", 0))
            rs_cpu = float(out.get("right_sizing_cpu", orig_cpu))
            orig_mem = float(inp.get("memory_gb", 0))
            rs_mem = float(out.get("right_sizing_memory", orig_mem))
            if rs_cpu < orig_cpu * 0.7 or rs_mem < orig_mem * 0.7:
                sizing_details.append(f"  - {host}: {int(orig_cpu)} to {int(rs_cpu)} vCPU, {orig_mem:.0f} to {rs_mem:.0f}GB RAM ({cpu:.0f}% CPU / {mem:.0f}% mem)")

            # PaaS candidates: web/API/app without DB -> compute PaaS; DB servers -> managed DB PaaS
            paas_ann = (out.get('paas_reserved_3yr', 0) + out.get('paas_licensing', 0) + out.get('paas_storage_price', 0)) * 12
            if s in ("Web Server", "API Gateway", "Application Server") and db in ("None", "", None):
                paas_candidates.append(f"  - {host} ({s}, {e}): Compute PaaS ${paas_ann:,.0f}/yr")
            elif s == "Database Server" or (db and db not in ("None", "")):
                paas_candidates.append(f"  - {host} ({s}, {db}): Managed DB PaaS ${paas_ann:,.0f}/yr (saves ${db_lic:,.0f}/yr DB license)")

            # Serverless candidates
            mod = out.get("modern_options", {})
            sl = mod.get("serverless", {})
            if sl and sl.get("suitable") and sl.get("monthly_cost", 999) < best / 12:
                serverless_candidates.append(f"  - {host} ({s}): serverless ${sl['monthly_cost']:,.0f}/mo vs IaaS ${best/12:,.0f}/mo")

        top_spenders.sort(key=lambda x: -x[1])
        top_savers.sort(key=lambda x: -x[1])

        top5_spend = "\n".join([f"  {i+1}. {h}: ${c:,.0f}/yr on-prem"
                                for i, (h, c) in enumerate(top_spenders[:5])])
        top5_save = "\n".join([f"  {i+1}. {h}: save ${s:,.0f}/yr (${op:,.0f} to ${b:,.0f} on {p})"
                               for i, (h, s, op, b, p) in enumerate(top_savers[:5])])
        eol_list = "\n".join([f"  - {h}: {e}" for h, e in eols.items()]) if eols else "  None"
        db_list = "\n".join([f"  - {h}: {d}" for h, d in dbs.items()]) if dbs else "  None"
        sizing_list = "\n".join(sizing_details[:10]) if sizing_details else "  No servers significantly over-provisioned"
        paas_list = "\n".join(paas_candidates[:8]) if paas_candidates else "  No strong PaaS candidates identified"
        sl_list = "\n".join(serverless_candidates[:5]) if serverless_candidates else "  No serverless candidates identified"

        prod_count = envs.get("Production", 0)
        dev_count = sum(envs.get(k, 0) for k in ["Development", "Testing", "QA"])
        stg_count = envs.get("Staging", 0)

        prompt = f"""You are a senior cloud migration strategist presenting to enterprise leadership (CTO, VP Infrastructure, Finance). Produce a comprehensive, data-driven portfolio analysis that enables executive decision-making.

PORTFOLIO OVERVIEW:
  Total Servers: {n}
  Cloud Distribution: {json.dumps(clouds)}
  Environments: {json.dumps(envs)}
  Server Types: {json.dumps(stype)}
  OS Distribution: {json.dumps(oses)}
  Instance Families: {json.dumps(fams)}

ANNUAL COST COMPARISON:
  On-Premises:       ${t_op:>13,.0f}  (baseline)
  AWS (3yr RI):      ${t_aws:>13,.0f}  (savings: ${t_op-t_aws:>10,.0f}, {((t_op-t_aws)/max(1,t_op)*100):.1f}%)
  Azure (3yr RI):    ${t_az:>13,.0f}  (savings: ${t_op-t_az:>10,.0f}, {((t_op-t_az)/max(1,t_op)*100):.1f}%)
  Azure Local:       ${t_azl:>13,.0f}  (savings: ${t_op-t_azl:>10,.0f}, {((t_op-t_azl)/max(1,t_op)*100):.1f}%)
  PaaS (3yr RI):     ${t_paas:>13,.0f}  (savings: ${t_op-t_paas:>10,.0f}, {((t_op-t_paas)/max(1,t_op)*100):.1f}%)
  DB Licensing (On-Prem): ${t_db_lic:>10,.0f}  (included in On-Prem total; eliminated when migrating to managed PaaS)

ALL-IN CLOUD ANNUAL (IaaS + Network + DR/Backup):
  AWS All-In:        ${t_aws_allin:>13,.0f}  (network: ${t_net:,.0f} + DR/Backup: ${t_dr:,.0f})
  Azure All-In:      ${t_az_allin:>13,.0f}
  Storage Tier Savings: ${t_stor_save:>10,.0f}/yr potential

BUDGET-GRADE PORTFOLIO TOTALS (IaaS + Network + DR + Support):
  Support Plans:     ${t_support:>13,.0f}/yr (all servers)
  Migration One-Time: ${t_mig_labor:>12,.0f} (labor + testing + training + parallel run + transfer)
  AWS Budget All-In: ${t_aws_budget:>13,.0f}/yr
  Azure Budget All-In: ${t_az_budget:>12,.0f}/yr

UTILIZATION INSIGHTS:
  High CPU (>80%): {', '.join(high_cpu[:8]) if high_cpu else 'None'}
  Low CPU (<20%): {', '.join(low_cpu[:8]) if low_cpu else 'None'}
  High Memory (>80%): {', '.join(high_mem[:8]) if high_mem else 'None'}
  Low Memory (<20%): {', '.join(low_mem[:8]) if low_mem else 'None'}

RIGHT-SIZING OPPORTUNITIES (servers with >30% reduction):
{sizing_list}

PaaS MIGRATION CANDIDATES:
{paas_list}

SERVERLESS COST-SAVING CANDIDATES:
{sl_list}

TOP 5 ON-PREM COST CENTERS:
{top5_spend}

TOP 5 SAVINGS OPPORTUNITIES:
{top5_save}

RISK ITEMS:
  EOL/Extended Support OS:
{eol_list}
  Database Workloads (complex migration):
{db_list}

ENVIRONMENT BREAKDOWN:
  Production: {prod_count} | Staging: {stg_count} | Dev/Test/QA: {dev_count}

ANALYSIS REQUIRED — Produce a STRUCTURED executive decision brief with these EXACT sections. Use real $ figures and server names throughout.

### EXECUTIVE SUMMARY
3-4 sentences with the headline recommendation, total savings opportunity (including all-in costs), and strategic rationale. Name specific dollar amounts.

### PROVIDER COMPARISON & RECOMMENDATION
Compare AWS vs Azure vs Azure Local for THIS portfolio. Which provider offers the best value?
- Cost differential between AWS and Azure (name the $ gap and all-in costs)
- Where Azure Local makes sense (data sovereignty, latency, compliance requirements)
- Multi-cloud vs single-provider strategy
- Specific recommendation with reasoning

### SIZING OPTIMIZATION STRATEGY
For the overall portfolio:
- **Over-provisioned servers**: List the top servers by waste (from right-sizing data above). Quantify total savings.
- **Instance family recommendations**: Are servers in the right families? Which should be compute-optimized vs memory-optimized vs general-purpose?
- **Burstable vs fixed**: Which servers should use burstable (T/B-series) based on their CPU patterns?
- **Dev/Test right-sizing**: {dev_count} non-production servers — aggressive downsizing recommendations with $ impact
- **Total portfolio right-sizing savings**: Sum it up

### PaaS vs IaaS DECISION FRAMEWORK
For each major workload category in this portfolio:
- **Strong PaaS candidates**: Name specific servers and the exact PaaS service (App Service, RDS, Azure SQL MI, etc.)
- **IaaS-only workloads**: Which servers must stay on VMs and why?
- **Hybrid approach**: Servers where DB goes to managed service but app stays on VM
- **Serverless opportunities**: Candidates for Lambda/Functions (name them and show cost comparison)
- **Total PaaS savings vs IaaS**: Portfolio-level comparison

### COST OPTIMIZATION ROADMAP
Quantify these optimization levers with specific $ and server names:
1. Right-sizing savings
2. Reserved instance commitment strategy
3. Dev/Test environment optimization ({dev_count} servers — scheduling, spot/preemptible)
4. PaaS migration candidates
5. License optimization (Windows to Linux where feasible)
6. Storage tier optimization (${t_stor_save:,.0f}/yr potential)

### GAPS & MISSING CONSIDERATIONS
Proactively identify what might be MISSING from this migration plan:
- **Licensing**: Application licenses not captured (Oracle, SQL Server CALs, SAP, middleware)? BYOL savings?
- **Network architecture**: VPC/VNet design, peering, Direct Connect/ExpressRoute, inter-server latency
- **Security & compliance**: WAF, DDoS, encryption at rest/transit, compliance certifications, identity federation
- **Operational readiness**: Cloud skills gap, runbook migration, monitoring/alerting (CloudWatch/Monitor), CI/CD pipeline changes
- **Hidden costs**: Support plans ($$ for Enterprise), data transfer between regions/AZs, premium support, third-party tools
- **Governance**: Tagging strategy, cost allocation, budget alerts, FinOps tooling
- **Testing**: Performance benchmarking, load testing, DR testing schedule
- **Change management**: Team training, documentation, organizational readiness

### MIGRATION WAVE PLAN
Recommend a phased migration sequence:
- Wave 1 (Quick Wins, Month 1-2): Which servers first and why
- Wave 2 (Core Migration, Month 3-6): Main workload moves
- Wave 3 (Complex/Database, Month 6-12): Database and stateful workloads
- Wave 4 (Optimization, Month 12-18): PaaS refactoring, serverless, further right-sizing
Include the specific server types and environments per wave.

### RISK REGISTER
For each risk, state: Description, Impacted Servers, Severity (High/Med/Low), Mitigation
- EOL operating systems requiring immediate attention
- Database migration complexity
- Performance-sensitive workloads (high CPU/IOPS)
- Licensing compliance during transition
- Operational knowledge gaps

### BUDGET-GRADE FINANCIAL PROJECTION
Use the CALCULATED budget data (not estimates):
- Year 0 Migration Investment: ${t_mig_labor:,.0f} (labor + testing + training + parallel run + transfer)
- Annual Cloud Run Rate: AWS ${t_aws_budget:,.0f}/yr | Azure ${t_az_budget:,.0f}/yr (IaaS + Network + DR + Support)
- Support Plans: ${t_support:,.0f}/yr across all servers
- Present P10/P50/P90 confidence range for the recommended option
- 3-year total: Cloud vs On-Prem cumulative (cloud -5%/yr deflation, on-prem +3-5%/yr inflation)
- Recommended annual budget (P50 + 10% contingency)
- Break-even timeline

### TOP 5 IMMEDIATE ACTIONS
Numbered, specific, actionable items with expected $ impact each. Include which team (Infra, DBA, Finance, Procurement) owns each action.

Be specific, use server names and real $ figures, and make clear recommendations. Never say "it depends" — commit to a recommendation. Avoid generic advice."""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=5000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except ImportError:
        return "Install anthropic SDK: `pip install anthropic`"
    except Exception as e:
        return f"Portfolio AI unavailable: {str(e)}"
