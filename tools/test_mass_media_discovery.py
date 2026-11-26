import unittest,json
from unittest.mock import patch
from mass_media_discovery import INVENTORY,tasks,search_query,candidate,discover
class MassMediaTest(unittest.TestCase):
 def test_inventory(self):
    targets=json.loads(INVENTORY.read_text())["targets"]
    self.assertEqual(len(targets),395)
    self.assertEqual(len(tasks(targets)),790)
    self.assertEqual(len({r["id"] for r in targets}),395)
    self.assertEqual(sum(len(r.get("steps",[])) for r in targets),465)
    self.assertTrue(all(s["ru"] and s["en"] for r in targets for s in r.get("steps",[])))
 def test_license_and_mime(self):
    t={"id":"guide:cpr","kind":"guide","en":"CPR"}
    p={"title":"File:Example.jpg","imageinfo":[{"mime":"image/jpeg","size":1200,"sha1":"a"*40,"url":"https://upload.wikimedia.org/example.jpg","extmetadata":{"LicenseShortName":{"value":"CC BY 4.0"},"LicenseUrl":{"value":"https://creativecommons.org/licenses/by/4.0/"},"Artist":{"value":"Example"}}}]}
    result=candidate(p,t,"photo",search_query(t,"photo"))
    self.assertFalse(result["clinical_approval"])
    self.assertEqual(result["rights_review"],"pending")
    with self.assertRaises(ValueError):candidate(p,t,"video","test")
    p["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"]="CC BY-NC 4.0"
    with self.assertRaises(ValueError):candidate(p,t,"photo","test")
 def test_no_candidates(self):
    with patch("mass_media_discovery.api",return_value=[]):
        self.assertEqual(discover({"id":"medicine:x","kind":"medicine","en":"Example"},"photo"),([],0))
