# KQL-ADX-Expert

**A GitHub Copilot skill for writing, optimizing, and debugging Kusto Query Language (KQL) queries for Azure Data Explorer and Azure Monitor.**

---

## 📖 Summary

**KQL-ADX-Expert** is a [GitHub Copilot CLI](https://docs.github.com/en/copilot) skill that provides expert-level guidance for Kusto Query Language (KQL) across Azure Data Explorer (ADX), Azure Monitor Log Analytics, Microsoft Sentinel, and Microsoft Defender.

It includes a **Python CLI tool** for live cluster interaction — run queries and spider cluster schemas directly from your terminal — and bundles comprehensive reference material for operators, functions, and real-world query patterns.

**Who is this for?** Developers, SREs, security analysts, and data engineers who work with Azure data platforms and want fast, accurate KQL assistance inside Copilot CLI.

---

## 🚀 Features

- **Expert KQL query authoring & optimization guidance** — get idiomatic, performant queries on the first try
- **Live query execution** against Azure Data Explorer clusters via the Python CLI tool
- **Cluster schema discovery (spider)** — explore databases, tables, and columns with JSON output
- **Schema-aware query building** — the skill reads discovered schema to use correct table and column names
- **Comprehensive operator, function & pattern reference** — bundled markdown docs for offline use
- **Performance optimization rules** — filter-first strategies, join hints, materialized views, and more
- **Common Azure Monitor table patterns** — Heartbeat, Perf, SecurityEvent, Syslog, AzureDiagnostics, and others
- **Error diagnosis & debugging guidance** — troubleshoot failing or slow queries
- **Anomaly detection & time-series analysis patterns** — `make-series`, `series_decompose_anomalies`, and seasonal analysis

---

## 📦 Installation

### 1. Adding the skill to Copilot CLI

Clone or copy the `kql-adx-expert/` directory into your Copilot CLI skills directory:

```bash
git clone https://github.com/coreycallaway/KQL-ADX-Expert.git
```

The skill auto-activates when you use relevant keywords such as *KQL*, *Kusto query*, *Azure Data Explorer*, *ADX*, *Log Analytics query*, *run query*, *spider cluster*, and more.

### 2. Python tool setup (optional)

> Only required if you want **live query execution** or **cluster schema discovery**.

```bash
pip install -r kql-adx-expert/requirements.txt
```

| Requirement | Details |
|---|---|
| **Python** | 3.9+ |
| **Authentication** | Interactive browser login via Entra ID (Azure AD) |
| **Access** | Entra ID credentials with permissions to the target ADX cluster |

Key dependencies: `azure-kusto-data >= 4.0.0`, `azure-identity >= 1.15.0`, `tabulate >= 0.9.0`

---

## 💡 Usage

The typical workflow has four steps:

1. **Ask a KQL question** — the skill activates automatically on relevant keywords.
2. **Spider the cluster** — discover databases, tables, and columns so the skill can write schema-aware queries.
3. **Build queries** — the skill uses the discovered schema to produce accurate KQL.
4. **Execute queries** — run queries against the cluster and view results in your terminal.

### Quick examples

```text
> Write a KQL query to find VMs with high CPU in the last hour
```

```text
> Spider my ADX cluster at https://mycluster.eastus.kusto.windows.net
```

```text
> Run this query against my cluster: StormEvents | summarize count() by State | top 10 by count_
```

For detailed tool usage (flags, output formats, authentication), see the **[tool documentation](kql-adx-expert/README.md)**.

---

## 💬 Example Prompts

Try these in Copilot CLI to see the skill in action:

| Prompt | What it does |
|---|---|
| *"Write a KQL query to find VMs with CPU usage above 90% in the last hour"* | Generates an optimized Perf-table query |
| *"Connect to my ADX cluster at `https://mycluster.region.kusto.windows.net` and explore the schema"* | Spiders the cluster and returns schema JSON |
| *"Optimize this KQL query for better performance: [paste query]"* | Applies filter-first, projection, and join-hint rules |
| *"Show me how to detect missing heartbeats from my VMs"* | Builds a Heartbeat gap-detection query |
| *"Write a query to parse JSON from AzureDiagnostics logs"* | Uses `parse_json` / `mv-expand` patterns |
| *"Find failed login attempts in SecurityEvent and group by account"* | Filters EventID 4625 and summarizes by Account |
| *"What's the difference between `has` and `contains` in KQL?"* | Explains semantics and performance trade-offs |
| *"Run this query against my cluster: StormEvents \| summarize count() by State \| top 10 by count_"* | Executes the query live and returns results |
| *"Help me build a time-series anomaly detection query"* | Walks through `make-series` and `series_decompose_anomalies` |

---

## 🗂️ Skill Contents

```text
kql-adx-expert/
├── SKILL.md              # Skill definition — triggers, instructions, and KQL reference
├── adx_tool.py           # Python CLI tool — query runner and cluster spider
├── requirements.txt      # Python dependencies
├── README.md             # Detailed tool documentation and setup
└── references/
    ├── operators.md      # Full KQL operator, function, and ADX concept reference
    └── patterns.md       # 10+ annotated real-world query examples
```

---

## 📚 Documentation Sources

### Internal references

- [`kql-adx-expert/references/operators.md`](kql-adx-expert/references/operators.md) — KQL operators, functions, and ADX concepts
- [`kql-adx-expert/references/patterns.md`](kql-adx-expert/references/patterns.md) — Annotated real-world query examples
- [`kql-adx-expert/README.md`](kql-adx-expert/README.md) — Detailed Python tool documentation

### External Microsoft documentation

- [KQL overview (Microsoft Learn)](https://learn.microsoft.com/en-us/kusto/query/)
- [Azure Data Explorer documentation](https://learn.microsoft.com/en-us/azure/data-explorer/)
- [Azure Monitor Logs reference](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/)
- [Microsoft Sentinel documentation](https://learn.microsoft.com/en-us/azure/sentinel/)

---

## Acknowledgments

Thanks to Roeland Nieuwenhuis [ranieuwe](https://github.com/ranieuwe) for the inspiration and early feedback on the skill concept.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

© 2026 Corey Callaway
