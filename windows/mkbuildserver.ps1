# Install all the default mkbuildmachine packages
.\mkbuildmachine.ps1
if ($LastExitCode -ne 0) {
  exit 1
}

# Install specific packages required by the build daemon
.\mkbuildmachine.ps1 -package python
if ($LastExitCode -ne 0) {
  exit 1
}

# Install the build daemon
mkdir C:\windbuildd
xcopy BuildDaemon\winbuild.cfg C:\winbuildd\winbuild.cfg
xcopy BuildDaemon\windbuildd C:\windbuildd\winbuildd

# Auto-start the build daemon
$startmenu = [Environment]::GetFolderPath("StartMenu")
$startup = $($startmenu)\Programs\Startup
$startupExists = Test-Path $($startup)
if ($startupExists -ne True) {
  mkdir $startup
}
xcopy BuildDaemon\winbuildd.bat $($startup)\winbuildd.bat

goto :EOF

:error
echo Command failed with error %errorlevel%.
exit /b %errorlevel%