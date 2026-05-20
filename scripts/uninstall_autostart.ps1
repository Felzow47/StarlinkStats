#Requires -Version 5.1
$TaskName = "StarlinkWidget"
schtasks /Delete /TN $TaskName /F 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Tache '$TaskName' supprimee."
} else {
    Write-Host "Tache '$TaskName' introuvable."
}
