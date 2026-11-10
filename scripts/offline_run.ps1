<#
.SYNOPSIS
Experimental offline CubeMX guard using a temporary capability-free AppContainer.
.DESCRIPTION
Provide a pre-isolated working directory, a new profile name and its pre-authorized
SID, a guard launch JSON template, plan, and new output paths. No ACLs are changed.
The template argv is wrapped by the launcher; its env and cwd are passed to guard.
The launcher's target cwd is always the target executable's directory, even when
the template specifies a different cwd. Standard input/output/error are inherited.
This does not fully isolate the filesystem. Abrupt termination of this PowerShell
process can leave the profile behind; delete it manually after checking ownership.
.EXAMPLE
.\offline_run.ps1 -WorkDir C:\isolated -ProfileName my-new-profile -ProfileSid S-1-15-2-... -Python C:\python\python.exe -Launch C:\isolated\template.json -Plan C:\isolated\plan.json -Events C:\isolated\events.json -Transcript C:\isolated\transcript.log
#>
param(
 [Parameter(Mandatory=$true)][string]$WorkDir,
 [Parameter(Mandatory=$true)][string]$ProfileName,
 [Parameter(Mandatory=$true)][string]$ProfileSid,
 [Parameter(Mandatory=$true)][string]$Python,
 [Parameter(Mandatory=$true)][string]$Launch,
 [Parameter(Mandatory=$true)][string]$Plan,
 [Parameter(Mandatory=$true)][string]$Events,
 [Parameter(Mandatory=$true)][string]$Transcript
)
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class OfflineProfile {
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] public static extern int CreateAppContainerProfile(string name,string display,string desc,IntPtr caps,uint count,out IntPtr sid);
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] public static extern int DeleteAppContainerProfile(string name);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool ConvertSidToStringSid(IntPtr sid,out IntPtr text);
 [DllImport("advapi32.dll")] public static extern IntPtr FreeSid(IntPtr sid);
 [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr ptr);
}
'@
$created=$false; $sid=[IntPtr]::Zero; $sidText=[IntPtr]::Zero; $exitCode=1
$generatedLaunch=$null; $exe=$null
try {
 if (-not [IO.Path]::IsPathRooted($WorkDir) -or -not (Test-Path -LiteralPath $WorkDir -PathType Container)) { throw 'WorkDir must be an existing absolute directory' }
 if (-not [IO.Path]::IsPathRooted($Python) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Python must be an existing absolute executable' }
 $template=Get-Content -LiteralPath $Launch -Raw -Encoding UTF8 | ConvertFrom-Json
 if (-not $template.argv -or -not [IO.Path]::IsPathRooted([string]$template.argv[0])) { throw 'Template argv must start with an absolute executable' }
 $id=[guid]::NewGuid().ToString('N')
 $exe=Join-Path $WorkDir "offline-launcher-$id.exe"
 $generatedLaunch=Join-Path $WorkDir "offline-launch-$id.json"
 $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
 if (-not (Test-Path -LiteralPath $csc -PathType Leaf)) { throw '.NET Framework C# compiler not found' }
 & $csc /nologo /target:exe "/out:$exe" (Join-Path $PSScriptRoot 'offline_launcher.cs')
 if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Launcher compilation failed' }
 $hr=[OfflineProfile]::CreateAppContainerProfile($ProfileName,$ProfileName,'temporary offline profile',[IntPtr]::Zero,0,[ref]$sid)
 if ($hr -ne 0) { throw ('Create profile failed: 0x{0:X8}' -f $hr) }
 $created=$true
 if (-not [OfflineProfile]::ConvertSidToStringSid($sid,[ref]$sidText)) { throw 'Cannot convert profile SID' }
 if ([Runtime.InteropServices.Marshal]::PtrToStringUni($sidText) -ne $ProfileSid) { throw 'Profile SID mismatch' }
 $wrapped=@{argv=@($exe,$ProfileSid)+@($template.argv)}
 if ($null -ne $template.cwd) { $wrapped.cwd=$template.cwd }
 if ($null -ne $template.env) { $wrapped.env=$template.env }
 $json=$wrapped | ConvertTo-Json -Depth 20
 [IO.File]::WriteAllText($generatedLaunch,$json,(New-Object System.Text.UTF8Encoding($false)))
 & $Python (Join-Path $PSScriptRoot 'cubemx_guard.py') --launch $generatedLaunch --plan $Plan --events $Events --transcript $Transcript
 $exitCode=$LASTEXITCODE
} catch { [Console]::Error.WriteLine("offline_run: $_"); $exitCode=1 }
finally {
 if ($sidText -ne [IntPtr]::Zero) { [void][OfflineProfile]::LocalFree($sidText) }
 if ($sid -ne [IntPtr]::Zero) { [void][OfflineProfile]::FreeSid($sid) }
 if ($created) { $hr=[OfflineProfile]::DeleteAppContainerProfile($ProfileName); if ($hr -ne 0) { [Console]::Error.WriteLine(('Profile cleanup failed: 0x{0:X8}' -f $hr)); $exitCode=1 } }
 foreach ($path in @($generatedLaunch,$exe)) { if ($path -and (Test-Path -LiteralPath $path)) { try { Remove-Item -LiteralPath $path -Force } catch { [Console]::Error.WriteLine("Temporary file cleanup failed: $path"); $exitCode=1 } } }
}
exit $exitCode
