# Changelog

## 0.3.0

- Manage single meetings and weekly series directly from the calendar, including an optional end date and restoration of the previous schedule afterward.
- Reschedule or cancel a meeting from its calendar card, with confirmation and enrollment protection.
- Make meeting dates more prominent and show the actual next meeting in the sidebar.
- Clarify declaration buttons and attendance prerequisites. Adapt court formations to 1–6 players, center unequal teams, and keep the seventh player in rotation.
- Add an explicit local preview with 14 demo profiles and role switching; preview controls are excluded from production builds.
- Apply migration 0008 to distinguish additional meetings from recurring occurrences. Back up before updating.

## 0.2.0

Własny PostgreSQL 17: bez osobnego serwera i ręcznego hasła bazy. Pusty host wybiera własną bazę, istniejący zachowuje zewnętrzną. Trwałe dane, prywatny listener, automatyczny backup i restore HA przed migracjami; blokada niejawnej zmiany trybu. Testy kontenerowe obejmują restart, awarię, aktualizację i odtworzenie. Walidacja pokazuje nazwy nieprawidłowych pól bez ich wartości.

## 0.1.1

Naprawa instalacji w Home Assistant: baza Debian jest przypięta bezpośrednio w Dockerfile. Usunięto przestarzały `build.yaml`, którego walidator odrzucał referencje obrazów z digestem. Parametr `BUILD_FROM` przekazywany przez Supervisor nie może już podmienić bazy na Alpine. CI odtwarza ten parametr dla obu architektur.

## 0.1.0

Pierwszy pakiet do samodzielnej instalacji w Home Assistant: lokalny build, statyczny frontend wariantu A, API, migracje, oddzielne wejście Ingress i bezpośrednie, bootstrap administratora z tokenu, backup PostgreSQL i konfiguracji oraz bezpieczne odtwarzanie do pustej bazy.

Nie jest to deklaracja odbioru na docelowym Raspberry Pi ani fizycznych telefonach. Stan weryfikacji jest w `docs/implementation/e10-report.md` w repozytorium.
