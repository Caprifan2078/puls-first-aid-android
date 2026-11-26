import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from audit_media_rights import verify_apk
class PackagedMetadataTests(unittest.TestCase):
    def test_tampered_and_missing_manifest_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"assets";root.mkdir()
            (root/"media/firstaid").mkdir(parents=True)
            (root/"index.html").write_text("guide")
            (root/"media/credits.json").write_text("{}")
            (root/"media/firstaid/manifest.json").write_text("[]")
            photo=root/"media/firstaid/photo.jpg";photo.write_bytes(b"test")
            rows=[{"asset":"media/firstaid/photo.jpg","sha256":hashlib.sha256(photo.read_bytes()).hexdigest()}]
            apk=Path(d)/"test.apk"
            def write(changes=None,omit=None,extra=None):
                with zipfile.ZipFile(apk,"w") as z:
                    for p in root.rglob("*"):
                        if not p.is_file():continue
                        name="assets/"+p.relative_to(root).as_posix()
                        if name!=omit:z.writestr(name,(changes or {}).get(name,p.read_bytes()))
                    for name,data in (extra or {}).items():z.writestr(name,data)
            write();verify_apk(apk,root,rows)
            for target in ("assets/index.html","assets/media/credits.json","assets/media/firstaid/manifest.json","assets/media/firstaid/photo.jpg"):
                write(changes={target:b"tampered"})
                with self.assertRaises(ValueError):verify_apk(apk,root,rows)
            write(omit="assets/media/firstaid/manifest.json")
            with self.assertRaises(ValueError):verify_apk(apk,root,rows)
            write(extra={"assets/media/kits/manifest.json":b"[]"})
            with self.assertRaises(ValueError):verify_apk(apk,root,rows)
if __name__=="__main__":unittest.main()
