# KQL-ADX Expert — Python ADX Tool

A Python CLI tool for running KQL queries and exploring Azure Data Explorer (ADX) cluster schemas. This tool is part of the **kql-adx-expert** Copilot CLI skill and is designed to be invoked by the skill to provide live cluster interaction.

## Project Structure

```text
kql-adx-expert/
├── SKILL.md              # Skill definition — KQL/ADX expert prompt and instructions
├── adx_tool.py           # Python CLI tool (doctor + query runner + cluster spider)
├── requirements.txt      # Python dependencies (public PyPI)
├── requirements-msft.txt # Same dependencies via the Microsoft package feed proxy
├── requirements-dev.txt  # Adds pytest for running the tests
├── README.md             # This file — setup and usage docs
├── tests/                # pytest suite (no network access)
└── references/
    ├── operators.md        # Full KQL operator, function, and ADX concept reference
    ├── patterns.md         # Annotated real-world query examples and patterns
    ├── azure-resources.md  # Azure resource monitoring tables and queries
    └── sentinel.md         # Sentinel hunting, ASIM, and detection patterns
```

## Prerequisites

- Python 3.9+
- Access to an Azure Data Explorer cluster with Entra ID (Azure AD) authentication

## Setup

Install into a virtual environment in this directory, not the system Python:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python adx_tool.py doctor --cluster https://mycluster.region.kusto.windows.net
```

- On Windows the interpreter is `.venv\Scripts\python.exe`.
- If your network requires the Microsoft package feed proxy, install from `requirements-msft.txt` instead.
- If the venv has no pip, run `.venv/bin/python -m ensurepip --upgrade` first.

Always run the tool with the venv's interpreter. `./adx_tool.py` uses the `#!/usr/bin/env python3` shebang, which picks the system Python and will not find the venv's packages.

### Check your setup with `doctor`

`doctor` checks the interpreter, pip, each required package, and, with `--cluster`, whether the cluster's HTTPS endpoint is reachable. It never signs in. Each check prints PASS or FAIL with the exact fix command.

`query` and `spider` run the same dependency and network checks before opening the browser sign-in.

| Exit code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | Setup problem: missing packages or pip, bad arguments, or a failed doctor check |
| 2 | Network: cluster unreachable (VPN, network, private endpoint) |
| 3 | Authentication, permission, query rejected by the cluster, or spider discovery incomplete (partial schema still saved) |

## Usage

### Run a KQL Query

Execute a query and display results as a formatted table:

```bash
.venv/bin/python adx_tool.py query \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDB \
  --query "StormEvents | take 10"
```

Run a query from a `.kql` file:

```bash
.venv/bin/python adx_tool.py query \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDB \
  --file my_query.kql
```

### Spider a Cluster

Discover databases, tables, and column schemas in a cluster. `--database` (repeatable) limits discovery to named databases; without it, every database your account can see is spidered:

```bash
.venv/bin/python adx_tool.py spider \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDatabase \
  --output cluster_schema.json
```

Progress prints one line per database. The summary reports succeeded and failed counts and elapsed time. `cluster_schema.json` is git-ignored: it maps your data estate, so don't commit it.

This saves a JSON file containing the full cluster schema. The skill uses this file to build accurate queries with correct table names, column names, and data types.

### Spider Output Format

```json
{
  "cluster": "https://mycluster.region.kusto.windows.net",
  "timestamp": "2026-03-20T17:54:00Z",
  "databases": [
    {
      "name": "MyDatabase",
      "tables": [
        {
          "name": "MyTable",
          "columns": [
            { "name": "Timestamp", "type": "datetime" },
            { "name": "UserId", "type": "string" },
            { "name": "Value", "type": "real" }
          ]
        }
      ]
    }
  ]
}
```

## Tests

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

## Authentication

The tool uses **interactive browser login** via `azure-identity.InteractiveBrowserCredential`. When you run a command, a browser window will open for you to authenticate with your Entra ID credentials. Tokens are cached for subsequent requests within the same session.

## CLI Reference

```text
adx_tool.py doctor [--cluster URL]
adx_tool.py query --cluster URL --database DB (--query KQL | --file PATH)
adx_tool.py spider --cluster URL [--database DB ...] [--output PATH]
```

| Argument    | Description                                                          |
|-------------|----------------------------------------------------------------------|
| `--cluster` | ADX cluster URI (e.g., `https://mycluster.region.kusto.windows.net`) |
| `--database`| `query`: database to query. `spider`: limit discovery to this database (repeatable) |
| `--query`   | Inline KQL query string                                              |
| `--file`    | Path to a `.kql` file                                                |
| `--output`  | Spider output file path (default: `cluster_schema.json`)             |

## How the Skill Uses This Tool

The `SKILL.md` file instructs the Copilot CLI skill to:

1. **Doctor first** — Run `doctor --cluster <URI>` and stop on any FAIL, before any browser sign-in.
2. **Spider first** — When a user provides a cluster URI and no schema exists, suggest running the spider to discover databases, tables, and column types.
3. **Read schema before building queries** — If `cluster_schema.json` exists, read it to use correct table/column names and data types.
4. **Execute queries on demand** — When the user asks to run a query, invoke the query subcommand and return the formatted results.
5. **Refresh schema on errors** — If a user encounters column/table-not-found errors, re-run the spider to get an updated schema.
