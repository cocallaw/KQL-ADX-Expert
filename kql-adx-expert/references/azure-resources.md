# Azure Resource Monitoring — Tables, Schemas & Query Patterns

KQL table schemas, key columns, and ready-to-use query patterns for monitoring and troubleshooting core Azure resources. Each section covers the resource-specific tables (preferred) and AzureDiagnostics fallback where applicable.

---

## Cross-Cutting Tables

These tables apply across all or many Azure resource types.

### AzureActivity — ARM Control-Plane Operations

| Column | Type | Description |
|--------|------|-------------|
| `TimeGenerated` | datetime | When the event occurred |
| `OperationNameValue` | string | ARM operation (e.g., `Microsoft.Compute/virtualMachines/write`) |
| `Caller` | string | UPN or service principal that initiated the operation |
| `CallerIpAddress` | string | IP address of the caller |
| `ActivityStatusValue` | string | `Success`, `Failure`, `Start` |
| `ResourceGroup` | string | Resource group of the target resource |
| `_ResourceId` | string | Full ARM resource ID |
| `Level` | string | `Informational`, `Warning`, `Error`, `Critical` |

```kql
// PURPOSE: Track failed ARM operations in the last 24 hours
// USE CASE: Audit trail, troubleshoot deployment failures
AzureActivity
| where TimeGenerated > ago(24h)
| where ActivityStatusValue == "Failure"
| summarize FailCount = count() by OperationNameValue, Caller, ResourceGroup
| sort by FailCount desc
```

```kql
// PURPOSE: Track resource deletions in the last 7 days
// USE CASE: Change management, accidental deletion investigation
AzureActivity
| where TimeGenerated > ago(7d)
| where OperationNameValue endswith "/delete"
| where ActivityStatusValue == "Success"
| project TimeGenerated, Caller, OperationNameValue, ResourceGroup, _ResourceId
| sort by TimeGenerated desc
```

### AzureMetrics — Platform Metrics

| Column | Type | Description |
|--------|------|-------------|
| `TimeGenerated` | datetime | Timestamp of the aggregation period |
| `ResourceProvider` | string | e.g., `MICROSOFT.COMPUTE`, `MICROSOFT.SQL`, `MICROSOFT.WEB` |
| `MetricName` | string | e.g., `Percentage CPU`, `cpu_percent`, `Http5xx` |
| `Average` | real | Average value over the period |
| `Maximum` | real | Maximum value |
| `Minimum` | real | Minimum value |
| `Total` | real | Sum of values |
| `Count` | real | Number of samples |
| `_ResourceId` | string | Full ARM resource ID |

```kql
// PURPOSE: VM CPU metrics over time
// USE CASE: Capacity planning, trending
AzureMetrics
| where ResourceProvider == "MICROSOFT.COMPUTE"
| where MetricName == "Percentage CPU"
| summarize AvgCPU = avg(Average) by bin(TimeGenerated, 5m), _ResourceId
| render timechart
```

### AzureDiagnostics — Legacy Catch-All

Filter by `ResourceProvider` and `Category`. Use resource-specific tables when available for cleaner schemas and better performance.

| Column | Type | Description |
|--------|------|-------------|
| `ResourceProvider` | string | e.g., `MICROSOFT.KEYVAULT`, `MICROSOFT.SQL` |
| `ResourceType` | string | e.g., `VAULTS`, `SERVERS/DATABASES` |
| `Category` | string | Log category (e.g., `AuditEvent`, `QueryStoreRuntimeStatistics`) |
| `OperationName` | string | Operation that generated the log |
| `DurationMs` | real | Duration of the operation in milliseconds |
| `_ResourceId` | string | Full ARM resource ID |

---

## Resource-Specific Table Mapping

| Azure Resource | Resource-Specific Table(s) | Legacy AzureDiagnostics Category |
|---------------|---------------------------|-----------------------------------|
| Virtual Machine | `Perf`, `Heartbeat`, `InsightsMetrics`, `Event`, `Syslog` | N/A (agent-based) |
| App Service | `AppServiceHTTPLogs`, `AppServiceConsoleLogs`, `AppServiceAppLogs`, `AppServicePlatformLogs` | `AppServiceHTTPLogs` |
| Azure Functions | `FunctionAppLogs` | `FunctionAppLogs` |
| Azure SQL Database | — | `QueryStoreRuntimeStatistics`, `Errors`, `Deadlocks`, `DatabaseWaitStatistics` |
| PostgreSQL / MySQL | — | `PostgreSQLLogs`, `QueryStoreRuntimeStatistics`, `MySqlSlowLogs`, `MySqlAuditLogs` |
| Azure Storage | `StorageBlobLogs`, `StorageQueueLogs`, `StorageTableLogs`, `StorageFileLogs` | `StorageRead`, `StorageWrite`, `StorageDelete` |
| AKS | `ContainerLogV2`, `KubePodInventory`, `KubeNodeInventory`, `KubeEvents` | `ContainerLog` (legacy) |
| Key Vault | `AZKVAuditLogs`, `AZKVPolicyEvaluationDetailsLogs` | `AuditEvent` |
| Application Gateway | `AGWAccessLogs`, `AGWFirewallLogs`, `AGWPerformanceLogs` | `ApplicationGatewayAccessLog`, `ApplicationGatewayFirewallLog` |
| Azure Firewall | `AZFWNetworkRule`, `AZFWApplicationRule` | `AzureFirewallNetworkRule`, `AzureFirewallApplicationRule` |
| NSG Flow Logs | `NTANetAnalytics` | `NetworkSecurityGroupFlowEvent` |
| Application Insights | `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces`, `AppMetrics` | N/A (separate ingestion) |

---

## Virtual Machines

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `Perf` | Performance counters | `ObjectName`, `CounterName`, `InstanceName`, `CounterValue`, `Computer` |
| `Heartbeat` | Agent connectivity, VM inventory | `Computer`, `OSType`, `ComputerEnvironment`, `ResourceGroup`, `ComputerIP` |
| `InsightsMetrics` | VM Insights lightweight metrics | `Namespace`, `Name`, `Val`, `Computer`, `Origin` (filter `Origin == "vm.azm.ms"`) |
| `Event` | Windows Event Log | `EventLog`, `EventLevelName`, `EventID`, `Computer`, `RenderedDescription` |
| `Syslog` | Linux syslog | `Facility`, `SeverityLevel`, `SyslogMessage`, `HostName`, `ProcessName` |

### Common Perf Counters

| ObjectName | CounterName | Description |
|------------|-------------|-------------|
| `Processor` | `% Processor Time` | CPU utilization (use `InstanceName == "_Total"`) |
| `Memory` | `Available MBytes` (Win) / `Available MBytes Memory` (Linux) | Free RAM |
| `Memory` | `% Used Memory` | Memory utilization percentage |
| `LogicalDisk` | `% Free Space` | Disk free space percentage |
| `LogicalDisk` | `Free Megabytes` | Disk free space in MB |
| `LogicalDisk` | `Disk Transfers/sec` | Disk IOPS |
| `LogicalDisk` | `Current Disk Queue Length` | Pending disk I/O |
| `Network Adapter` | `Bytes Total/sec` | Network throughput |

### VM Queries

```kql
// PURPOSE: CPU usage percentile trends over the last day
// PATTERN: summarize percentiles + bin + render
Perf
| where ObjectName == "Processor" and CounterName == "% Processor Time"
    and InstanceName == "_Total"
| summarize P50 = percentile(CounterValue, 50),
    P90 = percentile(CounterValue, 90),
    P99 = percentile(CounterValue, 99)
    by bin(TimeGenerated, 1h)
| render timechart
```

```kql
// PURPOSE: Top 10 VMs by CPU using VM Insights
// PATTERN: InsightsMetrics with percentile
InsightsMetrics
| where TimeGenerated > ago(1h)
| where Origin == "vm.azm.ms"
| where Namespace == "Processor" and Name == "UtilizationPercentage"
| summarize P90 = percentile(Val, 90) by Computer
| top 10 by P90
```

```kql
// PURPOSE: Bottom 10 by free disk space
InsightsMetrics
| where TimeGenerated > ago(24h)
| where Origin == "vm.azm.ms"
| where Namespace == "LogicalDisk" and Name == "FreeSpacePercentage"
| summarize P10 = percentile(Val, 10) by Computer
| top 10 by P10 asc
```

```kql
// PURPOSE: VMs that stopped heartbeating recently
Heartbeat
| summarize LastReported = now() - max(TimeGenerated) by ResourceGroup, Resource, ResourceType
| where LastReported between (1m .. 15m)
```

```kql
// PURPOSE: Available memory over time (Windows + Linux)
Perf
| where ObjectName == "Memory"
    and (CounterName == "Available MBytes Memory" or CounterName == "Available MBytes")
| summarize avg(CounterValue) by bin(TimeGenerated, 15m), Computer, _ResourceId
| render timechart
```

---

## Azure App Service

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `AppServiceHTTPLogs` | HTTP request/response logs | `CsMethod`, `CsUriStem`, `ScStatus`, `TimeTaken`, `CIp`, `UserAgent` |
| `AppServiceConsoleLogs` | Console output (stdout/stderr) | `ResultDescription`, `Level` |
| `AppServiceAppLogs` | Application logs | `Level`, `ResultDescription`, `StackTrace` |
| `AppServicePlatformLogs` | Platform events (scale, restart) | `Level`, `Message`, `OperationName` |

### App Service Queries

```kql
// PURPOSE: App health — success rate per 5 minutes
AppServiceHTTPLogs
| summarize (count() - countif(ScStatus >= 500)) * 100.0 / count()
    by bin(TimeGenerated, 5m), _ResourceId
| render timechart
```

```kql
// PURPOSE: Categorize 5xx failure endpoints
AppServiceHTTPLogs
| where ScStatus >= 500
| reduce by strcat(CsMethod, ':', CsUriStem)
```

```kql
// PURPOSE: Response time percentiles per app
AppServiceHTTPLogs
| summarize avg(TimeTaken),
    percentiles(TimeTaken, 90, 95, 99) by _ResourceId
```

```kql
// PURPOSE: Top 5 client IPs generating traffic
AppServiceHTTPLogs
| top-nested of _ResourceId by dummy = max(0),
  top-nested 5 of CIp by count()
| project-away dummy
```

---

## Azure Functions

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `FunctionAppLogs` | Function execution logs | `FunctionName`, `Level`, `Message`, `HostInstanceId`, `FunctionInvocationId`, `Category` |

### Azure Functions Queries

```kql
// PURPOSE: Individual function invocation results (last hour)
FunctionAppLogs
| where TimeGenerated > ago(1h)
| where Category startswith "Function." and Message startswith "Executed "
| parse Message with "Executed '" Name "' (" Result ", Id=" Id ", Duration=" Duration:long "ms)"
| project TimeGenerated, FunctionName, Result, FunctionInvocationId, Duration, _ResourceId
| sort by TimeGenerated desc
```

```kql
// PURPOSE: Function error rate per hour
FunctionAppLogs
| where Category startswith "Function." and Message startswith "Executed "
| parse Message with "Executed '" Name "' (" Result ", Id=" Id ", Duration=" Duration:long "ms)"
| summarize count() by bin(TimeGenerated, 1h), Name, Result, _ResourceId
| order by TimeGenerated desc
```

```kql
// PURPOSE: Function activity volume over time
FunctionAppLogs
| where Category startswith "Function." and Message startswith "Executed "
| summarize count() by bin(TimeGenerated, 1h), FunctionName
| render timechart
```

---

## Azure SQL Database

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `AzureMetrics` | Platform metrics (CPU, DTU, deadlocks) | `MetricName`, `Average`, `Maximum` (filter `ResourceProvider == "MICROSOFT.SQL"`) |
| `AzureDiagnostics` | Query Store, wait stats, errors, deadlocks | `Category`, `query_hash_s`, `wait_type_s`, `duration_d`, `cpu_time_d` |

### AzureDiagnostics Categories for SQL

| Category | Description |
|----------|-------------|
| `QueryStoreRuntimeStatistics` | Query execution stats (duration, CPU, rows) |
| `QueryStoreWaitStatistics` | Wait type statistics per query |
| `Errors` | SQL errors logged by the database |
| `Deadlocks` | Deadlock events with XML graphs |
| `SQLInsights` | Intelligent Insights diagnostics |
| `DatabaseWaitStatistics` | Aggregate wait stats |

### SQL Database Queries

```kql
// PURPOSE: CPU usage in the past hour
AzureMetrics
| where ResourceProvider == "MICROSOFT.SQL"
| where TimeGenerated >= ago(1h)
| where MetricName == "cpu_percent"
| parse _ResourceId with * "/microsoft.sql/servers/" Server "/databases/" DB
| summarize MaxCPU = max(Maximum), AvgCPU = avg(Average) by Server, DB
```

```kql
// PURPOSE: Deadlocks in the past 60 minutes
AzureMetrics
| where ResourceProvider == "MICROSOFT.SQL"
| where TimeGenerated >= ago(1h)
| where MetricName == "deadlock"
| parse _ResourceId with * "/microsoft.sql/servers/" Server
| summarize MaxDeadlocks = max(Maximum) by Server, MetricName
```

```kql
// PURPOSE: Wait types in the past 15 minutes
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.SQL"
| where TimeGenerated >= ago(15m)
| parse _ResourceId with * "/microsoft.sql/servers/" Server "/databases/" DB
| summarize TotalWaits = sum(delta_waiting_tasks_count_d) by Server, DB, wait_type_s
| sort by TotalWaits desc
```

```kql
// PURPOSE: PostgreSQL slow queries (top 5)
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DBFORPOSTGRESQL"
| where Category == "QueryStoreRuntimeStatistics"
| where user_id_s != "10"
| summarize AvgTime = avg(todouble(mean_time_s)) by event_class_s, db_id_s, query_id_s
| top 5 by AvgTime desc
```

```kql
// PURPOSE: MySQL slow queries (>10 seconds)
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DBFORMYSQL"
| where Category == "MySqlSlowLogs"
| where query_time_d > 10
| project TimeGenerated, LogicalServerName_s, query_time_d, sql_text_s
| sort by query_time_d desc
```

---

## Azure Storage

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `StorageBlobLogs` | Blob operations | `OperationName`, `StatusCode`, `StatusText`, `DurationMs`, `ServerLatencyMs`, `Uri`, `AuthenticationType`, `CallerIpAddress` |
| `StorageQueueLogs` | Queue operations | Same schema as blob logs |
| `StorageTableLogs` | Table operations | Same schema as blob logs |
| `StorageFileLogs` | File share operations | Same schema as blob logs |

### Storage Queries

```kql
// PURPOSE: Top 10 most common errors (last 3 days)
StorageBlobLogs
| where TimeGenerated > ago(3d) and StatusText !contains "Success"
| summarize count() by StatusText
| top 10 by count_ desc
```

```kql
// PURPOSE: Operations with highest latency
StorageBlobLogs
| where TimeGenerated > ago(3d)
| top 10 by DurationMs desc
| project TimeGenerated, OperationName, DurationMs, ServerLatencyMs,
    ClientLatencyMs = DurationMs - ServerLatencyMs
```

```kql
// PURPOSE: Server-side throttling events
StorageBlobLogs
| where TimeGenerated > ago(3d) and StatusText contains "ServerBusy"
| project TimeGenerated, OperationName, StatusCode, StatusText, _ResourceId
```

```kql
// PURPOSE: Anonymous access requests (security audit)
StorageBlobLogs
| where TimeGenerated > ago(3d) and AuthenticationType == "Anonymous"
| project TimeGenerated, OperationName, AuthenticationType, Uri, _ResourceId
```

---

## Azure Kubernetes Service (AKS)

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ContainerLogV2` | Container stdout/stderr (recommended) | `ContainerName`, `PodName`, `PodNamespace`, `LogMessage`, `LogSource`, `Computer` |
| `ContainerLog` | Container logs (legacy) | `LogEntry`, `ContainerID`, `Image`, `Name`, `Computer` |
| `KubePodInventory` | Pod inventory and status | `Name`, `Namespace`, `PodStatus`, `ContainerStatus`, `Computer`, `ClusterId` |
| `KubeNodeInventory` | Node inventory | `Computer`, `Status`, `KubeletVersion`, `KubeProxyVersion` |
| `KubeEvents` | Kubernetes events | `Name`, `Namespace`, `Reason`, `Message`, `ObjectKind` |
| `InsightsMetrics` | Container metrics (CPU, memory) | `Namespace`, `Name`, `Val`, `Tags` (filter `Origin == "container.azm.ms"`) |

### AKS Queries

```kql
// PURPOSE: Pod errors in the last hour
KubeEvents
| where TimeGenerated > ago(1h)
| where Reason in ("Failed", "BackOff", "Unhealthy", "FailedScheduling")
| project TimeGenerated, Name, Namespace, Reason, Message
| sort by TimeGenerated desc
```

```kql
// PURPOSE: Container logs containing errors
ContainerLogV2
| where TimeGenerated > ago(1h)
| where LogMessage contains "error" or LogMessage contains "exception"
| project TimeGenerated, PodName, PodNamespace, ContainerName, LogMessage
| sort by TimeGenerated desc
```

```kql
// PURPOSE: Pods not in Running state
KubePodInventory
| where TimeGenerated > ago(15m)
| where PodStatus != "Running" and PodStatus != "Succeeded"
| summarize arg_max(TimeGenerated, *) by Name, Namespace
| project TimeGenerated, Name, Namespace, PodStatus, ContainerStatus
```

```kql
// PURPOSE: Nodes not in Ready state
KubeNodeInventory
| summarize arg_max(TimeGenerated, *) by Computer
| project Computer, Status, KubeletVersion, LastTransitionTimeReady
| where Status != "Ready"
```

---

## Azure Key Vault

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `AZKVAuditLogs` | Key Vault operations (resource-specific, recommended) | `OperationName`, `ResultType`, `CallerIPAddress`, `Identity`, `DurationMs` |
| `AzureDiagnostics` | Key Vault operations (legacy) | `ResourceProvider == "MICROSOFT.KEYVAULT"`, `OperationName`, `CallerIPAddress`, `DurationMs`, `httpStatusCode_d` |

### Key Vault Queries

```kql
// PURPOSE: Slow Key Vault requests (>1 second)
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where DurationMs > 1000
| summarize count() by OperationName, _ResourceId
```

```kql
// PURPOSE: Top callers by IP
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| summarize RequestCount = count() by CallerIPAddress
| sort by RequestCount desc
```

```kql
// PURPOSE: Failed Key Vault operations
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where httpStatusCode_d >= 400
| summarize count() by OperationName, httpStatusCode_d, _ResourceId
| sort by count_ desc
```

```kql
// PURPOSE: Key Vault activity volume over time
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| summarize count() by bin(TimeGenerated, 1h), OperationName
| render timechart
```

---

## Networking (Application Gateway, Firewall, NSG)

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `AGWAccessLogs` | Application Gateway access logs | `ClientIp`, `HttpMethod`, `RequestUri`, `HttpStatusCode`, `TimeTaken` |
| `AGWFirewallLogs` | Application Gateway WAF logs | `Action`, `RuleId`, `Message`, `ClientIp` |
| `AZFWNetworkRule` | Azure Firewall network rules | `SourceIp`, `DestinationIp`, `DestinationPort`, `Protocol`, `Action` |
| `AZFWApplicationRule` | Azure Firewall application rules | `Fqdn`, `SourceIp`, `Protocol`, `Action` |
| `NTANetAnalytics` | NSG flow log analytics | `FlowStatus`, `FlowType`, `SrcIP`, `DestIP`, `SrcPort`, `DestPort`, `Protocol_s` |

### Networking Queries

```kql
// PURPOSE: Application Gateway 5xx errors
AGWAccessLogs
| where TimeGenerated > ago(1h)
| where HttpStatusCode >= 500
| summarize count() by HttpStatusCode, RequestUri, _ResourceId
| sort by count_ desc
```

```kql
// PURPOSE: WAF blocked requests
AGWFirewallLogs
| where TimeGenerated > ago(24h)
| where Action == "Blocked"
| summarize count() by RuleId, Message, ClientIp
| sort by count_ desc
```

```kql
// PURPOSE: Azure Firewall denied traffic
AZFWNetworkRule
| where TimeGenerated > ago(1h)
| where Action == "Deny"
| summarize count() by SourceIp, DestinationIp, DestinationPort, Protocol
| sort by count_ desc
```

```kql
// PURPOSE: NSG denied flows
NTANetAnalytics
| where TimeGenerated > ago(1h)
| where FlowStatus == "D"
| summarize count() by SrcIP, DestIP, DestPort_d, Protocol_s
| sort by count_ desc
```

---

## Application Insights

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `AppRequests` | Incoming HTTP requests | `Name`, `Url`, `DurationMs`, `ResultCode`, `Success`, `ClientIP`, `AppRoleName` |
| `AppDependencies` | Outgoing dependency calls (SQL, HTTP, etc.) | `Name`, `Type`, `Target`, `DurationMs`, `Success`, `ResultCode` |
| `AppExceptions` | Unhandled/logged exceptions | `ExceptionType`, `Message`, `OuterMessage`, `Assembly`, `Method` |
| `AppTraces` | Application trace logs | `Message`, `SeverityLevel`, `AppRoleName` |
| `AppPageViews` | Browser page view telemetry | `Name`, `Url`, `DurationMs`, `ClientBrowser` |
| `AppAvailabilityResults` | Availability test results | `Name`, `Success`, `Location`, `DurationMs`, `Message` |
| `AppMetrics` | Custom metrics | `Name`, `Sum`, `Count`, `Min`, `Max` |
| `AppEvents` | Custom events | `Name`, `Properties`, `Measurements` |

### Application Insights Queries

```kql
// PURPOSE: Failed requests by endpoint
AppRequests
| where TimeGenerated > ago(1h)
| where Success == false
| summarize FailCount = count() by Name, ResultCode
| sort by FailCount desc
```

```kql
// PURPOSE: Slowest dependencies
AppDependencies
| where TimeGenerated > ago(1h)
| summarize AvgDuration = avg(DurationMs),
    P95 = percentile(DurationMs, 95),
    FailRate = countif(Success == false) * 100.0 / count()
    by Type, Target, Name
| sort by P95 desc
```

```kql
// PURPOSE: Exception trends over 24 hours
AppExceptions
| where TimeGenerated > ago(24h)
| summarize count() by bin(TimeGenerated, 1h), ExceptionType
| render timechart
```

```kql
// PURPOSE: End-to-end request duration percentiles
AppRequests
| where TimeGenerated > ago(1h)
| summarize P50 = percentile(DurationMs, 50),
    P90 = percentile(DurationMs, 90),
    P99 = percentile(DurationMs, 99)
    by bin(TimeGenerated, 5m), AppRoleName
| render timechart
```

```kql
// PURPOSE: Availability test failures
AppAvailabilityResults
| where TimeGenerated > ago(24h)
| where Success == false
| project TimeGenerated, Name, Location, Message, DurationMs
| sort by TimeGenerated desc
```

---

## Common Diagnostic Patterns

### Unified Resource Health Dashboard

```kql
// PURPOSE: Multi-resource health view in a single query
// PATTERN: union + per-resource health logic
union
    (Heartbeat
     | summarize LastHeartbeat = max(TimeGenerated) by Computer, ResourceGroup
     | extend Status = iff(LastHeartbeat < ago(5m), "Unhealthy", "Healthy"),
         ResourceType = "VM"),
    (AppServiceHTTPLogs
     | where TimeGenerated > ago(5m)
     | summarize ErrorRate = countif(ScStatus >= 500) * 100.0 / count() by _ResourceId
     | extend Status = iff(ErrorRate > 5, "Unhealthy", "Healthy"),
         ResourceType = "AppService"),
    (AzureMetrics
     | where ResourceProvider == "MICROSOFT.SQL" and MetricName == "cpu_percent"
     | where TimeGenerated > ago(5m)
     | summarize AvgCPU = avg(Average) by _ResourceId
     | extend Status = iff(AvgCPU > 80, "Warning", "Healthy"),
         ResourceType = "SQL")
| project ResourceType, Status, _ResourceId
```

### Correlate High CPU with Recent ARM Changes

```kql
// PURPOSE: Find ARM changes that may have caused CPU spikes
// PATTERN: Cross-table join between Perf and AzureActivity
let HighCPUVMs = Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "Processor" and CounterName == "% Processor Time"
    and InstanceName == "_Total"
| summarize AvgCPU = avg(CounterValue) by Computer
| where AvgCPU > 80;
AzureActivity
| where TimeGenerated > ago(24h)
| where OperationNameValue contains "virtualMachines"
| join kind=inner (HighCPUVMs) on $left.Resource == $right.Computer
| project TimeGenerated, Computer, AvgCPU, OperationNameValue, Caller
```

---

## Performance Tips for Resource Queries

| Tip | Why | Example |
|-----|-----|---------|
| Filter by `ResourceProvider` first in AzureDiagnostics | Reduces scan to one resource type | `where ResourceProvider == "MICROSOFT.SQL"` |
| Use resource-specific tables when available | Cleaner schema, faster queries | `StorageBlobLogs` over `AzureDiagnostics` |
| Use `_ResourceId` for scoped queries | ARM resource ID is indexed | `where _ResourceId == "/subscriptions/..."` |
| `parse _ResourceId` to extract resource names | Extract server/database/vault names | `parse _ResourceId with * "/servers/" Server "/databases/" DB` |
| Time filter always first | Reduces partition scan | `where TimeGenerated > ago(1h)` |
