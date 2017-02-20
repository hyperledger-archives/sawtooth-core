
!define APPNAME sawtooth-validator
!define COMPANYNAME "Intel Corporation"
!define DESCRIPTION "Intel® Sawtooth Lake Validator"


# These will be displayed by the "Click here for support information" link in "Add/Remove Programs"
# It is possible to use "mailto:" links in here to open the email client
!define HELPURL "http://www.intel.com" # "Support Information" link

# This is the size (in kB) of all the files copied into "Program Files"
!define INSTALLSIZE 5,402

RequestExecutionLevel admin ;Require admin rights on NT6+ (When UAC is turned on)
 
InstallDir "$PROGRAMFILES\Intel\${APPNAME}"

# This will be in the installer/uninstaller's title bar
Name "${COMPANYNAME} - ${DESCRIPTION}"
#Icon "logo.ico"
outFile "sawtooth-validator.exe"
 
!include LogicLib.nsh

LicenseData "C:\Program Files (x86)\Intel\LICENSE"

page license

page instfiles
 
!macro VerifyUserIsAdmin
UserInfo::GetAccountType
pop $0
${If} $0 != "admin" ;Require admin rights on NT4+
        messageBox mb_iconstop "Administrator rights required!"
        setErrorLevel 740 ;ERROR_ELEVATION_REQUIRED
        quit
${EndIf}
!macroend

!include FileFunc.nsh
!insertmacro GetParameters
!insertmacro GetOptions

function .onInit
	setShellVarContext all
	!insertmacro VerifyUserIsAdmin
	${GetParameters} $R0
	ClearErrors
	${GetOptions} $R0 /EULA= $0
functionEnd
 
section "install"
	${If} ${Silent}
		${If} $0 != 'accept'
			System::Call 'kernel32::GetStdHandle(i -11)i.r0'
			System::Call 'kernel32::AttachConsole(i -1)i.r1'
			${If} $0 = 0
			${OrIf} $1 = 0
				System::Call 'kernel32::AllocConsole()'
				System::Call 'kernel32::GetStdHandle(i -11)i.r0'
			${EndIf}
			FileWrite $0 $\n
			FileWrite $0 "Please include the option '/eula=accept' to accept the license agreement during a silent install.$\n"
			FileWrite $0 "EXAMPLE: > sawtooth-validator.exe /S /eula=accept"
			FileWrite $0 $\n
			Abort "Install failed"
		${EndIf}
	${EndIf}

	# add install dir to pythonpath
	!include "winmessages.nsh"
	!define env_hklm 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'
	!define env_hkcu 'HKCU "Environment"'
	WriteRegExpandStr ${env_hklm} PYTHONPATH ";C:\Program Files (x86)\Intel\sawtooth-validator\lib\python\"
	SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

	# Files for the install directory - to build the installer, these should be in the same directory as the install script (this file)
	setOutPath $INSTDIR
	# Files added here should be removed by the uninstaller (see section "uninstall")
	File /r /x *.pyc /x pybtctool "sawtooth-validator\"

	
	# Uninstaller - See function un.onInit and section "uninstall" for configuration
	writeUninstaller "$INSTDIR\uninstall.exe"
 
	# Registry information for add/remove programs
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayName" "${DESCRIPTION}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "InstallLocation" "$\"$INSTDIR$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayIcon" "$\"$INSTDIR\logo.ico$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "Publisher" "${COMPANYNAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "HelpLink" "$\"${HELPURL}$\""
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayVersion" "${VERSION}"

	# There is no option for modifying or repairing the install
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoModify" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoRepair" 1

	# Set the INSTALLSIZE constant (!defined at the top of this script) so Add/Remove Programs can accurately report the size
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "EstimatedSize" ${INSTALLSIZE}

	Exec '"$PROGRAMFILES\Intel\${APPNAME}\bin\txnvalidator.exe" --startup=auto install'
	Exec '"$PROGRAMFILES\Intel\${APPNAME}\bin\sawtooth.exe" keygen --key-dir "$PROGRAMFILES\Intel\${APPNAME}\conf\keys" validator'

sectionEnd
 
# Uninstaller
 
function un.onInit
	SetShellVarContext all
 
	#Verify the uninstaller - last chance to back out
	MessageBox MB_OKCANCEL "Permanantly remove ${APPNAME}?" /SD IDOK IDOK next
		Abort
	next:
	!insertmacro VerifyUserIsAdmin
functionEnd
 
section "uninstall"

	# Remove windows service
	Exec 'sc.exe delete SawtoothValidator-Service'

	rmdir /r $INSTDIR\bin
	rmdir $INSTDIR\conf\keys
	rmdir $INSTDIR\conf
	rmdir $INSTDIR\data
	rmdir /r $INSTDIR\lib
	rmdir $INSTDIR\logs
	delete $INSTDIR\*

	# Always delete uninstaller as the last action
	delete $INSTDIR\uninstall.exe
 
	# Try to remove the install directory - this will only happen if it is empty
	rmDir $INSTDIR
	rmDir "$PROGRAMFILES\${COMPANYNAME}\"
 
	# Remove uninstaller information from the registry
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}"
sectionEnd
