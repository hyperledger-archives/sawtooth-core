# Necessary environment variables
$env:PYTHONPATH += ";C:\Program Files (x86)\Intel\sawtooth-validator\lib\python\"
$env:PATH += ";c:\python27;C:\Program Files (x86)\NSIS"

$build_dir = "c:\build"

# this makes running commands easier
$build_command = "python setup.py install --home='C:\Program Files (x86)\Intel\sawtooth-validator'"
$package_command = "makensis 'C:\Program Files (x86)\Intel\sawtooth-validator.nsi'"

if (test-path "C:\Program Files (x86)\Intel\sawtooth-validator\") {
	Remove-Item -Recurse -Force "C:\Program Files (x86)\Intel\sawtooth-validator\"
}

mkdir "C:\Program Files (x86)\Intel\sawtooth-validator\lib\python"


# build and install the SawtoothLake packages
cd $build_dir\sawtooth
iex $build_command
cd $build_dir\currency
iex $build_command
cd $build_dir\mktplace
iex $build_command

cp C:\vagrant\cryptopp561\x64\DLL_Output\Release\cryptopp.dll "C:\Program Files (x86)\Intel\sawtooth-validator\lib\python\SawtoothLakeLedger-0.1.151207-py2.7.egg\"

cp c:\vagrant\currency\windows\sawtooth-validator.nsi "C:\Program Files (x86)\Intel\"

# Build the package
iex $package_command

ii "C:\Program Files (x86)\Intel\"