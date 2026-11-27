import unittest
from targeted_gap_media import medicine_match
class GapSearch(unittest.TestCase):
    def test_name_and_alias(self):
        self.assertTrue(medicine_match("Diclofenac gel package.jpg","Diclofenac gel",""))
        self.assertTrue(medicine_match("Panadol box.jpg","Paracetamol","панадол Panadol"))
        self.assertFalse(medicine_match("Unrelated tablets.jpg","Paracetamol",""))
        self.assertFalse(medicine_match("Paracetamolxyz.jpg","Paracetamol",""))
