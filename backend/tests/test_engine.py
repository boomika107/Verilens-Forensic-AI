import os, tempfile, unittest
from app.engine import statements as S, comparison as C, timeline as T, integrity as I, rag as R

H = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class Engine(unittest.TestCase):
    def ev(self, **k):
        return {"id": 1, "description": "x", "source_type": "cctv", "source_file": "c.mp4", "source_ref": "00:02:14", **k}

    def test_claim(self):
        c = S.extract_claim("I was at home at 8:00 PM on 2024-03-05.")
        self.assertEqual((c["claimed_time"], c["claimed_location"], c["claimed_date"]), ("20:00", "home", "2024-03-05"))

    def test_times_dates(self):
        self.assertEqual(S.parse_time("around 9 o'clock in the evening"), "21:00")
        self.assertEqual(S.parse_time("12:15 am"), "00:15")
        self.assertIsNone(S.parse_time("I stayed home"))
        self.assertEqual(S.parse_date("on 5 March 2024"), "2024-03-05")
        self.assertIsNone(S.parse_date("on 31/02/2024"))

    def test_inconsistent(self):
        c = S.extract_claim("I was at home at 8:00 PM.")
        f = C.compare([c], [self.ev(time="20:05", location="railway station")])
        self.assertEqual(f[0]["label"], C.INCONSISTENT)
        self.assertEqual(f[0]["evidence"][0]["source_file"], "c.mp4")
        self.assertEqual(f[0]["human_review_status"], "pending")

    def test_other_labels(self):
        c = S.extract_claim("I was at home at 8:00 PM.")
        self.assertEqual(C.compare([c], [self.ev(time="20:10", location="home")])[0]["label"], C.CONSISTENT)
        self.assertEqual(C.compare([c], [self.ev(time="23:00", location="home")])[0]["label"], C.INSUFFICIENT)
        self.assertEqual(C.compare([S.extract_claim("I was home.")], [])[0]["label"], C.UNVERIFIED)
        self.assertEqual(C.compare([c], [self.ev(time="20:05", location=None)])[0]["label"], C.REVIEW)

    def test_statement_not_independent_and_date_mismatch(self):
        c = S.extract_claim("I was at home at 8:00 PM on 2024-03-05.")
        self.assertEqual(C.compare([c], [self.ev(source_type="statement", time="20:00", location="home")])[0]["label"], C.INSUFFICIENT)
        self.assertEqual(C.compare([c], [self.ev(date="2024-03-06", time="20:00", location="home")])[0]["label"], C.INSUFFICIENT)

    def test_timeline(self):
        t = T.build_timeline([{"id": 1, "time": "21:00"}, {"id": 2}, {"id": 3, "time": "08:00"}])
        self.assertEqual([e["id"] for e in t["ordered"]], [3, 1])
        self.assertEqual([e["id"] for e in t["unplaced"]], [2])

    def test_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"abc")
        self.assertTrue(I.verify(f.name, H))
        with open(f.name, "ab") as g:
            g.write(b"x")
        self.assertFalse(I.verify(f.name, H))
        os.unlink(f.name)

    def test_rag(self):
        p = [{"text": "The vehicle was seen at the railway station at 8:05 PM.", "source_file": "a.txt", "ref": "p1"}]
        self.assertEqual(R.retrieve("railway station", p)[0]["source_file"], "a.txt")
        self.assertEqual(R.answer("quantum physics", p)["citations"], [])

    def test_extract_events(self):
        ev = S.extract_events_from_text("A van arrived at the depot at 21:30. Nothing else happened.", "doc.txt p1")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["time"], "21:30")


if __name__ == "__main__":
    unittest.main()
