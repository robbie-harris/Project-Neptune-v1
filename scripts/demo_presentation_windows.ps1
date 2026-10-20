param([string]$Action='layout',[string]$OutputPath='')

function Get-PresentationPlacement {
 param([int]$WorkX,[int]$WorkY,[int]$WorkWidth,[int]$WorkHeight,
       [int]$StonefishOuterWidth,[int]$StonefishOuterHeight)
 $half=[int][Math]::Floor($WorkWidth/2)
 # Preserve the measured outer size, including decorations. Never fit the renderer
 # to a panel: a narrow desktop may require overlap instead of a larger framebuffer.
 $sfX=$WorkX+[int][Math]::Max(0,[Math]::Floor(($half-$StonefishOuterWidth)/2))
 $sfY=$WorkY+[int][Math]::Max(0,[Math]::Floor(($WorkHeight-$StonefishOuterHeight)/2))
 $guiX=[int][Math]::Max($WorkX+$half+6,$sfX+$StonefishOuterWidth+12)
 if($WorkX+$WorkWidth-12-$guiX -lt 736){$guiX=$WorkX+$half+6}
 [PSCustomObject]@{
  StonefishX=$sfX;StonefishY=$sfY
  GuiX=$guiX;GuiY=$WorkY+12
  GuiWidth=[int][Math]::Max(320,$WorkX+$WorkWidth-12-$guiX)
  GuiHeight=[int][Math]::Max(320,$WorkHeight-24)
 }
}

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class NeptuneWindows {
 public delegate bool Callback(IntPtr h,IntPtr p);
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback c,IntPtr p);
 [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int command);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int w,int height,uint flags);
 public static Dictionary<string,IntPtr> Find() {
  var found=new Dictionary<string,IntPtr>();
  EnumWindows((h,p)=> { var s=new StringBuilder(512);GetWindowText(h,s,512);string t=s.ToString();
   if(IsWindowVisible(h)&&(t=="Stonefish Simulator"||t.StartsWith("Stonefish Simulator (")||t=="Project Neptune - Demo V0"||t.StartsWith("Project Neptune - Demo V0 ("))){found[t.Contains("Stonefish Simulator")?"Stonefish Simulator":"Project Neptune - Demo V0"]=h;}
   return true;
  },IntPtr.Zero);return found;
 }
}
'@
[NeptuneWindows]::SetProcessDPIAware() | Out-Null
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$work=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
if($Action -eq 'geometry') {
 # GUI-only client pixels from the Windows work area; excludes the taskbar.
 # Stonefish always launches at 1280x720 independently of these dimensions.
 [PSCustomObject]@{width=[int](($work.Width-36)/2)-16;height=$work.Height-64} | ConvertTo-Json -Compress
 exit
}
# One demo instance is expected; ordinary movable windows, never always-on-top.
$deadline=[DateTime]::UtcNow.AddSeconds(75)
do {
 $found=[NeptuneWindows]::Find()
 if($found.Count -ge 2){break}
 Start-Sleep -Milliseconds 250
} while([DateTime]::UtcNow -lt $deadline)
if($found.Count -lt 2){Write-Error 'Presentation windows did not both appear';exit 1}
$sfRect=New-Object NeptuneWindows+Rect
[NeptuneWindows]::GetWindowRect($found['Stonefish Simulator'],[ref]$sfRect)|Out-Null
$placement=Get-PresentationPlacement -WorkX $work.X -WorkY $work.Y `
 -WorkWidth $work.Width -WorkHeight $work.Height `
 -StonefishOuterWidth ($sfRect.Right-$sfRect.Left) -StonefishOuterHeight ($sfRect.Bottom-$sfRect.Top)
foreach($name in @('Stonefish Simulator','Project Neptune - Demo V0')) {
 $h=$found[$name]
 if($Action -eq 'layout') {
  if($name -eq 'Stonefish Simulator') {
   # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE. Move only: do not restore,
   # maximize, stretch or resize the OpenGL window, even on a small desktop.
   [NeptuneWindows]::SetWindowPos($h,[IntPtr]::Zero,$placement.StonefishX,$placement.StonefishY,0,0,0x15)|Out-Null
  } else {
   [NeptuneWindows]::ShowWindow($h,9)|Out-Null
   [NeptuneWindows]::SetWindowPos($h,[IntPtr]::Zero,$placement.GuiX,$placement.GuiY,$placement.GuiWidth,$placement.GuiHeight,0x14)|Out-Null
   [NeptuneWindows]::SetForegroundWindow($h)|Out-Null
  }
 }
 $r=New-Object NeptuneWindows+Rect
 [NeptuneWindows]::GetWindowRect($h,[ref]$r)|Out-Null
 [PSCustomObject]@{Title=$name;X=$r.Left;Y=$r.Top;Width=$r.Right-$r.Left;Height=$r.Bottom-$r.Top} | ConvertTo-Json -Compress
}
if($OutputPath) {
 Start-Sleep -Milliseconds 500
 $bounds=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
 $bmp=New-Object System.Drawing.Bitmap($bounds.Width,$bounds.Height)
 $g=[System.Drawing.Graphics]::FromImage($bmp)
 $g.CopyFromScreen($bounds.X,$bounds.Y,0,0,$bounds.Size)
 $bmp.Save($OutputPath,[System.Drawing.Imaging.ImageFormat]::Png)
 $g.Dispose();$bmp.Dispose()
}
