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

#define MyAppName "NeuCockpit"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Rahul"
#define MyAppExeName "NeuCockpit.exe"
#define MyCliExeName "neufs.exe"
#define MyWorkerExeName "NeuronLLMWorker.exe"
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
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=NeuCockpitSetup_v1.0_windows_x64
SetupIconFile=assets\neuron_icon.ico
UninstallDisplayIcon={app}\assets\neuron_icon.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2
SolidCompression=no
WizardStyle=modern
WizardImageFile=assets\wizard_sidebar.bmp
WizardSmallImageFile=assets\wizard_small.bmp
PrivilegesRequired=lowest
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DiskSpanning=no
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Semantic Search + Offline Chat
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DisableWelcomePage=no
InfoBeforeFile=docs\pre_install_info.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nNeuCockpit v1.0 is a local semantic search engine and offline chat engine with optional internet access for live data.%n%nIncluded:%n  - BGE Small ONNX embeddings for semantic search%n  - Qwen 2.5 Coder 3B GGUF for offline chat%n  - MemoryOS Auto / Query / Action modes%n  - neufs terminal command%n%nMinimum Requirements:%n  - Windows 10/11 (64-bit)%n  - 8 GB RAM minimum, 16 GB recommended%n  - 6 GB free disk space

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "runonstartup"; Description: "Launch NeuCockpit on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; ── PyInstaller --onedir output (ENTIRE self-contained app) ──
Source: "dist\Neuron\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"
Name: "{group}\neufs command"; Filename: "{app}\{#MyCliExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: startmenuicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\neuron_icon.ico"; Tasks: desktopicon
; Startup folder shortcut — ensures app appears in Windows Settings > Startup Apps
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: runonstartup

[Registry]
; PATH registration
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}'))

; Startup entry — with proper cleanup on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: runonstartup; Flags: uninsdeletevalue

; App Paths registration — makes Neuron findable via Windows Search and "App Paths"
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyCliExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyCliExeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyCliExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey

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
procedure KillProcessByImage(ImageName: string);
var
  ResultCode: Integer;
begin
  Log('Upgrade guard: attempting to close ' + ImageName);
  Exec(
    ExpandConstant('{cmd}'),
    '/C taskkill /F /T /IM "' + ImageName + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Log('Upgrade guard: taskkill ' + ImageName + ' exit code=' + IntToStr(ResultCode));
end;

procedure CloseRunningNeuronProcesses();
begin
  KillProcessByImage('{#MyWorkerExeName}');
  KillProcessByImage('{#MyCliExeName}');
  KillProcessByImage('{#MyAppExeName}');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    CloseRunningNeuronProcesses();
end;

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

function StripPathSegment(PathValue: string; Segment: string): string;
var
  Work: string;
begin
  Work := ';' + PathValue + ';';
  StringChangeEx(Work, ';' + Segment + ';', ';', True);
  while Pos(';;', Work) > 0 do
    StringChangeEx(Work, ';;', ';', True);
  if (Length(Work) > 0) and (Copy(Work, 1, 1) = ';') then
    Delete(Work, 1, 1);
  if (Length(Work) > 0) and (Copy(Work, Length(Work), 1) = ';') then
    Delete(Work, Length(Work), 1);
  Result := Work;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath: string;
  NewPath: string;
  AppPath: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppPath := ExpandConstant('{app}');
    if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
    begin
      NewPath := StripPathSegment(OrigPath, AppPath);
      if NewPath <> OrigPath then
        RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath);
    end;
  end;
end;
