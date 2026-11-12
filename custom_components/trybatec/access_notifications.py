"""Static, secret-free notifications following Home Assistant's instance language.

Persistent notifications are shared across users; the language is that of the
Home Assistant instance. No username, UUID, response body or token is passed
into this formatter.
"""

_MESSAGES = {
    "en": {
        "title": "Trybatec access unavailable",
        "authentication": (
            "Trybatec authentication was rejected. Open Home Assistant "
            "integrations to reauthenticate this connection."
        ),
        "access_denied": (
            "The Trybatec account is not authorized to read the configured "
            "property's meters. Check its permissions in the Trybatec portal."
        ),
        "connectivity": (
            "Trybatec has not responded after several attempts. Meter data "
            "is temporarily unavailable; the integration will try again."
        ),
    },
    "fr": {
        "title": "Accès Trybatec indisponible",
        "authentication": (
            "Trybatec a refusé l'authentification. Ouvrez les intégrations "
            "Home Assistant pour réauthentifier cette connexion."
        ),
        "access_denied": (
            "Ce compte Trybatec n'est pas autorisé à consulter les relevés "
            "de cette copropriété. Vérifiez ses droits sur le portail Trybatec."
        ),
        "connectivity": (
            "Trybatec ne répond plus après plusieurs essais. Les relevés sont "
            "temporairement indisponibles ; une nouvelle tentative sera effectuée."
        ),
    },
}


def access_notification_text(kind: str, language: str | None) -> tuple[str, str]:
    """Return title and message with no private data embedded."""
    lang = (language or "en").replace("_", "-").split("-", 1)[0].lower()
    catalog = _MESSAGES.get(lang, _MESSAGES["en"])
    return catalog["title"], catalog[kind]
