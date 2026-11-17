#!/usr/bin/env python3
"""ADX Tool — Query runner and cluster spider for Azure Data Explorer.

Subcommands:
    doctor  Check the interpreter, pip, dependencies, and cluster reachability.
    query   Run a KQL query against an ADX cluster and print results.
    spider  Explore an ADX cluster and save schema as JSON.

Authentication uses interactive browser login (Entra ID).

Exit codes: 0 success, 1 setup problem, 2 network/VPN, 3 auth, permission, or service error.
"""

import argparse
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

# Azure SDK and tabulate are imported lazily so `doctor` and `--help` work without them.

SKILL_DIR = Path(__file__).resolve().parent
REQUIRED_MODULES = ("azure.kusto.data", "azure.identity", "tabulate")
CONNECT_TIMEOUT_SECONDS = 10

EXIT_SETUP = 1
EXIT_NETWORK = 2
EXIT_SERVICE = 3


# ---------------------------------------------------------------------------
# Setup and connectivity checks
# ---------------------------------------------------------------------------

def install_commands() -> list[str]:
    """Return pip install commands for this interpreter, one per package source.

    Returns:
        Shell commands for public PyPI and the Microsoft package feed proxy.
    """
    exe = sys.executable
    return [
        f'"{exe}" -m pip install -r "{SKILL_DIR / "requirements.txt"}"   # public PyPI',
        f'"{exe}" -m pip install -r "{SKILL_DIR / "requirements-msft.txt"}"   # Microsoft package feed proxy',
    ]


def module_available(name: str) -> bool:
    """Return True if a module can be imported by this interpreter.

    Args:
        name: Dotted module name.

    Returns:
        Whether the module is importable.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # parent package missing
        return False


def require_deps() -> None:
    """Exit with install instructions if any required module is missing.

    Raises:
        SystemExit: With EXIT_SETUP when a dependency is missing.
    """
    missing = [m for m in REQUIRED_MODULES if not module_available(m)]
    if not missing:
        return
    print(f"Error: missing Python packages: {', '.join(missing)}", file=sys.stderr)
    print(f"Interpreter: {sys.executable}", file=sys.stderr)
    print("Install them into this interpreter with one of:", file=sys.stderr)
    for cmd in install_commands():
        print(f"  {cmd}", file=sys.stderr)
    print(f'Then check setup with: "{sys.executable}" "{SKILL_DIR / "adx_tool.py"}" doctor', file=sys.stderr)
    sys.exit(EXIT_SETUP)


def check_connectivity(cluster_uri: str, timeout: float = CONNECT_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """Check that the cluster's HTTPS endpoint answers, without authenticating.

    Requests the auth metadata endpoint the Kusto SDK fetches before sign-in.
    Any HTTP response, including 4xx, proves the network path works.

    Args:
        cluster_uri: Cluster URI, e.g. https://mycluster.region.kusto.windows.net.
        timeout: Seconds to wait for a connection.

    Returns:
        (reachable, detail) where detail explains the result.
    """
    parsed = urlparse(cluster_uri)
    if parsed.scheme != "https" or not parsed.netloc:
        return False, f"invalid cluster URI '{cluster_uri}' — expected https://<cluster>.<region>.kusto.windows.net"
    url = f"https://{parsed.netloc}/v1/rest/auth/metadata"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return True, f"{parsed.netloc} answered HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return True, f"{parsed.netloc} answered HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"cannot reach {parsed.netloc} ({reason}) — check VPN / network / private endpoint"


def preflight_network(cluster_uri: str) -> None:
    """Exit before sign-in if the cluster is unreachable.

    Args:
        cluster_uri: Cluster URI to check.

    Raises:
        SystemExit: With EXIT_NETWORK when the cluster cannot be reached.
    """
    ok, detail = check_connectivity(cluster_uri)
    if not ok:
        print(f"Network error: {detail}", file=sys.stderr)
        sys.exit(EXIT_NETWORK)


def handle_doctor(args: argparse.Namespace) -> None:
    """Handle the 'doctor' subcommand: print one PASS/FAIL line per check."""
    failed = False

    def report(ok: bool, label: str, detail: str, fix: Optional[list[str]] = None) -> None:
        nonlocal failed
        failed = failed or not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")
        for line in fix or []:
            print(f"       fix: {line}")

    in_venv = sys.prefix != sys.base_prefix
    report(True, "interpreter", f"{sys.executable} (Python {sys.version.split()[0]})")
    report(True, "environment", f"{sys.prefix} ({'virtual environment' if in_venv else 'NOT a virtual environment'})")

    has_pip = module_available("pip")
    report(has_pip, "pip", "available" if has_pip else "missing",
           None if has_pip else [f'"{sys.executable}" -m ensurepip --upgrade'])

    missing = False
    for name in REQUIRED_MODULES:
        spec = importlib.util.find_spec(name) if module_available(name) else None
        if spec is not None:
            location = spec.origin or next(iter(spec.submodule_search_locations or []), "?")
            report(True, f"import {name}", location)
        else:
            missing = True
            report(False, f"import {name}", "not installed for this interpreter")
    if missing:
        print("       fix (pick the one for your network):")
        for cmd in install_commands():
            print(f"         {cmd}")

    if args.cluster:
        ok, detail = check_connectivity(args.cluster)
        report(ok, "cluster reachable", detail)
    else:
        print("[SKIP] cluster reachable: pass --cluster <URI> to test network access")

    print("\nAll checks passed." if not failed else "\nFix the FAIL lines above, then run doctor again.")
    if failed:
        sys.exit(EXIT_SETUP)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def create_client(cluster_uri: str) -> Any:
    """Create an authenticated KustoClient using interactive browser login."""
    from azure.identity import InteractiveBrowserCredential
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder

    credential = InteractiveBrowserCredential()
    kcsb = KustoConnectionStringBuilder.with_azure_token_credential(cluster_uri, credential)
    return KustoClient(kcsb)


# ---------------------------------------------------------------------------
# Query subcommand
# ---------------------------------------------------------------------------

def run_query(client: Any, database: str, query: str) -> None:
    """Execute a KQL query and print the results as a formatted table."""
    from tabulate import tabulate

    response = client.execute(database, query)
    primary = response.primary_results[0]

    columns = [col.column_name for col in primary.columns]
    rows = []
    for row in primary:
        rows.append([row[col] for col in columns])

    if not rows:
        print("(query returned no results)")
        return

    print(tabulate(rows, headers=columns, tablefmt="grid"))
    print(f"\n({len(rows)} row(s) returned)")


def handle_query(args: argparse.Namespace) -> None:
    """Handle the 'query' subcommand."""
    require_deps()
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            query_text = f.read()
    else:
        query_text = args.query

    preflight_network(args.cluster)
    client = create_client(args.cluster)
    run_query(client, args.database, query_text)


# ---------------------------------------------------------------------------
# Spider subcommand
# ---------------------------------------------------------------------------

def spider_cluster(client: Any, cluster_uri: str,
                   only_databases: Optional[list[str]] = None) -> tuple[dict, dict]:
    """Explore an ADX cluster and return its schema and discovery stats.

    Args:
        client: Authenticated KustoClient.
        cluster_uri: Cluster URI, recorded in the schema.
        only_databases: Limit discovery to these databases; None means all visible ones.

    Returns:
        (schema, stats). stats holds succeeded/failed counts for databases and tables.
    """
    schema = {
        "cluster": cluster_uri,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "databases": [],
    }
    stats = {"db_ok": 0, "db_failed": 0, "tables_ok": 0, "tables_failed": 0, "visible": 0}

    # .show databases lists only the databases this account can see.
    db_response = client.execute("", ".show databases")
    visible = [row["DatabaseName"] for row in db_response.primary_results[0]]
    stats["visible"] = len(visible)

    if only_databases:
        visible_lower = {name.lower(): name for name in visible}
        databases = []
        for wanted in only_databases:
            actual = visible_lower.get(wanted.lower())
            if actual:
                databases.append(actual)
            else:
                stats["db_failed"] += 1
                print(f"  Error: database '{wanted}' not found or not visible to this account", file=sys.stderr)
    else:
        databases = visible

    for index, db_name in enumerate(databases, start=1):
        started = time.monotonic()
        db_entry = {"name": db_name, "tables": []}

        try:
            tbl_response = client.execute(db_name, ".show tables")
            table_names = [row["TableName"] for row in tbl_response.primary_results[0]]
        except Exception as exc:
            stats["db_failed"] += 1
            print(f"  [{index}/{len(databases)}] {db_name} — FAILED to list tables: {exc}", file=sys.stderr)
            schema["databases"].append(db_entry)
            continue

        for tbl_name in table_names:
            tbl_entry = {"name": tbl_name, "columns": []}
            try:
                col_response = client.execute(db_name, f".show table ['{tbl_name}'] schema as json")
                for row in col_response.primary_results[0]:
                    schema_json = json.loads(row["Schema"])
                    for col in schema_json.get("OrderedColumns", []):
                        tbl_entry["columns"].append({"name": col["Name"], "type": col["CslType"]})
                    break  # only one row expected
                stats["tables_ok"] += 1
            except Exception as exc:
                stats["tables_failed"] += 1
                print(f"  Warning: Could not get schema for '{db_name}.{tbl_name}': {exc}", file=sys.stderr)
            db_entry["tables"].append(tbl_entry)

        stats["db_ok"] += 1
        schema["databases"].append(db_entry)
        print(f"  [{index}/{len(databases)}] {db_name} — {len(table_names)} tables "
              f"({time.monotonic() - started:.1f}s)", file=sys.stderr)

    return schema, stats


def handle_spider(args: argparse.Namespace) -> None:
    """Handle the 'spider' subcommand."""
    require_deps()
    preflight_network(args.cluster)
    client = create_client(args.cluster)
    scope = ", ".join(args.database) if args.database else "all visible databases"
    print(f"Spidering cluster: {args.cluster} ({scope})")

    started = time.monotonic()
    schema, stats = spider_cluster(client, args.cluster, args.database)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    total_columns = sum(len(tbl["columns"]) for db in schema["databases"] for tbl in db["tables"])
    print(f"\nDiscovered in {time.monotonic() - started:.1f}s:")
    print(f"  Databases: {stats['db_ok']} succeeded, {stats['db_failed']} failed "
          f"({stats['visible']} visible to this account)")
    print(f"  Tables:    {stats['tables_ok']} succeeded, {stats['tables_failed']} failed")
    print(f"  Columns:   {total_columns}")
    print(f"\nSchema saved to: {args.output}")
    if stats["db_failed"] or stats["tables_failed"]:
        print("Note: failed items appear with empty lists in the JSON — that means unreadable, not empty.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_with_error_handling(args: argparse.Namespace) -> None:
    """Run a subcommand, turning SDK failures into one-line messages and exit codes.

    Args:
        args: Parsed CLI arguments with a `func` handler.

    Raises:
        SystemExit: EXIT_NETWORK or EXIT_SERVICE on classified failures.
    """
    if args.command == "doctor":
        args.func(args)
        return

    try:
        args.func(args)
    except Exception as exc:
        # Imported here: require_deps() has already confirmed the SDK is installed.
        from azure.core.exceptions import ClientAuthenticationError
        from azure.kusto.data.exceptions import (KustoAuthenticationError, KustoNetworkError,
                                                 KustoServiceError)

        if isinstance(exc, KustoNetworkError):
            print(f"Network error: {exc} — check VPN / network / private endpoint", file=sys.stderr)
            sys.exit(EXIT_NETWORK)
        if isinstance(exc, (KustoAuthenticationError, ClientAuthenticationError)):
            print(f"Authentication failed: {exc}", file=sys.stderr)
            sys.exit(EXIT_SERVICE)
        if isinstance(exc, KustoServiceError):
            print(f"Cluster rejected the request (permission or query error): {exc}", file=sys.stderr)
            sys.exit(EXIT_SERVICE)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adx_tool",
        description="Query runner and cluster spider for Azure Data Explorer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    cluster_help = "ADX cluster URI (e.g., https://mycluster.region.kusto.windows.net)"

    # -- doctor subcommand --
    doctor_parser = subparsers.add_parser("doctor", help="Check interpreter, pip, dependencies, and cluster reachability.")
    doctor_parser.add_argument("--cluster", help=cluster_help + "; omit to skip the network check")
    doctor_parser.set_defaults(func=handle_doctor)

    # -- query subcommand --
    query_parser = subparsers.add_parser("query", help="Run a KQL query against an ADX cluster.")
    query_parser.add_argument("--cluster", required=True, help=cluster_help)
    query_parser.add_argument("--database", required=True, help="Database name to query")
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="KQL query string")
    query_group.add_argument("--file", help="Path to a .kql file containing the query")
    query_parser.set_defaults(func=handle_query)

    # -- spider subcommand --
    spider_parser = subparsers.add_parser("spider", help="Explore an ADX cluster and save schema as JSON.")
    spider_parser.add_argument("--cluster", required=True, help=cluster_help)
    spider_parser.add_argument("--database", action="append",
                               help="Only discover this database (repeatable). Default: all visible databases")
    spider_parser.add_argument("--output", default="cluster_schema.json", help="Output JSON file path (default: cluster_schema.json)")
    spider_parser.set_defaults(func=handle_spider)

    args = parser.parse_args()
    run_with_error_handling(args)


if __name__ == "__main__":
    main()
