@echo off
REM SAWTOOTH WINDOWS ENVIRONMENT SETUP SCRIPT
REM Assumes python 2.7 is installed to the default path
REM Assumes and proxy environment variables are already set.
REM This script assumes it is in the standard location 
REM for a cloned working environment. ie the sawtooth-dev-tools
REM is a peer to sawtooth-core and the other sawtooth-repos.
REM this assumption is not checked. :)
REM This script will activate an existing python virtual environment
REM if it exists. If it does not exist the python virtual environment 
REM with all the dependent python components will be created. . 

SET SCRIPTDIR=%~dp0

SET VC2008="%HOMEDRIVE%%HOMEPATH%\AppData\Local\Programs\Common\Microsoft\Visual C++ for Python\9.0\vcvarsall.bat"
IF NOT EXIST %VC2008% GOTO SKIP_VC2008
ECHO Setting VC2008 environment.
CALL %VC2008% amd64
SET VS90COMNTOOLS=%VCINSTALLDIR%

:SKIP_VC2008

REM Setup environment
ECHO Setting Sawtooth environment.
SET STHOME=%~dp0\..\..\..\
SET SAWTOOTHHOME=%STHOME%sawtooth-core\
SET SAWTOOTHCOREHOME=%SAWTOOTHHOME%\core\
SET SAWTOOTHVALIDATORHOME=%SAWTOOTHHOME%validator\
SET MKTPLACEHOME=%SAWTOOTHOME%extensions\mktplace\

SET POETHOME=%STHOME%sawtooth-poet\

SET CURRENCYHOME=%SAWTOOTHVALIDATORHOME%
SET CURRENCYLIBS=%SAWTOOTHCOREHOME%;%SAWTOOTHVALIDATORHOME%\build\lib.win-amd64-2.7;%MKTPLACEHOME%;%SAWTOOTHVALIDATORHOME%;%POETHOME%
SET PYTHONPATH=%CURRENCYLIBS%

SET PATH=%PATH%;%SCRIPTDIR%;%SAWTOOTHHOME%bin;%MKTPLACEHOME%bin

PUSHD %STHOME%
SET PYTHON=c:\python27\python.exe

SET ST_VE=%STHOME%sawtooth-virtual-env-win\
IF NOT EXIST %ST_VE%NUL GOTO SETUP_VE

ECHO Activating Sawtooth python virtual environment.
CALL %ST_VE%scripts\activate.bat
GOTO EXIT

:SETUP_VE
ECHO Creating Sawtooth python virtual environment.
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install --upgrade virtualenv
%PYTHON% -m virtualenv %ST_VE%
CALL %ST_VE%scripts\activate.bat
pip install enum34 setuptools colorlog pybitcointools cbor
pip install twisted requests nose2 coverage cov-core pypiwin32
pip install pylint setuptools-lint pep8
pip install psutil pyyaml

:EXIT
POPD

REM if the user double clicks this file from explorer leave a shell open for them. 
SET INTERACTIVE_SHELL=1
ECHO %CMDCMDLINE% | find /i "%~0" >nul
IF NOT errorlevel 1 SET INTERACTIVE_SHELL=0
IF _%INTERACTIVE_SHELL%_==_0_ cmd /K 

