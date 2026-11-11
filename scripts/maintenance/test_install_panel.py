import io
from pathlib import Path
import tarfile
import unittest
from install_panel import adapted_installer, members_checked, RULES, OVERRIDES


class PanelInstallTests(unittest.TestCase):
    def test_pinned_installer_and_entrypoint(self):
        original = Path('output/1panel-install/install.sh').read_bytes()
        result = adapted_installer(original)
        self.assertTrue(result.endswith(OVERRIDES))
        self.assertEqual(result.count('\nmain\n'), 1)
        with self.assertRaises(ValueError):
            adapted_installer(original + b'\n')

    def test_actual_package_members(self):
        with tarfile.open('output/1panel-install/1panel-v2.5.0-linux-amd64.tar.gz') as archive:
            self.assertEqual(len(members_checked(archive)), 20)

    def test_escape_and_links_rejected(self):
        for name, kind in [('outside', tarfile.REGTYPE),
                           ('1panel-v2.5.0-linux-amd64/../escape', tarfile.REGTYPE),
                           ('1panel-v2.5.0-linux-amd64/link', tarfile.SYMTYPE)]:
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                member = tarfile.TarInfo(name); member.type = kind
                archive.addfile(member)
            buffer.seek(0)
            with tarfile.open(fileobj=buffer) as archive:
                with self.assertRaises(ValueError):
                    members_checked(archive)


if __name__ == '__main__':
    unittest.main()
