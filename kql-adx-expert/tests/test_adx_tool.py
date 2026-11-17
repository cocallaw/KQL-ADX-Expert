"""Tests for adx_tool.py. No network access: urlopen and KustoClient are mocked."""

import argparse
import json
import sys
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adx_tool  # noqa: E402

CLUSTER = "https://mycluster.westus.kusto.windows.net"


# ---------------------------------------------------------------------------
# check_connectivity
# ---------------------------------------------------------------------------

def test_http_error_response_counts_as_reachable() -> None:
    err = urllib.error.HTTPError(CLUSTER, 401, "Unauthorized", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err) as urlopen:
        ok, detail = adx_tool.check_connectivity(CLUSTER)
    assert ok and "401" in detail
    assert urlopen.call_args.args[0] == "https://mycluster.westus.kusto.windows.net/v1/rest/auth/metadata"


@pytest.mark.parametrize("exc", [urllib.error.URLError("Name or service not known"), TimeoutError("timed out")])
def test_network_failure_counts_as_unreachable(exc: Exception) -> None:
    with mock.patch("urllib.request.urlopen", side_effect=exc):
        ok, detail = adx_tool.check_connectivity(CLUSTER)
    assert not ok and "VPN" in detail


def test_invalid_uri_is_rejected_without_network() -> None:
    with mock.patch("urllib.request.urlopen") as urlopen:
        ok, detail = adx_tool.check_connectivity("mycluster.kusto.windows.net")
    assert not ok and "invalid cluster URI" in detail
    urlopen.assert_not_called()


# ---------------------------------------------------------------------------
# spider_cluster
# ---------------------------------------------------------------------------

def _result(rows: list[dict]) -> mock.Mock:
    response = mock.Mock()
    response.primary_results = [rows]
    return response


def _fake_client() -> mock.Mock:
    schema = json.dumps({"OrderedColumns": [{"Name": "Timestamp", "CslType": "datetime"}]})

    def execute(database: str, command: str) -> mock.Mock:
        if command == ".show databases":
            return _result([{"DatabaseName": "Samples"}, {"DatabaseName": "Other"}])
        if command == ".show tables":
            return _result([{"TableName": "StormEvents"}])
        return _result([{"Schema": schema}])

    client = mock.Mock()
    client.execute.side_effect = execute
    return client


def test_spider_database_filter_only_queries_named_database() -> None:
    client = _fake_client()
    schema, stats = adx_tool.spider_cluster(client, CLUSTER, ["samples"])  # case-insensitive match

    assert [db["name"] for db in schema["databases"]] == ["Samples"]
    assert schema["databases"][0]["tables"][0]["columns"] == [{"name": "Timestamp", "type": "datetime"}]
    assert {call.args[0] for call in client.execute.call_args_list} == {"", "Samples"}
    assert stats == {"db_ok": 1, "db_failed": 0, "tables_ok": 1, "tables_failed": 0, "visible": 2}


def test_spider_unknown_database_is_a_failure() -> None:
    schema, stats = adx_tool.spider_cluster(_fake_client(), CLUSTER, ["Missing"])
    assert schema["databases"] == []
    assert stats["db_failed"] == 1 and stats["db_ok"] == 0


def test_spider_without_filter_covers_all_visible_databases() -> None:
    schema, stats = adx_tool.spider_cluster(_fake_client(), CLUSTER)
    assert [db["name"] for db in schema["databases"]] == ["Samples", "Other"]
    assert stats["db_ok"] == 2


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def test_doctor_fails_and_prints_install_command_when_sdk_missing(capsys: pytest.CaptureFixture) -> None:
    real = adx_tool.module_available
    with mock.patch.object(adx_tool, "module_available", lambda name: name != "azure.kusto.data" and real(name)):
        with pytest.raises(SystemExit) as exit_info:
            adx_tool.handle_doctor(argparse.Namespace(cluster=None))

    out = capsys.readouterr().out
    assert exit_info.value.code == adx_tool.EXIT_SETUP
    assert "[FAIL] import azure.kusto.data" in out
    assert "requirements.txt" in out and "requirements-msft.txt" in out
