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
