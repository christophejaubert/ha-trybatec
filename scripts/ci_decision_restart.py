"""Persistence regression: real HA Core processes and a physical .storage file.

Invoke write and verify separately with the same temporary config directory.
Integration code is imported from the selected release via PYTHONPATH.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from homeassistant.core import HomeAssistant
from custom_components.trybatec.history_store import load_decisions, save_decision
from custom_components.trybatec.history_review import reading_key, review_candidates, apply_review_to_meter

ENTRY = "synthetic-ci-entry-persistence"
LOT, FLUID, SERIAL = "SYNTHETIC-LOT", "EF", "SYNTHETIC-METER"
START = datetime.fromisoformat("2025-01-01T12:00:00+01:00")
END = datetime.fromisoformat("2025-01-20T12:00:00+01:00")
AMOUNT = 105.25
ACCOUNTING_DATE = "2024-12-31T23:59:00+01:00"
REASON = "Synthetic year-end accounting reassignment for restart verification"


def meter(value=AMOUNT):
    return {"lot": LOT, "fluid": FLUID, "serial": SERIAL,
            "indexes": {START: 100.0, END: value}}


def identity(value=AMOUNT):
    return reading_key(LOT, FLUID, SERIAL, END, value)


def candidates(m, saved):
    return review_candidates({(LOT, FLUID, SERIAL): m}, saved)


async def execute(stage, config_dir):
    config_dir.mkdir(parents=True, exist_ok=True)
    hass = HomeAssistant(str(config_dir))
    await hass.async_start()
    try:
        if stage == "write":
            assert await load_decisions(hass, ENTRY) == {}
            pending = candidates(meter(), {})
            assert len(pending) == 1 and pending[0]["decision"] == "unreviewed"
            saved = await save_decision(hass, ENTRY, identity(), {
                "action": "correct", "mode": "accounting",
                "timestamp": ACCOUNTING_DATE, "reason": REASON,
                "out_of_period_confirmed": True,
            })
            assert saved[identity()]["action"] == "correct"
            key = "trybatec.review_v4_" + sha256(ENTRY.encode()).hexdigest()[:20]
            file = config_dir / ".storage" / key
            assert file.is_file(), "Home Assistant did not write a physical storage file"
            envelope = json.loads(file.read_text(encoding="utf-8"))
            assert envelope["version"] == 1
            assert envelope["data"]["decisions"][identity()]["reason"] == REASON
            print(f"WRITE: separate HA process {os.getpid()}, durable on-disk file verified")
        elif stage == "verify":
            saved = await load_decisions(hass, ENTRY)
            assert set(saved) == {identity()}
            choice = saved[identity()]
            assert choice["action"] == "correct" and choice["mode"] == "accounting"
            assert choice["timestamp"] == ACCOUNTING_DATE
            assert choice["reason"] == REASON
            assert choice["out_of_period_confirmed"] is True
            review = candidates(meter(), saved)
            assert len(review) == 1 and review[0]["decision"] == "correct"
            assert not any(x["decision"] == "unreviewed" for x in review)
            indexes, allocation, clashes = apply_review_to_meter(meter(), saved)
            assert not clashes and indexes[END] == AMOUNT and len(indexes) == 2
            assert allocation[END] == (
                datetime.fromisoformat(ACCOUNTING_DATE).astimezone(timezone.utc),
                identity(), True,
            )
            # Source changes are not authorized by the old decision.
            amended = candidates(meter(AMOUNT + 1.0), saved)
            assert len(amended) == 1
            assert amended[0]["key"] != identity()
            assert amended[0]["decision"] == "unreviewed"
            assert await load_decisions(hass, ENTRY) == saved
            print(f"RESTART: new HA process {os.getpid()}, decision and resync verified")
        else:
            raise ValueError("Unknown stage")
    finally:
        await hass.async_stop()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("write", "verify"):
        raise SystemExit("Usage: ci_decision_restart.py write|verify config_directory")
    asyncio.run(execute(sys.argv[1], Path(sys.argv[2]).resolve()))
