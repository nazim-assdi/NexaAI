$ErrorActionPreference = "Stop"

$partNames = @(
    "NexaAI-offline-source.zip.part00",
    "NexaAI-offline-source.zip.part01",
    "NexaAI-offline-source.zip.part02",
    "NexaAI-offline-source.zip.part03"
)
$expectedLength = 22073
$expectedSha256 = "354c8ace67fdf3f25809f891f64db7a5e3186b2e6a469b2768303ab1a9f0f122"
$root = $PSScriptRoot
$output = Join-Path $root "NexaAI-offline-source.zip"

foreach ($name in $partNames) {
    $path = Join-Path $root $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing ZIP part: $name. Run this script from a complete repository clone."
    }
}

$stream = [System.IO.File]::Create($output)
try {
    foreach ($name in $partNames) {
        $bytes = [System.IO.File]::ReadAllBytes((Join-Path $root $name))
        $stream.Write($bytes, 0, $bytes.Length)
    }
}
finally {
    $stream.Dispose()
}

$actualLength = (Get-Item -LiteralPath $output).Length
$actualHash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualLength -ne $expectedLength -or $actualHash -ne $expectedSha256) {
    Remove-Item -LiteralPath $output -Force
    throw "The reconstructed ZIP failed integrity verification. Download the repository again and retry."
}

Write-Host "NexaAI source archive verified." -ForegroundColor Green
Write-Host "Extracting source to .\NexaAI-source ..."
$destination = Join-Path $root "NexaAI-source"
if (Test-Path -LiteralPath $destination) {
    Remove-Item -LiteralPath $destination -Recurse -Force
}
Expand-Archive -LiteralPath $output -DestinationPath $destination -Force
Write-Host "Done. Open .\NexaAI-source and run setup.bat." -ForegroundColor Green
