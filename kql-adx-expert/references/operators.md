# KQL Operator, Function & ADX Concept Reference

Complete reference for all KQL operators, scalar functions, aggregation functions, special operators, and Azure Data Explorer concepts.

---

## Tabular Operators

### Filtering & Selection

| Operator | Purpose | Example |
|----------|---------|---------|
| `where` | Filter rows by predicate | `T \| where Status == "Error"` |
| `project` | Select/rename/compute columns (drops others) | `T \| project Name, Len = strlen(Name)` |
| `project-away` | Remove specific columns | `T \| project-away TempCol` |
| `project-rename` | Rename columns | `T \| project-rename NewName = OldName` |
| `extend` | Add computed columns (keeps all existing) | `T \| extend Duration = EndTime - StartTime` |
| `distinct` | Unique rows by specified columns | `T \| distinct Country, City` |

### Sorting & Limiting

| Operator | Purpose | Example |
|----------|---------|---------|
| `sort by` / `order by` | Sort rows | `T \| sort by TimeGenerated desc` |
| `top` | Return top N rows by expression | `T \| top 10 by Count desc` |
| `take` / `limit` | Return arbitrary N rows (no ordering) | `T \| take 100` |

### Aggregation

| Operator | Purpose | Example |
|----------|---------|---------|
| `summarize` | Group and aggregate (like SQL GROUP BY) | `T \| summarize avg(Price) by Category` |
| `count` | Shorthand for counting all rows | `T \| count` |

### Combining Tables

| Operator | Purpose | Example |
|----------|---------|---------|
| `join` | Combine rows from two tables on key | `T1 \| join kind=inner (T2) on Key` |
| `union` | Concatenate rows from multiple tables | `union Table1, Table2` |
| `lookup` | Efficient left-outer join for enrichment | `T \| lookup LookupTable on Key` |

### Parsing & Extraction

| Operator | Purpose | Example |
|----------|---------|---------|
| `parse` | Extract fields from strings | `T \| parse Message with "Error: " ErrCode " at " Loc` |
| `parse-where` | Parse with built-in filtering | `T \| parse-where Message with "Code=" Code:int` |
| `evaluate` | Invoke plugin functions | `T \| evaluate bag_unpack(DynCol)` |

### Visualization

| Operator | Purpose | Example |
|----------|---------|---------|
| `render` | Render a chart | `T \| render timechart` |

Render types: `timechart`, `barchart`, `piechart`, `columnchart`, `scatterchart`, `areachart`, `ladderchart`, `pivotchart`.

---

## Join Flavors — Complete Reference

| Flavor | Left Unmatched | Right Unmatched | Matched | Columns Returned |
|--------|:-:|:-:|:-:|-----------------|
| `inner` | ✗ | ✗ | ✓ | All from both |
| `innerunique` | ✗ (deduped left) | ✗ | ✓ | All from both |
| `leftouter` | ✓ (nulls for right) | ✗ | ✓ | All from both |
| `rightouter` | ✗ | ✓ (nulls for left) | ✓ | All from both |
| `fullouter` | ✓ | ✓ | ✓ | All from both |
| `leftanti` | ✓ | ✗ | ✗ | Left only |
| `rightanti` | ✗ | ✓ | ✗ | Right only |
| `leftsemi` | ✗ | ✗ | ✓ | Left only |
| `rightsemi` | ✗ | ✗ | ✓ | Right only |

**Syntax:**

```kql
TableA
| join kind=leftouter (
    TableB | where SomeFilter
) on $left.KeyA == $right.KeyB
```

**Join hints:**

- `hint.shufflekey = KeyCol` — distributes by key for high-cardinality columns
- `hint.strategy = broadcast` — broadcasts small left table (≤100K rows) to all nodes
- `hint.remote = auto` — for cross-cluster joins

---

## Scalar Functions

### String Functions

| Function | Description | Example |
|----------|-------------|---------|
| `extract(regex, group, source)` | Extract regex group | `extract("(\\d+)", 1, "Error 404")` → `"404"` |
| `split(source, delimiter)` | Split into dynamic array | `split("a-b-c", "-")` → `["a","b","c"]` |
| `strcat(s1, s2, ...)` | Concatenate strings | `strcat("Hello", " ", "World")` |
| `indexof(source, lookup)` | Find position (-1 if missing) | `indexof("hello world", "world")` → `6` |
| `trim(regex, source)` | Trim matching chars | `trim("\\s", "  hello  ")` → `"hello"` |
| `substring(source, start, len)` | Extract substring | `substring("Hello", 0, 3)` → `"Hel"` |
| `tolower(s)` / `toupper(s)` | Case conversion | `toupper("hello")` → `"HELLO"` |
| `replace_string(src, old, new)` | Replace occurrences | `replace_string("aaa", "a", "b")` → `"bbb"` |
| `strlen(s)` | String length | `strlen("test")` → `4` |
| `has` / `contains` / `startswith` | String predicates (case-insensitive) | `where Name has "error"` |
| `has_cs` / `contains_cs` | Case-sensitive variants | `where Name has_cs "Error"` |

**Performance**: `has` is faster than `contains` because `has` uses the term index.

### Datetime Functions

| Function | Description | Example |
|----------|-------------|---------|
| `ago(timespan)` | Time before now | `ago(1h)`, `ago(7d)` |
| `now()` | Current UTC time | `now()` |
| `bin(value, roundTo)` | Floor to nearest bin | `bin(TimeGenerated, 5m)` |
| `startofday(dt)` | Truncate to start of day | `startofday(now())` |
| `startofweek(dt)` / `startofmonth(dt)` | Truncate to week/month | `startofweek(now())` |
| `datetime_diff(part, dt1, dt2)` | Difference between datetimes | `datetime_diff("hour", dt1, dt2)` |
| `datetime_add(part, amount, dt)` | Add time | `datetime_add("day", 7, now())` |
| `format_datetime(dt, format)` | Format as string | `format_datetime(now(), "yyyy-MM-dd")` |
| `between(lower .. upper)` | Range check (inclusive) | `where TimeGenerated between(ago(1d) .. now())` |

### Math Functions

| Function | Description |
|----------|-------------|
| `abs(x)`, `ceiling(x)`, `floor(x)` | Absolute value, ceiling, floor |
| `log(x)`, `log2(x)`, `log10(x)` | Logarithms |
| `pow(x, y)`, `sqrt(x)` | Power, square root |
| `round(x, precision)` | Round to precision |
| `min_of(a, b, ...)`, `max_of(a, b, ...)` | Scalar min/max |

### Type Conversion

| Function | Description |
|----------|-------------|
| `tostring(v)` | Convert to string |
| `toint(v)` / `tolong(v)` | Convert to 32/64-bit integer |
| `todouble(v)` / `toreal(v)` | Convert to double |
| `todatetime(v)` | Convert to datetime |
| `totimespan(v)` | Convert to timespan |
| `todynamic(v)` / `parse_json(v)` | Parse JSON string to dynamic (equivalent) |
| `tobool(v)` | Convert to boolean |

---

## Aggregation Functions

Used inside `summarize`:

| Function | Description | Example |
|----------|-------------|---------|
| `count()` | Count rows | `summarize count() by State` |
| `countif(pred)` | Conditional count | `countif(Level == "Error")` |
| `sum(expr)` | Sum | `sum(BytesSent)` |
| `sumif(expr, pred)` | Conditional sum | `sumif(Cost, Region == "US")` |
| `avg(expr)` | Mean | `avg(Duration)` |
| `min(expr)` / `max(expr)` | Min/max | `min(StartTime), max(EndTime)` |
| `dcount(expr)` | Approx distinct count (HyperLogLog) | `dcount(UserId)` |
| `dcountif(expr, pred)` | Conditional distinct count | `dcountif(UserId, Active)` |
| `make_list(expr [, max])` | Collect all values into array | `make_list(FileName)` |
| `make_set(expr [, max])` | Collect unique values into array | `make_set(IPAddress)` |
| `percentile(expr, n)` | Nth percentile | `percentile(Duration, 95)` |
| `percentiles(expr, n1, n2..)` | Multiple percentiles | `percentiles(Duration, 50, 90, 99)` |
| `arg_max(maxExpr, *cols)` | Row with max value, returning cols | `arg_max(TimeGenerated, *) by Computer` |
| `arg_min(minExpr, *cols)` | Row with min value | `arg_min(StartTime, *) by EventType` |
| `stdev(expr)` | Standard deviation | `stdev(ResponseTime)` |
| `any(expr)` | Arbitrary value from group | `any(IPAddress)` |

**`dcount` vs `dcountif` vs `countif`:**
- `dcount(col)` — approximate count of *distinct* values (HyperLogLog)
- `dcountif(col, pred)` — distinct count only for matching rows
- `countif(pred)` — count of *rows* (not distinct) matching predicate

---

## Special Operators

### mv-expand

Expand dynamic arrays into multiple rows:

```kql
T | mv-expand IPAddresses
| extend IP = tostring(IPAddresses)
```

### mv-apply

Apply a subquery to each array element per record:

```kql
T | mv-apply item = Metrics on (
    where item.Value > 100
    | summarize HighCount = count()
)
```

### bag_unpack

Flatten a dynamic property bag into columns:

```kql
T | evaluate bag_unpack(Properties)
```

### pivot

Rotate rows into columns:

```kql
T | evaluate pivot(AggColumn, sum(Value), GroupColumn)
```

### serialize

Force sequential row ordering (required for `row_number()`, `prev()`, `next()`):

```kql
T | serialize | extend RowNum = row_number(), PrevValue = prev(Value)
```

### range

Generate a series of values:

```kql
range x from 1 to 10 step 1
range ts from ago(7d) to now() step 1d
```

---

## Let Statements and Functions

### let (scalar, tabular, and function)

```kql
// Scalar
let threshold = 100;
let startTime = ago(1h);

// Tabular
let errorLogs = Syslog | where SeverityLevel == "err";

// Inline function
let getErrors = (tbl: (TimeGenerated: datetime, Level: string)) {
    tbl | where Level == "Error"
};

errorLogs | where CounterValue > threshold
```

### Stored Functions

```kql
.create-or-alter function with (docstring = "Get failed logons")
    FailedLogons(timeRange: timespan = 1h) {
        SecurityEvent
        | where TimeGenerated > ago(timeRange)
        | where EventID == 4625
        | summarize FailCount = count() by Account, Computer
    }

// Invoke
FailedLogons(2h)
```

---

## ADX Column Types

| Type | Description | Example |
|------|-------------|---------|
| `bool` | Boolean | `true`, `false` |
| `int` | 32-bit integer | `42` |
| `long` | 64-bit integer | `9223372036854775807` |
| `real` / `double` | 64-bit float | `3.14` |
| `decimal` | 128-bit decimal | `1.234m` |
| `string` | UTF-8 (up to 1 MB) | `"hello"` |
| `datetime` | UTC date and time | `datetime(2025-01-15)` |
| `timespan` | Duration | `1h`, `5m`, `2d` |
| `dynamic` | JSON object/array/scalar | `dynamic({"key": "val"})` |
| `guid` | 128-bit UUID | `guid(...)` |

**Best practice**: Use `string` for IDs. Use `dynamic` for sparse/semi-structured data. Promote frequently queried properties to typed columns.

---

## Dynamic (JSON) Column Operations

```kql
// Dot-notation access
T | extend city = Properties.address.city

// Parse JSON string
T | extend data = parse_json(JsonStringCol)

// Discover keys
T | extend keys = bag_keys(Properties)

// Type-safe extraction
T | extend name = tostring(Properties.name), count = toint(Properties.count)
```

---

## ADX Table Policies

| Policy | Purpose | Command |
|--------|---------|---------|
| Retention | How long data is kept | `.alter table T policy retention '{"SoftDeletePeriod": "365.00:00:00"}'` |
| Caching (Hot) | SSD hot cache duration | `.alter table T policy caching hot = 30d` |
| Update | Transform data on ingestion | `.alter table T policy update ...` |
| Merge | Control extent merge behavior | `.alter table T policy merge ...` |
| Partitioning | Partition by column for pruning | `.alter table T policy partitioning ...` |

---

## Materialized Views

```kql
.create materialized-view HourlyMetrics on table RawMetrics {
    RawMetrics
    | summarize AvgCPU = avg(CPU), MaxMem = max(Memory) by Computer, bin(TimeGenerated, 1h)
}

HourlyMetrics | where TimeGenerated > ago(7d)
```

---

## External Tables and Cross-Cluster Queries

```kql
// External table
external_table("ExternalLogs") | where Timestamp > ago(1d)

// Cross-cluster
cluster("other.kusto.windows.net").database("OtherDB").Table | take 10

// Cross-database (same cluster)
database("OtherDB").Table | take 10
```

---

## .show Management Commands

| Command | Purpose |
|---------|---------|
| `.show cluster` | Cluster metadata |
| `.show databases` | List databases |
| `.show database DB schema` | Full schema |
| `.show tables` | List tables |
| `.show table T schema` | Table schema |
| `.show table T details` | Table details (extents, size, policies) |
| `.show queries` | Recently completed queries |
| `.show running queries` | Currently executing queries |
| `.show commands` | Completed management commands with resource usage |

---

## Query Limits

| Limit | Default |
|-------|---------|
| Result set rows | 500,000 records |
| Result set size | 64 MB |
| Concurrent queries | ~Cores-per-node × 10 |

Override with `set truncationmaxrecords = N;` or add more filters.
