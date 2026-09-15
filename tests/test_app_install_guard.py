"""A running bundle cannot be replaced underneath its loaded Python server."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "app_install_guard", ROOT / "scripts/check_app_closed.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class AppInstallGuard(unittest.TestCase):
    def test_only_launcher_processes_are_candidates(self):
        processes = "\n".join([
            "11 /opt/python -u -m gauntlet.launcher",
            "12 /opt/python run.py serve --port 8897",
            "13 /bin/sh -c echo -m gauntlet.launcher done",
            "14 /usr/bin/python3 -m gauntlet.launcher",
        ])
        self.assertEqual(guard.launcher_pids(processes), [11, 14])

    def test_installed_and_previously_moved_bundle_are_guarded(self):
        bundle = Path('/Users/player/Applications/Gauntlet.app')
        for root in (bundle, Path('/Users/player/Applications/Backups/old/Gauntlet.app')):
            with self.subTest(root=root):
                self.assertTrue(guard.belongs_to_bundle(root / 'Contents/Resources/app', [bundle]))
        self.assertFalse(guard.belongs_to_bundle(Path('/Users/player/project'), [bundle]))
        self.assertFalse(guard.belongs_to_bundle(Path('/Users/player/Other.app'), [bundle]))

    def test_process_inspection_failure_does_not_allow_replacement(self):
        with patch.object(guard.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ps', 5)):
            self.assertEqual(guard.main(['/Applications/Gauntlet.app']), 1)

    def test_active_bundle_is_refused_and_closed_bundle_is_allowed(self):
        with patch.object(guard, 'running_bundles', return_value=[11]):
            self.assertEqual(guard.main(['/Applications/Gauntlet.app']), 1)
        with patch.object(guard, 'running_bundles', return_value=[]):
            self.assertEqual(guard.main(['/Applications/Gauntlet.app']), 0)

    def test_build_checks_before_any_bundle_mutation(self):
        script = (ROOT / 'scripts/build_app.sh').read_text()
        self.assertLess(script.index('scripts/check_app_closed.py'), script.index('rm -rf'))

    def test_install_rechecks_after_staging_before_replacing(self):
        script = (ROOT / 'scripts/build_app.sh').read_text()
        last_check = script.rindex('scripts/check_app_closed.py')
        self.assertLess(script.index('cp -R "$APP" "$STAGING/"'), last_check)
        self.assertLess(last_check, script.index('mv "$INSTALLED" "$BACKUP_DIR/"'))


if __name__ == '__main__':
    unittest.main()
