import concurrent.futures
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

CLI = Path(__file__).resolve().parents[1] / "bin/config-baseline"
loader = importlib.machinery.SourceFileLoader("baseline_module", str(CLI))
spec = importlib.util.spec_from_loader(loader.name, loader)
MODULE = importlib.util.module_from_spec(spec)
loader.exec_module(MODULE)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="config baseline ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "configuration with spaces"
        self.root.mkdir()
        (self.root / "settings.json").write_text('{"enabled":true}\n')
        (self.root / "nested").mkdir()
        (self.root / "nested/config.txt").write_text("one\n")
        self.manifest = self.base / "reference.json"

    def run_cli(self, command, *options, expected=0, roots=None, manifest=None):
        arguments = [str(CLI), command, "--json", "--manifest", str(manifest or self.manifest)]
        for name, path in (roots or {"config": self.root}).items():
            arguments += ["--root", name + "=" + str(path)]
        result = subprocess.run(arguments + list(options), text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return json.loads(result.stdout)

    def baseline(self, **kwargs):
        return self.run_cli("snapshot", **kwargs)

    def edit_manifest(self, mutate):
        value = json.loads(self.manifest.read_text())
        mutate(value)
        self.manifest.write_text(json.dumps(value))

    def test_snapshot_and_unchanged_check(self):
        result = self.baseline()
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["entries"], 4)
        self.assertEqual(stat.S_IMODE(self.manifest.stat().st_mode), 0o600)
        result = self.run_cli("check")
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(result["findings"], [])

    def test_added_removed_and_content_changed(self):
        self.baseline()
        (self.root / "new.txt").write_text("new")
        (self.root / "nested/config.txt").unlink()
        (self.root / "settings.json").write_text("changed")
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["summary"], dict(added=1, removed=1, changed=1))
        self.assertEqual({row["path"]: row["state"] for row in result["findings"]},
                         {"new.txt": "added", "nested/config.txt": "removed", "settings.json": "changed"})

    def test_permission_changes_include_files_and_directories(self):
        self.baseline()
        (self.root / "settings.json").chmod(0o700)
        (self.root / "nested").chmod(0o750)
        result = self.run_cli("check", expected=3)
        self.assertEqual(len(result["findings"]), 2)
        self.assertTrue(all(row["fields"] == ["mode"] for row in result["findings"]))

    def test_mtime_changes_do_not_count_as_content_changes(self):
        self.baseline()
        os.utime(self.root / "settings.json", (100, 100))
        self.assertEqual(self.run_cli("check")["status"], "unchanged")

    def test_symlink_targets_are_not_traversed_or_hashed(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret").write_text("outside bytes")
        (self.root / "outside-link").symlink_to(outside, target_is_directory=True)
        (self.root / "dangling").symlink_to(self.base / "missing")
        (self.root / "loop").symlink_to("loop")
        self.baseline()
        value = json.loads(self.manifest.read_text())
        entry = next(row for row in value["entries"] if row["path"] == "outside-link")
        self.assertEqual(entry["type"], "symlink")
        self.assertEqual(entry["target"], str(outside))
        self.assertFalse(any("secret" in row["path"] for row in value["entries"]))
        (outside / "secret").write_text("changed outside")
        self.assertEqual(self.run_cli("check")["status"], "unchanged")
        (self.root / "outside-link").unlink()
        (self.root / "outside-link").symlink_to("nested")
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["findings"][0]["fields"], ["target"])

    def test_explicit_file_and_symlink_roots(self):
        link = self.base / "selected-link"
        link.symlink_to(self.root)
        roots = {"file": self.root / "settings.json", "link": link}
        self.baseline(roots=roots)
        result = self.run_cli("check", roots=roots)
        self.assertEqual(result["status"], "unchanged")
        entries = json.loads(self.manifest.read_text())["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual({row["type"] for row in entries}, {"file", "symlink"})

    def test_odd_filenames_round_trip(self):
        for name in ("new\nline.txt", "tab\tname", 'quote"slash\\', "-option", "snowman-☃"):
            (self.root / name).write_bytes(b"\x00binary\xff")
        self.baseline()
        self.assertEqual(self.run_cli("check")["status"], "unchanged")
        (self.root / "new\nline.txt").unlink()
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["findings"][0]["path"], "new\nline.txt")

    def test_root_path_with_trailing_newline(self):
        moved = self.base / "config\n"
        self.root.rename(moved)
        self.root = moved
        self.baseline()
        self.assertEqual(self.run_cli("check")["status"], "unchanged")

    def test_relocated_roots_keep_same_inventory(self):
        self.baseline()
        moved = self.base / "relocated configuration"
        self.root.rename(moved)
        self.root = moved
        self.assertEqual(self.run_cli("check")["status"], "unchanged")
        text = self.manifest.read_text()
        self.assertNotIn(str(self.base), text)

    def test_missing_root_is_removal_but_snapshot_refuses_it(self):
        self.baseline()
        shutil.rmtree(self.root)
        result = self.run_cli("check", expected=3)
        self.assertEqual(result["summary"]["removed"], 4)
        self.run_cli("snapshot", "--overwrite", expected=2)
        self.assertEqual(len(json.loads(self.manifest.read_text())["entries"]), 4)

    def test_snapshot_requires_explicit_overwrite(self):
        self.baseline()
        before = self.manifest.read_bytes()
        (self.root / "settings.json").write_text("changed")
        self.run_cli("snapshot", expected=2)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.run_cli("snapshot", "--overwrite")
        self.assertNotEqual(self.manifest.read_bytes(), before)
        self.assertEqual(self.run_cli("check")["status"], "unchanged")

    def test_manifest_inside_root_is_rejected_without_mutation(self):
        bad = self.root / "baseline.json"
        self.run_cli("snapshot", manifest=bad, expected=2)
        self.assertFalse(bad.exists())
        alias = self.base / "root-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.run_cli("snapshot", manifest=alias / "baseline.json", expected=2)
        self.assertFalse(bad.exists())

    def test_manifest_symlink_is_rejected_without_overwriting_target(self):
        target = self.base / "target.txt"
        target.write_text("retained")
        self.manifest.symlink_to(target)
        self.run_cli("snapshot", "--overwrite", expected=2)
        self.run_cli("check", expected=2)
        self.assertEqual(target.read_text(), "retained")

    def test_overlapping_roots_are_rejected(self):
        self.run_cli("snapshot", roots={"one": self.root, "two": self.root / "nested"}, expected=2)
        self.assertFalse(self.manifest.exists())

    def test_limits_fail_without_partial_manifest(self):
        for options in (("--max-entries", "1"), ("--max-bytes", "1"), ("--max-depth", "0")):
            with self.subTest(options=options):
                self.run_cli("snapshot", *options, expected=2)
                self.assertFalse(self.manifest.exists())
                self.assertEqual(list(self.base.glob(".config-baseline-*.tmp")), [])

    def test_fifo_is_rejected_without_blocking(self):
        os.mkfifo(self.root / "pipe")
        self.run_cli("snapshot", expected=2)
        self.assertFalse(self.manifest.exists())

    @unittest.skipIf(os.geteuid() == 0, "root bypasses ordinary permission checks")
    def test_unreadable_file_or_directory_is_an_error(self):
        self.baseline()
        for path in (self.root / "settings.json", self.root / "nested"):
            old_mode = stat.S_IMODE(path.stat().st_mode)
            path.chmod(0)
            try:
                result = self.run_cli("check", expected=2)
                self.assertEqual(result["status"], "error")
                self.assertNotIn("findings", result)
                self.run_cli("snapshot", "--overwrite", expected=2)
            finally:
                path.chmod(old_mode)
        self.assertEqual(self.run_cli("check")["status"], "unchanged")

    def test_invalid_and_incomplete_json_fail_closed(self):
        for value in ("", "{", "{}", "[]", '{"version":1,"version":1}', "NaN"):
            with self.subTest(value=value):
                self.manifest.write_text(value)
                result = self.run_cli("check", expected=2)
                self.assertEqual(result["status"], "error")
                self.assertEqual(self.manifest.read_text(), value)

    def test_invalid_schema_paths_and_duplicates_fail_closed(self):
        self.baseline()
        original = self.manifest.read_bytes()
        mutations = [
            lambda value: value.update(version=2),
            lambda value: value.update(version=True),
            lambda value: value["entries"].append(value["entries"][0]),
            lambda value: value["entries"][1].update(path="../escape"),
            lambda value: value["entries"][1].update(path="/absolute"),
            lambda value: value["entries"][1].update(mode=True),
            lambda value: value["entries"].pop(0),
            lambda value: value["entries"][-1].update(sha256="invalid"),
        ]
        for mutation in mutations:
            self.manifest.write_bytes(original)
            self.edit_manifest(mutation)
            result = self.run_cli("check", expected=2)
            self.assertEqual(result["status"], "error")

    def test_structural_manifest_omissions_and_invalid_hierarchy_fail_closed(self):
        self.baseline()
        original = json.loads(self.manifest.read_text())
        def child_below_file(value):
            child = dict(next(row for row in value["entries"] if row["type"] == "file"))
            child["path"] = "settings.json/impossible"
            value["entries"].append(child)
        mutations = [
            lambda value: value.update(entries=[]),
            lambda value: value.update(roots=["config", "config"]),
            lambda value: value.update(roots=["config", "omitted"]),
            lambda value: value["entries"][1].update(root="unknown"),
            lambda value: value["entries"][1].update(path="missing-parent/child"),
            lambda value: value["entries"][1].update(path="nested//child"),
            lambda value: value["entries"][1].update(path="nested/./child"),
            lambda value: value["entries"][1].update(path="nested/../child"),
            lambda value: value["entries"][1].update(path="nul\0path"),
            lambda value: value["entries"][1].update(extra="unexpected"),
            lambda value: value["entries"][-1].update(size=True),
            lambda value: value["entries"][-1].pop("sha256"),
            child_below_file,
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                value = json.loads(json.dumps(original))
                mutation(value)
                self.manifest.write_text(json.dumps(value))
                result = self.run_cli("check", expected=2)
                self.assertEqual(result["status"], "error")
                self.assertNotIn("findings", result)

    def test_oversized_manifest_and_deep_json_fail_without_clean_result(self):
        with self.manifest.open("wb") as target:
            target.truncate(MODULE.MANIFEST_LIMIT + 1)
        self.assertEqual(self.run_cli("check", expected=2)["status"], "error")
        self.manifest.write_text("[" * 1500 + "0" + "]" * 1500)
        self.assertEqual(self.run_cli("check", expected=2)["status"], "error")

    def test_current_inventory_budget_failure_preserves_reference(self):
        self.baseline()
        previous = self.manifest.read_bytes()
        (self.root / "oversized").write_text("x" * 128)
        result = self.run_cli("check", "--max-bytes", "64", expected=2)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("findings", result)
        self.run_cli("snapshot", "--overwrite", "--max-bytes", "64", expected=2)
        self.assertEqual(self.manifest.read_bytes(), previous)
        self.assertEqual(list(self.base.glob(".config-baseline-*.tmp")), [])

    def test_root_names_must_match_manifest_exactly(self):
        self.baseline()
        self.run_cli("check", roots={"different": self.root}, expected=2)

    def test_concurrent_no_overwrite_snapshot_has_one_winner(self):
        def attempt(_):
            return subprocess.run([str(CLI), "snapshot", "--json", "--manifest", str(self.manifest),
                                   "--root", "config=" + str(self.root)], capture_output=True, text=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(result.returncode == 0 for result in results), 1)
        self.assertTrue(all(result.returncode in (0, 2) for result in results))
        self.assertEqual(self.run_cli("check")["status"], "unchanged")
        self.assertEqual(list(self.base.glob(".config-baseline-*.tmp")), [])

    def test_failed_publication_preserves_existing_manifest_and_cleans_stage(self):
        self.baseline()
        before = self.manifest.read_bytes()
        manifest = json.loads(before)
        with mock.patch.object(MODULE.os, "replace", side_effect=OSError("simulated rename failure")):
            with self.assertRaises(OSError):
                MODULE.publish(self.manifest, manifest, True)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(list(self.base.glob(".config-baseline-*.tmp")), [])

    def test_symlink_swap_during_file_open_never_reads_target(self):
        secret = self.base / "outside-secret"
        secret.write_text("outside")
        target = self.root / "settings.json"
        actual_open = os.open
        def swap(path, flags, *args, **kwargs):
            if path == "settings.json" and kwargs.get("dir_fd") is not None:
                target.unlink()
                target.symlink_to(secret)
            return actual_open(path, flags, *args, **kwargs)
        with mock.patch.object(MODULE.os, "open", side_effect=swap):
            with self.assertRaises(OSError):
                MODULE.Inventory(100, 10000, 10).scan({"config": self.root}, False)
        self.assertEqual(secret.read_text(), "outside")

    def test_inputs_are_never_executed_and_no_subprocess_is_used(self):
        marker = self.base / "executed"
        script = self.root / "hook.sh"
        script.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
        script.chmod(0o755)
        self.baseline()
        with mock.patch("subprocess.run", side_effect=AssertionError("no process execution allowed")), \
                mock.patch("socket.socket", side_effect=AssertionError("no network access allowed")):
            entries = MODULE.Inventory(100, 10000, 10).scan({"config": self.root}, False)
        self.assertGreater(len(entries), 0)
        self.assertFalse(marker.exists())

    def test_self_contained_install_with_spaces(self):
        prefix = self.base / "installed tool"
        result = subprocess.run(["make", "install", "PREFIX=" + str(prefix)], cwd=CLI.parents[1], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(prefix / "bin/config-baseline"), "--version"], cwd=self.base, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_case_alias_cannot_hide_manifest_self_inclusion(self):
        selected = self.base / "SelectedConfig"
        selected.mkdir()
        (selected / "config.txt").write_text("config")
        alias = self.base / "selectedconfig"
        if not alias.exists():
            self.skipTest("filesystem treats these case variants as different entries")
        inside = alias / "inside.json"
        self.run_cli("snapshot", roots={"config": selected}, manifest=inside, expected=2)
        self.assertFalse((selected / "inside.json").exists())

    def test_case_alias_roots_cannot_overlap(self):
        selected = self.base / "SelectedConfig"
        selected.mkdir()
        (selected / "nested").mkdir()
        alias = self.base / "selectedconfig"
        if not alias.exists():
            self.skipTest("filesystem treats these case variants as different entries")
        for other in (alias, alias / "nested"):
            self.run_cli("snapshot", roots={"one": selected, "two": other}, expected=2)
        self.assertFalse(self.manifest.exists())

    def test_hardlink_identity_cannot_hide_selected_manifest_or_duplicate_root(self):
        selected = self.root / "settings.json"
        alias = self.base / "hardlink.json"
        os.link(selected, alias)
        original = selected.read_bytes()
        self.run_cli("snapshot", "--overwrite", roots={"config": selected}, manifest=alias, expected=2)
        self.run_cli("snapshot", roots={"one": selected, "two": alias}, expected=2)
        self.assertEqual(selected.read_bytes(), original)
        self.assertEqual(alias.read_bytes(), original)

    def test_dotdot_root_cannot_hide_manifest_self_inclusion(self):
        root = self.root / "nested" / ".."
        inside = self.root / "reference.json"
        self.run_cli("snapshot", roots={"config": root}, manifest=inside, expected=2)
        self.assertFalse(inside.exists())

    def test_root_disappearing_after_scan_is_error_not_partial_inventory(self):
        actual_stat = os.stat
        root_calls = 0
        def disappear(path, *args, **kwargs):
            nonlocal root_calls
            if path == self.root.name and kwargs.get("dir_fd") is not None:
                root_calls += 1
                if root_calls == 3:
                    shutil.rmtree(self.root)
            return actual_stat(path, *args, **kwargs)
        with mock.patch.object(MODULE.os, "stat", side_effect=disappear):
            with self.assertRaises(MODULE.BaselineError):
                MODULE.Inventory(100, 10000, 10).scan({"config": self.root}, True)


if __name__ == "__main__":
    unittest.main()
