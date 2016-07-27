param([string] $build_dir ="c:\project",
      [string] $build_version=$(Get-Date -format s))
$ErrorActionPreference = "Stop"

# Necessary environment variables
$env:PYTHONPATH += ";C:\Program Files (x86)\Intel\sawtooth-validator\lib\python\"
$env:PATH += ";c:\swig;c:\python27;C:\Program Files (x86)\NSIS"

# this makes running commands easier
$build_command = "python setup.py install --home='C:\Program Files (x86)\Intel\sawtooth-validator'"
$package_command = "makensis /DVERSION=$build_version 'C:\Program Files (x86)\Intel\sawtooth-validator.nsi'"

if (test-path "C:\Program Files (x86)\Intel\sawtooth-validator\") {
    remove-item -recurse -force "C:\Program Files (x86)\Intel\sawtooth-validator\"
}

if (test-path "C:\Program Files (x86)\Intel\sawtooth-validator.nsi") {
    remove-item -force 'C:\Program Files (x86)\Intel\sawtooth-validator.nsi'
}

if (test-path "C:\Program Files (x86)\Intel\sawtooth-validator.exe") {
    remove-item -force 'C:\Program Files (x86)\Intel\sawtooth-validator.exe'
}

mkdir 'C:\Program Files (x86)\Intel\sawtooth-validator\lib\python'

Add-Content ` 'C:\Program Files (x86)\Intel\sawtooth-validator\versions.txt' `
            "Build number: $build_version"

# build and install the SawtoothLake packages

cd $build_dir\sawtooth-core
python setup.py clean --all
if ($lastexitcode -ne 0) { exit 1 }
if (test-path $build_dir\sawtooth-core\deps ) {
    remove-item -recurse -force $build_dir\sawtooth-core\deps
    if ($lastexitcode -ne 0) { exit 1 }
}
mkdir $build_dir\sawtooth-core\deps
copy-item -recurse $build_dir\deps\cryptopp\* $build_dir\sawtooth-core\deps
copy-item -recurse -force $build_dir\deps\json-c\* $build_dir\sawtooth-core\deps
if ($lastexitcode -ne 0) { exit 1 }
python setup.py build
if ($lastexitcode -ne 0) { exit 1 }
iex $build_command
if ($lastexitcode -ne 0) { exit 1 }


cd $build_dir\sawtooth-validator
python setup.py clean --all
if ($lastexitcode -ne 0) { exit 1 }
python setup.py build
if ($lastexitcode -ne 0) { exit 1 }
iex $build_command
if ($lastexitcode -ne 0) { exit 1 }


foreach ($script in (ls $PSScriptRoot\create_package.d)) {
    Invoke-expression $PSScriptRoot\create_package.d\$script
    if ($lastexitcode -ne 0) { write-host "ERROR: There were problems running $script"; exit 1 }
}

move-item 'C:\Program Files (x86)\Intel\sawtooth-validator\conf\txnvalidator.js' 'C:\Program Files (x86)\Intel\sawtooth-validator\conf\txnvalidator.js.example'

# ensure config files have windows line endings

foreach ($example in (ls "C:\Program Files (x86)\Intel\sawtooth-validator\conf\*.example")) {
    $example_crlf = Get-Content $example
    Set-Content $example $example_crlf
}

remove-item 'C:\Program Files (x86)\Intel\sawtooth-validator\bin\easy_install-3.4-script.py'
remove-item 'C:\Program Files (x86)\Intel\sawtooth-validator\bin\easy_install-3.4.exe'
remove-item 'C:\Program Files (x86)\Intel\sawtooth-validator\bin\easy_install-script.py'
remove-item 'C:\Program Files (x86)\Intel\sawtooth-validator\bin\easy_install.exe'

copy-item $build_dir\sawtooth-validator\packaging\sawtooth-validator.nsi "C:\Program Files (x86)\Intel"

# Build the package
iex $package_command
if ($lastexitcode -ne 0) { exit 1 }
