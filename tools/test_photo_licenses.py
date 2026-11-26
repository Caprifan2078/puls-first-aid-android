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

from audit_media_rights import validate_license_metadata, validate_record, audit
import tempfile, hashlib, json
from pathlib import Path
class RightsGateTests(unittest.TestCase):
    def entry(self):
        return dict(id="sample",title="Sample",author="Creator",source="https://commons.wikimedia.org/wiki/File:Sample.jpg",license="CC BY-SA 4.0",license_url=LICENSES["CC BY-SA 4.0"],source_license_url=LICENSES["CC BY-SA 4.0"],derivative_license="CC BY-SA 4.0",original_sha256="a"*64,original_sha1="b"*40,sha256=hashlib.sha256(b"sample").hexdigest(),bytes=6,modifications="Resize",reviewed_at="2026-11-26",rights_review="pending",visual_review="pending")
    def test_mismatched_license_url(self):
        with self.assertRaises(ValueError):validate_license_metadata("CC BY-SA 4.0","https://creativecommons.org/licenses/by-nc/4.0/","CC BY-SA 4.0")
    def test_qa_not_release(self):
        row=self.entry()
        self.assertEqual(validate_record(row,"medicines","qa"),"sample.jpg")
        with self.assertRaises(ValueError):validate_record(row,"medicines","release")
    def test_sharealike_required(self):
        row=self.entry();row["derivative_license"]="CC BY 4.0"
        with self.assertRaises(ValueError):validate_record(row,"medicines","qa")
    def test_unknown_and_tampered_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/"media/medicines";folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps([self.entry()]))
            (folder/"sample.jpg").write_bytes(b"sample")
            self.assertEqual(len(audit(root,"qa")),1)
            (folder/"untracked.jpg").write_bytes(b"sample")
            with self.assertRaises(ValueError):audit(root,"qa")
            (folder/"untracked.jpg").unlink();(folder/"sample.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):audit(root,"qa")

    def test_firstaid_step_binding_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/"media/firstaid";folder.mkdir(parents=True)
            (root/"index.html").write_text('const PAGES='+json.dumps([dict(id="cpr",stepsRu=["RU"],stepsEn=["EN"])]),encoding="utf-8")
            row=self.entry()
            row.update(topic="cpr",file="sample.jpg",clinical_approval=True,rights_review="approved",visual_review="approved",review_ref="fixture-only",step_index=0,step_ru="RU",step_en="EN")
            (folder/"sample.jpg").write_bytes(b"sample")
            manifest=folder/"manifest.json"
            manifest.write_text(json.dumps([row]))
            self.assertEqual(len(audit(root,"qa")),1)
            row["step_en"]="changed"
            manifest.write_text(json.dumps([row]))
            with self.assertRaises(ValueError):audit(root,"qa")
            row["step_en"]="EN";row["topic"]="unknown"
            manifest.write_text(json.dumps([row]))
            with self.assertRaises(ValueError):audit(root,"qa")
