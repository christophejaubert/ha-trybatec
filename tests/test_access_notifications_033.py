"""Synthetic regression tests for Trybatec access notifications (#35).

Compile the two actual coordinator methods from source so the pure-Python
matrix exercises their logic without a live Home Assistant or vendor account.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "trybatec" / "coordinator.py"
)


class Notifications:
    def __init__(self) -> None:
        self.created: list[tuple[object, str, str, str]] = []
        self.dismissed: list[tuple[object, str]] = []

    def async_create(
        self, hass: object, message: str, *,
        title: str, notification_id: str,
    ) -> None:
        self.created.append((hass, message, title, notification_id))

    def async_dismiss(self, hass: object, notification_id: str) -> None:
        self.dismissed.append((hass, notification_id))


def _notifier() -> tuple[object, Notifications]:
    source = ast.parse(SOURCE.read_text(encoding="utf-8"))
    coordinator = next(
        node for node in source.body
        if isinstance(node, ast.ClassDef) and node.name == "TrybatecCoordinator"
    )
    methods = [
        node for node in coordinator.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_notify_access_issue", "_clear_access_issue"}
    ]
    assert len(methods) == 2
    test_class = ast.ClassDef(
        name="AccessNotifierUnderTest",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
        type_params=[],
    )
    module = ast.fix_missing_locations(
        ast.Module(body=[test_class], type_ignores=[])
    )
    notifications = Notifications()
    scope: dict[str, object] = {"persistent_notification": notifications}
    exec(compile(module, str(SOURCE), "exec"), scope)
    notifier = scope["AccessNotifierUnderTest"]()
    notifier.hass = object()
    notifier._access_notification_id = "trybatec_access_synthetic"
    notifier._access_notification_active = False
    notifier._access_notification_kind = None
    notifier._consecutive_connection_failures = 0
    return notifier, notifications


def test_repeated_connectivity_errors_are_deduplicated() -> None:
    notifier, notifications = _notifier()
    notifier._notify_access_issue(authorization=False)
    notifier._notify_access_issue(authorization=False)

    assert len(notifications.created) == 1
    assert notifier._access_notification_kind == "connectivity"
    assert "réessaiera" in notifications.created[0][1]
    assert notifications.created[0][3] == notifier._access_notification_id


def test_authentication_error_upgrades_connectivity_warning_in_place() -> None:
    notifier, notifications = _notifier()
    notifier._notify_access_issue(authorization=False)
    notifier._notify_access_issue(authorization=True)
    notifier._notify_access_issue(authorization=True)

    assert len(notifications.created) == 2
    assert notifications.created[0][3] == notifications.created[1][3]
    assert "réauthentifier" in notifications.created[1][1]
    assert notifier._access_notification_kind == "authentication"


def test_authentication_warning_cannot_be_downgraded_by_a_transient_error() -> None:
    notifier, notifications = _notifier()
    notifier._notify_access_issue(authorization=True)
    notifier._notify_access_issue(authorization=False)

    assert len(notifications.created) == 1
    assert notifier._access_notification_kind == "authentication"


def test_success_dismisses_incident_and_allows_future_notification() -> None:
    notifier, notifications = _notifier()
    notifier._notify_access_issue(authorization=False)
    notifier._consecutive_connection_failures = 3
    notifier._clear_access_issue()
    notifier._clear_access_issue()

    assert notifications.dismissed == [
        (notifier.hass, notifier._access_notification_id)
    ]
    assert notifier._consecutive_connection_failures == 0
    assert notifier._access_notification_kind is None
    assert notifier._access_notification_active is False

    notifier._notify_access_issue(authorization=True)
    assert len(notifications.created) == 2
    assert notifications.created[0][3] == notifications.created[1][3]
