import hashlib, tempfile, unittest
from pathlib import Path
from package_review_media import validate
class ReviewMedia(unittest.TestCase):
    def test_invalid_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.jpg";p.write_bytes(b"\xff\xd8\xfftest")
            with self.assertRaises(ValueError):validate({"clinical_approval":True},p)
    def test_valid_and_tampered_media(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.jpg";p.write_bytes(b"\xff\xd8\xfftest")
            row=dict(id="x",file="x.jpg",title="Fixture",author="QA",source="https://commons.wikimedia.org/wiki/File:Fixture.jpg",license="CC0 1.0",license_url="https://creativecommons.org/publicdomain/zero/1.0/",source_license_url="https://creativecommons.org/publicdomain/zero/1.0/",modifications="fixture",sha256=hashlib.sha256(p.read_bytes()).hexdigest(),original_sha256="a"*64,original_sha1="b"*40,reviewed_at="2026-11-27",rights_review="pending",visual_review="pending",clinical_approval=False,bytes=p.stat().st_size)
            validate(row,p)
            p.write_bytes(b"\xff\xd8\xffxxxx")
            with self.assertRaises(ValueError):validate(row,p)

    def test_coverage_distinguishes_step_matches_and_guide_matches(self):
        from package_review_media import summarize_coverage
        targets={"guide:a":{"kind":"guide"},"guide:b":{"kind":"guide"},"guide:a:step:0":{"kind":"guide","step_binding":{"topic":"a","index":0}},"medicine:x":{"kind":"medicine"}}
        rows=[{"file":"1.jpg","labels":[{"id":"guide:a:step:0"},{"id":"guide:a:step:0"}]},{"file":"2.mp4","labels":[{"id":"guide:a"},{"id":"unknown"}]}]
        c=summarize_coverage(targets,rows)
        self.assertEqual(c["guide"],{"targets":2,"photo_targets":1,"video_targets":1,"any_targets":1})
        self.assertEqual(c["guide_step"],{"targets":1,"photo_targets":1,"video_targets":0,"any_targets":1})
        self.assertEqual(c["medicine"]["any_targets"],0)
