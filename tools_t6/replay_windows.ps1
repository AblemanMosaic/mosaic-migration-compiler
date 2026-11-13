param([Parameter(Mandatory=$true)][string]$ExpectedSource, [Parameter(Mandatory=$true)][string]$Out)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
foreach ($phase in @('test-t1','test-t2','test-t3','test-t4','test-t5','base-tests','scenarios','examples','base-audit','base-assemble','test-t6','audit','assemble')) {
  & python tools_t6/qualify.py --expected-source $ExpectedSource --out $Out --phase $phase --require-platform Windows
  if ($LASTEXITCODE -ne 0) { throw "Qualification stopped in $phase with exit $LASTEXITCODE. Preserve the failed evidence." }
}
