# build and install sawtooth-mktplace for packaging

cd $top_dir\extensions\mktplace
python setup.py clean --all
if ($lastexitcode -ne 0) { exit 1 }
python setup.py build
if ($lastexitcode -ne 0) { exit 1 }
iex $build_command
if ($lastexitcode -ne 0) { exit 1 }
