<# Derive an AppContainer SID from a profile name without creating a profile or changing ACLs. #>
param([Parameter(Mandatory=$true)][string]$ProfileName)
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class OfflineProfileSid {
 [DllImport("userenv.dll",CharSet=CharSet.Unicode)] public static extern int DeriveAppContainerSidFromAppContainerName(string name,out IntPtr sid);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool ConvertSidToStringSid(IntPtr sid,out IntPtr text);
 [DllImport("advapi32.dll")] public static extern IntPtr FreeSid(IntPtr sid);
 [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr ptr);
}
'@
$sid=[IntPtr]::Zero; $text=[IntPtr]::Zero
try {
 $hr=[OfflineProfileSid]::DeriveAppContainerSidFromAppContainerName($ProfileName,[ref]$sid)
 if($hr -ne 0){throw ('SID derivation failed: 0x{0:X8}' -f $hr)}
 if(-not [OfflineProfileSid]::ConvertSidToStringSid($sid,[ref]$text)){throw 'SID conversion failed'}
 [Runtime.InteropServices.Marshal]::PtrToStringUni($text)
} finally {
 if($text -ne [IntPtr]::Zero){[void][OfflineProfileSid]::LocalFree($text)}
 if($sid -ne [IntPtr]::Zero){[void][OfflineProfileSid]::FreeSid($sid)}
}
