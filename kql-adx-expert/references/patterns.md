# KQL Query Patterns & Annotated Examples

Real-world KQL query patterns for Azure Monitor, Log Analytics, Microsoft Sentinel, and Azure Data Explorer.

> **Sentinel-specific content**: For hunting queries organized by MITRE ATT&CK tactic, ASIM normalized schemas, watchlist/TI patterns, and Sentinel table reference, see **[sentinel.md](sentinel.md)**.

---

## Azure Monitor Core Tables

| Table | Contents | Common Use |
|-------|----------|------------|
| `Heartbeat` | Agent connectivity and VM health | VM inventory, disconnect detection |
| `Perf` | Performance counters (CPU, memory, disk) | Resource monitoring, capacity planning |
| `Event` | Windows Event Log entries | Error tracking, security events |
| `Syslog` | Linux syslog messages | System monitoring, auth failures |
| `AzureActivity` | Azure control plane operations | Audit trail, change tracking |
| `AzureDiagnostics` | Aggregated diagnostics (legacy mode) | Multi-resource diagnostics |
| `SecurityEvent` | Windows Security Event Log | Authentication, access tracking |
| `SigninLogs` | Microsoft Entra ID sign-in events | Sign-in analysis, brute force detection |
| `AuditLogs` | Microsoft Entra ID audit events | Consent grants, role/app changes |
| `CommonSecurityLog` | CEF-format device logs (firewalls, proxies) | Network security, C2 detection |

---

## AzureDiagnostics vs Resource-Specific Tables

**AzureDiagnostics** (legacy mode) aggregates logs from many resource types into one table with up to 500 columns. Overflow goes to `AdditionalFields` (dynamic).

**Resource-specific tables** (preferred) like `AppServiceHTTPLogs`, `AzureFirewallDnsProxy`, `StorageBlobLogs` provide cleaner schemas and better performance.

```kql
// Resource-specific (preferred)
AppServiceHTTPLogs
| where TimeGenerated > ago(1h)
| summarize RequestCount = count() by CsHost, bin(TimeGenerated, 5m)

// AzureDiagnostics (legacy)
AzureDiagnostics
| where ResourceType == "MICROSOFT.WEB/SITES"
| where Category == "AppServiceHTTPLogs"
```

---

## Annotated Query Examples

### Example 1: Time-Series CPU Aggregation with Chart

```kql
// PURPOSE: Chart average CPU utilization per VM in 15-minute bins
// PATTERN: summarize + bin() + render timechart
// USE CASE: Performance monitoring dashboard
Perf
| where TimeGenerated > ago(24h)
| where ObjectName == "Processor"
    and CounterName == "% Processor Time"
    and InstanceName == "_Total"
| summarize AvgCPU = avg(CounterValue) by Computer, bin(TimeGenerated, 15m)
| render timechart
// NOTES:
// - bin() creates evenly-spaced time buckets
// - render timechart → one line per Computer
// - Filter ObjectName/CounterName BEFORE summarize
```

### Example 2: Join with Lookup Table for VM Enrichment

```kql
// PURPOSE: Enrich error logs with VM metadata (OS, environment)
// PATTERN: arg_max for latest Heartbeat + leftouter join
// USE CASE: Correlating app errors with infrastructure
let VMInfo = Heartbeat
    | summarize arg_max(TimeGenerated, OSType, ComputerEnvironment, ResourceGroup) by Computer;
Syslog
| where TimeGenerated > ago(1h)
| where SeverityLevel in ("err", "crit", "alert", "emerg")
| summarize ErrorCount = count() by Computer, Facility
| join kind=leftouter (VMInfo) on Computer
| project Computer, Facility, ErrorCount, OSType, ComputerEnvironment, ResourceGroup
| sort by ErrorCount desc
// NOTES:
// - arg_max gets most recent heartbeat record per Computer
// - leftouter keeps all errors even without heartbeat data
```

### Example 3: Parsing JSON from Cloud Service Logs

```kql
// PURPOSE: Extract structured fields from JSON diagnostic messages
// PATTERN: parse_json() + tostring()/todouble() for type-safe extraction
// USE CASE: Analyzing Azure Function execution logs
AzureDiagnostics
| where ResourceType == "MICROSOFT.WEB/SITES"
| where Category == "FunctionAppLogs"
| where TimeGenerated > ago(6h)
| extend parsed = parse_json(message_s)
| extend
    FunctionName = tostring(parsed.functionName),
    DurationMs   = todouble(parsed.durationMs),
    Success      = tobool(parsed.succeeded)
| summarize
    AvgDuration = avg(DurationMs),
    FailCount   = countif(Success == false),
    TotalCalls  = count()
    by FunctionName
| sort by FailCount desc
// NOTES:
// - parse_json() and todynamic() are equivalent
// - Always cast dynamic sub-properties before aggregating
// - Filter ResourceType/Category FIRST to reduce parsing cost
```

### Example 4: Summarize with bin() for Threshold Alert

```kql
// PURPOSE: Detect when response time exceeds threshold in any 5-min window
// PATTERN: summarize + bin() + post-aggregation where
// USE CASE: Alert rule for API latency SLA breach
AppRequests
| where TimeGenerated > ago(1h)
| summarize
    AvgDuration = avg(DurationMs),
    P95Duration = percentile(DurationMs, 95),
    RequestCount = count()
    by bin(TimeGenerated, 5m), AppRoleName
| where AvgDuration > 500 or P95Duration > 2000
| project TimeGenerated, AppRoleName, AvgDuration, P95Duration, RequestCount
// NOTES:
// - Combining avg and percentile gives central tendency + tail latency
// - Post-agg where is correct: alerting on aggregated values
```

### Example 5: Detecting Missing Heartbeats (Gap Detection)

```kql
// PURPOSE: Find VMs that stopped sending heartbeats
// PATTERN: summarize max + datetime_diff + threshold
// USE CASE: VM availability monitoring and alerting
Heartbeat
| summarize LastHeartbeat = max(TimeGenerated) by Computer
| extend MinutesSinceLast = datetime_diff("minute", now(), LastHeartbeat)
| where MinutesSinceLast > 15
| project Computer, LastHeartbeat, MinutesSinceLast
| sort by MinutesSinceLast desc
// NOTES:
// - Simple single-pass over Heartbeat table
// - 15-minute threshold is typical for heartbeat monitoring
// - For richer gap detection, use make-series with default=0
```

### Example 6: Top-N Per Group Using arg_max

```kql
// PURPOSE: Most recent security event per computer with full row details
// PATTERN: summarize arg_max(TimeGenerated, *) by GroupCol
// USE CASE: "Last known state" — latest config, last login
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID in (4624, 4625)
| summarize arg_max(TimeGenerated, Account, EventID, LogonTypeName, IpAddress)
    by Computer
| extend EventType = iff(EventID == 4624, "Success", "Failure")
| project Computer, TimeGenerated, Account, EventType, LogonTypeName, IpAddress
// NOTES:
// - arg_max is KQL's idiomatic "top 1 per group"
// - Much faster than sort + serialize + row_number() + where RowNum == 1
// - Use arg_min for earliest event per group
```

### Example 7: Expanding JSON Arrays with mv-expand

```kql
// PURPOSE: Analyze individual IPs from a JSON array column
// PATTERN: mv-expand to flatten → aggregate per element
// USE CASE: Network security — events with multiple IPs
SigninLogs
| where TimeGenerated > ago(1d)
| where ResultType != "0"
| mv-expand IPAddress = todynamic(IPAddresses)
| extend IP = tostring(IPAddress.ipAddress), Country = tostring(IPAddress.countryOrRegion)
| summarize AttemptCount = count(), DistinctAccounts = dcount(UserPrincipalName)
    by IP, Country
| where AttemptCount > 50
| sort by AttemptCount desc
// NOTES:
// - mv-expand creates one row per array element
// - Always cast after expansion (tostring, toint)
// - dcount for multi-dimensional analysis
```

### Example 8: Anomaly Detection with make-series

```kql
// PURPOSE: Detect anomalous drops in request volume
// PATTERN: make-series + series_decompose_anomalies
// USE CASE: Proactive service health monitoring
AppRequests
| where TimeGenerated > ago(7d)
| make-series RequestCount = count() default=0
    on TimeGenerated from ago(7d) to now() step 1h
    by AppRoleName
| extend (anomalies, score, baseline) =
    series_decompose_anomalies(RequestCount, 1.5, -1, "linefit")
| mv-expand
    TimeGenerated to typeof(datetime),
    RequestCount to typeof(long),
    anomalies to typeof(int),
    score to typeof(double)
| where anomalies != 0
| project TimeGenerated, AppRoleName, RequestCount, anomalies, score
| sort by abs(score) desc
// NOTES:
// - make-series fills missing bins with default=0
// - Threshold 1.5 = std deviations for anomaly flag
// - mv-expand converts series arrays back to rows
// - Use render timechart on series (before mv-expand) for viz
```

### Example 9: materialize() for Multi-Pass Analysis

```kql
// PURPOSE: Count AND first-occurrence of errors per source
// PATTERN: materialize() to cache intermediate result used twice
// USE CASE: Incident triage — "how many errors and when did they start?"
let recentErrors = materialize(
    Syslog
    | where TimeGenerated > ago(6h)
    | where SeverityLevel in ("err", "crit")
);
let errorCounts = recentErrors
    | summarize ErrorCount = count() by Computer, Facility;
let firstSeen = recentErrors
    | summarize FirstSeen = min(TimeGenerated) by Computer, Facility;
errorCounts
| join kind=inner (firstSeen) on Computer, Facility
| extend HoursActive = datetime_diff("hour", now(), FirstSeen)
| project Computer, Facility, ErrorCount, FirstSeen, HoursActive
| sort by ErrorCount desc
// NOTES:
// - Without materialize(), the base query runs TWICE
// - ~5GB cache limit per node
```

### Example 10: Cross-Table Union with Conditional Logic

```kql
// PURPOSE: Unified security signal view from multiple sources
// PATTERN: union + extend for schema normalization + summarize
// USE CASE: SOC dashboard combining signal types
union
    (SecurityEvent
     | where TimeGenerated > ago(1h) | where EventID == 4625
     | extend SignalType = "FailedLogon", Entity = Account, Detail = Computer),
    (Syslog
     | where TimeGenerated > ago(1h) | where Facility == "auth" and SeverityLevel == "err"
     | extend SignalType = "AuthError", Entity = HostName, Detail = SyslogMessage),
    (AzureActivity
     | where TimeGenerated > ago(1h) | where ActivityStatusValue == "Failure"
     | extend SignalType = "AzureFailure", Entity = Caller, Detail = OperationNameValue)
| summarize SignalCount = count() by SignalType, Entity
| top 20 by SignalCount desc
// NOTES:
// - union merges rows from multiple tables
// - extend with common column names normalizes schema
// - Each sub-query should have its own where clause
```

---

## Alert Query Patterns

### CPU Threshold Breach

```kql
Perf
| where TimeGenerated > ago(15m)
| where ObjectName == "Processor" and CounterName == "% Processor Time"
| summarize AvgCPU = avg(CounterValue) by Computer
| where AvgCPU > 90
```

### Disk Space Low

```kql
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "LogicalDisk" and CounterName == "% Free Space"
| summarize MinFree = min(CounterValue) by Computer, InstanceName
| where MinFree < 10
```

### Anomaly with make-series (Heartbeat)

```kql
Heartbeat
| where TimeGenerated > ago(1d)
| make-series HeartbeatCount = count() default=0
    on TimeGenerated from ago(1d) to now() step 5m by Computer
| extend (anomalies, score, baseline) = series_decompose_anomalies(HeartbeatCount, 1.5)
| mv-expand TimeGenerated to typeof(datetime), HeartbeatCount, anomalies to typeof(int)
| where HeartbeatCount == 0 or anomalies != 0
```

---

## Heartbeat Join Pattern for VM Correlation

```kql
// Get latest VM info from Heartbeat, join with any other table
let VMInfo = Heartbeat | summarize arg_max(TimeGenerated, *) by Computer;
<AnyTable>
| where TimeGenerated > ago(1h)
| join kind=leftouter (
    VMInfo | project Computer, OSType, ComputerEnvironment, ResourceGroup
) on Computer
```

---

## Iterative Query Building Process

```kql
// Step 1: Explore shape
SecurityEvent | take 10

// Step 2: Filter
SecurityEvent | where TimeGenerated > ago(1h) | where EventID == 4625

// Step 3: Aggregate
SecurityEvent | where TimeGenerated > ago(1h) | where EventID == 4625
| summarize FailedCount = count() by Account

// Step 4: Refine
SecurityEvent | where TimeGenerated > ago(1h) | where EventID == 4625
| summarize FailedCount = count() by Account
| top 10 by FailedCount desc
```
