"""FR/EN: real cross-module synthetic integration of #36/#37/#88 batch B."""
from __future__ import annotations

from datetime import date

import pytest

from custom_components.trybatec.energy_bulk_contract_l6 import crosscheck_36_37_120
from custom_components.trybatec.energy_bulk_lot_b_bridge import preview_lot_b_readonly
from custom_components.trybatec.history import build_history


ACCOUNT = "SYNTHETIC-ACCOUNT"
LOT = "SYNTHETIC-DWELLING"


def inputs():
    history = build_history(
        [{"lines": [{
            "lot": LOT, "fluide": "EF", "compteur": "SYNTHETIC-RETIRED",
            "depose": True,
            "indexes": [
                {"date": "2026-01-01T12:00:00+01:00", "value": 100},
                {"date": "2026-01-02T12:00:00+01:00", "value": 102},
            ],
        }]}],
        date(2026, 1, 1), date(2026, 1, 4),
        allowed_lots={LOT},
    )
    units = {key: "m³" for key in history["__physical_meters__"]}
    # An unavailable B15 ledger is unknown evidence, NEVER proof of absence.
    l6 = crosscheck_36_37_120(
        ledger=None, retired=None, observed=None, account=ACCOUNT, lot=LOT,
    )
    return {"history": history, "verified_units": units, "decisions": {},
            "account_key": ACCOUNT, "lot": LOT, "l6_crosscheck": l6}


def test_integrates_actual_history_lineage_and_l6_without_write_permission():
    result = preview_lot_b_readonly(**inputs())
    assert result["schema"] == "lot_b_readonly_preflight_v1"
    assert result["physical_sources_observed"] == 1
    assert result["consolidated_groups_observed"] == 1
    assert result["recorder_writes"] is False
    assert result["energy_writes"] is False
    assert result["admissible"] is False
    assert result["activation_authorized"] is False
    assert result["diagnostic"]["fluids"]["EF"]["lineage_verified"] is True
    assert result["diagnostic"]["fluids"]["EF"]["coverage_verified"] is True
    assert "crosscheck_37_physical_meter_count_mismatch" in (
        result["diagnostic"]["fluids"]["EF"]["blockers"]
    )


def test_repeated_preview_is_deterministic_and_does_not_modify_history():
    arg = inputs()
    first = preview_lot_b_readonly(**arg)
    second = preview_lot_b_readonly(**arg)
    assert first == second
    assert first["energy_writes"] is False


def test_unknown_archived_physical_generation_blocks_without_inventing_index():
    arg = inputs()
    arg["archived"] = {"extra": {
        "lot": LOT, "fluid": "EF", "serial": "SYNTHETIC-UNOBSERVED",
        "retired": True,
    }}
    result = preview_lot_b_readonly(**arg)
    assert result["physical_sources_observed"] == 2
    assert result["diagnostic"]["fluids"]["EF"]["status"] == "blocked"
    assert result["activation_authorized"] is False


def test_foreign_lot_rejected():
    arg = inputs()
    arg["lot"] = "SYNTHETIC-OTHER-LOT"
    with pytest.raises(ValueError):
        preview_lot_b_readonly(**arg)


def test_browser_like_positive_admissibility_claim_is_rejected():
    arg = inputs()
    arg["l6_crosscheck"]["admissible"] = True
    with pytest.raises(ValueError):
        preview_lot_b_readonly(**arg)
