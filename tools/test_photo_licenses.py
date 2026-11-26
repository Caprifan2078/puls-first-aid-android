import unittest
from collect_ui_medicine_photos import normalize_license, LICENSES
class LicenseTests(unittest.TestCase):
    def test_cc0_alias(self):
        self.assertEqual(normalize_license("CC0"), "CC0 1.0")
    def test_no_broad_license_matching(self):
        self.assertNotIn(normalize_license("CC BY-NC-SA 4.0"), LICENSES)
        self.assertNotIn(normalize_license("CC BY-SA 4.0 or unknown"), LICENSES)
    def test_unchanged_supported_license(self):
        self.assertEqual(normalize_license("CC BY-SA 4.0"), "CC BY-SA 4.0")
