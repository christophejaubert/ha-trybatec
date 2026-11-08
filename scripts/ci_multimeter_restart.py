"""Two-process b7 multi-meter import crash/recovery using durable HA Store.

Called independently as 'write' then 'verify', with same config directory.
Recorder is deliberately modeled by a file-backed SQLite queue adapter here;
the separate pytest integration tests exercise genuine HA Recorder SQLite.
No vendor network access or production configuration.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from custom_components.trybatec import history_services
from custom_components.trybatec.history import build_history
from custom_components.trybatec.const import DOMAIN


ENTRY = "ci-durable-recorder-three-meters"


def sample_history():
    lines = []
    for i in range(3):
        base = 100 + 10 * i
        lines.append({
            "compteur": f"CI-PHYSICAL-{i}", "fluide": "EF",
            "lot": "CI-ONLY-LOT", "depose": False, "indexUnit": "m3",
            "indexes": [
                {"date": "2026-01-02T12:00:00+01:00", "value": base},
                {"date": "2026-01-03T12:00:00+01:00", "value": base + 1.5},
                {"date": "2026-01-04T12:00:00+01:00", "value": base + 3.0},
            ],
        })
    return build_history(
        [{"lines": lines}], date(2026, 1, 1), date(2026, 1, 5)
    )


def action(*, retry=False):
    return SimpleNamespace(data={
        "confirm": True, "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        "include_cold_water": True,
        "include_hot_water": False,
        "include_heating": False,
        "retry_pending": retry,
    })


async def run(stage: str, folder: Path, fault: str):
    folder.mkdir(parents=True, exist_ok=True)
    hass = HomeAssistant(str(folder))
    conn = sqlite3.connect(folder / "ci_recorded_rows.sqlite3")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rows("
        "id TEXT NOT NULL, stamp TEXT NOT NULL, amount REAL NOT NULL,"
        "PRIMARY KEY(id, stamp))"
    )
    conn.commit()
    await hass.async_start()
    try:
        # The real HA Recorder backend is checked by a separate E2E test.
        # This adapter allows a physical HA process boundary with deterministic
        # persisted queue semantics, regardless of worker shutdown timing.
        hass.config.components.add("recorder")

        async def statistics_handler(call):
            result = {}
            for stat_id in call.data["statistic_ids"]:
                values = conn.execute(
                    "SELECT stamp, amount FROM rows WHERE id = ? ORDER BY stamp",
                    (stat_id,),
                ).fetchall()
                result[stat_id] = [
                    {"start": stamp, "sum": amount}
                    for stamp, amount in values
                ]
            return {"statistics": result}

        hass.services.async_register(
            "recorder", "get_statistics", statistics_handler,
            supports_response=SupportsResponse.ONLY,
        )

        coordinator = SimpleNamespace(
            entry=SimpleNamespace(
                entry_id=ENTRY, unique_id=ENTRY, options={},
            )
        )

        async def fake_load(_hass, _call):
            return (
                coordinator, date(2026, 1, 1),
                date(2026, 1, 5), sample_history(), 1,
            )

        async def accept_test_admin(_hass, _call):
            return None

        history_services._load = fake_load
        history_services._coordinator = lambda *_: coordinator
        history_services._require_admin = accept_test_admin
        enqueue_count = 0

        def queue(_hass, metadata, buckets):
            nonlocal enqueue_count
            enqueue_count += 1
            if fault == "before_first_queue" and enqueue_count == 1 and stage == "write":
                raise RuntimeError("Synthetic queue interruption #1")
            if fault == "before_second_queue" and enqueue_count == 2 and stage == "write":
                raise RuntimeError("Synthetic queue interruption #2")
            for row in buckets:
                stat_id = metadata["statistic_id"]
                stamp = row["start"].astimezone(timezone.utc).isoformat()
                existing = conn.execute(
                    "SELECT amount FROM rows WHERE id=? AND stamp=?",
                    (stat_id, stamp),
                ).fetchone()
                if existing is not None:
                    if abs(existing[0] - row["sum"]) > 1e-6:
                        raise AssertionError("Changed Recorder row on retry")
                    continue
                conn.execute(
                    "INSERT INTO rows(id,stamp,amount) VALUES (?,?,?)",
                    (stat_id, stamp, row["sum"]),
                )
            conn.commit()
            if fault == "after_third_queue" and enqueue_count == 3 and stage == "write":
                raise RuntimeError("Synthetic post-enqueue interruption #3")

        history_services.async_add_external_statistics = queue
        real_store = history_services.Store
        if fault == "before_ledger" and stage == "write":
            class RefusingStore:
                def __init__(self, *args):
                    self.real = real_store(*args)

                async def async_load(self):
                    return await self.real.async_load()

                async def async_save(self, _value):
                    raise OSError("Simulated failed durable journal")

            history_services.Store = RefusingStore

        store_key = "trybatec.history_v5_" + sha256(
            ENTRY.encode("utf-8")
        ).hexdigest()[:20]
        store = Store(hass, 1, store_key)
        if stage == "write":
            try:
                await history_services.async_import_history(hass, action())
            except ServiceValidationError:
                pass
            else:
                raise AssertionError("First process must experience injected interruption")
            ledger = await store.async_load()
            actual_rows = conn.execute("SELECT count(*) FROM rows").fetchone()[0]
            expected_rows = {
                "before_ledger": 0, "before_first_queue": 0,
                "before_second_queue": 3, "after_third_queue": 9,
            }[fault]
            assert actual_rows == expected_rows, (actual_rows, expected_rows)
            if fault == "before_ledger":
                assert ledger is None
            else:
                assert isinstance(ledger, dict)
                assert len(ledger["pending"]) == 3
                assert len(ledger["pending_fingerprint"]) == 64
            print(f"WRITE: {fault}, {actual_rows} durable rows")
        elif stage == "verify":
            ledger = await store.async_load()
            if fault == "before_ledger":
                assert ledger is None
                result = await history_services.async_import_history(hass, action())
                assert len(result["series"]) == 3
            else:
                assert len(ledger["pending"]) == 3
                initial = await history_services.async_verify_history(
                    hass, action()
                )
                prior_verified = {
                    "before_first_queue": 0, "before_second_queue": 1,
                    "after_third_queue": 3,
                }[fault]
                assert len(initial["verified"]) == prior_verified, initial
                if prior_verified < 3:
                    remaining = await history_services.async_import_history(
                        hass, action(retry=True)
                    )
                    assert len(remaining["series"]) == 3 - prior_verified
                    assert enqueue_count == 3 - prior_verified
                else:
                    assert enqueue_count == 0
            final = await history_services.async_verify_history(hass, action())
            assert final["status"] == "verified" and not final["pending"]
            verified_ledger = await store.async_load()
            assert verified_ledger["pending"] == {}
            assert len(verified_ledger["series"]) == 3
            rows = conn.execute("SELECT id,stamp,amount FROM rows").fetchall()
            assert len(rows) == 9
            for stat_id in {r[0] for r in rows}:
                sums = [
                    amount for _, _, amount in conn.execute(
                        "SELECT id,stamp,amount FROM rows WHERE id=? ORDER BY stamp",
                        (stat_id,),
                    ).fetchall()
                ]
                assert sums == [0.0, 1.5, 3.0]
            print(f"RESTART: {fault}, 3 meters and 9 rows verified")
        else:
            raise ValueError("Expected write or verify")
    finally:
        await hass.async_stop()
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: ci_multimeter_restart.py write|verify dir fault")
    asyncio.run(run(sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3]))
