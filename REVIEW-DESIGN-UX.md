# Design & UX Review: Datenschutz-Agent

## Zusammenfassung

Die Anwendung ist solide aufgebaut mit React, Radix UI, Tailwind CSS und einem konsistenten Design-System. Die folgende Analyse identifiziert **21 konkrete Verbesserungsvorschläge** in den Bereichen Navigation, Responsive Design, Interaktionsdesign, Barrierefreiheit, visuelles Design und Datenmanagement.

---

## 1. Navigation & Header

### 1.1 Kein mobiles Navigationsmenü (Kritisch)

**Problem:** Der Header enthält 5-7 horizontale Links ohne Hamburger-Menü oder Responsive-Anpassung. Auf Geräten < 1024px werden die Links abgeschnitten oder überlappen.

**Dateien:** Jede Page-Datei dupliziert den Header (`cases-page.tsx:103-135`, `case-detail-page.tsx:151-183`, `playbooks-page.tsx:43-75`, `vvt-overview-page.tsx:141-187`, `profile-page.tsx:65-97`).

**Vorschlag:**
- Mobile: Hamburger-Menü (`Sheet`-Komponente ist bereits vorhanden) mit Slide-in-Navigation
- Tablet: Kollabierte Navigation mit Icons
- Desktop: Aktuelle horizontale Links beibehalten

### 1.2 Header-Duplikation (Architektur-Problem)

**Problem:** Der komplette Header-Code (30+ Zeilen) wird in **jeder Page-Datei** identisch wiederholt. Das aktive Menü-Item wird manuell pro Seite hart codiert (z.B. `text-blue-600` auf der aktuellen Seite vs. `text-slate-600` auf den anderen).

**Vorschlag:**
- Header in eine gemeinsame `AppLayout`-Komponente extrahieren
- Aktives Menü-Item automatisch anhand der aktuellen Route (`useLocation()`) bestimmen
- Reduziert ca. 200 Zeilen duplizierter Code

### 1.3 Keine Breadcrumb-Navigation

**Problem:** Auf der `CaseDetailPage` gibt es nur einen "Zurück zur Übersicht"-Button, aber keine strukturierte Breadcrumb-Navigation. Bei tieferen Verschachtelungen (z.B. Fall > Dokument > Annotation) verliert der Nutzer die Orientierung.

**Vorschlag:**
- `Breadcrumb`-Komponente ist bereits in `/components/ui/` vorhanden, wird aber nicht genutzt
- Einsetzen auf CaseDetailPage: `Vorgänge > [Vorgangsname]`
- Einsetzen auf PlaybookDetailPage: `Playbooks > [Playbookname]`

---

## 2. Responsive Design

### 2.1 Tabelle auf Mobilgeräten unlesbar

**Problem:** Die VVT-Übersicht (`vvt-overview-page.tsx:418-479`) und Stats-Tabellen nutzen `overflow-x-auto`, aber 7-spaltige Tabellen erfordern auf Mobilgeräten horizontales Scrollen ohne visuellen Hinweis.

**Vorschlag:**
- Auf kleinen Bildschirmen (< 768px) Tabelle als vertikale Card-Liste anzeigen (responsive Tabelle)
- Alternativ: Weniger Spalten auf Mobile anzeigen und Details per Expand/Collapse verfügbar machen
- Visuellen Hinweis ("Wischen für mehr") bei Overflow anzeigen

### 2.2 Dialog-Breite auf Mobilgeräten

**Problem:** `NewCaseDialog` nutzt `max-w-2xl` (40rem), was auf kleinen Bildschirmen nicht den vollen Platz nutzt. Der Step-Indicator mit drei Schritten bricht auf schmalen Screens um.

**Vorschlag:**
- Dialog auf Mobile Fullscreen (`DialogContent` mit `sm:max-w-2xl` statt `max-w-2xl`)
- Step-Indicator auf Mobile als schmale Fortschrittsanzeige statt Labels
- Buttons im Footer vertikal stapeln auf < 640px

### 2.3 Filter-Layout auf Mobile

**Problem:** Die VVT-Filter (`vvt-overview-page.tsx:326-391`) verwenden `flex flex-wrap gap-4` mit festen Breiten (`w-[220px]`, `w-[200px]`, `w-[160px]`), was auf schmalen Screens zu unerwartetem Umbruch führt.

**Vorschlag:**
- Filter auf Mobile als vollbreite, gestapelte Selects (`w-full` auf `< sm`)
- Oder: Filter hinter einem "Filter"-Button mit Slide-out-Panel verbergen (wie auf der CasesPage)

---

## 3. Interaktionsdesign & UX-Flows

### 3.1 Hardcodiertes Datum in Deadline-Berechnung (Bug) — **bereits behoben**

**Status:** Erledigt. `case-utils.ts:23` verwendet `Date.now()`; in `cases-page.tsx` ist kein hartcodiertes `2026-02-06` mehr enthalten. Verbleibende Vorkommen liegen ausschließlich in Mock-Daten und einem Test-Fixture und sind dort korrekt.

### 3.2 Loading-State kommt nach Content

**Problem:** In `cases-page.tsx:287-293` wird der Lade-Indikator erst **nach** der gefilterten Falliste gerendert. Beim initialen Laden zeigt die Seite zuerst eine leere Liste und dann den Spinner darunter.

**Vorschlag:**
- Loading-State sollte **vor** der Liste stehen oder die Liste komplett ersetzen
- Skeleton-Loader statt Spinner verwenden (3-4 Skeleton-Cards) für bessere Wahrnehmung der Ladezeit
- `Skeleton`-Komponente ist bereits vorhanden in `/components/ui/skeleton.tsx`

### 3.3 Fehlende Erfolgsmeldung nach Aktionen

**Problem:** Nach dem Speichern des Profils, dem Ändern eines Finding-Status oder dem Anlegen eines neuen Vorgangs gibt es keine Toast-Benachrichtigung. Der Dialog schließt sich einfach, und der Nutzer ist unsicher, ob die Aktion erfolgreich war.

**Vorschlag:**
- `Sonner` (Toast-Library) ist bereits installiert und als `/components/ui/sonner.tsx` konfiguriert
- Toast-Benachrichtigungen einbauen: "Vorgang erfolgreich angelegt", "Profil gespeichert", "Finding-Status aktualisiert"

### 3.4 Kein Bestätigungsdialog beim Löschen

**Problem:** Auf der `LegalBasesPage` gibt es einen Lösch-Button, aber es fehlt ein konsistentes Pattern für Bestätigungsdialoge bei destruktiven Aktionen (z.B. Dokument löschen, Playbook archivieren).

**Vorschlag:**
- `AlertDialog`-Komponente (bereits vorhanden) für alle destruktiven Aktionen nutzen
- Text klar formulieren: "Möchten Sie [Objekt] wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden."

### 3.5 Zwei Submit-Buttons in Step 2 des NewCaseDialog

**Problem:** In `new-case-dialog.tsx:338-346` (Step 2) gibt es sowohl "Weiter" als auch "Vorgang anlegen (ohne Dokumente)". Zwei primäre Aktionen verwirren den Nutzer.

**Vorschlag:**
- "Vorgang anlegen (ohne Dokumente)" als sekundären Button (`variant="outline"`) darstellen
- Oder: Diesen Button entfernen und in Step 3 nur "Überspringen & Anlegen" anbieten
- Klarer visueller Unterschied zwischen primärer und sekundärer Aktion

### 3.6 Unsichtbare Drag & Drop-Grenzen

**Problem:** Die Drag-Zone im `DocumentUploadZone` hat nur `border-dashed` als visuellen Hinweis. Es fehlt ein deutlicheres visuelles Feedback beim Drag-Over (z.B. Animation, Icon-Vergrößerung).

**Vorschlag:**
- Beim Drag-Over: Scale-Animation auf dem Upload-Icon, dunklerer Hintergrund, pulsierender Border
- Text ändern auf "Dateien loslassen zum Hochladen"
- Bessere visuelle Hierarchie der Dropzone

---

## 4. Barrierefreiheit (Accessibility)

### 4.1 Klickbare Cards ohne semantische Rolle

**Problem:** Case-Cards in `cases-page.tsx:188-283` und Playbook-Cards in `playbooks-page.tsx:126-167` sind klickbare `<Card>`-Elemente mit `onClick` und `cursor-pointer`, aber keine `<a>`- oder `<button>`-Elemente. Sie sind per Tastatur nicht erreichbar.

**Vorschlag:**
- Cards in `<Link>`-Elemente wrappen oder `role="link"` mit `tabIndex={0}` und `onKeyDown` (Enter/Space) hinzufügen
- Besser: Die gesamte Card als `<Link to={...}>` rendern und das Styling anpassen

### 4.2 Fehlende aria-labels auf Icon-Only-Buttons

**Problem:** Buttons mit nur Icons (z.B. "X" zum Schließen in `cases-search-filter.tsx:102-108`, Datei-Entfernen-Buttons) haben kein `aria-label`.

**Vorschlag:**
- `aria-label="Suche leeren"`, `aria-label="Datei entfernen"`, etc. auf allen Icon-Only-Buttons
- Alternativ: `sr-only` Text innerhalb des Buttons

### 4.3 Farbabhängige Informationen ohne Alternative

**Problem:** Finding-Schweregrade und Case-Status werden nur durch Farbe unterschieden (rot = kritisch, orange = hoch, gelb = mittel). Für farbenblinde Nutzer sind diese nicht unterscheidbar.

**Vorschlag:**
- Zusätzlich zu Farben: Icons pro Schweregrad verwenden (z.B. Schild-Icon für kritisch, Dreieck für hoch)
- Oder: Muster/Formen in Fortschrittsbalken (Dashboard) einsetzen
- Labels sind bereits vorhanden, aber die Fortschrittsbalken im Dashboard sind rein farbcodiert

### 4.4 Keine Skip-Navigation

**Problem:** Es gibt keinen "Skip to main content"-Link für Tastaturnutzer, die nicht bei jedem Seitenaufruf durch die Navigation tabben möchten.

**Vorschlag:**
- Versteckten Skip-Link (`sr-only focus:not-sr-only`) als erstes Element im `<body>` hinzufügen
- Sprungziel: `<main id="main-content">` (bereits semantisch vorhanden)

---

## 5. Visuelles Design & Konsistenz

### 5.1 Inkonsistente Dark-Mode-Stile

**Problem:** Die `ProfilePage` verwendet explizite Dark-Mode-Klassen direkt auf Komponenten (`dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100` in `profile-page.tsx:124`), obwohl das Design-System CSS-Variablen für Farben definiert. Andere Seiten nutzen die Variablen konsistent.

**Vorschlag:**
- Alle manuellen `dark:`-Klassen auf `ProfilePage` entfernen
- Stattdessen die CSS-Variablen aus `theme.css` nutzen (wie auf allen anderen Seiten)
- Dies vereinfacht auch zukünftige Theme-Anpassungen

### 5.2 Fehlende Hover-/Focus-States auf Tabellen-Zeilen

**Problem:** Die VVT-Übersicht-Tabelle hat keine visuellen Hover-States auf Zeilen, obwohl die Titel klickbar sind. Der Nutzer erkennt nicht auf den ersten Blick, welche Zeile er gerade betrachtet.

**Vorschlag:**
- `hover:bg-muted/50` auf `<TableRow>` für bessere Scanbarkeit
- Alternativ: Zebra-Striping (abwechselnde Hintergrundfarben)

### 5.3 Lange Zeilen im Step-Indicator

**Problem:** Die Verbindungslinien zwischen Steps im `NewCaseDialog` (`max-w-4`) sind zu kurz und wirken abgehackt. Der Step-Indicator sieht nicht wie eine zusammenhängende Progression aus.

**Vorschlag:**
- `max-w-4` entfernen und `flex-1` allein nutzen, damit die Linien den verfügbaren Platz füllen
- Oder: Ein dediziertes Stepper-Pattern mit durchgängiger Linie implementieren

### 5.4 Dashboard mit hardcodierten Trends

**Problem:** In `dashboard-stats.tsx:67-69` werden Trend-Daten hardcodiert angezeigt ("+2 seit letzter Woche", "-3 seit letzter Woche"), die nicht aus echten Daten berechnet werden.

**Vorschlag:**
- Trend-Daten aus dem API-Backend beziehen oder aus historischen Daten berechnen
- Wenn nicht verfügbar: Trend-Anzeige ausblenden statt falsche Werte anzeigen
- Gleiches gilt für "Ø 3.5 Tage in Review" (`dashboard-stats.tsx:102`)

---

## 6. Datenmanagement & Performance

### 6.1 Keine Pagination

**Problem:** `cases-page.tsx` und `vvt-overview-page.tsx` laden alle Datensätze auf einmal (`limit: 500`). Bei wachsender Nutzung (>100 Fälle) wird die Seite langsam.

**Vorschlag:**
- Server-seitige Pagination mit "Mehr laden"-Button oder Seitennummerierung
- `Pagination`-Komponente ist bereits in `/components/ui/pagination.tsx` vorhanden
- Alternativ: Infinite Scroll mit Intersection Observer

### 6.2 Kein Client-Side-Caching

**Problem:** Jede Navigation zwischen Seiten löst einen neuen API-Call aus. Es gibt keine Caching-Schicht (kein React Query, kein SWR), obwohl die Daten sich selten ändern.

**Vorschlag:**
- `@tanstack/react-query` einführen für:
  - Automatisches Caching mit konfigurierbarer Stale-Time
  - Hintergrund-Refetching
  - Optimistic Updates (z.B. bei Finding-Status-Änderungen)
  - Deduplizierte Requests

---

## Priorisierung

| Priorität | Nr.  | Thema                                  | Aufwand |
|-----------|------|----------------------------------------|---------|
| Erledigt  | 3.1  | Hardcodiertes Datum (Bug)              | —       |
| Kritisch  | 1.1  | Mobile Navigation                      | Mittel  |
| Hoch      | 1.2  | Header-Duplikation extrahieren         | Mittel  |
| Hoch      | 3.2  | Loading-State-Reihenfolge              | Gering  |
| Hoch      | 4.1  | Klickbare Cards als Links/Buttons      | Gering  |
| Hoch      | 3.3  | Toast-Benachrichtigungen               | Gering  |
| Hoch      | 5.4  | Dashboard-Trends hardcodiert           | Gering  |
| Mittel    | 2.1  | Responsive Tabellen                    | Mittel  |
| Mittel    | 4.2  | aria-labels auf Icon-Buttons           | Gering  |
| Mittel    | 4.3  | Farbunabhängige Informationen          | Mittel  |
| Mittel    | 3.5  | Zwei Submit-Buttons in Step 2          | Gering  |
| Mittel    | 1.3  | Breadcrumb-Navigation                  | Gering  |
| Mittel    | 6.1  | Pagination                             | Mittel  |
| Mittel    | 5.1  | Inkonsistente Dark-Mode-Stile          | Gering  |
| Mittel    | 5.2  | Hover-States auf Tabellen              | Gering  |
| Niedrig   | 2.2  | Dialog-Breite auf Mobile               | Gering  |
| Niedrig   | 2.3  | Filter-Layout auf Mobile               | Gering  |
| Niedrig   | 3.4  | Bestätigungsdialoge                    | Gering  |
| Niedrig   | 3.6  | Drag & Drop visuelles Feedback         | Gering  |
| Niedrig   | 4.4  | Skip-Navigation                        | Gering  |
| Niedrig   | 5.3  | Step-Indicator-Linien                  | Gering  |
| Niedrig   | 6.2  | Client-Side-Caching                    | Hoch    |

---

## Fazit

Die Anwendung hat eine solide technische Basis mit guter Komponentenstruktur. Die dringendsten Verbesserungen betreffen:

1. **Bug-Fix**: Hardcodiertes Datum bei Deadline-Berechnung
2. **Mobile UX**: Navigation für mobile Geräte nutzbar machen
3. **Code-Qualität**: Header-Komponente zentral extrahieren
4. **Nutzer-Feedback**: Toast-Benachrichtigungen bei Aktionen einbauen
5. **Barrierefreiheit**: Klickbare Cards als semantische Links umbauen

Diese fünf Punkte haben den größten positiven Effekt auf die Nutzererfahrung bei vergleichsweise geringem Aufwand.
