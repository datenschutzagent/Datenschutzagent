# Mein Profil

Unter **„Mein Profil“** (Route `/profile`) können Sie Ihren Anzeigenamen und Ihre Präferenzen verwalten. Theme und Sprache werden app-weit übernommen.

## Einstellungen

- **Anzeigename** – Name, der z. B. im Header und bei Kommentaren erscheint.
- **E-Mail** – Optional, je nach Konfiguration und OIDC.
- **Theme:** Hell / Dunkel / System – steuert das Erscheinungsbild der Oberfläche.
- **Sprache:** Deutsch (de) oder Englisch (en) – für die Oberfläche und ggf. für LLM-Ausgaben (Run-Checks, VVT) bei passender Case-Sprache.

Die Daten werden über `PATCH /api/v1/me` gespeichert; das Frontend lädt sie mit `GET /api/v1/me` und wendet Theme und Sprache global an.

## Zugriff

Nach Anmeldung (mit OIDC oder als Default-User) über den Nutzerbereich im Header (Dropdown) → „Mein Profil“ oder direkt über die Route `/profile`.
