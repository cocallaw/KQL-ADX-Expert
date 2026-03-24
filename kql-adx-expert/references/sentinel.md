# Microsoft Sentinel Hunting Queries & Detection Patterns

Hunting queries, detection rule patterns, and security analysis techniques for Microsoft Sentinel. Organized by data source, MITRE ATT&CK tactic, and advanced technique.

---

## Sentinel Table Reference

### Identity & Authentication

| Table | Source | Key Columns | Hunting Use |
|-------|--------|-------------|-------------|
| `SecurityEvent` | Windows Security Event Log (via AMA) | `EventID`, `Account`, `Computer`, `LogonType`, `IpAddress` | Failed logons (4625), privilege escalation (4672), process creation (4688) |
| `SigninLogs` | Microsoft Entra ID | `UserPrincipalName`, `IPAddress`, `LocationDetails`, `ResultType`, `AppDisplayName` | Brute force, impossible travel, anomalous sign-ins |
| `AADSignInEventsBeta` | Defender XDR advanced hunting | `AccountUpn`, `IPAddress`, `ErrorCode` | Extended sign-in telemetry |
| `AuditLogs` | Microsoft Entra ID | `OperationName`, `InitiatedBy`, `TargetResources`, `CorrelationId` | Consent grants, role assignments, app registrations |
| `IdentityLogonEvents` | Defender for Identity | `AccountName`, `LogonType`, `DestinationDeviceName` | On-premises lateral movement |
| `BehaviorAnalytics` | Sentinel UEBA | `UserPrincipalName`, `ActivityInsights`, `UsersInsights` | Anomalous behavior scoring |
| `IdentityInfo` | UEBA (synced from Entra ID) | `AccountName`, `Department`, `JobTitle`, `IsAccountEnabled` | Identity enrichment |

### Network & Endpoint

| Table | Source | Key Columns | Hunting Use |
|-------|--------|-------------|-------------|
| `CommonSecurityLog` | CEF-format devices (firewalls, proxies, WAFs) | `SourceIP`, `DestinationIP`, `DeviceAction`, `SentBytes`, `ReceivedBytes` | C2 beaconing, data exfiltration, blocked connections |
| `Syslog` | Linux hosts | `HostName`, `Facility`, `SeverityLevel`, `SyslogMessage` | SSH brute force, privilege escalation, service anomalies |
| `DeviceProcessEvents` | Defender for Endpoint | `FileName`, `ProcessCommandLine`, `InitiatingProcessFileName` | Suspicious process execution, LOLBin usage |
| `DeviceNetworkEvents` | Defender for Endpoint | `RemoteIP`, `RemotePort`, `RemoteUrl`, `DeviceName` | C2 communication, lateral movement |
| `DeviceFileEvents` | Defender for Endpoint | `FileName`, `FolderPath`, `ActionType`, `SHA256` | Malware drops, suspicious file creation |
| `DeviceRegistryEvents` | Defender for Endpoint | `RegistryKey`, `RegistryValueName`, `RegistryValueData` | Persistence via registry, defense evasion |

### Cloud Activity

| Table | Source | Key Columns | Hunting Use |
|-------|--------|-------------|-------------|
| `AzureActivity` | Azure Resource Manager | `OperationNameValue`, `Caller`, `CallerIpAddress`, `ActivityStatusValue` | Suspicious Azure operations, resource modifications |
| `OfficeActivity` | Office 365 | `Operation`, `UserId`, `ClientIP` | Mailbox access, file sharing anomalies |
| `CloudAppEvents` | Defender for Cloud Apps | `ActionType`, `AccountDisplayName`, `Application` | SaaS anomalies |

### Sentinel-Native Tables

| Table | Purpose |
|-------|---------|
| `SecurityAlert` | Aggregated alerts from all Microsoft security products |
| `SecurityIncident` | Sentinel incidents with status, severity, and assignment |
| `SentinelAudit` | Changes to Sentinel configuration (rules, connectors, workspaces) |
| `Watchlist` | User-defined reference data (VIP lists, known bad IPs, etc.) |
| `ThreatIntelligenceIndicator` | Threat intelligence IOCs (IPs, domains, file hashes, URLs) |
| `Anomalies` | Machine learning-detected anomalies |

### Key SecurityEvent EventIDs

| EventID | Description | ATT&CK Relevance |
|---------|-------------|-------------------|
| 4624 | Successful logon | Lateral movement (LogonType 3, 10) |
| 4625 | Failed logon | Brute force, password spray |
| 4648 | Explicit credential logon | Credential theft |
| 4672 | Special privileges assigned | Privilege escalation |
| 4688 | New process created | Execution, LOLBins |
| 4720 | User account created | Persistence |
| 4732 | Member added to local group | Privilege escalation |
| 1102 | Security log cleared | Defense evasion |

### Key SigninLogs ResultTypes

| ResultType | Description | Hunting Relevance |
|------------|-------------|-------------------|
| `0` | Success | Baseline; unusual if from suspicious IP/location |
| `50074` | MFA required | MFA fatigue attacks if high volume |
| `50076` | MFA not satisfied | Failed MFA attempts |
| `50126` | Invalid username or password | Brute force / password spray |
| `500121` | MFA denied by user | MFA bombing indicator |
| `53003` | Blocked by Conditional Access | Policy testing / evasion attempts |

---

## ASIM — Advanced Security Information Model

ASIM provides normalized, source-agnostic schemas so a single hunting query works across all data sources that support the same schema. Instead of writing separate queries for each firewall or auth provider, write against ASIM parsers.

### Key ASIM Schemas and Parsers

| Schema | Unifying Parser | Normalized Table | Example Sources |
|--------|----------------|-----------------|-----------------|
| Authentication | `imAuthentication` | `ASimAuthenticationEventLogs` | SecurityEvent (4624/4625), SigninLogs, Okta, AWS CloudTrail |
| DNS Activity | `imDns` | `ASimDnsActivityLogs` | DNS server logs, Infoblox, Cisco Umbrella |
| Network Session | `imNetworkSession` | `ASimNetworkSessionLogs` | CommonSecurityLog, NSG flow logs, Palo Alto, Fortinet |
| Process Event | `imProcessCreate` | `ASimProcessEventLogs` | Sysmon, Defender for Endpoint, SecurityEvent 4688 |
| File Event | `imFileEvent` | `ASimFileEventLogs` | Defender for Endpoint, Sysmon |
| Web Session | `imWebSession` | `ASimWebSessionLogs` | Proxy logs, WAF, Zscaler |
| Registry Event | `imRegistry` | `ASimRegistryEventLogs` | Defender for Endpoint, Sysmon |
| Audit Event | `imAuditEvent` | `ASimAuditEventLogs` | AzureActivity, Exchange, various SaaS |
| User Management | `imUserManagement` | `ASimUserManagementActivityLogs` | Entra ID, Active Directory |

### ASIM Usage Pattern

```kql
// Cross-source brute force detection — works against ANY authentication source
imAuthentication
| where TimeGenerated > ago(1h)
| where EventResult == "Failure"
| summarize
    FailureCount = count(),
    DistinctSources = dcount(EventProduct),
    Sources = make_set(EventProduct, 5)
    by TargetUsername, SrcIpAddr
| where FailureCount > 20
| sort by FailureCount desc
// NOTES:
// - imAuthentication unifies SecurityEvent, SigninLogs, Okta, AWS, etc.
// - EventResult, TargetUsername, SrcIpAddr are normalized field names
// - DistinctSources shows how many different systems saw the attack
```

```kql
// Cross-source DNS threat hunting — detect queries to known-bad domains
imDns
| where TimeGenerated > ago(24h)
| where DnsQuery has_any ("malware.com", "c2server.net", "exfil.io")
| summarize QueryCount = count() by SrcIpAddr, DnsQuery, EventProduct
| sort by QueryCount desc
```

---

## Watchlist Integration

Watchlists store reference data (VIP users, known bad IPs, terminated employees) in the `Watchlist` table. Use `_GetWatchlist('alias')` to query them.

```kql
// Alert on sign-ins from blocklisted IPs
let BlockedIPs = _GetWatchlist('BlockedIPAddresses') | project SearchKey;
SigninLogs
| where TimeGenerated > ago(1h)
| where IPAddress in (BlockedIPs)
| project TimeGenerated, UserPrincipalName, IPAddress, AppDisplayName, ResultType
```

```kql
// Enrich alerts with VIP user context
let VIPUsers = _GetWatchlist('VIPAccounts') | project SearchKey;
SecurityAlert
| where TimeGenerated > ago(24h)
| mv-expand Entity = todynamic(Entities)
| extend AccountName = tostring(Entity.Name)
| where AccountName in (VIPUsers)
| project TimeGenerated, AlertName, AlertSeverity, AccountName
| sort by AlertSeverity asc
```

```kql
// Detect logins by terminated employees
let TerminatedUsers = _GetWatchlist('TerminatedEmployees') | project SearchKey;
SigninLogs
| where TimeGenerated > ago(7d)
| where ResultType == "0"  // successful sign-in
| where UserPrincipalName in (TerminatedUsers)
| project TimeGenerated, UserPrincipalName, IPAddress, AppDisplayName
```

---

## Threat Intelligence Correlation

```kql
// Match outbound network connections against TI indicators
ThreatIntelligenceIndicator
| where Active == true and ExpirationDateTime > now()
| where isnotempty(NetworkIP)
| join kind=inner (
    CommonSecurityLog
    | where TimeGenerated > ago(1d)
    | where DeviceAction != "Deny"
) on $left.NetworkIP == $right.DestinationIP
| project TimeGenerated, SourceIP, DestinationIP, Description,
    ThreatType, ConfidenceScore, DeviceVendor
| sort by ConfidenceScore desc
```

```kql
// Match file hashes from endpoint telemetry against TI
ThreatIntelligenceIndicator
| where Active == true
| where isnotempty(FileHashValue)
| join kind=inner (
    DeviceFileEvents
    | where Timestamp > ago(7d)
    | extend FileHash = SHA256
) on $left.FileHashValue == $right.FileHash
| project Timestamp, DeviceName, FileName, FolderPath, FileHash,
    ThreatType, Description, ConfidenceScore
```

---

## Hunting Queries by MITRE ATT&CK Tactic

### Initial Access (TA0001)

#### Brute Force — SigninLogs

```kql
// PURPOSE: Detect brute-force login attempts against Azure-hosted apps
// PATTERN: summarize + threshold + dcount for spray detection
// ATT&CK: T1110 — Brute Force
SigninLogs
| where TimeGenerated > ago(1d)
| where ResultType != "0"
| summarize
    FailureCount = count(),
    DistinctAccounts = dcount(UserPrincipalName),
    Accounts = make_set(UserPrincipalName, 10),
    Apps = make_set(AppDisplayName, 5)
    by IPAddress, bin(TimeGenerated, 1h)
| where FailureCount > 30 or DistinctAccounts > 5
| sort by FailureCount desc
// NOTES:
// - DistinctAccounts > 5 with one IP = password spray (T1110.003)
// - FailureCount > 30 from one account = brute force (T1110.001)
// - ResultType "50126" specifically = invalid credentials
```

#### Anomalous Sign-In Locations (Time-Series Trend)

```kql
// PURPOSE: Find users whose sign-in location diversity is increasing anomalously
// PATTERN: make-series + series_fit_line to detect location drift
// ATT&CK: T1078 — Valid Accounts
SigninLogs
| where TimeGenerated > ago(14d)
| extend locationString = strcat(
    tostring(LocationDetails["countryOrRegion"]), "/",
    tostring(LocationDetails["state"]), "/",
    tostring(LocationDetails["city"]))
| make-series dLocationCount = dcount(locationString)
    on TimeGenerated step 1d
    by UserPrincipalName, AppDisplayName
| extend (RSquare, Slope, Variance, RVariance, Interception, LineFit) =
    series_fit_line(dLocationCount)
| top 10 by Slope desc
// NOTES:
// - Slope = rate of change in location diversity
// - High slope = account being used from increasing number of locations
// - Combine with join to extract actual location names
```

#### MFA Fatigue / Push Bombing

```kql
// PURPOSE: Detect MFA push-bombing attacks
// PATTERN: Count MFA prompts per user in short windows
// ATT&CK: T1621 — Multi-Factor Authentication Request Generation
SigninLogs
| where TimeGenerated > ago(1d)
| where ResultType in ("50074", "500121", "50076")
| summarize
    MFAPrompts = count(),
    DeniedCount = countif(ResultType == "500121"),
    IPs = make_set(IPAddress, 5)
    by UserPrincipalName, bin(TimeGenerated, 30m)
| where MFAPrompts > 10
| sort by MFAPrompts desc
// NOTES:
// - 50074 = MFA required, 500121 = MFA denied by user, 50076 = MFA not satisfied
// - >10 prompts in 30 min is abnormal for legitimate users
// - Check if a successful sign-in follows the burst
```

### Execution (TA0002)

#### Suspicious PowerShell / Encoded Commands

```kql
// PURPOSE: Detect encoded or obfuscated PowerShell execution
// PATTERN: Process creation events with command-line keyword matching
// ATT&CK: T1059.001 — Command and Scripting Interpreter: PowerShell
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4688
| where Process has_any ("powershell.exe", "pwsh.exe")
| where CommandLine has_any (
    "-enc", "-EncodedCommand", "FromBase64String",
    "IEX", "Invoke-Expression", "downloadstring",
    "Net.WebClient", "Invoke-WebRequest", "-nop", "-w hidden")
| project TimeGenerated, Computer, Account, Process, CommandLine, ParentProcessName
| sort by TimeGenerated desc
// NOTES:
// - has_any uses term index for fast matching
// - ParentProcessName helps identify the execution chain
// - For Defender for Endpoint, use DeviceProcessEvents instead
```

#### LOLBin Abuse (Defender for Endpoint)

```kql
// PURPOSE: Detect living-off-the-land binary abuse
// PATTERN: Filename + suspicious command-line pattern
// ATT&CK: T1218 — System Binary Proxy Execution
DeviceProcessEvents
| where Timestamp > ago(1d)
| where FileName in~ ("certutil.exe", "mshta.exe", "regsvr32.exe",
    "rundll32.exe", "msbuild.exe", "cmstp.exe", "wmic.exe")
| where ProcessCommandLine has_any ("http", "ftp", "/decode", "-urlcache",
    "scrobj.dll", "javascript:", "vbscript:")
| project Timestamp, DeviceName, FileName, ProcessCommandLine,
    InitiatingProcessFileName, AccountName
| sort by Timestamp desc
```

### Persistence (TA0003)

#### New Service Principal or App Credential

```kql
// PURPOSE: Detect new app registrations or credential additions
// PATTERN: AuditLogs filtered by sensitive operations
// ATT&CK: T1098.001 — Account Manipulation: Additional Cloud Credentials
AuditLogs
| where TimeGenerated > ago(7d)
| where OperationName in (
    "Add application",
    "Add service principal",
    "Add service principal credentials",
    "Update application – Certificates and secrets management")
| extend InitiatedBy = iff(
    isnotempty(tostring(parse_json(tostring(InitiatedBy.user)).userPrincipalName)),
    tostring(parse_json(tostring(InitiatedBy.user)).userPrincipalName),
    tostring(parse_json(tostring(InitiatedBy.app)).displayName))
| extend TargetApp = tostring(TargetResources[0].displayName)
| project TimeGenerated, InitiatedBy, OperationName, TargetApp, CorrelationId
| sort by TimeGenerated desc
```

#### Suspicious Consent Grant

```kql
// PURPOSE: Detect OAuth consent grants that may indicate illicit consent attacks
// PATTERN: AuditLogs consent operations with scope analysis
// ATT&CK: T1098.003 — Account Manipulation: Additional Cloud Roles
AuditLogs
| where TimeGenerated > ago(7d)
| where OperationName == "Consent to application"
| extend InitiatedBy = tostring(parse_json(tostring(InitiatedBy.user)).userPrincipalName)
| extend TargetApp = tostring(TargetResources[0].displayName)
| extend ModProps = TargetResources[0].modifiedProperties
| mv-expand ModProps
| extend PropertyName = tostring(ModProps.displayName)
| where PropertyName == "ConsentAction.Permissions"
| extend Permissions = tostring(ModProps.newValue)
| where Permissions has_any ("Mail.Read", "Files.ReadWrite.All",
    "Directory.ReadWrite.All", "full_access_as_app")
| project TimeGenerated, InitiatedBy, TargetApp, Permissions
```

#### Registry Run Key Persistence

```kql
// PURPOSE: Detect new auto-start persistence via registry
// PATTERN: Registry write events to known persistence keys
// ATT&CK: T1547.001 — Boot or Logon Autostart Execution: Registry Run Keys
DeviceRegistryEvents
| where Timestamp > ago(1d)
| where RegistryKey has_any (
    @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    @"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    @"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
| where ActionType == "RegistryValueSet"
| project Timestamp, DeviceName, RegistryKey, RegistryValueName,
    RegistryValueData, InitiatingProcessFileName, InitiatingProcessCommandLine
| sort by Timestamp desc
```

### Defense Evasion (TA0005)

#### Security Log Cleared

```kql
// PURPOSE: Detect clearing of Windows Security Event Log
// PATTERN: Simple EventID filter
// ATT&CK: T1070.001 — Indicator Removal: Clear Windows Event Logs
SecurityEvent
| where TimeGenerated > ago(7d)
| where EventID == 1102
| project TimeGenerated, Computer, Account
| sort by TimeGenerated desc
```

#### Timestomping — File Creation Time Anomaly

```kql
// PURPOSE: Detect files with creation times that don't match the file system timeline
// PATTERN: DeviceFileEvents with time delta analysis
// ATT&CK: T1070.006 — Indicator Removal: Timestomp
DeviceFileEvents
| where Timestamp > ago(7d)
| where ActionType == "FileCreated"
| extend HoursSinceCreation = datetime_diff("hour", Timestamp, todatetime(FileOriginReferrerUrl))
| where HoursSinceCreation < -24  // creation time predates the event by >24h
| project Timestamp, DeviceName, FileName, FolderPath, HoursSinceCreation
```

### Credential Access (TA0006)

#### Password Spray Detection

```kql
// PURPOSE: Detect password spray — one IP, many accounts, few attempts each
// PATTERN: Pivot on IP with dcount(Account) threshold
// ATT&CK: T1110.003 — Brute Force: Password Spraying
SecurityEvent
| where TimeGenerated > ago(1h)
| where EventID == 4625
| summarize
    FailedCount = count(),
    DistinctAccounts = dcount(TargetAccount),
    AccountList = make_set(TargetAccount, 25)
    by IpAddress, bin(TimeGenerated, 15m)
| where DistinctAccounts > 10 and FailedCount < DistinctAccounts * 3
| sort by DistinctAccounts desc
// NOTES:
// - Password spray: many accounts, few attempts each (low FailedCount per account)
// - Brute force: few accounts, many attempts (high FailedCount per account)
// - The ratio check (FailedCount < DistinctAccounts * 3) filters for spray
```

### Lateral Movement (TA0008)

#### RDP Lateral Movement

```kql
// PURPOSE: Detect one account using RDP to reach many machines
// PATTERN: LogonType 10 (RemoteInteractive) with dcount(Computer)
// ATT&CK: T1021.001 — Remote Services: Remote Desktop Protocol
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4624 and LogonType == 10
| summarize
    RDPCount = count(),
    DistinctComputers = dcount(Computer),
    Computers = make_set(Computer, 20)
    by Account, IpAddress
| where DistinctComputers > 3
| sort by DistinctComputers desc
```

#### SMB Lateral Movement

```kql
// PURPOSE: Detect account using network logon to many machines (PsExec, SMB)
// PATTERN: LogonType 3 (Network) with dcount threshold
// ATT&CK: T1021.002 — Remote Services: SMB/Windows Admin Shares
SecurityEvent
| where TimeGenerated > ago(24h)
| where EventID == 4624 and LogonType == 3
| where Account !endswith "$"  // exclude machine accounts
| summarize
    Logons = count(),
    DistinctComputers = dcount(Computer),
    Computers = make_set(Computer, 20)
    by Account, IpAddress
| where DistinctComputers > 5
| sort by DistinctComputers desc
```

### Discovery (TA0007)

#### Rare Azure Subscription Operations

```kql
// PURPOSE: Detect sensitive Azure operations not seen in baseline period
// PATTERN: leftanti join for first-occurrence detection
// ATT&CK: T1580 — Cloud Infrastructure Discovery
let SensitiveOps = dynamic([
    "microsoft.compute/snapshots/write",
    "microsoft.network/networksecuritygroups/write",
    "microsoft.storage/storageaccounts/listkeys/action"]);
let baseline = AzureActivity
| where TimeGenerated between (ago(14d) .. ago(1d))
| where OperationNameValue in~ (SensitiveOps)
| where ActivityStatusValue =~ "Success"
| summarize count() by CallerIpAddress, Caller, OperationNameValue;
AzureActivity
| where TimeGenerated > ago(1d)
| where OperationNameValue in~ (SensitiveOps)
| where ActivityStatusValue =~ "Success"
| summarize StartTime = min(TimeGenerated), EndTime = max(TimeGenerated),
    Count = count()
    by CallerIpAddress, Caller, OperationNameValue
| join kind=leftanti (baseline) on CallerIpAddress, Caller, OperationNameValue
| sort by Count desc
// NOTES:
// - leftanti returns only rows WITHOUT a match in baseline
// - This finds operations by new IPs/users not seen in the past 14 days
// - Add more operations to SensitiveOps as needed
```

### Command & Control (TA0011)

#### DNS Beaconing Detection

```kql
// PURPOSE: Detect periodic DNS queries that may indicate C2 beaconing
// PATTERN: make-series + series_periods_detect for periodicity
// ATT&CK: T1071.004 — Application Layer Protocol: DNS
DnsEvents
| where TimeGenerated > ago(7d)
| where Name !endswith ".microsoft.com" and Name !endswith ".windows.net"
| summarize QueryCount = count() by Name, ClientIP, bin(TimeGenerated, 10m)
| make-series RequestSeries = sum(QueryCount) default=0
    on TimeGenerated step 10m
    by Name, ClientIP
| extend (periods, scores) = series_periods_detect(RequestSeries, 4.0, 144.0, 2)
| mv-expand periods to typeof(double), scores to typeof(double)
| where scores > 0.7  // high periodicity confidence
| project Name, ClientIP, periods, scores
| sort by scores desc
// NOTES:
// - Beaconing shows consistent periodic patterns
// - series_periods_detect finds dominant periodicities
// - Filter out known-good domains to reduce noise
```

#### Network Data Exfiltration Baseline

```kql
// PURPOSE: Identify hosts with anomalous outbound data volume
// PATTERN: summarize bytes with threshold comparison
// ATT&CK: T1041 — Exfiltration Over C2 Channel
CommonSecurityLog
| where TimeGenerated > ago(1d)
| where DeviceAction != "Deny"
| summarize
    TotalBytesSent = sum(SentBytes),
    TotalBytesReceived = sum(ReceivedBytes),
    DistinctDestinations = dcount(DestinationIP),
    ConnectionCount = count()
    by SourceIP, DeviceVendor
| where TotalBytesSent > 500000000  // >500 MB sent
| sort by TotalBytesSent desc
```

### Impact (TA0040)

#### Mass File Encryption (Ransomware Indicator)

```kql
// PURPOSE: Detect rapid file modifications that may indicate ransomware
// PATTERN: High-volume file renames/modifications in short window
// ATT&CK: T1486 — Data Encrypted for Impact
DeviceFileEvents
| where Timestamp > ago(1h)
| where ActionType in ("FileRenamed", "FileModified")
| summarize
    FileCount = count(),
    DistinctExtensions = dcount(tostring(split(FileName, ".")[-1])),
    Extensions = make_set(tostring(split(FileName, ".")[-1]), 10)
    by DeviceName, InitiatingProcessFileName, bin(Timestamp, 5m)
| where FileCount > 100
| sort by FileCount desc
// NOTES:
// - Ransomware typically renames files in bulk with a new extension
// - High FileCount + new unusual extensions = strong indicator
// - Combine with DeviceProcessEvents to identify the encrypting process
```

---

## Sentinel Configuration Auditing

```kql
// PURPOSE: Detect changes to Sentinel analytics rules by unauthorized users
// PATTERN: SentinelAudit with user group exclusion
SentinelAudit
| where TimeGenerated > ago(7d)
| where Status == "Success"
| where OperationName has_any (
    "Create or update analytics rule",
    "Delete analytics rule",
    "Create or update data connector")
| extend CallerName = tostring(parse_json(ExtendedProperties)["CallerName"])
| project TimeGenerated, CallerName, OperationName,
    SentinelResourceName, SentinelResourceType
| sort by TimeGenerated desc
```

---

## Time-Series Anomaly Detection Patterns

### Failed Sign-In Spike Detection

```kql
// PURPOSE: Detect anomalous spikes in failed sign-ins using statistical decomposition
// PATTERN: make-series + series_decompose_anomalies for spike detection
SigninLogs
| where TimeGenerated > ago(14d)
| where ResultType != "0"
| make-series FailCount = count() default=0
    on TimeGenerated from ago(14d) to now() step 1h
| extend (anomalies, score, baseline) =
    series_decompose_anomalies(FailCount, 2.0, -1, "linefit")
| mv-expand
    TimeGenerated to typeof(datetime),
    FailCount to typeof(long),
    anomalies to typeof(int),
    score to typeof(double)
| where anomalies == 1  // positive anomaly (spike)
| project TimeGenerated, FailCount, score
| sort by score desc
// NOTES:
// - Threshold 2.0 = number of standard deviations for anomaly
// - anomalies == 1 for spikes, -1 for drops
// - Use render timechart BEFORE mv-expand to visualize the full series
```

### Rare App Activity Detection

```kql
// PURPOSE: Detect apps performing rare actions not seen in the past 14 days
// PATTERN: Two-period comparison with leftanti join
let auditBaseline = AuditLogs
| where TimeGenerated between (ago(14d) .. ago(1d))
| where isnotempty(tostring(parse_json(tostring(InitiatedBy.app)).displayName))
| extend InitiatedByApp = tostring(parse_json(tostring(InitiatedBy.app)).displayName)
| summarize by OperationName, InitiatedByApp;
AuditLogs
| where TimeGenerated > ago(1d)
| where isnotempty(tostring(parse_json(tostring(InitiatedBy.app)).displayName))
| extend InitiatedByApp = tostring(parse_json(tostring(InitiatedBy.app)).displayName)
| extend TargetName = tostring(TargetResources[0].displayName)
| summarize EventCount = count(), FirstSeen = min(TimeGenerated)
    by OperationName, InitiatedByApp, TargetName
| join kind=leftanti (auditBaseline) on OperationName, InitiatedByApp
| sort by EventCount desc
```

---

## Analytics Rule Promotion

When a hunting query proves valuable, promote it to a scheduled analytics rule:

1. **Entity mapping** — Map query output columns to Sentinel entity types:
   - `Account` → `UserPrincipalName` or `Account`
   - `Host` → `Computer` or `DeviceName`
   - `IP` → `IPAddress`, `IpAddress`, `SourceIP`, etc.

2. **MITRE ATT&CK tagging** — Assign the relevant tactic and technique IDs

3. **Alert grouping** — Configure entity-based grouping to merge related alerts into a single incident

```kql
// Example: Ready-to-promote brute force rule with entity mappings
SecurityEvent
| where TimeGenerated > ago(1h)
| where EventID == 4625
| summarize FailedCount = count() by TargetAccount, Computer, IpAddress
| where FailedCount > 20
// Entity mappings (configured in Sentinel UI):
//   Account entity → TargetAccount
//   Host entity    → Computer
//   IP entity      → IpAddress
```
