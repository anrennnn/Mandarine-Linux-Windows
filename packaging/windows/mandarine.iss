; Mandarine installer for Windows 10/11 (x64), built with Inno Setup 6:
;   iscc /DAppVersion=1.0.0 packaging\windows\mandarine.iss
; Expects the PyInstaller output in dist\Mandarine. Installs per user (no admin
; prompt) into %LOCALAPPDATA%\Programs\Mandarine; "Install for all users" is
; offered on the first page.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1D9E52-3B7A-4F0E-9C2D-8E5A7B4F1A30}
AppName=Mandarine
AppVersion={#AppVersion}
AppVerName=Mandarine {#AppVersion}
AppPublisher=anrennnn
AppPublisherURL=https://github.com/anrennnn/Mandarine-Linux-Windows
AppSupportURL=https://github.com/anrennnn/Mandarine-Linux-Windows/issues
DefaultDirName={autopf}\Mandarine
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\..\dist
OutputBaseFilename=Mandarine-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\Mandarine.exe
UninstallDisplayName=Mandarine
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.ContextMenu=Añadir Mandarine al clic derecho del Explorador
english.ContextMenu=Add Mandarine to the File Explorer right-click menu
spanish.StartAtLogin=Abrir Mandarine al iniciar sesión (necesario para Shift + arrastrar)
english.StartAtLogin=Open Mandarine at sign-in (needed for Shift + drag)
spanish.Helpers=Programas auxiliares (se instalan con winget, necesitan Internet):
english.Helpers=Helper programs (installed with winget, need Internet):
spanish.FFmpeg=ffmpeg: vídeo y audio (MP4, GIF, MP3…)
english.FFmpeg=ffmpeg: video and audio (MP4, GIF, MP3…)
spanish.LibreOffice=LibreOffice: Word, Excel y PowerPoint (unos 350 MB)
english.LibreOffice=LibreOffice: Word, Excel and PowerPoint (about 350 MB)
spanish.Tesseract=Tesseract: texto de imágenes (OCR)
english.Tesseract=Tesseract: text from images (OCR)
spanish.Installing=Instalando %1 con winget…
english.Installing=Installing %1 with winget…

[Tasks]
Name: "contextmenu"; Description: "{cm:ContextMenu}"
Name: "startup"; Description: "{cm:StartAtLogin}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "ffmpeg"; Description: "{cm:FFmpeg}"; GroupDescription: "{cm:Helpers}"; Check: WingetAvailable
Name: "libreoffice"; Description: "{cm:LibreOffice}"; GroupDescription: "{cm:Helpers}"; Flags: unchecked; Check: WingetAvailable
Name: "tesseract"; Description: "{cm:Tesseract}"; GroupDescription: "{cm:Helpers}"; Flags: unchecked; Check: WingetAvailable

[Files]
Source: "..\..\dist\Mandarine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Mandarine"; Filename: "{app}\Mandarine.exe"
Name: "{autodesktop}\Mandarine"; Filename: "{app}\Mandarine.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Mandarine"; \
  ValueData: """{app}\Mandarine.exe"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{cmd}"; Parameters: "/c winget install -e --id Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements"; \
  StatusMsg: "{cm:Installing,ffmpeg}"; Flags: runhidden waituntilterminated; Tasks: ffmpeg
Filename: "{cmd}"; Parameters: "/c winget install -e --id TheDocumentFoundation.LibreOffice --silent --accept-source-agreements --accept-package-agreements"; \
  StatusMsg: "{cm:Installing,LibreOffice}"; Flags: runhidden waituntilterminated; Tasks: libreoffice
Filename: "{cmd}"; Parameters: "/c winget install -e --id UB-Mannheim.TesseractOCR --silent --accept-source-agreements --accept-package-agreements"; \
  StatusMsg: "{cm:Installing,Tesseract}"; Flags: runhidden waituntilterminated; Tasks: tesseract
Filename: "{app}\Mandarine.exe"; Parameters: "integrate --no-login"; Flags: runhidden waituntilterminated; Tasks: contextmenu
Filename: "{app}\Mandarine.exe"; Description: "{cm:LaunchProgram,Mandarine}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Mandarine.exe"; Flags: runhidden; RunOnceId: "StopMandarine"
Filename: "{app}\Mandarine.exe"; Parameters: "integrate --remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveIntegration"

[Code]
function WingetAvailable: Boolean;
var
  Code: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/c winget --version', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  { An upgrade must replace the files of a running copy. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Mandarine.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;
