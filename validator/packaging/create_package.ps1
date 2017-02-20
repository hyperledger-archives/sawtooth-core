param([string] $build_version=$(Get-Date -format s))
$ErrorActionPreference = "Stop"

. $PSScriptRoot\functions.ps1

$top_dir = Split-Path -Parent $(Split-Path -Parent $(Split-Path -Parent $PSCommandPath))

# Necessary environment variables
$env:PYTHONPATH += ";C:\Program Files (x86)\Intel\sawtooth-validator\lib\python\"
$env:PATH += ";c:\swig;c:\python27;C:\Program Files (x86)\NSIS"

# this makes running commands easier
$build_command = "python setup.py install --home='C:\Program Files (x86)\Intel\sawtooth-validator'"
$package_command = "makensis /DVERSION=$build_version 'C:\Program Files (x86)\Intel\sawtooth-validator.nsi'"

if (test-path "C:\Program Files (x86)\Intel\sawtooth-validator*") {
    remove-item -recurse -force "C:\Program Files (x86)\Intel\sawtooth-validator*"
}

mkdir "C:\Program Files (x86)\Intel\sawtooth-validator\lib\python"

Add-Content ` 'C:\Program Files (x86)\Intel\sawtooth-validator\versions.txt' `
            "Build number: $build_version"

# build and install the SawtoothLake packages

copy-deps $top_dir\signing
copy-deps $top_dir\validator

$pkgs = @("core",`
        "signing",`
        "validator"`
        )

foreach ($dir in $pkgs) {
    echo "installing $dir"
    cd $top_dir\$dir
    python setup.py clean --all
    if ($lastexitcode -ne 0) { exit 1 }
    Git-Version
    python setup.py build
    if ($lastexitcode -ne 0) { exit 1 }
    iex $build_command
    if ($lastexitcode -ne 0) { exit 1 }
}


foreach ($script in (ls $PSScriptRoot\create_package.d)) {
    Invoke-expression $PSScriptRoot\create_package.d\$script
    if ($lastexitcode -ne 0) { write-host "ERROR: There were problems running $script"; exit 1 }
}

# ensure config files have windows line endings

foreach ($example in (ls "C:\Program Files (x86)\Intel\sawtooth-validator\conf\*.example")) {
    $example_crlf = Get-Content $example
    Set-Content $example $example_crlf
}

Remove-Item "C:\Program Files (x86)\Intel\sawtooth-validator\bin\*" -exclude mktclient*, sawtooth*, txnvalidator*, xo*

copy-item $top_dir\validator\packaging\sawtooth-validator.nsi "C:\Program Files (x86)\Intel"

if (test-path "C:\Program Files (x86)\Intel\LICENSE") {
    remove-item -recurse -force "C:\Program Files (x86)\Intel\LICENSE"
}

cp $top_dir\LICENSE "C:\Program Files (x86)\Intel"

# Build the package
iex $package_command
if ($lastexitcode -ne 0) { exit 1 }

mkdir $top_dir\build\exe
mv "C:\Program Files (x86)\Intel\sawtooth-validator.exe" "$top_dir\build\exe\sawtooth-validator-$ENV:BUILD_NUMBER.exe"
