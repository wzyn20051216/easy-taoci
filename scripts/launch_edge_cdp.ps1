param(
    [Parameter(Mandatory = $false)]
    [string]$ProfileDir = "private/edge-profile",

    [Parameter(Mandatory = $false)]
    [ValidateRange(1024, 65535)]
    [int]$Port = 9222,

    [Parameter(Mandatory = $false)]
    [ValidateSet("netease", "163", "qq", "gmail", "outlook")]
    [string]$Provider = "netease",

    [Parameter(Mandatory = $false)]
    [string]$StartUrl = ""
)

$ErrorActionPreference = "Stop"
$resolvedProfile = [System.IO.Path]::GetFullPath($ProfileDir)
New-Item -ItemType Directory -Force -Path $resolvedProfile | Out-Null

$edgeCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft/Edge/Application/msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft/Edge/Application/msedge.exe"),
    (Join-Path $env:LOCALAPPDATA "Microsoft/Edge/Application/msedge.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if (-not $edgeCandidates) {
    throw "未找到 Microsoft Edge。请确认已安装 Edge。"
}

$providerUrls = @{
    "netease" = "https://mail.163.com/"
    "163" = "https://mail.163.com/"
    "qq" = "https://mail.qq.com/"
    "gmail" = "https://mail.google.com/"
    "outlook" = "https://outlook.live.com/mail/"
}

if (-not $StartUrl) {
    $StartUrl = $providerUrls[$Provider]
}

Start-Process -FilePath $edgeCandidates[0] -WindowStyle Normal -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$resolvedProfile",
    "--new-window",
    $StartUrl
)

Write-Host "已启动受控 Edge。请在浏览器中自行登录目标邮箱：$StartUrl"
Write-Host "CDP 地址：http://127.0.0.1:$Port"
