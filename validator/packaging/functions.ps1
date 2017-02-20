function Git-Version() {
    if (Get-Command "git.exe" -ErrorAction SilentlyContinue)
    {
        $ver = (git describe)
        if ($lastexitcode -ne 0) {
            Add-Content `
            'C:\Program Files (x86)\Intel\sawtooth-validator\versions.txt' `
            "$(get-location | split-path -leaf): Problems determining git version"
            $lastexitcode = 0
        }
        elseif ($null -ne $ver) {
            Add-Content `
            'C:\Program Files (x86)\Intel\sawtooth-validator\versions.txt' `
            "$(get-location | split-path -leaf): $ver"
        }
    }
}

function Copy-Deps($pkg_dir) {
    echo $pkg_dir
    if (Test-Path $pkg_dir\deps\) {
        rmdir -recurse $pkg_dir\deps\
    }
    mkdir $pkg_dir\deps
    foreach ($dir in (ls c:\jenkins\deps) ) {
        copy c:\jenkins\deps\$dir\* $pkg_dir\deps -recurse -force
    }
}
