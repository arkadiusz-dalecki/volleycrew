# Volleycrew

Aplikacja prywatnej grupy siatkarskiej: kalendarz i zapisy, rezerwa, obecność, drużyny na boisku, lista podpisów PDF oraz ranking ELO.

Home Assistant buduje ją lokalnie przy instalacji, tak jak maybe-finance. Obsługiwane architektury: Raspberry Pi 64-bit (`aarch64`) i `amd64`. Od 0.2.0 zawiera własny PostgreSQL 17 z automatyczną konfiguracją i trwałymi danymi. Wymaga domeny HTTPS. Istniejące konfiguracje zewnętrznej bazy pozostają obsługiwane. Użytkownicy Volleycrew logują się profilem i PIN-em; nie potrzebują kont HA.

[Instalacja i konfiguracja](DOCS.md) · [Historia wersji](CHANGELOG.md)
