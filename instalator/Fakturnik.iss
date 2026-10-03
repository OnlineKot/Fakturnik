; Instalator Fakturnika (Inno Setup 6). Budowany automatycznie w GitHub Actions:
;   ISCC /DWersja=1.0.N instalator\Fakturnik.iss
;
; Instalacja z uprawnieniami administratora:
;  * program trafia do Program Files: zwykły użytkownik (i programy na jego koncie) nie może go
;    zmienić ani usunąć,
;  * usługa kopii (Harmonogram zadań, konto SYSTEM) co godzinę i po starcie komputera kopiuje dane
;    do C:\ProgramData\Fakturnik\kopie, skąd użytkownik może je przywrócić, ale nie usunąć,
;  * ta sama usługa instaluje aktualizacje,
;  * odinstalowanie wymaga hasła Fakturnika (gdy jest ustawione); dane i kopie zostają na dysku.

#ifndef Wersja
  #define Wersja "1.0.0"
#endif

[Setup]
AppId={{8C1F6E2A-3B7D-4E59-A0C4-5F2D9B71E6A3}
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
PrivilegesRequired=admin
UsedUserAreasWarning=no
DefaultDirName={autopf}\Fakturnik
DisableDirPage=yes
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
Name: "autostart"; Description: "Uruchamiaj Fakturnik w tle razem z Windows (zalecane: pilnuje danych i robi kopie co 10 minut)"
Name: "pulpit"; Description: "Skrót na pulpicie"

[Dirs]
Name: "{commonappdata}\Fakturnik\kopie"

[Files]
Source: "..\dist\Fakturnik.exe"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly
Source: "..\dist\FakturnikPrzegladarka.exe"; DestDir: "{app}"; Flags: ignoreversion overwritereadonly uninsremovereadonly

[Icons]
Name: "{commonprograms}\Fakturnik"; Filename: "{app}\Fakturnik.exe"; AppUserModelID: "TeodorTeo.Fakturnik"
Name: "{commondesktop}\Fakturnik"; Filename: "{app}\Fakturnik.exe"; AppUserModelID: "TeodorTeo.Fakturnik"; Tasks: pulpit

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
; kopie chronione: pełny dostęp tylko SYSTEM i Administratorzy, zwykli użytkownicy tylko czytają (i przywracają)
; katalog mógł założyć wcześniej zwykły użytkownik: najpierw właścicielem zostają Administratorzy i znikają cudze uprawnienia
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\Fakturnik"" /setowner *S-1-5-32-544 /T /C /Q"; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\Fakturnik"" /reset /T /C /Q"; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\Fakturnik"" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F *S-1-5-32-545:(OI)(CI)RX"; Flags: runhidden waituntilterminated; StatusMsg: "Zabezpieczanie katalogu kopii..."
; usługa kopii i aktualizacji: co godzinę oraz 5 minut po starcie komputera, z konta SYSTEM
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /F /RU SYSTEM /RL HIGHEST /SC HOURLY /TN ""Fakturnik\Kopie co godzine"" /TR ""\""{app}\Fakturnik.exe\"" --usluga"""; Flags: runhidden waituntilterminated; StatusMsg: "Włączanie usługi kopii..."
Filename: "{sys}\schtasks.exe"; Parameters: "/Create /F /RU SYSTEM /RL HIGHEST /SC ONSTART /DELAY 0005:00 /TN ""Fakturnik\Kopie po starcie"" /TR ""\""{app}\Fakturnik.exe\"" --usluga"""; Flags: runhidden waituntilterminated
; pierwsza chroniona kopia od razu
Filename: "{app}\Fakturnik.exe"; Parameters: "--usluga"; Flags: runhidden nowait
Filename: "{app}\Fakturnik.exe"; Description: "Uruchom Fakturnik"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""Fakturnik\Kopie co godzine"""; Flags: runhidden; RunOnceId: "UsunZadanie1"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /F /TN ""Fakturnik\Kopie po starcie"""; Flags: runhidden; RunOnceId: "UsunZadanie2"

[UninstallDelete]
Type: files; Name: "{app}\Fakturnik.old.exe"
Type: files; Name: "{app}\Fakturnik.new.exe"
Type: files; Name: "{app}\FakturnikPrzegladarka.old.exe"
Type: files; Name: "{app}\FakturnikPrzegladarka.new.exe"

[Messages]
polski.FinishedLabel=Fakturnik został zainstalowany. Dane są kopiowane co 10 minut i co godzinę do chronionego katalogu, i nie znikają przy aktualizacji ani odinstalowaniu.

[Code]
const
  StaryKlucz = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{5D0E3C55-6A41-4B7E-9F0B-3C7A1E2B9D41}_is1';

{ Poprzednia wersja instalowała się tylko dla użytkownika (bez administratora). Usuwamy ją po cichu,
  żeby nie zostały dwa programy; dane użytkownika zostają nietknięte. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Odinstaluj: String;
  Kod: Integer;
begin
  Result := '';
  { wpis w HKCU może zmienić każdy program użytkownika, więc uruchamiamy go bez uprawnień administratora }
  if RegQueryStringValue(HKCU, StaryKlucz, 'UninstallString', Odinstaluj) then
  begin
    Odinstaluj := RemoveQuotes(Odinstaluj);
    if FileExists(Odinstaluj) then
      ExecAsOriginalUser(Odinstaluj, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Kod);
  end;
end;

{ Odinstalowanie tylko po podaniu hasła Fakturnika (gdy jest ustawione). }
function InitializeUninstall(): Boolean;
var
  Kod: Integer;
  Exe: String;
begin
  Result := True;
  Exe := ExpandConstant('{app}\Fakturnik.exe');
  if FileExists(Exe) then
  begin
    if not Exec(Exe, '--odinstaluj', '', SW_SHOW, ewWaitUntilTerminated, Kod) then
      Result := False
    else
      Result := (Kod = 0);
  end;
  if not Result then
    MsgBox('Fakturnik nie został odinstalowany (wymagane hasło Fakturnika).', mbInformation, MB_OK);
end;
