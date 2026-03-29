; ═══════════════════════════════════════════════════════════════
; Neuron — Professional Windows Installer (Inno Setup 6)
; ═══════════════════════════════════════════════════════════════
; Bundles: Launcher .exe + Source + Python venv + Ollama (optional)
; Target: Any Windows 10/11 x64 machine

#define MyAppName "Neuron"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Rahul"
#define MyAppExeName "Neuron.exe"
#define MyAppURL "https://github.com/RAHUL-DevelopeRR/deepseekfs"
#define OllamaInstaller "OllamaSetup.exe"
#define OllamaURL "https://ollama.com/download/OllamaSetup.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=NeuronSetup
SetupIconFile=assets\neuron_icon.ico
UninstallDisplayIcon={app}\Neuron.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DiskSpanning=no
LicenseFile=
InfoBeforeFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "installollama"; Description: "Install Ollama (AI engine for Encyl summarization)"; GroupDescription: "AI Engine:"; Flags: unchecked
Name: "pullmodel"; Description: "Download AI model (llama3.2:1b — ~700MB, requires internet)"; GroupDescription: "AI Engine:"; Flags: unchecked
Name: "addtopath"; Description: "Add Neuron to system PATH"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; ── Launcher exe (7.6MB - with DNA icon) ──
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

; ── Python venv (all dependencies) ──
Source: "venv\*"; DestDir: "{app}\venv"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"
Name: "{group}\Warmup Encyl AI"; Filename: "{app}\venv\Scripts\python.exe"; Parameters: """{app}\warmup_encyl.py"""; IconFilename: "{app}\assets\neuron_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: desktopicon

[Registry]
; Add to PATH if selected
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
; Install Ollama if checkbox was selected
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Invoke-WebRequest -Uri '{#OllamaURL}' -OutFile '{tmp}\{#OllamaInstaller}'"""; StatusMsg: "Downloading Ollama..."; Tasks: installollama; Flags: runhidden waituntilterminated
Filename: "{tmp}\{#OllamaInstaller}"; Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"; StatusMsg: "Installing Ollama..."; Tasks: installollama; Flags: runhidden waituntilterminated

; Pull the model if checkbox was selected
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Start-Process 'ollama' -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep -Seconds 5; ollama pull llama3.2:1b"""; StatusMsg: "Downloading AI model (llama3.2:1b)..."; Tasks: pullmodel; Flags: runhidden waituntilterminated

; Warmup the model
Filename: "{app}\venv\Scripts\python.exe"; Parameters: """{app}\warmup_encyl.py"""; StatusMsg: "Warming up AI engine..."; Tasks: pullmodel; Flags: runhidden waituntilterminated nowait

; Launch Neuron
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

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
