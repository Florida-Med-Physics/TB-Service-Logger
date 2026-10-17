import hashlib, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import html_application as app
class HtmlLauncherTests(unittest.TestCase):
    def test_stable_install_keeps_exact_html_and_does_not_rewrite_unchanged_file(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source.html';source.write_text('<!doctype html><p>Approved design</p>')
            home=root/'app'
            with patch.object(app,'html_resource',return_value=source),patch.object(app,'app_home',return_value=home):
                first=app.install_html();stamp=first.stat().st_mtime_ns
                second=app.install_html()
                self.assertEqual(first,second);self.assertEqual(second.read_bytes(),source.read_bytes());self.assertEqual(stamp,second.stat().st_mtime_ns)
                source.write_text('<!doctype html><p>Updated approved design</p>')
                self.assertEqual(app.install_html(),first);self.assertEqual(first.read_bytes(),source.read_bytes())
                self.assertEqual(list(home.glob('*.html')),[first])
    def test_failure_preserves_previous_html(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source.html';source.write_text('new');home=root/'app';home.mkdir();target=home/'TrueBeam-Local.html';target.write_text('previous')
            with patch.object(app,'html_resource',return_value=source),patch.object(app,'app_home',return_value=home),patch.object(app.os,'replace',side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):app.install_html()
            self.assertEqual(target.read_text(),'previous')
    def test_mac_launcher_opens_supported_browser_without_a_new_layout(self):
        with patch.object(app.sys,'platform','darwin'),patch.object(app.subprocess,'run') as run:
            run.return_value.returncode=0
            app.launch(Path('/private/tmp/TrueBeam-Local.html'))
            self.assertIn('Google Chrome',run.call_args.args[0]);self.assertEqual(run.call_args.args[0][-1],'file:///private/tmp/TrueBeam-Local.html')
if __name__=='__main__':unittest.main()
