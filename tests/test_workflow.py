import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import assembly_cli as cli


class WorkflowTests(unittest.TestCase):
    def make_job(self, root):
        src = root / "snapshot.json"
        src.write_text(json.dumps({"model_path": "C:\\CAD\\Demo.iam", "components": [
            {"id": "Base:1", "name": "Base"}, {"id": "Bolt:1", "name": "Bolt"}]}), encoding="utf-8")
        job = root / "job"
        self.assertEqual(cli.main(["init", "--snapshot", str(src), "--job", str(job)]), 0)
        return job

    def test_init_and_review(self):
        with tempfile.TemporaryDirectory() as d:
            job = self.make_job(pathlib.Path(d))
            self.assertEqual(cli.main(["validate", "--job", str(job)]), 0)
            self.assertFalse(cli.read_json(job / "validation.json")["release_ready"])
            self.assertEqual(cli.main(["approve", "--job", str(job), "--step", "all", "--reviewer", "Tester"]), 0)
            self.assertTrue(cli.evaluate(cli.read_json(job / "plan.json"))["release_ready"])
            self.assertEqual(cli.main(["preview", "--job", str(job)]), 0)
            self.assertIn("不是 CAD 幾何圖", (job / "preview-steps.svg").read_text(encoding="utf-8"))

    def test_bad_steps_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            job = self.make_job(pathlib.Path(d))
            plan = cli.read_json(job / "plan.json")
            plan["steps"][1]["add"] = ["Base:1"]
            result = cli.evaluate(plan)
            self.assertFalse(result["valid"])

    def test_prevent_overwrite_and_release_without_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            job = self.make_job(pathlib.Path(d))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["init", "--snapshot", str(pathlib.Path(d)/"snapshot.json"), "--job", str(job)]), 2)
                self.assertEqual(cli.main(["release", "--job", str(job), "--reviewer", "Tester"]), 2)


if __name__ == "__main__":
    unittest.main()
