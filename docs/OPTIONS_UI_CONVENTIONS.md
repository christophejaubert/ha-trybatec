# Trybatec options UI — navigation and release-quality contract

This rule applies to current and future OptionsFlow screens. It supersedes
the b10 practice of inserting intermediate menus before ordinary forms.

1. The **six principal destinations** are direct Home Assistant menu choices:
   `settings`, `diagnostics`, `meter_units`, `history_overview`,
   `history_meters`, `history_review`. Do **not** interpose new menu
   screens between the principal menu and these existing steps.
2. Native `async_show_menu` is appropriate for **read-only screens,
   informational notices and action decisions**, with one-click Back/Main
   entries when that screen already is a menu. A click must not write an
   option, historical decision or Recorder statistic.
3. Home Assistant **cannot mix a native clickable menu row with data fields
   in the same `async_show_form`**. Forms therefore only collect and validate
   real data; they do not contain post-save navigation radio fields.
   Users may close an unsubmitted form with X to abandon changes.
   After successful validation, save first and return to the logical menu
   or meter list. Do not add a preceding menu merely to offer Edit/Back.
4. Historical review decisions use the established one-click
   `history_decision` menu, followed by a separate **mandatory confirmation**
   form. Correction details are drafts until confirmation. Out-of-period
   decisions require their additional explicit approval. Navigating alone
   never persists a historical action.
5. Each native menu ID must have a matching handler. The three checked-in
   localization sources (`strings.json`, `translations/en.json`,
   `translations/fr.json`) must include a **nonempty label** for every
   menu option, and Home Assistant's actual translation loader must return
   that label for French and English.
6. Required regression tests: exactly six direct root destinations;
   actual Home Assistant FlowManager traversal; translated, nonempty
   menu strings; unit persistence across navigation and restart-like
   re-entry; invalid form input rejection; historical approval never
   inferred from navigation; and no incidental Trybatec portal polling.
7. Passing CI is **necessary but not sufficient** to publish. After test
   success, a real frontend visual check on the supported Home Assistant
   instance (French menu and all relevant screens) and explicit owner
   acceptance are mandatory. A green backend test is not a visual test.

No PR, CI result, test assertion or documentation text independently
authorizes merging, tagging, publishing, historical imports or changing a
real Home Assistant installation.
