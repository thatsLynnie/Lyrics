$ErrorActionPreference = 'Stop'

$envPath = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "No existe el archivo de configuración: $envPath"
}
Get-Command python -ErrorAction Stop | Out-Null

$securePassword = Read-Host 'Pega la contraseña generada por phpMyAdmin (no se mostrará)' -AsSecureString
$password = (New-Object System.Net.NetworkCredential('', $securePassword)).Password
if ($password -notmatch '^[A-Fa-f0-9]{48}$') {
    $securePassword.Dispose()
    $password = $null
    throw 'La contraseña debe ser el valor hexadecimal de 48 caracteres que generó setup_mysql.sql. Vuelve a ejecutar el SQL si no lo tienes.'
}

$lines = New-Object 'System.Collections.Generic.List[string]'
foreach ($line in Get-Content -LiteralPath $envPath) {
    $lines.Add($line)
}
$settings = @{
    'LYRICS_DB_BACKEND' = 'mysql'
    'LYRICS_MYSQL_USER' = 'lyrics_app'
    'LYRICS_MYSQL_PASSWORD' = $password
}

foreach ($key in $settings.Keys) {
    $pattern = '^\s*' + [regex]::Escape($key) + '='
    $indexes = @(for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) { $index }
    })
    if ($indexes.Count -eq 0) {
        $lines.Add("$key=$($settings[$key])")
    } else {
        $lines[$indexes[0]] = "$key=$($settings[$key])"
        for ($index = $indexes.Count - 1; $index -gt 0; $index--) {
            $lines.RemoveAt($indexes[$index])
        }
    }
}

[System.IO.File]::WriteAllLines(
    $envPath,
    $lines.ToArray(),
    (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList @($false))
)
$securePassword.Dispose()
$password = $null

Write-Host 'Configuración guardada en .env. Iniciando Lyrics...'
Push-Location $PSScriptRoot
try {
    & python app.py
    if ($LASTEXITCODE -ne 0) {
        throw "Lyrics terminó con código $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
