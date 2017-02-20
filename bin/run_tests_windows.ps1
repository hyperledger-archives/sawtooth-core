param([string]$module = "all")
$ErrorActionPreference = "Stop"

. validator/packaging/functions.ps1

$top_dir = Split-Path -Parent $(Split-Path -Parent $PSCommandPath)

# set env vars
$env:VERSION = ""

$env:PATH += ";$top_dir\bin"

function test_core() {
    $env:PYTHONPATH = ";$top_dir\core"
    cd $top_dir\core
    python c:\python27\scripts\nose2 -v
    if ($lastexitcode -ne 0) { exit 1 }
    cd ..
}

function test_signing() {
    $env:PYTHONPATH = "$top_dir\signing"
    $env:PYTHONPATH += ";$top_dir\signing\build\lib.win-amd64-2.7"
    cd $top_dir\signing
    python c:\python27\scripts\nose2 -v
    if ($lastexitcode -ne 0) { exit 1 }
    cd ..
}

function test_validator() {
    $env:PYTHONPATH = "$top_dir\signing"
    $env:PYTHONPATH += ";$top_dir\signing\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\core"
    $env:PYTHONPATH += ";$top_dir\validator"
    $env:PYTHONPATH += ";$top_dir\validator\build\lib.win-amd64-2.7"

    cd $top_dir\validator
    python c:\python27\scripts\nose2 -v unit

    $env:RUN_TEST_SUITES = "1"
    python c:\python27\scripts\nose2 -v sawtooth_suites.ts_pr_dev_mode.DevModeTestSuite
    if ($lastexitcode -ne 0) { exit 1 }
    python c:\python27\scripts\nose2 -v sawtooth_suites.ts_pr_poet1.Poet1TestSuite
    if ($lastexitcode -ne 0) { exit 1 }
    remove-item env:\RUN_TEST_SUITES
    cd ..
}

function test_mktplace() {
    $env:PYTHONPATH = "$top_dir\signing"
    $env:PYTHONPATH += ";$top_dir\signing\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\core"
    $env:PYTHONPATH += ";$top_dir\validator"
    $env:PYTHONPATH += ";$top_dir\validator\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\extensions\mktplace"

    cd $top_dir\extensions\mktplace
    python c:\python27\scripts\nose2 -v unit
    if ($lastexitcode -ne 0) { exit 1 }
    $env:RUN_TEST_SUITES = "1"
    python c:\python27\scripts\nose2 -v sawtooth_suites.ts_pr_mkt_dev_mode.DevModeMktTestSuite
    if ($lastexitcode -ne 0) { exit 1 }
    remove-item env:\RUN_TEST_SUITES
    cd ..\..
}

function test_bond() {
    $env:PYTHONPATH = "$top_dir\signing"
    $env:PYTHONPATH += ";$top_dir\signing\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\core"
    $env:PYTHONPATH += ";$top_dir\validator"
    $env:PYTHONPATH += ";$top_dir\validator\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\extensions\bond"
    cd $top_dir\extensions\bond
    python c:\python27\scripts\nose2 -v
    if ($lastexitcode -ne 0) { exit 1 }
    cd ..\..
}

function test_arcade() {
    $env:PYTHONPATH = "$top_dir\signing"
    $env:PYTHONPATH += ";$top_dir\signing\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\core"
    $env:PYTHONPATH += ";$top_dir\validator"
    $env:PYTHONPATH += ";$top_dir\validator\build\lib.win-amd64-2.7"
    $env:PYTHONPATH += ";$top_dir\extensions\arcade"
    cd $top_dir\extensions\arcade
    python c:\python27\scripts\nose2 -v
    if ($lastexitcode -ne 0) { exit 1 }
    cd ..\..
}

switch($module) {

    all {
        test_core
        test_signing
        test_validator
        test_mktplace
        test_bond
        test_arcade
    }
    core {
        test_core
    }
    signing {
        test_signing
    }
    validator {
        test_validator
    }
    mktplace {
        test_mktplace
    }
    bond {
        test_bond
    }
    arcade {
        test_arcade
    }
}
