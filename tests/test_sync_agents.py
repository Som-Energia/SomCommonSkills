import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_agents.py"


class SyncAgentsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.toolkit = self.root / "toolkit"
        self.consumer = self.root / "consumer"
        self.toolkit.mkdir()
        self.consumer.mkdir()
        (self.toolkit / "instructions").mkdir()
        (self.toolkit / "instructions" / "base.md").write_text(
            "# Shared instructions\n", encoding="utf-8"
        )
        self.write_skill(
            self.toolkit,
            "shared-one",
            "Shared skill content.\n",
            resource="references/shared.txt",
        )
        self.pin = self.initialize_toolkit()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_skill(self, root, directory, body, resource=None, name=None):
        skill_directory = root / directory
        skill_directory.mkdir(parents=True)
        skill_name = name or directory
        skill = (
            "---\n"
            f"name: {skill_name}\n"
            "description: A test skill.\n"
            "---\n\n"
            f"{body}"
        )
        (skill_directory / "SKILL.md").write_text(skill, encoding="utf-8")
        if resource:
            resource_path = skill_directory / resource
            resource_path.parent.mkdir(parents=True, exist_ok=True)
            resource_path.write_text("shared resource\n", encoding="utf-8")
            (skill_directory / "SKILL.md").write_text(
                skill + f"\n[Resource]({resource})\n", encoding="utf-8"
            )
        return skill_directory

    def initialize_toolkit(self):
        subprocess.run(["git", "init", "-q", str(self.toolkit)], check=True)
        subprocess.run(
            ["git", "-C", str(self.toolkit), "config", "user.email", "test@example.org"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.toolkit), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.toolkit), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.toolkit), "commit", "-qm", "fixture"], check=True
        )
        return subprocess.check_output(
            ["git", "-C", str(self.toolkit), "rev-parse", "HEAD"], text=True
        ).strip()

    def write_manifest(self, common=None, local_skills=".agents/local-skills", overrides=None):
        manifest = {
            "source": {
                "repository": "https://example.org/toolkit.git",
                "revision": self.pin,
                "skill_root": ".",
            },
            "local_instructions": "AGENTS.local.md",
            "local_skills": local_skills,
            "common_skills": ["shared-one"] if common is None else common,
            "overrides": overrides or {},
        }
        (self.consumer / "agent-toolkit.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        (self.consumer / "AGENTS.local.md").write_text(
            "# Local instructions\n", encoding="utf-8"
        )
        (self.consumer / local_skills).mkdir(parents=True, exist_ok=True)

    def run_sync(self, *arguments, expected=0, use_toolkit=True):
        command = [sys.executable, str(SCRIPT), "--repo", str(self.consumer)]
        if use_toolkit:
            command.extend(["--toolkit-dir", str(self.toolkit)])
        result = subprocess.run(
            command + list(arguments),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_composes_instructions_copies_resources_and_is_idempotent(self):
        self.write_manifest()

        self.run_sync()
        generated = (self.consumer / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLess(generated.index("# Shared instructions"), generated.index("# Local instructions"))
        self.assertEqual(
            (self.consumer / ".agents/skills/shared-one/references/shared.txt").read_text(
                encoding="utf-8"
            ),
            "shared resource\n",
        )
        first_state = (self.consumer / ".agent-toolkit-state.json").read_bytes()

        self.run_sync()

        self.assertEqual((self.consumer / ".agent-toolkit-state.json").read_bytes(), first_state)

    def test_replaces_a_common_skill_as_a_whole(self):
        local = self.write_skill(
            self.consumer / ".agents/local-skills",
            "replacement",
            "Only replacement content.\n",
            name="shared-one",
        )
        self.write_manifest(overrides={"shared-one": ".agents/local-skills/replacement"})

        self.run_sync()

        generated = (self.consumer / ".agents/skills/shared-one/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Only replacement content.", generated)
        self.assertNotIn("Shared skill content.", generated)
        self.assertFalse((self.consumer / ".agents/skills/shared-one/references/shared.txt").exists())
        self.assertTrue(local.exists())

    def test_manual_edits_are_not_overwritten(self):
        self.write_manifest()
        self.run_sync()
        output = self.consumer / "AGENTS.md"
        output.write_text("manual edit\n", encoding="utf-8")

        self.run_sync(expected=2)

        self.assertEqual(output.read_text(encoding="utf-8"), "manual edit\n")

    def test_check_is_read_only_and_detects_drift(self):
        self.write_manifest()
        self.run_sync()
        output = self.consumer / "AGENTS.md"
        before = output.read_bytes()

        self.run_sync("--check")
        self.assertEqual(output.read_bytes(), before)

        output.write_text("manual edit\n", encoding="utf-8")
        self.run_sync("--check", expected=1)
        self.assertEqual(output.read_text(encoding="utf-8"), "manual edit\n")

    def test_unresolved_duplicate_skill_names_are_rejected(self):
        local_root = self.consumer / ".agents/local-skills"
        self.write_skill(local_root, "duplicate", "Duplicate.\n", name="shared-one")
        self.write_manifest()

        result = self.run_sync(expected=2)

        self.assertIn("duplicate", result.stderr.lower())
        self.assertFalse((self.consumer / "AGENTS.md").exists())

    def test_existing_generated_content_requires_explicit_adoption(self):
        self.write_manifest()
        output = self.consumer / "AGENTS.md"
        output.write_text("original local instructions\n", encoding="utf-8")

        self.run_sync(expected=2)
        self.assertEqual(output.read_text(encoding="utf-8"), "original local instructions\n")

        self.run_sync("--adopt")
        self.assertIn("# Shared instructions", output.read_text(encoding="utf-8"))

    def test_traversing_local_skill_paths_are_rejected(self):
        self.write_manifest(local_skills="../outside")

        self.run_sync(expected=2)

        self.assertFalse((self.consumer / "AGENTS.md").exists())

    def test_manifest_revision_must_match_the_toolkit_checkout(self):
        self.write_manifest()
        manifest = yaml.safe_load(
            (self.consumer / "agent-toolkit.yml").read_text(encoding="utf-8")
        )
        manifest["source"]["revision"] = "0" * 40
        (self.consumer / "agent-toolkit.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        self.run_sync(expected=2)

        self.assertFalse((self.consumer / "AGENTS.md").exists())

    def test_fetches_the_pinned_commit_when_no_checkout_is_provided(self):
        self.write_manifest()
        manifest = yaml.safe_load(
            (self.consumer / "agent-toolkit.yml").read_text(encoding="utf-8")
        )
        manifest["source"]["repository"] = self.toolkit.as_uri()
        (self.consumer / "agent-toolkit.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

        self.run_sync(use_toolkit=False)

        state = json.loads(
            (self.consumer / ".agent-toolkit-state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["revision"], self.pin)

    def test_removing_a_managed_skill_preserves_unmanaged_files(self):
        self.write_manifest(common=["shared-one"])
        self.run_sync()
        unmanaged_in_skill = self.consumer / ".agents/skills/shared-one/local-note.txt"
        unmanaged_in_skill.write_text("keep inside former skill\n", encoding="utf-8")
        alien = self.consumer / ".agents/skills/unmanaged/notes.txt"
        alien.parent.mkdir(parents=True)
        alien.write_text("keep\n", encoding="utf-8")

        self.write_manifest(common=[])
        self.run_sync()

        self.assertFalse((self.consumer / ".agents/skills/shared-one/SKILL.md").exists())
        self.assertEqual(
            unmanaged_in_skill.read_text(encoding="utf-8"), "keep inside former skill\n"
        )
        self.assertEqual(alien.read_text(encoding="utf-8"), "keep\n")

    def test_missing_resource_references_are_rejected_before_writing(self):
        skill = self.toolkit / "shared-one/SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\n[Missing](not-here.md)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.toolkit), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.toolkit), "commit", "-qm", "bad reference"],
            check=True,
        )
        self.pin = subprocess.check_output(
            ["git", "-C", str(self.toolkit), "rev-parse", "HEAD"], text=True
        ).strip()
        self.write_manifest()

        result = self.run_sync(expected=2)

        self.assertIn("not-here.md", result.stderr)
        self.assertFalse((self.consumer / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
