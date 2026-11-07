# 0.2.0b5 — Historical review safety, thermal units and meter isolation

Experimental GitHub pre-release. No automatic Recorder writes. Back up Home Assistant including Recorder and .storage before importing.

- Diehl SHARKY 774 measures thermal energy in configurable kWh, MWh or GJ; DN 15 alone does not prove the portal unit. CET defaults to unverified until an administrator selects the confirmed source unit, with conversion to kWh where appropriate.
- Live meter parsing no longer merges the same serial across multiple lots or fluids. Historical lot, fluid and physical meter isolation remains mandatory.
- The options review wizard refreshes in memory after each choice without 24 new API calls. Saved decisions remain persistent after restart; sources can be fetched again when needed.
- Out-of-interval accounting allocation requires an additional affirmative confirmation and written reason. Original timestamps remain separate from accounting dates; sparse allocations remain separate from daily measurements.
- Regression tests cover the new approval path, account isolation and verified thermal units.

Remaining limitations: Recorder imports remain asynchronous and lack atomic acknowledgement; no automatic series migration or Energy-dashboard switching. The options UI is not a full bulk wizard and no broad Trybatec customer-account verification exists. Former CET entities may retain incorrectly assumed kWh statistics; review before reusing.
