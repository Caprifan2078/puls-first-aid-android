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
