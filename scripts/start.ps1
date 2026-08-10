Set-Location (Join-Path $PSScriptRoot "..")

docker compose up -d --build

Write-Host "App running at http://localhost:8000"
