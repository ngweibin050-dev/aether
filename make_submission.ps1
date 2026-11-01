# Copy C:\Aether\aether-lab into the clean submission folder C:\AetherLab-submission and scan it for secrets.
# Safe to run again (Nov 3 final sync): the target's .git folder is never touched; files removed from aether-lab are
# removed from the copy. Nothing in C:\Aether is changed.
#
#   powershell -ExecutionPolicy Bypass -File C:\Aether\make_submission.ps1
#   powershell -ExecutionPolicy Bypass -File C:\Aether\make_submission.ps1 -IncludeThirdPartyImages
param(
    [string]$Source = "C:\Aether\aether-lab",
    [string]$Target = "C:\AetherLab-submission",
    [switch]$IncludeThirdPartyImages     # Dreamstime stock machine drawing and the Lamborghini three-view (licence unknown)
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Source)) { throw "Source not found: $Source" }
New-Item -ItemType Directory -Force $Target | Out-Null

# folders and files that never go into the public repo
$xd = @(".git", "__pycache__", "output", "graphify-out", "node_modules", ".vite", "web")
$xf = @(".env", "*.pyc", "*.log", "server_log*.txt", "deploy_modal.bat",
        # never mounted in the UI (no import anywhere, absent from the build)
        "LeftPanel.jsx", "RightPanel.jsx", "TopBar.jsx", "Assistant.jsx", "Hud.jsx", "ResultsDock.jsx",
        # scratch test runner superseded by tests\run_reference.py
        "run_blueprint.py")
if (-not $IncludeThirdPartyImages) { $xf += @("machine_dense.jpg", "blueprint_example2.jpg", "car_three_view.gif") }

# /MIR mirrors the tree; /XD .git keeps the target's own git history out of the mirror (never deleted)
robocopy $Source $Target /MIR /XD $xd /XF $xf /NFL /NDL /NJH /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

# secret scan: report file and line only, with any long token masked, so a leaked key is never printed
$patterns = @("LLM_", "sk-", "api_key", "Bearer ", "META_API=", "BASETAN_API", "\.env\b")
$hits = Get-ChildItem $Target -Recurse -File -Exclude *.png, *.jpg, *.gif, *.glb, *.woff2, *.task, *.wasm |
    Where-Object { $_.FullName -notmatch "\\\.git\\" -and $_.FullName -notmatch "\\ui\\dist\\assets\\" } |
    Select-String -Pattern $patterns
$keyLike = $hits | Where-Object { $_.Line -match "(sk-|META_API=|BASETAN_API=)[A-Za-z0-9_\-]{12,}" -or $_.Line -match "Bearer [A-Za-z0-9_\-\.]{20,}" }
Write-Host "Copied to $Target"
Write-Host "Secret scan: $($hits.Count) pattern hit(s), $($keyLike.Count) that look like a real key."
foreach ($h in $hits) {
    $masked = ($h.Line.Trim() -replace "[A-Za-z0-9_\-\.]{24,}", "***")
    if ($masked.Length -gt 110) { $masked = $masked.Substring(0, 110) + "..." }
    Write-Host ("  {0}:{1}  {2}" -f $h.Path.Substring($Target.Length + 1), $h.LineNumber, $masked)
}
if (Test-Path (Join-Path $Target ".env")) { throw ".env is in the submission folder - remove it" }
if ($keyLike.Count) { throw "Something that looks like a real key is in the submission folder - fix before pushing" }
