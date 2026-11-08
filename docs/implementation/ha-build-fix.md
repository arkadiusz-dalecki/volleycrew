# E10 — poprawka instalacji HA 0.1.1

2026-11-08. Zakres: usunięcie błędu budowania zgłoszonego podczas samodzielnej instalacji użytkownika. Bez zmian w HA, tunelu ani produkcyjnej bazie wykonywanych przez agenta.

## Przyczyna i poprawka

Supervisor odrzucił referencję z digestem w build_from z powodu walidacji build.yaml. Następnie przekazał BUILD_FROM=ghcr.io/home-assistant/base:latest, zastępując domyślny Debian obrazem Alpine. W tym obrazie nie ma apt-get. Poprzednie CI jawnie podawało poprawne per-arch BUILD_FROM i nie wykrywało tej ścieżki.

Usunięto przestarzały build.yaml. Runtime FROM wskazuje bezpośrednio przypięty digest indeksu multiarch Debian base 9.3.0; Docker wybiera ARM64/amd64. BUILD_FROM nie jest argumentem Dockerfile i nie może zmienić systemu bazowego. Wersja pakietu i domyślny BUILD_VERSION: 0.1.1. Dane i schemat bazy pozostają bez zmian.

## Weryfikacja

- npm run lint: zaliczone.
- npm run test:backend -- tests/test_deployment.py -q: 8 zaliczonych, w tym regresja wyboru bazy odpornego na argument Supervisor.
- Macierz CI buduje oba CPU z takim samym awaryjnym BUILD_FROM=ghcr.io/home-assistant/base:latest jak w logu instalacji. Nie ma już obejścia przez poprawny per-arch argument. Po buildzie uruchamia istniejące próby HTTPS/Ingress, PDF, backup i restore.
- Zdalne wyniki nowej macierzy wymagają potwierdzenia w PR; test fizycznego HA/Pi pozostaje po stronie użytkownika po scaleniu i odświeżeniu sklepu.

Źródło: [HA — budowanie obrazu](https://contributors.home-assistant.io/apps/guides/dockerfile/), sekcje Build arguments i build.yaml; log użytkownika. Sekrety z logu nie zostały zapisane w repozytorium.
