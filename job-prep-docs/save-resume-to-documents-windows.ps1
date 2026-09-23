# Saves Sonaal Topno resume PDF to your Documents folder (Windows)
$folder = Join-Path $env:USERPROFILE "Documents\Job-Prep"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$url = "https://raw.githubusercontent.com/Sonaal8/Data-Analysis/master/job-prep-docs/SONAAL_TOPNO_Resume.pdf"
$out = Join-Path $folder "SONAAL_TOPNO_Resume.pdf"
Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
Write-Host "Saved to: $out"
explorer $folder
