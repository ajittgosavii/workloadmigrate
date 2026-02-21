# 💎 Infosys Cobalt — Migration Analyzer

Enterprise Streamlit application for cloud migration planning with **zero data persistence**, **real-time pricing**, **dynamic computation**, and **AI recommendations**.

---

## 🔒 Compliance Architecture

```
┌─────────────────────── BROWSER ONLY ───────────────────────┐
│  Session state (RAM only) ← Discarded on close/refresh     │
│  Export generates fresh Excel/CSV ← Never saved on server   │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Streamlit  │  ← Stateless compute
                    │  App Server │  ← No database, no cache
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        Azure Retail   AWS Pricing   Claude AI
        Prices API     Reference     API (opt.)
        (live)         (fallback)    (stateless)
```

**Key compliance guarantees:**
- ✅ **Zero server-side storage** — no files, databases, or caches
- ✅ **In-memory computation** — inputs processed, outputs generated, nothing retained
- ✅ **No PII persistence** — hostnames/IPs exist only in browser session
- ✅ **Session cleared on close** — browser memory released automatically
- ✅ **Manual clear** — "Clear Session Now" button in sidebar
- ✅ **Export = fresh generation** — Excel/CSV created on-the-fly in RAM, streamed to browser

---

## ✨ Features

### Dynamic Computation (Zero Static Data)
Every output is calculated at runtime from user inputs:
- **Right-sizing**: CPU, memory, storage from actual utilization metrics
- **Instance matching**: Workload family detection → best-fit instance selection
- **Pricing**: Live Azure API → AWS regional catalog fallback → dynamic computation
- **TCO**: On-premises vs cloud comparison with OS licensing
- **PaaS alternatives**: Service mapping from database type

### Export Formats
| Format | Contents |
|--------|----------|
| **Excel (.xlsx)** | 4 sheets: Input Data, Output (Dynamic), Cost Summary, Compliance Notice |
| **CSV** | Flat file with all INPUT: and OUTPUT: columns |

### Real-Time Pricing
- **Azure**: Live via `prices.azure.com/api/retail/prices` (VM + Storage)
- **AWS**: Reference catalog with 12-region multipliers
- Pricing source badge shown: `● LIVE API PRICING` or `● REFERENCE PRICING`

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Docker
```bash
docker build -t cloud-migration . && docker run -p 8501:8501 cloud-migration
```

---

## 📁 Files
```
├── app.py                        # Main UI — zero storage, dynamic exports
├── pricing_engine.py             # Stateless pricing — live APIs + fallback
├── recommendation_engine.py      # Stateless Claude AI integration
├── requirements.txt
├── Dockerfile
├── .gitignore                    # Prevents secrets.toml from being committed
└── .streamlit/
    ├── config.toml               # Theme
    └── secrets.toml.example      # Template — copy to secrets.toml with your key
```

---

## 🔑 API Key Configuration (secrets.toml)

The app reads the Anthropic API key in this priority order:
1. **`secrets.toml`** (Streamlit Cloud recommended)
2. **Environment variable** `ANTHROPIC_API_KEY`
3. **Manual UI input** (sidebar fallback)

### Streamlit Cloud Deployment
1. Push repo to GitHub (secrets.toml is gitignored)
2. Connect at [share.streamlit.io](https://share.streamlit.io)
3. Go to **App Settings → Secrets**
4. Paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-xxxxx-your-actual-key"
   ```

### Local Development
```bash
# Copy the template
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit with your key
nano .streamlit/secrets.toml
```

### Docker / ECS / Azure Container Apps
```bash
docker run -p 8501:8501 \
  -e ANTHROPIC_API_KEY="sk-ant-xxxxx" \
  cloud-migration-tool
```

> **Security**: `secrets.toml` is gitignored and never committed. On Streamlit Cloud, secrets are encrypted at rest and injected at runtime. The key is never logged, displayed, or stored by the application.

---

## 📊 Input → Output Mapping

### Inputs (22 parameters)
Cloud Provider, Cloud Region, Host Name, IP Address, Platform, Operating System, Environment, Server Type, OS EOL Status, Migration Type, Databases/Caches, AppServices, InstanceUsage, VCPUCount, AvgCPUUsage (%), Memory(GB), Avg Memory (%), Total Storage(GB), Storage Usage (%), Avg Network Throughput, Total Network Throughput, Avg Disk IOPS

### Outputs (30 fields — all dynamically computed)
Right-Sized CPU/Memory/Storage, IaaS On-Demand/1yr/3yr RI prices, Licensing, Recommended Instance Type/vCPU/Memory, Storage Type/Price, PaaS Service/Instance/Pricing, On-Prem Yearly Cost, Target OS

### Computation Rules
| Output | Formula |
|--------|---------|
| Right-sized CPU | `actual_used × 1.3 headroom → nearest standard size` |
| Right-sized Memory | `actual_used × 1.3 headroom → nearest standard size` |
| Right-sized Storage | `actual_used × 1.4 headroom → min 20 GB` |
| Workload family | `DB presence → database; mem/cpu > 6 → memory; cpu > 70% → compute; else general` |
| Reserved 1yr | `on_demand × 0.60` |
| Reserved 3yr | `on_demand × 0.40` |
| On-prem TCO | `(hardware × 1.45 overhead) + OS licensing × 12` |

*Built for enterprise compliance • Zero data persistence • Dynamic computation*
