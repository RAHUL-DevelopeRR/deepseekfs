; ═══════════════════════════════════════════════════════════════
; Neuron v1.0 — Professional Windows Installer (Inno Setup 6)
; ═══════════════════════════════════════════════════════════════

#define MyAppName "Neuron"
#define MyAppVersion "1.0.0"
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
OutputBaseFilename=NeuronSetup
SetupIconFile=assets\neuron_icon.ico
UninstallDisplayIcon={app}\assets\neuron_icon.ico
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DiskSpanning=no
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} — AI-Powered Semantic File Intelligence
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
; Welcome & info pages
DisableWelcomePage=no
InfoBeforeFile=docs\pre_install_info.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nNeuron is an AI-powered semantic file search engine for Windows. It lets you search by meaning, summarize any file with AI, and browse with a Windows 11 native interface.%n%nMinimum Requirements:%n  • Windows 10/11 (64-bit)%n  • 4 GB RAM (8 GB recommended)%n  • 2 GB free disk space%n%nOptional (for AI Summarization):%n  • Ollama (can be installed during setup)%n  • llama3.2:1b model (~700 MB download)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked
Name: "installollama"; Description: "Install Ollama AI engine (required for file summarization)"; GroupDescription: "AI Engine (Encyl):"; Flags: unchecked
Name: "pullmodel"; Description: "Download llama3.2:1b model (~700 MB — requires internet)"; GroupDescription: "AI Engine (Encyl):"; Flags: unchecked
Name: "addtopath"; Description: "Add Neuron to system PATH"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; ── Launcher exe ──
Source: "dist\Neuron.exe"; DestDir: "{app}"; Flags: ignoreversion

; ── Source code ──
Source: "run_desktop.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "warmup_encyl.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "services\*"; DestDir: "{app}\services"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ui\*"; DestDir: "{app}\ui"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "storage\*"; DestDir: "{app}\storage"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Python venv ──
Source: "venv\*"; DestDir: "{app}\venv"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: startmenuicon
Name: "{group}\Warmup Encyl AI"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\warmup_encyl.py"""; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: startmenuicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
; Install Ollama — download to known location, then run
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $out = Join-Path '{tmp}' 'OllamaSetup.exe'; Write-Host 'Downloading Ollama...'; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $out -UseBasicParsing; Write-Host 'Download complete.'"""; StatusMsg: "Downloading Ollama (this may take a few minutes)..."; Tasks: installollama; Flags: runhidden waituntilterminated
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"; StatusMsg: "Installing Ollama..."; Tasks: installollama; Flags: runhidden waituntilterminated skipifdoesntexist

; Pull model — start ollama serve, then pull
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); $ollama = Get-Command ollama -ErrorAction SilentlyContinue; if ($ollama) {{ Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden -ErrorAction SilentlyContinue; Start-Sleep 8; & ollama pull llama3.2:1b }} else {{ Write-Host 'Ollama not found, skipping model pull' }}"""; StatusMsg: "Downloading AI model llama3.2:1b (~700 MB)..."; Tasks: pullmodel; Flags: runhidden waituntilterminated

; Warmup model
Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\warmup_encyl.py"""; StatusMsg: "Warming up AI engine..."; Tasks: pullmodel; Flags: runhidden nowait skipifdoesntexist

; Launch Neuron
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\storage\neuron_index"
Type: files; Name: "{app}\*.log"

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
