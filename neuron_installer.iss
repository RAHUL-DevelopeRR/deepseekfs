; ═══════════════════════════════════════════════════════════════
; Neuron v4.7 — Professional Windows Installer (Inno Setup 6)
; ═══════════════════════════════════════════════════════════════
; Bundles: PyInstaller --onedir output (self-contained, no venv)
; Target: Any Windows 10/11 x64 machine — no Python required
; Changes from v4.6:
;   - PyInstaller --onedir instead of venv + launcher stub
;   - Pre-cached AI model (no internet needed for first run)
;   - Writable storage fallback (%LOCALAPPDATA%\Neuron)
;   - Removed dead code, fixed all portability bugs

#define MyAppName "Neuron"
#define MyAppVersion "4.7.1"
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
OutputBaseFilename=NeuronSetup_v4.7.1
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
VersionInfoVersion=4.7.1.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} — AI-Powered Semantic File Intelligence
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DisableWelcomePage=no
InfoBeforeFile=docs\pre_install_info.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nNeuron is an AI-powered semantic file search engine for Windows. It lets you search by meaning, summarize any file with AI, and browse with a Windows 11 native interface.%n%nNo Python or other software is required — everything is included.%n%nMinimum Requirements:%n  - Windows 10/11 (64-bit)%n  - 4 GB RAM (8 GB recommended)%n  - 500 MB free disk space%n%nOptional (for AI Summarization):%n  - Ollama (can be installed during setup)%n  - llama3.2:1b model (~700 MB download)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "installollama"; Description: "Install Ollama AI engine (required for file summarization)"; GroupDescription: "AI Engine (Encyl):"; Flags: unchecked
Name: "pullmodel"; Description: "Download llama3.2:1b model (~700 MB, requires internet)"; GroupDescription: "AI Engine (Encyl):"; Flags: unchecked
Name: "addtopath"; Description: "Add Neuron to system PATH"; GroupDescription: "System Integration:"; Flags: unchecked
Name: "runonstartup"; Description: "Launch Neuron on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; ── PyInstaller --onedir output (ENTIRE self-contained app) ──
Source: "dist\Neuron\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: runonstartup

[Run]
; Install Ollama — only if not already installed (smart detection)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install_ollama.ps1"" -TempDir ""{tmp}"""; StatusMsg: "Checking and installing Ollama..."; Tasks: installollama; Flags: runhidden waituntilterminated

; Pull model — smart detection (only if not already present)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); $ollama = Get-Command ollama -ErrorAction SilentlyContinue; if (-not $ollama) {{ $paths = @('C:\Users\' + $env:USERNAME + '\AppData\Local\Programs\Ollama\ollama.exe', 'C:\Program Files\Ollama\ollama.exe', 'C:\Program Files (x86)\Ollama\ollama.exe'); foreach ($p in $paths) {{ if (Test-Path $p) {{ $ollama = Get-Item $p; break }} }}; }}; if ($ollama) {{ $ollamaPath = if ($ollama.Source) {{ $ollama.Source }} else {{ $ollama.FullName }}; Start-Process $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden -ErrorAction SilentlyContinue; Start-Sleep 8; & $ollamaPath pull llama3.2:1b }} else {{ Write-Host 'Ollama not found' }}"""; StatusMsg: "Downloading AI model llama3.2:1b (~700 MB)..."; Tasks: pullmodel; Flags: runhidden waituntilterminated

; Launch Neuron
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\storage\neuron_index"
Type: filesandordirs; Name: "{app}\storage\cache"
Type: filesandordirs; Name: "{app}\storage\faiss_index"
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
