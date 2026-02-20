"""
AI Recommendation Engine — Stateless
======================================
Uses Claude API for deep, decision-grade migration analysis.
NO data is stored, cached, or persisted. Each call is independent.

Two functions:
  1. get_ai_recommendation() — Single server deep-dive
  2. get_batch_ai_summary() — Portfolio executive brief with decision matrix
"""

import json
from typing import Dict, List, Optional


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

        prompt = f"""You are a senior cloud architect and financial analyst preparing a migration decision brief for an enterprise Architecture Review Board (ARB). Produce a thorough, data-driven analysis.

SERVER PROFILE:
  Host: {inputs.get('host_name','N/A')}
  Platform: {inputs.get('platform','N/A')} / OS: {inputs.get('operating_system','N/A')}
  Environment: {inputs.get('environment','N/A')} | Type: {inputs.get('server_type','N/A')}
  OS EOL Status: {inputs.get('os_eol_status','N/A')}
  Proposed Migration: {inputs.get('migration_type','N/A')}
  Databases/Caches: {inputs.get('databases_caches','None')}
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

CROSS-PROVIDER COST COMPARISON (Annual, 3yr Reserved):
  AWS:         ${aws_ann:>12,.2f}/yr  Instance: {xp.get('AWS',{}).get('instance_type','N/A')} ({xp.get('AWS',{}).get('vcpu',0)} vCPU / {xp.get('AWS',{}).get('memory',0)} GB)
  Azure:       ${az_ann:>12,.2f}/yr  Instance: {xp.get('Azure',{}).get('instance_type','N/A')} ({xp.get('Azure',{}).get('vcpu',0)} vCPU / {xp.get('Azure',{}).get('memory',0)} GB)
  Azure Local: ${azl.get('recommended_annual',0):>12,.2f}/yr  Scenario: {azl.get('recommended_label','N/A')}
    Linux: ${azl.get('linux_total_annual',0):,.2f}  |  Windows: ${azl.get('windows_total_annual',0):,.2f}  |  AHB: ${azl.get('ahb_total_annual',0):,.2f}
  On-Premises: ${outputs.get('on_prem_yearly_cost',0):>12,.2f}/yr
    Hardware: ${bk.get('hw_total',0):,.2f} | Power: ${bk.get('power_cooling',0):,.2f} | Facility: ${bk.get('facility',0):,.2f} | Labor: ${bk.get('admin_labor',0):,.2f} | License: ${bk.get('annual_licensing',0):,.2f}

PaaS OPTION:
  Service: {outputs.get('paas_service_name','N/A')} ({outputs.get('paas_instance_type','N/A')})
  PaaS On-Demand: ${outputs.get('paas_on_demand',0):,.2f}/mo | PaaS 3yr: ${outputs.get('paas_reserved_3yr',0):,.2f}/mo

ANALYSIS REQUIRED — Produce a STRUCTURED decision brief with these exact sections. Use real $ amounts and % throughout. Be specific to THIS server's data.

### EXECUTIVE RECOMMENDATION
State the recommended path (AWS/Azure/Azure Local/On-Prem/PaaS) with the strongest financial and technical justification. Name the specific instance and annual cost. 2-3 sentences.

### COST DECISION MATRIX
Create a comparison showing each option's annual cost, savings vs on-prem, and a 1-line verdict:
- AWS IaaS (3yr RI)
- Azure IaaS (3yr RI)
- Azure Local (recommended scenario)
- PaaS
- Stay On-Prem

### RIGHT-SIZING ANALYSIS
Comment on the CPU/memory utilization patterns. Is this server over-provisioned? What does the {inputs.get('avg_cpu_usage',0)}% CPU / {inputs.get('avg_memory_usage',0)}% memory suggest about workload patterns? Quantify savings from right-sizing.

### MIGRATION STRATEGY
- Recommended migration approach for this specific workload type ({inputs.get('server_type','N/A')})
- If databases are involved ({inputs.get('databases_caches','None')}), address data migration complexity
- Downtime requirements and rollback plan considerations
- Dependencies and sequencing

### RISK ASSESSMENT
- Technical risks specific to this migration (OS compatibility, EOL status: {inputs.get('os_eol_status','N/A')})
- Performance risks (IOPS: {inputs.get('avg_disk_iops',0)}, network: {inputs.get('avg_network_throughput',0)} Mbps)
- Compliance / licensing risks
- Operational risks during transition

### 3-YEAR TCO PROJECTION
Project 3-year total cost for the recommended option vs on-prem. Include migration one-time costs estimate (typically 15-20% of Year 1 savings for planning, testing, cutover).

Be concrete, use actual $ figures from the data, and make clear recommendations."""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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
        t_paas = sum(r["outputs"].get("paas_on_demand", 0) * 12 for r in all_results)

        # Per-cloud breakdown
        clouds, oses, fams, envs, stype, dbs = {}, {}, {}, {}, {}, {}
        eols = {}
        high_cpu, low_cpu, high_mem, low_mem = [], [], [], []
        top_spenders, top_savers = [], []

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
            if db != "None":
                dbs[host] = db

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

        top_spenders.sort(key=lambda x: -x[1])
        top_savers.sort(key=lambda x: -x[1])

        top5_spend = "\n".join([f"  {i+1}. {h}: ${c:,.0f}/yr on-prem"
                                for i, (h, c) in enumerate(top_spenders[:5])])
        top5_save = "\n".join([f"  {i+1}. {h}: save ${s:,.0f}/yr (${op:,.0f} to ${b:,.0f} on {p})"
                               for i, (h, s, op, b, p) in enumerate(top_savers[:5])])
        eol_list = "\n".join([f"  - {h}: {e}" for h, e in eols.items()]) if eols else "  None"
        db_list = "\n".join([f"  - {h}: {d}" for h, d in dbs.items()]) if dbs else "  None"

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
  PaaS (On-Demand):  ${t_paas:>13,.0f}  (savings: ${t_op-t_paas:>10,.0f}, {((t_op-t_paas)/max(1,t_op)*100):.1f}%)

UTILIZATION INSIGHTS:
  High CPU (>80%): {', '.join(high_cpu[:8]) if high_cpu else 'None'}
  Low CPU (<20%): {', '.join(low_cpu[:8]) if low_cpu else 'None'}
  High Memory (>80%): {', '.join(high_mem[:8]) if high_mem else 'None'}
  Low Memory (<20%): {', '.join(low_mem[:8]) if low_mem else 'None'}

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
3-4 sentences with the headline recommendation, total savings opportunity, and strategic rationale. Name specific dollar amounts.

### PROVIDER COMPARISON & RECOMMENDATION
Compare AWS vs Azure vs Azure Local for THIS portfolio. Which provider offers the best value? Consider:
- Cost differential between AWS and Azure (name the $ gap)
- Where Azure Local makes sense (data sovereignty, latency, compliance requirements)
- Whether a multi-cloud or single-provider strategy is optimal
- Specific recommendation with reasoning

### COST OPTIMIZATION ROADMAP
Quantify these optimization levers with specific $ and server names:
1. Right-sizing savings (identify the most over-provisioned servers by name)
2. Reserved instance commitment strategy
3. Dev/Test environment optimization ({dev_count} servers — scheduling, spot/preemptible)
4. PaaS migration candidates (which workloads benefit most)
5. License optimization (Windows to Linux where feasible)

### MIGRATION WAVE PLAN
Recommend a phased migration sequence:
- Wave 1 (Quick Wins, Month 1-2): Which servers first and why
- Wave 2 (Core Migration, Month 3-6): Main workload moves
- Wave 3 (Complex/Database, Month 6-12): Database and stateful workloads
- Wave 4 (Optimization, Month 12-18): PaaS refactoring, further right-sizing
Include the specific server types and environments per wave.

### RISK REGISTER
For each risk, state: Description, Impacted Servers, Severity (High/Med/Low), Mitigation
- EOL operating systems requiring immediate attention
- Database migration complexity
- Performance-sensitive workloads (high CPU/IOPS)
- Licensing compliance during transition
- Operational knowledge gaps

### 3-YEAR FINANCIAL PROJECTION
Project Year 1 / Year 2 / Year 3 costs for the recommended approach:
- Include one-time migration costs (estimate 15-20% of Year 1 savings)
- Show cumulative savings vs staying on-prem
- Break-even timeline
- Total 3-year savings

### TOP 5 IMMEDIATE ACTIONS
Numbered, specific, actionable items with expected $ impact each. Include which team (Infra, DBA, Finance, Procurement) owns each action.

Be specific, use server names and real $ figures, and make clear recommendations. Avoid generic advice."""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except ImportError:
        return "Install anthropic SDK: `pip install anthropic`"
    except Exception as e:
        return f"Portfolio AI unavailable: {str(e)}"
