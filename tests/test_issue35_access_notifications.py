"""Issue #35 bilingual access notifications: pure tests, no network."""

import unittest

from custom_components.trybatec.access_notifications import access_notification_text


class NotificationLanguageTests(unittest.TestCase):
    def test_french_variants(self):
        for lang in ("fr", "fr-FR", "fr_FR"):
            for kind in ("authentication", "access_denied", "connectivity"):
                with self.subTest(lang=lang, kind=kind):
                    title, message = access_notification_text(kind, lang)
                    self.assertIn("Accès", title)
                    self.assertIn("Trybatec", message)

    def test_english_variants_and_fallback(self):
        for lang in ("en", "en-US", "de", None):
            for kind in ("authentication", "access_denied", "connectivity"):
                with self.subTest(lang=lang, kind=kind):
                    title, message = access_notification_text(kind, lang)
                    self.assertEqual(title, "Trybatec access unavailable")
                    self.assertIn("Trybatec", message)

    def test_language_is_not_a_format_input(self):
        for kind in ("authentication", "access_denied", "connectivity"):
            title, message = access_notification_text(kind, "fr")
            for private_text in (
                "SYNTHETIC_SECRET_VALUE", "synthetic-only@example.invalid",
                "FAKE_BEARER_TOKEN",
            ):
                self.assertNotIn(private_text, title + message)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(KeyError):
            access_notification_text("SYNTHETIC_SECRET_VALUE", "en")


if __name__ == "__main__":
    unittest.main()
