# Trybatec options UI — navigation contract

This design rule applies to **every existing and future OptionsFlow screen**.

1. Read-only screens, notices, action selection, previous-screen and main-menu
   navigation **MUST** use native `async_show_menu` and matching
   `async_step_<id>` handlers. Each available return must be a single clickable
   menu row, not a select, radio, toggle or checkbox followed by Submit.
2. Input forms (`async_show_form`) are for **data entry and explicit validation
   only**. Use radio-list selectors exclusively for real data choices, such as
   units, meter identity, logging levels or correction type. Never add a
   "return to menu" choice to an editable form.
3. Because Home Assistant does not support a native click-to-navigate menu
   row inside a form, expose a preceding native navigation menu offering
   **Edit**, **Back** and **Main menu**. Closing an unsubmitted form discards
   changes. After a successful data submission, save first and route back to
   the logical screen; validation errors must keep the user on the form.
4. Historical decisions MUST retain a separate **explicit approval** form.
   The preceding native confirmation menu provides safe back/exit actions.
   Never persist a decision when opening a menu, going back, or editing a
   draft. Out-of-period corrections require their additional explicit approval.
5. Every menu option MUST have a valid handler in the actual Home Assistant
   options flow manager. Provide localized English/French labels in
   `strings.json`, `translations/en.json`, and `translations/fr.json`.
6. Test each screen with (a) direct navigation (no accidental write), (b)
   persistence after Submit, (c) invalid data that cannot be saved, (d)
   pending historical approval without write, and (e) a native HA FlowManager
   traversal. Do not equate green unit tests with a successful field trial.
