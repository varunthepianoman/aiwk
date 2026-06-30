import unittest

from aiwk.config import Config, dump_config, load_config

class ConfigTests(unittest.TestCase):
    def test_config_round_trip(self):
        with self.subTest("generated YAML"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as directory:
                expected = Config(
                    project="demo", repo="/repo with spaces", workflow_folder="custom_workflows",
                    project_folder="custom_workflows/demo", relevant_paths=["src/", "tests/"],
                    ignored_scratch_dirs=["scratch/"], test_commands={"unit": "python -m unittest"},
                )
                path = Path(directory) / "aiwk.yaml"
                dump_config(expected, path)
                self.assertEqual(load_config(path), expected)
