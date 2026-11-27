import unittest
from mega_media import tasklist
class MegaTasks(unittest.TestCase):
    def test_tasks_are_balanced_unique_and_include_video(self):
        ts={"guide:cpr":{"id":"guide:cpr","kind":"guide","en":"CPR","critical":True},"guide:cpr:step:0":{"id":"guide:cpr:step:0","kind":"guide","en":"Step","step_binding":{"topic":"cpr"}},"medicine:x":{"id":"medicine:x","kind":"medicine","en":"Example"}}
        tasks=tasklist(ts,[{"target":"guide:cpr","term":"chest compressions"}])
        self.assertEqual(len(tasks),6)
        self.assertEqual(len({(t["target"],t["kind"],t["term"]) for t in tasks}),len(tasks))
        self.assertTrue(any(t["kind"]=="video" for t in tasks))
        self.assertFalse(any(t["target"].endswith("step:0") for t in tasks))
