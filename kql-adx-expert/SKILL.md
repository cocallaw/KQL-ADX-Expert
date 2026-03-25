---
name: kql-adx-expert
description: 'KQL and Azure Data Explorer expert. Write, optimize, debug, and run Kusto queries for ADX, Azure Monitor, Log Analytics, Microsoft Sentinel, and Defender. Covers Perf, Heartbeat, SecurityEvent, SigninLogs, AuditLogs, CommonSecurityLog, AzureActivity, AzureDiagnostics, AppServiceHTTPLogs, FunctionAppLogs, StorageBlobLogs, ContainerLogV2, KubePodInventory, AZKVAuditLogs, AzureMetrics, InsightsMetrics, AppRequests, AppExceptions, DeviceProcessEvents, AGWAccessLogs, AZFWNetworkRule, NTANetAnalytics. Sentinel threat hunting, ASIM, MITRE ATT&CK detection rules, watchlists, and TI correlation. Live ADX query execution and cluster schema spider. Triggers on: KQL, Kusto query, ADX, Log Analytics, Azure Monitor, Sentinel hunting, threat hunting, detection rule, ASIM, run query, spider cluster, Azure VM, App Service, SQL Database, AKS, Key Vault, Application Insights, Azure Firewall, NSG flow.'
---

# KQL & Azure Data Explorer Expert

Write, optimize, and debug Kusto Query Language (KQL) queries for Azure Data Explorer, Azure Monitor Log Analytics, Microsoft Sentinel, and Microsoft Defender. This skill covers the full KQL language, ADX-specific concepts, performance optimization, common Azure service query patterns, and Microsoft Sentinel threat hunting and detection.

## How to Build KQL Queries

Follow this process for every query:

0. **Check for cluster schema** — If a `cluster_schema.json` file exists from a prior spider run, read it first. Use it to identify valid table and column names, and apply correct data types. If the user provides a cluster URI and no schema exists, suggest running the spider first: `python adx_tool.py spider --cluster <URI>`
1. **Identify the table** — From the spider schema or known tables:
   - **Azure Monitor**: Heartbeat (VMs), Perf (metrics), Syslog (Linux), AzureDiagnostics (resource logs)
   - **Security**: SecurityEvent (Windows auth/process), SigninLogs (Entra ID sign-ins), AuditLogs (Entra ID changes), CommonSecurityLog (CEF firewalls/proxies)
   - **Cloud**: AzureActivity (ARM operations), OfficeActivity (Office 365)
   - **Defender for Endpoint**: DeviceProcessEvents, DeviceNetworkEvents, DeviceFileEvents, DeviceRegistryEvents
   - **Sentinel-native**: SecurityAlert, SecurityIncident, ThreatIntelligenceIndicator, Watchlist, BehaviorAnalytics, SentinelAudit
   - **ASIM (normalized)**: imAuthentication, imDns, imNetworkSession, imProcessCreate, imFileEvent, imWebSession — use these for cross-source hunting
   - **Azure Resource Monitoring** (resource-specific tables preferred over AzureDiagnostics):
     - App Service → `AppServiceHTTPLogs`, `AppServiceConsoleLogs`, `AppServiceAppLogs`
     - Azure Functions → `FunctionAppLogs`
     - Azure SQL/PostgreSQL/MySQL → `AzureMetrics` (platform metrics) + `AzureDiagnostics` (query store, wait stats, errors)
     - Azure Storage → `StorageBlobLogs`, `StorageQueueLogs`, `StorageTableLogs`, `StorageFileLogs`
     - AKS → `ContainerLogV2`, `KubePodInventory`, `KubeNodeInventory`, `KubeEvents`
     - Key Vault → `AZKVAuditLogs` (resource-specific) or `AzureDiagnostics` (legacy)
     - Application Gateway → `AGWAccessLogs`, `AGWFirewallLogs`
     - Azure Firewall → `AZFWNetworkRule`, `AZFWApplicationRule`
     - NSG Flow Logs → `NTANetAnalytics`
     - Application Insights → `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces`
     - Platform metrics (any resource) → `AzureMetrics` (filter by `ResourceProvider`)
2. **Filter early with `where`** — time range first (`where TimeGenerated > ago(1h)`), then predicates
3. **Project only needed columns** — `project` or `project-away` before joins/aggregations
4. **Aggregate with `summarize`** — use `count()`, `avg()`, `dcount()`, `arg_max()`, etc. with `by` clause
5. **Sort/limit** — `top N by Col desc` or `sort by Col`
6. **Validate with `take 10`** before running expensive aggregations
7. **Execute against live cluster** — If the user wants to run the query, use `python adx_tool.py query --cluster <URI> --database <DB> --query "<KQL>"` to execute and return results

## Core Operator Quick Reference

```
Table | where <filter> | project <cols> | extend <computed> | summarize <agg> by <group> | sort by <col> | top N by <col>
```

| Operator | Purpose |
|----------|---------|
| `where` | Filter rows by predicate |
| `project` | Select/rename/compute columns (drops others) |
| `extend` | Add computed columns (keeps all existing) |
| `summarize` | Group and aggregate (`count`, `avg`, `sum`, `dcount`, `arg_max`, etc.) |
| `join kind=<flavor>` | Combine tables (inner, leftouter, leftanti, leftsemi, fullouter, lookup) |
| `union` | Concatenate rows from multiple tables |
| `mv-expand` | Expand dynamic arrays into rows |
| `parse_json()` / `todynamic()` | Parse JSON string to dynamic type |
| `bin(col, interval)` | Floor values into time/numeric buckets |
| `render timechart` | Visualize as time-series chart |
| `let` | Bind names to expressions for reuse |
| `materialize()` | Cache subquery result used multiple times |

## Performance Rules (Always Follow)

1. **Filter before join/summarize** — `where` first, always
2. **Time filter on both join sides** — reduces scan on each table
3. **Smaller table on the right** side of join
4. **Use `has` over `contains`** — `has` uses the term index, `contains` does not
5. **Use `hint.shufflekey`** for large joins on high-cardinality keys
6. **Use `lookup`** instead of `join kind=leftouter` for simple enrichment
7. **Avoid `distinct`; prefer `summarize by`** for large datasets
8. **Use `materialize()`** when a subexpression is referenced multiple times

## Canonical Examples

### Time-Series Aggregation with Chart

```kql
Perf
| where TimeGenerated > ago(24h)
| where ObjectName == "Processor" and CounterName == "% Processor Time"
| summarize AvgCPU = avg(CounterValue) by Computer, bin(TimeGenerated, 15m)
| render timechart
```

### Join with Lookup Table for Enrichment

```kql
let VMInfo = Heartbeat | summarize arg_max(TimeGenerated, OSType, ComputerEnvironment) by Computer;
Syslog
| where TimeGenerated > ago(1h)
| where SeverityLevel in ("err", "crit")
| summarize ErrorCount = count() by Computer
| join kind=leftouter (VMInfo) on Computer
| project Computer, ErrorCount, OSType, ComputerEnvironment
```

### Detecting Missing Heartbeats (Gap Detection)

```kql
Heartbeat
| summarize LastHeartbeat = max(TimeGenerated) by Computer
| extend MinutesSinceLast = datetime_diff("minute", now(), LastHeartbeat)
| where MinutesSinceLast > 15
| sort by MinutesSinceLast desc
```

### Parsing JSON and Aggregating

```kql
AzureDiagnostics
| where Category == "FunctionAppLogs"
| extend parsed = parse_json(message_s)
| extend FunctionName = tostring(parsed.functionName), DurationMs = todouble(parsed.durationMs)
| summarize AvgDuration = avg(DurationMs), Calls = count() by FunctionName
| sort by Calls desc
```

## Common Error Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `Column 'X' not found` | Typo or wrong table | Check with `T \| getschema` or `T \| take 1` |
| `Incompatible types` | Type mismatch | Cast: `tostring()`, `toint()`, `todatetime()` |
| `Ambiguous column reference` | Same name in both join sides | Use `$left.Col` / `$right.Col` |
| `Partial query failure` | Result set too large (>500K rows / 64MB) | Add more `where` filters or `summarize` |

## When to Use Materialized Views vs On-Demand

| Scenario | Recommendation |
|----------|---------------|
| Dashboard refreshing every 5 min | **Materialized view** |
| Ad-hoc exploration | **On-demand query** |
| Aggregation over billions of rows | **Materialized view** |
| Dynamic multi-table analysis | **On-demand** with `materialize()` |

## Azure Resource Monitoring & Troubleshooting

When the user asks about monitoring, troubleshooting, or analyzing Azure resource performance and health, follow this process:

### Resource Monitoring Workflow

1. **Identify the Azure service** — What resource type? (VM, App Service, SQL DB, Storage, AKS, Key Vault, etc.)
2. **Choose the right table** — Prefer resource-specific tables over AzureDiagnostics:
   - For **platform metrics** (CPU, DTU, throughput) → `AzureMetrics` with `ResourceProvider` filter
   - For **resource logs** → Use the resource-specific table (see table routing above)
   - For **control-plane operations** (who created/deleted/modified a resource) → `AzureActivity`
   - For **application telemetry** → `AppRequests`, `AppDependencies`, `AppExceptions` (Application Insights)
3. **Use `_ResourceId`** — Filter by ARM resource ID for scoped queries; use `parse _ResourceId` to extract resource names
4. **Apply the right pattern**:
   - **Health check**: Threshold-based (`summarize | where value > threshold`)
   - **Trend analysis**: `bin(TimeGenerated, interval)` + `render timechart`
   - **Top-N analysis**: `top 10 by value desc` or `summarize | sort by`
   - **Error investigation**: Filter by status codes, error levels, or failure categories
   - **Anomaly detection**: `make-series` + `series_decompose_anomalies`

### Key Resource Monitoring Patterns

#### VM CPU Percentiles

```kql
Perf
| where ObjectName == "Processor" and CounterName == "% Processor Time"
    and InstanceName == "_Total"
| summarize P50 = percentile(CounterValue, 50), P90 = percentile(CounterValue, 90)
    by bin(TimeGenerated, 1h)
| render timechart
```

#### App Service Health (Success Rate)

```kql
AppServiceHTTPLogs
| summarize (count() - countif(ScStatus >= 500)) * 100.0 / count()
    by bin(TimeGenerated, 5m), _ResourceId
| render timechart
```

#### SQL Database CPU + Deadlocks

```kql
AzureMetrics
| where ResourceProvider == "MICROSOFT.SQL"
| where TimeGenerated >= ago(1h)
| where MetricName in ("cpu_percent", "deadlock")
| parse _ResourceId with * "/microsoft.sql/servers/" Server "/databases/" DB
| summarize Max = max(Maximum), Avg = avg(Average) by Server, DB, MetricName
```

#### Storage Throttling Detection

```kql
StorageBlobLogs
| where TimeGenerated > ago(1d) and StatusText contains "ServerBusy"
| project TimeGenerated, OperationName, StatusCode, StatusText, _ResourceId
```

#### AKS Pod Failures

```kql
KubeEvents
| where TimeGenerated > ago(1h)
| where Reason in ("Failed", "BackOff", "Unhealthy", "FailedScheduling")
| project TimeGenerated, Name, Namespace, Reason, Message
```

#### Application Insights — Failed Requests + Slow Dependencies

```kql
AppRequests
| where TimeGenerated > ago(1h) and Success == false
| summarize FailCount = count() by Name, ResultCode
| sort by FailCount desc
```

## Microsoft Sentinel Threat Hunting

When the user asks about threat hunting, detection rules, security investigations, or MITRE ATT&CK techniques, follow this process:

### Hunting Query Workflow

1. **Identify the threat scenario** — What tactic/technique? (e.g., brute force = T1110, lateral movement = T1021)
2. **Select the right table** — Match the data source to the attack surface:
   - Identity attacks → `SigninLogs`, `SecurityEvent`, `AuditLogs`
   - Endpoint threats → `DeviceProcessEvents`, `DeviceFileEvents`, `DeviceRegistryEvents`
   - Network threats → `CommonSecurityLog`, `DeviceNetworkEvents`, `DnsEvents`
   - Cloud attacks → `AzureActivity`, `AuditLogs`, `OfficeActivity`
   - Cross-source → Use ASIM parsers (e.g., `imAuthentication` for auth across all sources)
3. **Build the detection logic** — Use appropriate patterns:
   - **Threshold-based**: `summarize count() | where count_ > N`
   - **Baseline comparison**: `leftanti` join against historical period
   - **Time-series anomaly**: `make-series` + `series_decompose_anomalies`
   - **IOC matching**: `join` with `ThreatIntelligenceIndicator` or `_GetWatchlist()`
4. **Map entities** — Ensure output includes identifiable entities (Account, IP, Host) for incident creation
5. **Tag MITRE ATT&CK** — Identify the tactic (TA00XX) and technique (T1XXX)

### Key Sentinel Patterns

#### Brute Force Detection

```kql
SigninLogs
| where TimeGenerated > ago(1h)
| where ResultType != "0"
| summarize FailureCount = count(), DistinctAccounts = dcount(UserPrincipalName)
    by IPAddress, bin(TimeGenerated, 1h)
| where FailureCount > 30 or DistinctAccounts > 5
```

#### Cross-Source Hunting with ASIM

```kql
imAuthentication
| where TimeGenerated > ago(1h)
| where EventResult == "Failure"
| summarize FailureCount = count(), Sources = make_set(EventProduct)
    by TargetUsername, SrcIpAddr
| where FailureCount > 20
```

#### Threat Intelligence Correlation

```kql
ThreatIntelligenceIndicator
| where Active == true and ExpirationDateTime > now()
| where isnotempty(NetworkIP)
| join kind=inner (
    CommonSecurityLog | where TimeGenerated > ago(1d)
) on $left.NetworkIP == $right.DestinationIP
| project TimeGenerated, SourceIP, DestinationIP, ThreatType, ConfidenceScore
```

#### Watchlist Enrichment

```kql
let VIPs = _GetWatchlist('VIPAccounts') | project SearchKey;
SigninLogs
| where TimeGenerated > ago(1h)
| where UserPrincipalName in (VIPs)
| where LocationDetails.countryOrRegion != "US"
```

#### Rare Activity Detection (Baseline Comparison)

```kql
let baseline = AzureActivity
| where TimeGenerated between (ago(14d) .. ago(1d))
| where ActivityStatusValue == "Success"
| summarize by CallerIpAddress, Caller, OperationNameValue;
AzureActivity
| where TimeGenerated > ago(1d)
| where ActivityStatusValue == "Success"
| join kind=leftanti (baseline) on CallerIpAddress, Caller, OperationNameValue
```

## Live Query Execution & Cluster Exploration

This skill includes a Python CLI tool (`adx_tool.py`) that can run live KQL queries and explore ADX cluster schemas. The tool requires Python 3.9+ and the dependencies listed in `requirements.txt` (install with `pip install -r requirements.txt`).

### Workflow: When to Spider vs Query

1. **New cluster / unknown schema** → Run spider first to discover the cluster structure, then build queries using the schema output.
2. **Known cluster with existing schema** → Read `cluster_schema.json` for context, then build and optionally execute queries.
3. **User asks to run a query** → Execute directly with the query subcommand.
4. **User reports column/table errors** → Re-run the spider to refresh schema, then verify names against the JSON output.

### Running a KQL Query

Use `adx_tool.py query` to execute a KQL query against a live ADX cluster and display results as a formatted table:

```bash
python adx_tool.py query --cluster https://mycluster.region.kusto.windows.net --database MyDB --query "StormEvents | take 10"
```

Or run a query from a `.kql` file:

```bash
python adx_tool.py query --cluster https://mycluster.region.kusto.windows.net --database MyDB --file my_query.kql
```

When the user asks to run a query, use this tool to execute it and return the results. Authentication happens via interactive browser login (Entra ID).

### Cluster Spider — Schema Discovery

Use `adx_tool.py spider` to explore an ADX cluster and save its schema (databases, tables, columns, and data types) to a JSON file:

```bash
python adx_tool.py spider --cluster https://mycluster.region.kusto.windows.net --output cluster_schema.json
```

The resulting JSON file contains the full structure of the cluster. When this file is available, **always read it first** before building queries to:
- Use correct table and column names (no guessing)
- Apply correct data types in `where` clauses and casts
- Suggest relevant tables based on the user's intent
- Avoid `Column 'X' not found` errors

### Spider JSON Output Format

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
            { "name": "UserId", "type": "string" }
          ]
        }
      ]
    }
  ]
}
```

## Extended References

For the complete operator reference, all join flavors, full scalar/aggregation function tables, ADX column types, policies, and management commands, see:

- **[references/operators.md](references/operators.md)** — Full operator, function, and ADX concept reference
- **[references/patterns.md](references/patterns.md)** — 10+ annotated real-world query examples and Azure Monitor patterns
- **[references/azure-resources.md](references/azure-resources.md)** — Azure resource monitoring tables, schemas, and query patterns for VMs, App Service, Functions, SQL, Storage, AKS, Key Vault, Networking, and Application Insights
- **[references/sentinel.md](references/sentinel.md)** — Microsoft Sentinel hunting queries, MITRE ATT&CK-organized detection patterns, ASIM schemas, watchlist/TI correlation, and Sentinel table reference
