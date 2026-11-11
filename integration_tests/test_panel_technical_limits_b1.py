"""Guardrails: effective values remain authoritative and candidates are not active."""
from pathlib import Path
import shutil
import subprocess

import pytest

from custom_components.trybatec.api import (
    AUTH_TIMEOUT_SECONDS,
    DEVICE_TIMEOUT_SECONDS,
    HOUSING_TIMEOUT_SECONDS,
    INDEX_TIMEOUT_SECONDS,
    MAX_AUTH_BYTES,
    MAX_INDEX_BYTES,
    MAX_INDEX_LINES,
    MAX_INDEX_POINTS,
    TRANSIENT_MAX_ATTEMPTS,
)
from custom_components.trybatec.history_services import HISTORY_WINDOW_PAUSE_SECONDS
from custom_components.trybatec.panel_technical_limits import technical_limits_snapshot


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"
BACKEND = ROOT / "custom_components/trybatec/panel_api.py"


def test_effective_limits_are_read_from_backend_not_ui_constants():
    snapshot = technical_limits_snapshot()
    assert snapshot["read_only"] is True
    effective = snapshot["effective"]
    assert effective["index_response_max_bytes"] == MAX_INDEX_BYTES == 16 * 1024 * 1024
    assert effective["metadata_response_max_bytes"] == MAX_AUTH_BYTES == 64 * 1024
    assert effective["index_response_max_lines"] == MAX_INDEX_LINES == 20000
    assert effective["index_response_max_points"] == MAX_INDEX_POINTS == 120000
    assert effective["request_timeout_seconds"] == {
        "indexes": INDEX_TIMEOUT_SECONDS,
        "authentication": AUTH_TIMEOUT_SECONDS,
        "housing_discovery": HOUSING_TIMEOUT_SECONDS,
        "device_metadata": DEVICE_TIMEOUT_SECONDS,
    }
    assert effective["transient_max_attempts"] == TRANSIENT_MAX_ATTEMPTS == 3
    assert effective["historical_inter_request_pause_ms"] == round(
        HISTORY_WINDOW_PAUSE_SECONDS * 1000
    ) == 200
    assert effective["historical_operation_timeout_seconds"] is None
    assert effective["historical_operation_max_http_requests"] is None
    assert '"technical_limits": technical_limits_snapshot()' in BACKEND.read_text()


def test_approved_budgets_remain_candidates_until_load_tests():
    limits = technical_limits_snapshot()
    assert limits["candidate"] == {
        "status": "not_enforced_pending_load_tests",
        "standard": {"duration_seconds": 120, "http_requests": 24},
        "exhaustive": {"duration_seconds": 600, "http_requests": 80},
        "historical_inter_request_pause_ms": 500,
        "max_historical_operations_per_account": 1,
        "progress_visible_after_seconds": 3,
        "slow_information_after_seconds": 30,
        "requires_async_progress_cancel_resume": True,
    }
    assert limits["effective"]["historical_inter_request_pause_ms"] != (
        limits["candidate"]["historical_inter_request_pause_ms"]
    )


def test_frontend_displays_effective_and_unenforced_budgets_as_read_only():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for dynamic browser contract")
    script = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const panel=fs.readFileSync(process.argv[1],"utf8");
const ctx={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(panel+
  "\n globalThis.__Panel=TrybatecPanel;",ctx,{timeout:2000});
const proto=ctx.__Panel.prototype;
const fixture={
  _data:{technical_limits:{
    read_only:true,
    effective:{
      index_response_max_bytes:16777216,
      metadata_response_max_bytes:65536,
      index_response_max_lines:20000,
      index_response_max_points:120000,
      request_timeout_seconds:{indexes:60,authentication:30,housing_discovery:25,device_metadata:20},
      transient_max_attempts:3,index_max_iterations_with_reauthentication:5,
      transient_backoff_step_ms:250,historical_inter_request_pause_ms:200,
      historical_operations_serialized_per_account:true,
      historical_operation_timeout_seconds:null,historical_operation_max_http_requests:null},
    candidate:{status:"not_enforced_pending_load_tests",
      standard:{duration_seconds:120,http_requests:24},
      exhaustive:{duration_seconds:600,http_requests:80},
      historical_inter_request_pause_ms:500,max_historical_operations_per_account:1}
  }},
  _t:(fr,en)=>fr,_number:value=>String(value)
};
const html=proto._technicalLimits.call(fixture);
assert.match(html,/16 Mio/);
assert.match(html,/64 Kio/);
assert.match(html,/200 ms/);
assert.match(html,/120 s/);
assert.match(html,/600 s/);
assert.match(html,/24/);
assert.match(html,/80/);
assert.match(html,/500 ms/);
assert.match(html,/Budgets proposés — non actifs/);
assert.match(html,/Non défini/);
assert.doesNotMatch(html,/<input|<select|<button/i);
const unavailable=proto._technicalLimits.call({...fixture,_data:{}});
assert.match(unavailable,/non disponibles/);
'''
    result = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stderr
