"""
AI Recommendation Engine — Stateless
======================================
Uses Claude API for intelligent migration recommendations.
NO data is stored, cached, or persisted. Each call is independent.
"""

import json
from typing import Dict, Optional


def get_ai_recommendation(inputs: Dict, outputs: Dict, api_key: str) -> Optional[str]:
    """Stateless: Generate per-server recommendation. Nothing is stored."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""You are a cloud migration expert. Analyze this server and provide concise recommendations.

## Server
- Host: {inputs.get('host_name','N/A')} | Platform: {inputs.get('platform','N/A')} / {inputs.get('operating_system','N/A')}
- Environment: {inputs.get('environment','N/A')} | Type: {inputs.get('server_type','N/A')} | EOL: {inputs.get('os_eol_status','N/A')}
- Migration: {inputs.get('migration_type','N/A')} | DBs: {inputs.get('databases_caches','None')}

## Resources
- vCPU: {inputs.get('vcpu_count',0)} @ {inputs.get('avg_cpu_usage',0)}% | Memory: {inputs.get('memory_gb',0)}GB @ {inputs.get('avg_memory_usage',0)}%
- Storage: {inputs.get('total_storage_gb',0)}GB @ {inputs.get('storage_usage_pct',0)}% | IOPS: {inputs.get('avg_disk_iops',0)}

## Calculated
- Target: {inputs.get('cloud_provider','AWS')} ({inputs.get('cloud_region','N/A')})
- Right-sized: {outputs.get('right_sizing_cpu','N/A')} vCPU / {outputs.get('right_sizing_memory','N/A')}GB
- Instance: {outputs.get('recomm_instance_type','N/A')} | IaaS 3yr: ${outputs.get('iaas_rec_reserved_3yr',0)}/mo
- PaaS: {outputs.get('paas_service_name','N/A')} @ ${outputs.get('paas_on_demand',0)}/mo
- On-Prem: ${outputs.get('on_prem_yearly_cost',0)}/yr

In 150 words: 1) Migration Strategy 2) Cost Optimization 3) Risks 4) IaaS vs PaaS recommendation. Be specific."""

        msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=500,
                                     messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    except ImportError:
        return "⚠️ Install anthropic SDK: `pip install anthropic`"
    except Exception as e:
        return f"⚠️ AI unavailable: {str(e)}"


def get_batch_ai_summary(all_results: list, api_key: str) -> Optional[str]:
    """Stateless: Generate portfolio summary. Nothing is stored."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        n = len(all_results)
        t_op = sum(r["outputs"].get("on_prem_yearly_cost", 0) for r in all_results)
        t_iaas = sum(r["outputs"].get("iaas_rec_on_demand", 0) * 12 for r in all_results)
        t_3yr = sum(r["outputs"].get("iaas_rec_reserved_3yr", 0) * 12 for r in all_results)
        t_paas = sum(r["outputs"].get("paas_on_demand", 0) * 12 for r in all_results)
        clouds, oses, fams = {}, {}, {}
        for r in all_results:
            c = r["outputs"].get("_cloud_provider", "?")
            clouds[c] = clouds.get(c, 0) + 1
            o = r["inputs"].get("operating_system", "?")
            oses[o] = oses.get(o, 0) + 1
            f = r["outputs"].get("_instance_family", "?")
            fams[f] = fams.get(f, 0) + 1

        prompt = f"""Cloud migration portfolio analyst. Concise executive summary.

Servers: {n} | Clouds: {json.dumps(clouds)} | OS: {json.dumps(oses)} | Families: {json.dumps(fams)}
Annual — On-Prem: ${t_op:,.0f} | IaaS OD: ${t_iaas:,.0f} | IaaS 3yr: ${t_3yr:,.0f} | PaaS: ${t_paas:,.0f}

In 200 words: 1) Executive Summary 2) Cost Analysis with savings % 3) Top 3 prioritized actions. Use specific $."""

        msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=600,
                                     messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ Portfolio AI unavailable: {str(e)}"
