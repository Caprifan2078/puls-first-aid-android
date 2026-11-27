import hashlib,subprocess,tempfile,unittest
from pathlib import Path
from compact_review_videos import compact_to_budget,compact_one,probe
class Compact(unittest.TestCase):
    def test_real_video_duration_and_original_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/("a"*40+".mp4")
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=640x480:rate=25","-t","3","-c:v","libx264","-crf","10","-pix_fmt","yuv420p",str(p)],check=True)
            before=p.stat().st_size;sha=hashlib.sha256(p.read_bytes()).hexdigest()
            row={"file":p.name,"bytes":before,"sha256":sha,"modifications":"fixture","clinical_approval":False}
            result=compact_one(p,row,before//2)
            self.assertIsNotNone(result);self.assertLess(row["bytes"],before)
            self.assertEqual(row["compacted_from_sha256"],sha)
            self.assertAlmostEqual(probe(p)[0],3,delta=.2)
            self.assertFalse(row["clinical_approval"])
    def test_under_budget_unchanged(self):
        rows=[{"bytes":100,"file":"x.jpg"}]
        self.assertEqual(compact_to_budget(rows,Path("."),100)["changes"],[])
