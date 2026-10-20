"""Test pure Windows placement math without finding, moving or opening windows."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest


POWERSHELL = (shutil.which('pwsh') or
              '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')


@unittest.skipUnless(Path(POWERSHELL).is_file(), 'Windows PowerShell unavailable')
class PlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helper = Path(__file__).with_name('demo_presentation_windows.ps1').resolve()
        if shutil.which('wslpath') and POWERSHELL.endswith('.exe'):
            helper = subprocess.check_output(['wslpath', '-w', str(helper)], text=True).strip()
        quoted = "'"+str(helper).replace("'", "''")+"'"
        # Parse only. Execute just the pure function, never the helper's top-level
        # Windows API calls, discovery loop or SetWindowPos branch.
        code = '''
$tokens=$null;$parseErrors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(PATH,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw ($parseErrors|Out-String)}
$function=$ast.Find({param($node)
 $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
 $node.Name -eq 'Get-PresentationPlacement'
},$true)
. ([ScriptBlock]::Create($function.Extent.Text))
@(
 (Get-PresentationPlacement 0 0 2560 1540 1296 760)
 (Get-PresentationPlacement 0 0 3840 2160 1296 760)
 (Get-PresentationPlacement -2560 40 2560 1540 1296 760)
 (Get-PresentationPlacement 0 0 1920 1080 1296 760)
) | ConvertTo-Json -Compress
'''.replace('PATH', quoted)
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', code],
                                capture_output=True, text=True, check=True, timeout=15)
        cls.plans = json.loads(result.stdout)

    def test_current_monitor_left_renderer_centered_vertically_gui_right(self):
        plan = self.plans[0]
        self.assertEqual((plan['StonefishX'], plan['StonefishY']), (0, 390))
        self.assertEqual((plan['GuiX'], plan['GuiY']), (1308, 12))
        self.assertEqual((plan['GuiWidth'], plan['GuiHeight']), (1240, 1516))
        self.assertGreaterEqual(plan['GuiX'], plan['StonefishX']+1296+12)
        self.assertEqual(plan['GuiX']+plan['GuiWidth'], 2560-12)

    def test_large_monitor_centers_renderer_inside_left_half(self):
        plan = self.plans[1]
        self.assertEqual((plan['StonefishX'], plan['StonefishY']), (312, 700))
        self.assertLessEqual(plan['StonefishX']+1296, 3840//2)
        self.assertGreater(plan['GuiX'], 3840//2)

    def test_work_area_offset_and_narrow_monitor(self):
        offset, narrow = self.plans[2:]
        self.assertEqual(offset['StonefishX'], -2560)
        self.assertEqual(offset['StonefishY'], 430)
        self.assertEqual(offset['GuiX'], -1252)
        self.assertEqual(narrow['StonefishX'], 0)
        self.assertEqual(narrow['StonefishY'], 160)
        self.assertEqual(narrow['GuiX']+narrow['GuiWidth'], 1920-12)
        # Placement plans contain positions for Stonefish, never resize requests.
        for plan in self.plans:
            self.assertNotIn('StonefishWidth', plan)
            self.assertNotIn('StonefishHeight', plan)


if __name__ == '__main__':
    unittest.main()
