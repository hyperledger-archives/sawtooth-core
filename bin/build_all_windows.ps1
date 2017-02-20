$ErrorActionPreference = "Stop"

. validator/packaging/functions.ps1

$top_dir = Split-Path -Parent $(Split-Path -Parent $PSCommandPath)

$pkgs = @("core",`
        "signing",`
        "validator",`
        "extensions\mktplace",`
        "extensions\bond",`
        "extensions\arcade")

copy-deps "$top_dir\signing"
copy-deps "$top_dir\validator"

foreach ($pkg in $pkgs) {
    echo "building $pkg"
    cd $top_dir\$pkg
    python setup.py clean --all
    python setup.py build
    if ($lastexitcode -ne 0) { exit 1 }
    if ($pkg -eq "signing" -or $pkg -eq "validator") {
        python setup.py build
        if ($lastexitcode -ne 0) { exit 1 }
    }
}
