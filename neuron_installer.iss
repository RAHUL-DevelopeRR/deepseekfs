; ═══════════════════════════════════════════════════════════════
; Neuron v5.2 - Professional Windows Installer (Inno Setup 6)
; ═══════════════════════════════════════════════════════════════
; Bundles: PyInstaller --onedir output (self-contained, no venv)
; Target: Any Windows 10/11 x64 machine — no Python required
; Changes from v5.1:
;   - REMOVED Ollama dependency (no more external AI server)
;   - AI engine now uses llama-cpp-python (in-process GGUF inference)
;   - Model auto-downloaded from HuggingFace on first run
;   - Added MemoryOS agent + Research Overlay
;   - Fixed Windows Startup Apps / System Apps visibility
;   - Added App Paths registration for Windows search integration
;   - Added startup folder shortcut for reliable auto-start

#define MyAppName "Neuron"
#define MyAppVersion "5.2.0"
#define MyAppPublisher "Rahul"
#define MyAppExeName "Neuron.exe"
#define MyAppURL "https://github.com/RAHUL-DevelopeRR/deepseekfs"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=NeuronSetup_v5.2
SetupIconFile=assets\neuron_icon.ico
UninstallDisplayIcon={app}\assets\neuron_icon.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=assets\wizard_sidebar.bmp
WizardSmallImageFile=assets\wizard_small.bmp
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DiskSpanning=no
VersionInfoVersion=5.2.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} — AI-Powered Semantic File Intelligence + MemoryOS
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DisableWelcomePage=no
InfoBeforeFile=docs\pre_install_info.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nNeuron is an AI-powered semantic file search engine with MemoryOS — an offline AI agent that can search, create, edit, and organize your files via natural language.%n%nNew in v5.2:%n  - MemoryOS: Full AI agent with 14 tools%n  - Research Overlay: Stealth AI assistant (Ctrl+Shift+R)%n  - No Ollama required — AI runs directly in-app%n  - AI model downloaded on first launch (~1.8 GB)%n%nMinimum Requirements:%n  - Windows 10/11 (64-bit)%n  - 8 GB RAM (for AI features)%n  - 3 GB free disk space (with AI model)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "addtopath"; Description: "Add Neuron to system PATH"; GroupDescription: "System Integration:"; Flags: unchecked
Name: "runonstartup"; Description: "Launch Neuron on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; ── PyInstaller --onedir output (ENTIRE self-contained app) ──
Source: "dist\Neuron\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: desktopicon
; Startup folder shortcut — ensures app appears in Windows Settings > Startup Apps
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: runonstartup

[Registry]
; PATH registration
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

; Startup entry — with proper cleanup on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: runonstartup; Flags: uninsdeletevalue

; App Paths registration — makes Neuron findable via Windows Search and "App Paths"
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey

; Application registration metadata (for Add/Remove Programs visibility)
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
; Launch Neuron after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\storage\neuron_index"
Type: filesandordirs; Name: "{app}\storage\cache"
Type: filesandordirs; Name: "{app}\storage\faiss_index"
Type: filesandordirs; Name: "{app}\storage\models"
Type: files; Name: "{app}\*.log"

[UninstallRun]
; Remove startup shortcut on uninstall
Filename: "cmd.exe"; Parameters: "/c del /f ""{userstartup}\{#MyAppName}.lnk"""; Flags: runhidden

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
