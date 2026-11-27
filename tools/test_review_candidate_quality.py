import unittest,tempfile
from pathlib import Path
from review_candidate_quality import evaluate,save_csv
class ReviewQuality(unittest.TestCase):
    def fixture(self):
        targets={"medicine:a":{"kind":"medicine","ru":"А","en":"Alpha"},"medicine:b":{"kind":"medicine","ru":"Б","en":"Beta"},"guide:one:step:0":{"kind":"guide","ru":"Шаг","en":"Step","step_binding":{"topic":"one"},"critical":True}}
        row={"original_sha1":"a"*40,"file":"a"*40+".jpg","clinical_approval":False,"rights_review":"pending","visual_review":"pending","title":"Alpha","labels":[{"id":"medicine:a"},{"id":"medicine:b"}]}
        return targets,row
    def test_multi_drug_and_missing_step(self):
        t,r=self.fixture();q,g,s=evaluate(t,[r])
        self.assertIn("multiple-drug-identities",q[0]["flags"])
        self.assertEqual(q[0]["priority"],0)
        self.assertEqual(s["groups"]["guide_step"]["without_either"],1)
        self.assertEqual(s["approved"],0)
    def test_never_accept_approved_or_duplicate(self):
        t,r=self.fixture()
        with self.assertRaises(ValueError):evaluate(t,[r,r])
        with self.assertRaises(ValueError):evaluate(t,[{**r,"clinical_approval":True}])
    def test_csv_formula_guard(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.csv";save_csv(p,[{"name":"=1+1"}])
            self.assertIn("'=1+1",p.read_text(encoding="utf-8-sig"))
