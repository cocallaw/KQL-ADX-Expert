# KQL-ADX Expert — Python ADX Tool

A Python CLI tool for running KQL queries and exploring Azure Data Explorer (ADX) cluster schemas. This tool is part of the **kql-adx-expert** Copilot CLI skill and is designed to be invoked by the skill to provide live cluster interaction.

## Project Structure

```text
kql-adx-expert/
├── SKILL.md              # Skill definition — KQL/ADX expert prompt and instructions
├── adx_tool.py           # Python CLI tool (query runner + cluster spider)
├── requirements.txt      # Python dependencies
├── README.md             # This file — setup and usage docs
└── references/
    ├── operators.md      # Full KQL operator, function, and ADX concept reference
    └── patterns.md       # Annotated real-world query examples and patterns
```

## Prerequisites

- Python 3.9+
- Access to an Azure Data Explorer cluster with Entra ID (Azure AD) authentication

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Run a KQL Query

Execute a query and display results as a formatted table:

```bash
python adx_tool.py query \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDB \
  --query "StormEvents | take 10"
```

Run a query from a `.kql` file:

```bash
python adx_tool.py query \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDB \
  --file my_query.kql
```

### Spider a Cluster

Discover all databases, tables, and column schemas in a cluster:

```bash
python adx_tool.py spider \
  --cluster https://mycluster.region.kusto.windows.net \
  --output cluster_schema.json
```

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

## Authentication

The tool uses **interactive browser login** via `azure-identity.InteractiveBrowserCredential`. When you run a command, a browser window will open for you to authenticate with your Entra ID credentials. Tokens are cached for subsequent requests within the same session.

## CLI Reference

```text
adx_tool.py query --cluster URL --database DB (--query KQL | --file PATH)
adx_tool.py spider --cluster URL [--output PATH]
```

| Argument    | Description                                                          |
|-------------|----------------------------------------------------------------------|
| `--cluster` | ADX cluster URI (e.g., `https://mycluster.region.kusto.windows.net`) |
| `--database`| Database name (query subcommand only)                                |
| `--query`   | Inline KQL query string                                              |
| `--file`    | Path to a `.kql` file                                                |
| `--output`  | Spider output file path (default: `cluster_schema.json`)             |

## How the Skill Uses This Tool

The `SKILL.md` file instructs the Copilot CLI skill to:

1. **Spider first** — When a user provides a cluster URI and no schema exists, suggest running the spider to discover databases, tables, and column types.
2. **Read schema before building queries** — If `cluster_schema.json` exists, read it to use correct table/column names and data types.
3. **Execute queries on demand** — When the user asks to run a query, invoke the query subcommand and return the formatted results.
4. **Refresh schema on errors** — If a user encounters column/table-not-found errors, re-run the spider to get an updated schema.
