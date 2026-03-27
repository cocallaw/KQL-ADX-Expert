#!/usr/bin/env python3
"""ADX Tool — Query runner and cluster spider for Azure Data Explorer.

Subcommands:
    query   Run a KQL query against an ADX cluster and print results.
    spider  Explore an ADX cluster and save schema as JSON.

Authentication uses interactive browser login (Entra ID) with a persistent
token cache so that repeat invocations within the same user session do not
require a new browser-based auth flow.
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from tabulate import tabulate


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def create_client(cluster_uri: str, allow_unencrypted_cache: bool = False) -> KustoClient:
    """Create an authenticated KustoClient using interactive browser login.

    Tokens are persisted to the system's secure storage (Windows Credential
    Manager, macOS Keychain, Linux keyring) under the cache name
    ``kql-adx-expert``.  Subsequent invocations within the token's lifetime
    will reuse the cached credential and skip the browser prompt.

    On Linux systems without a keyring daemon the cache falls back to an
    unencrypted local file only when *allow_unencrypted_cache* is ``True``;
    otherwise no persistence is used and each process must authenticate
    independently.
    """
    cache_options = None
    try:
        cache_options = TokenCachePersistenceOptions(
            name="kql-adx-expert",
            allow_unencrypted_storage=allow_unencrypted_cache,
        )
    except Exception:
        # If persistent-cache support (e.g., msal-extensions via azure-identity[cache])
        # is not available or fails to initialize, fall back to a credential
        # without cache persistence to avoid breaking the CLI.
        cache_options = None

    if cache_options is not None:
        credential = InteractiveBrowserCredential(
            cache_persistence_options=cache_options,
        )
    else:
        credential = InteractiveBrowserCredential()
    kcsb = KustoConnectionStringBuilder.with_azure_token_credential(cluster_uri, credential)
    return KustoClient(kcsb)


# ---------------------------------------------------------------------------
# Query subcommand
# ---------------------------------------------------------------------------

def run_query(client: KustoClient, database: str, query: str) -> None:
    """Execute a KQL query and print the results as a formatted table."""
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
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            query_text = f.read()
    elif args.query:
        query_text = args.query
    else:
        print("Error: Provide --query or --file.", file=sys.stderr)
        sys.exit(1)

    client = create_client(args.cluster, allow_unencrypted_cache=args.allow_unencrypted_cache)
    run_query(client, args.database, query_text)


# ---------------------------------------------------------------------------
# Spider subcommand
# ---------------------------------------------------------------------------

def spider_cluster(client: KustoClient, cluster_uri: str) -> dict:
    """Explore an ADX cluster and return its schema as a dictionary."""
    schema = {
        "cluster": cluster_uri,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "databases": [],
    }

    # Discover databases
    db_response = client.execute("", ".show databases")
    db_rows = db_response.primary_results[0]

    databases = []
    for row in db_rows:
        db_name = row["DatabaseName"]
        databases.append(db_name)

    for db_name in databases:
        db_entry = {"name": db_name, "tables": []}

        # Discover tables in this database
        try:
            tbl_response = client.execute(db_name, ".show tables")
            tbl_rows = tbl_response.primary_results[0]
        except Exception as exc:
            print(f"  Warning: Could not list tables in '{db_name}': {exc}", file=sys.stderr)
            schema["databases"].append(db_entry)
            continue

        table_names = []
        for row in tbl_rows:
            table_names.append(row["TableName"])

        # Discover columns for each table
        for tbl_name in table_names:
            tbl_entry = {"name": tbl_name, "columns": []}
            try:
                col_query = f".show table ['{tbl_name}'] schema as json"
                col_response = client.execute(db_name, col_query)
                col_rows = col_response.primary_results[0]

                for row in col_rows:
                    schema_json = json.loads(row["Schema"])
                    ordered_columns = schema_json.get("OrderedColumns", [])
                    for col in ordered_columns:
                        tbl_entry["columns"].append({
                            "name": col["Name"],
                            "type": col["CslType"],
                        })
                    break  # only one row expected
            except Exception as exc:
                print(f"  Warning: Could not get schema for '{db_name}.{tbl_name}': {exc}", file=sys.stderr)

            db_entry["tables"].append(tbl_entry)

        schema["databases"].append(db_entry)

    return schema


def handle_spider(args: argparse.Namespace) -> None:
    """Handle the 'spider' subcommand."""
    client = create_client(args.cluster, allow_unencrypted_cache=args.allow_unencrypted_cache)
    print(f"Spidering cluster: {args.cluster}")

    schema = spider_cluster(client, args.cluster)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    # Print summary
    total_tables = sum(len(db["tables"]) for db in schema["databases"])
    total_columns = sum(
        len(tbl["columns"]) for db in schema["databases"] for tbl in db["tables"]
    )
    print(f"\nDiscovered:")
    print(f"  Databases: {len(schema['databases'])}")
    print(f"  Tables:    {total_tables}")
    print(f"  Columns:   {total_columns}")
    print(f"\nSchema saved to: {args.output}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adx_tool",
        description="Query runner and cluster spider for Azure Data Explorer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- query subcommand --
    query_parser = subparsers.add_parser("query", help="Run a KQL query against an ADX cluster.")
    query_parser.add_argument("--cluster", required=True, help="ADX cluster URI (e.g., https://mycluster.region.kusto.windows.net)")
    query_parser.add_argument("--database", required=True, help="Database name to query")
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="KQL query string")
    query_group.add_argument("--file", help="Path to a .kql file containing the query")
    query_parser.add_argument(
        "--allow-unencrypted-cache",
        action="store_true",
        default=False,
        help=(
            "Allow the token cache to fall back to an unencrypted local file on systems "
            "that lack a secure keyring (e.g. headless Linux). Off by default to follow "
            "security best practices."
        ),
    )
    query_parser.set_defaults(func=handle_query)

    # -- spider subcommand --
    spider_parser = subparsers.add_parser("spider", help="Explore an ADX cluster and save schema as JSON.")
    spider_parser.add_argument("--cluster", required=True, help="ADX cluster URI (e.g., https://mycluster.region.kusto.windows.net)")
    spider_parser.add_argument("--output", default="cluster_schema.json", help="Output JSON file path (default: cluster_schema.json)")
    spider_parser.add_argument(
        "--allow-unencrypted-cache",
        action="store_true",
        default=False,
        help=(
            "Allow the token cache to fall back to an unencrypted local file on systems "
            "that lack a secure keyring (e.g. headless Linux). Off by default to follow "
            "security best practices."
        ),
    )
    spider_parser.set_defaults(func=handle_spider)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
