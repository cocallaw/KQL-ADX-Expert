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

The tool uses **interactive browser login** via `azure-identity.InteractiveBrowserCredential`. The first time you run a command a browser window will open for you to authenticate with your Entra ID credentials.

### Persistent token caching

Tokens can be cached persistently across process invocations using MSAL's token-cache feature (`TokenCachePersistenceOptions`). When persistent caching is active the cache is stored under the name **`kql-adx-expert`** in the platform's secure storage:

| Platform | Storage location |
|---|---|
| Windows | Windows Credential Manager |
| macOS | Keychain |
| Linux (with keyring daemon) | Secret Service / keyring |
| Linux (no keyring) | No persistent cache by default (see below) |

As long as the cached access or refresh token has not expired, subsequent `query` and `spider` invocations against the same tenant will reuse it without opening a browser. If the token expires or is revoked, the tool will automatically prompt for re-authentication.

#### Required dependency: `azure-identity[cache]`

Persistent caching relies on the **`msal-extensions`** package, which is pulled in by installing the `[cache]` extra of `azure-identity`. The project's `requirements.txt` already includes this extra:

```
azure-identity[cache]>=1.15.0
```

If you installed plain `azure-identity` (without the `[cache]` extra), `msal-extensions` will be missing. In that case the tool **silently disables persistence** — it will not crash, but every invocation will open a browser prompt for authentication. To fix this, install the extra:

```bash
pip install "azure-identity[cache]>=1.15.0"
```

> **Troubleshooting — prompted to log in every time?** Verify that `msal-extensions` is installed (`pip show msal-extensions`). If it is missing, install the cache extra as shown above. On Linux, also confirm that a keyring daemon (e.g., `gnome-keyring`, `kwallet`) is running, or use `--allow-unencrypted-cache`.

### Linux without a keyring daemon

On headless Linux systems that have no secure keyring available, persistent caching is disabled by default to protect token security. You can opt in to an unencrypted local file cache by adding the `--allow-unencrypted-cache` flag:

```bash
python adx_tool.py query \
  --cluster https://mycluster.region.kusto.windows.net \
  --database MyDB \
  --query "StormEvents | take 10" \
  --allow-unencrypted-cache
```

> **Security note:** When `--allow-unencrypted-cache` is used the token cache is stored as a plaintext file on disk. Use this option only in trusted, single-user environments.

## CLI Reference

```text
adx_tool.py query --cluster URL --database DB (--query KQL | --file PATH) [--allow-unencrypted-cache]
adx_tool.py spider --cluster URL [--output PATH] [--allow-unencrypted-cache]
```

| Argument    | Description                                                          |
|-------------|----------------------------------------------------------------------|
| `--cluster` | ADX cluster URI (e.g., `https://mycluster.region.kusto.windows.net`) |
| `--database`| Database name (query subcommand only)                                |
| `--query`   | Inline KQL query string                                              |
| `--file`    | Path to a `.kql` file                                                |
| `--output`  | Spider output file path (default: `cluster_schema.json`)             |
| `--allow-unencrypted-cache` | Allow token cache to fall back to an unencrypted file on systems without a secure keyring (off by default) |

## How the Skill Uses This Tool

The `SKILL.md` file instructs the Copilot CLI skill to:

1. **Spider first** — When a user provides a cluster URI and no schema exists, suggest running the spider to discover databases, tables, and column types.
2. **Read schema before building queries** — If `cluster_schema.json` exists, read it to use correct table/column names and data types.
3. **Execute queries on demand** — When the user asks to run a query, invoke the query subcommand and return the formatted results.
4. **Refresh schema on errors** — If a user encounters column/table-not-found errors, re-run the spider to get an updated schema.
