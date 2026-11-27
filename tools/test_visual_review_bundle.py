import unittest
from visual_review_bundle import sample_times,card,page
class ContactSheet(unittest.TestCase):
    def test_samples(self):
        self.assertEqual(sample_times(10),[1,5,8.5])
        self.assertEqual(sample_times(0),[0])
    def test_untrusted_titles_are_escaped(self):
        q={"format":"photo","title":"<script>alert(1)</script>","flags":"", "author":"x","license":"CC0","source":"https://commons.wikimedia.org/wiki/File:x","file":"a.jpg"}
        h=card({"labels":[]},q,{"previews":[{"path":"thumbs/a.jpg","at":0}]})
        self.assertNotIn("<script>",h)
        self.assertIn("&lt;script&gt;",h)
        self.assertIn("pending",h)
        self.assertIn("Не инструкция",page("QA",h))

    def test_real_jpeg_and_corrupt_file(self):
        import tempfile,zipfile,hashlib
        from pathlib import Path
        from PIL import Image
        from visual_review_bundle import make_previews
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/"input.jpg";Image.new("RGB",(640,480),"red").save(original,"JPEG")
            for data,expected in [(original.read_bytes(),1),(b"not an image",0)]:
                name="a"*40+".jpg";apk=root/"test.apk"
                with zipfile.ZipFile(apk,"w") as z:z.writestr("assets/media/review/"+name,data)
                result=make_previews(apk,{"file":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()},root)
                self.assertEqual(len(result["previews"]),expected)
                self.assertEqual(len(result["errors"]),1-expected)
                if expected:
                    with Image.open(root/("a"*40+"-0.jpg")) as im:self.assertEqual(im.size,(320,240))
