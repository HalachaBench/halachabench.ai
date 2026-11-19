# Cloudflare helpers for the team preview. The API token is read from Windows Credential Manager
# (target HalachaBench/cloudflare-token) only for the call that needs it, and is never printed.
param(
  [Parameter(Mandatory = $true)][ValidateSet('access-org', 'deploy', 'access-apps', 'protect')][string]$Action,
  [string]$Project = 'halachabench-preview',
  [string[]]$Emails = @()
)
$ErrorActionPreference = 'Stop'
$Account = 'a966c50be786a15597dea5a10e74820c'

Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class CredR {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
  public struct CREDENTIAL { public int Flags; public int Type; public string TargetName; public string Comment;
    public long LastWritten; public int CredentialBlobSize; public IntPtr CredentialBlob; public int Persist;
    public int AttributeCount; public IntPtr Attributes; public string TargetAlias; public string UserName; }
  [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
  static extern bool CredReadW(string target, int type, int flags, out IntPtr cred);
  [DllImport("advapi32.dll")] static extern void CredFree(IntPtr cred);
  public static byte[] Read(string target) {
    IntPtr p; if (!CredReadW(target, 1, 0, out p)) throw new Exception("Credential " + target + " not found");
    try { var c = (CREDENTIAL)Marshal.PtrToStructure(p, typeof(CREDENTIAL)); var b = new byte[c.CredentialBlobSize];
      Marshal.Copy(c.CredentialBlob, b, 0, b.Length); return b; } finally { CredFree(p); } }
}
'@ -ErrorAction SilentlyContinue

function Get-Token { [Text.Encoding]::UTF8.GetString([CredR]::Read('HalachaBench/cloudflare-token')) }
function Cf($Method, $Path, $Body) {
  $h = @{ Authorization = "Bearer $(Get-Token)" }
  $args = @{ Method = $Method; Uri = "https://api.cloudflare.com/client/v4/accounts/$Account$Path"; Headers = $h }
  if ($Body) { $args.Body = ($Body | ConvertTo-Json -Depth 10); $args.ContentType = 'application/json' }
  Invoke-RestMethod @args
}

switch ($Action) {
  'access-org' {
    try { $r = Cf GET '/access/organizations'; "Zero Trust team domain: $($r.result.auth_domain)" }
    catch { "No Zero Trust organization yet (or no access): $($_.Exception.Message)" }
  }
  'access-apps' {
    (Cf GET '/access/apps').result | ForEach-Object { "$($_.name)  $($_.domain)  $($_.id)" }
  }
  'deploy' {
    $root = Split-Path $PSScriptRoot -Parent
    $env:CLOUDFLARE_ACCOUNT_ID = $Account
    $env:CLOUDFLARE_API_TOKEN = Get-Token
    try {
      npx --yes wrangler@4.45.0 pages project list 2>$null | Out-String | Select-String -Quiet $Project | Out-Null
      npx --yes wrangler@4.45.0 pages project create $Project --production-branch main 2>&1 | Out-String | Write-Output
      npx --yes wrangler@4.45.0 pages deploy (Join-Path $root 'preview-build') --project-name $Project --branch main --commit-dirty=true 2>&1 | Out-String | Write-Output
    } finally { Remove-Item Env:CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue }
  }
  'protect' {
    if ($Emails.Count -eq 0) { throw 'Pass -Emails a@b.com,c@d.com' }
    $include = @($Emails | ForEach-Object { @{ email = @{ email = $_ } } })
    $app = @{
      name = "HalachaBench team preview"; type = 'self_hosted'; session_duration = '720h'
      domain = "$Project.pages.dev"
      self_hosted_domains = @("$Project.pages.dev", "*.$Project.pages.dev")
      policies = @(@{ name = 'Team emails'; decision = 'allow'; include = $include })
    }
    $r = Cf POST '/access/apps' $app
    "Access app created: $($r.result.name) on $($r.result.domain), success $($r.success)"
  }
}
