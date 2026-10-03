; Instalator Fakturnika (Inno Setup 6). Budowany automatycznie w GitHub Actions:
;   ISCC /DWersja=1.0.N instalator\Fakturnik.iss
; Instalacja dla bieżącego użytkownika (bez uprawnień administratora), dzięki czemu program
; może sam się aktualizować. Odinstalowanie NIE usuwa danych (%APPDATA%\Fakturnik) ani kopii.

#ifndef Wersja
  #define Wersja "1.0.0"
#endif

[Setup]
AppId={{5D0E3C55-6A41-4B7E-9F0B-3C7A1E2B9D41}
AppName=Fakturnik
AppVersion={#Wersja}
AppVerName=Fakturnik {#Wersja}
AppPublisher=TeodorTeo.com
AppPublisherURL=https://teodorteo.com
AppSupportURL=https://github.com/OnlineKot/Fakturnik
VersionInfoVersion={#Wersja}
VersionInfoCompany=TeodorTeo.com
VersionInfoDescription=Instalator programu Fakturnik
VersionInfoProductName=Fakturnik
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Fakturnik
DisableDirPage=auto
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=FakturnikSetup
SetupIconFile=..\fakturnik\zasoby\ikona.ico
UninstallDisplayIcon={app}\Fakturnik.exe
UninstallDisplayName=Fakturnik
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; działający Fakturnik trzyma ten muteks: instalator poprosi o jego zamknięcie przed podmianą pliku
AppMutex=FakturnikUruchomiony
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "polski"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "autostart"; Description: "Uruchamiaj Fakturnik w tle razem z Windows (zalecane: pilnuje danych i aktualizacji)"
Name: "pulpit"; Description: "Skrót na pulpicie"

[Files]
Source: "..\dist\Fakturnik.exe"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly

[Icons]
Name: "{userprograms}\Fakturnik"; Filename: "{app}\Fakturnik.exe"; AppUserModelID: "TeodorTeo.Fakturnik"
Name: "{userdesktop}\Fakturnik"; Filename: "{app}\Fakturnik.exe"; AppUserModelID: "TeodorTeo.Fakturnik"; Tasks: pulpit

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Fakturnik"; ValueData: """{app}\Fakturnik.exe"" --w-tle"; Tasks: autostart; Flags: uninsdeletevalue
; pozycje „Dodaj do Fakturnika” (włączane w programie) znikają razem z programem
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.jpg\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.jpeg\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.png\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.tif\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.tiff\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.bmp\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.webp\shell\Fakturnik"; Flags: uninsdeletekey dontcreatekey

[Run]
Filename: "{app}\Fakturnik.exe"; Description: "Uruchom Fakturnik"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\Fakturnik.old.exe"
Type: files; Name: "{app}\Fakturnik.new.exe"

[Messages]
polski.FinishedLabel=Fakturnik został zainstalowany. Twoje dane są przechowywane osobno i nie znikają przy aktualizacji ani odinstalowaniu.
