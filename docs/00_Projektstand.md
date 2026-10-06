# Projektstand (Übergabe an nächste Session)

Stand: 6. Oktober 2026

## Erledigt
1. Dateien, Programme und Konfiguration geprüft (HyperFrames CLI 0.8.136 via npx, ffmpeg, Chromium unter /opt/pw-browsers, Schrift Inter).
2. Skript und Szenen: `docs/01_Sprechskript_und_Szenen.md`. VON SOPHIE FREIGEGEBEN am 6.10.2026 (inkl. Änderung: Kapitel 6 «Mein Wunsch» statt Transferaufgabe).
3. Quellenliste: `docs/02_Quellen.md`.
4. Assets: Fotos `assets/fotos/`, Logos `assets/logos/`, Referenz-PDFs `assets/referenzen/`.

## Hinweise
- Hundertmark-Logo (`assets/logos/hundertmark_logo.png`) ist als gelieferte Datei SCHWARZ auf transparent (nicht weiss). Es wird deshalb direkt auf Weiss gesetzt, ohne schwarze Logofläche.
- HSLU-Logo: `assets/logos/HSLU_Logo_DE_Schwarz.jpg`, oben rechts auf Weiss.
- ElevenLabs-Key: aus Umgebungsvariable `ELEVENLABS_API_KEY` (oder lokale `.env`, nie committen, nie ausgeben).
- Nur Standardstimmen (category premade/default), keine Voice Library, kein Klon. Kontingent vor Vertonung prüfen (/v1/user/subscription). Vollvertonung ca. 7'700 Zeichen.
- Timing-Endpunkt: POST /v1/text-to-speech/{voice_id}/with-timestamps, Zeichen-Alignment -> Wortzeiten ableiten. Modell bevorzugt eleven_multilingual_v2.

## Nächste Schritte
1. Drei Hörbeispiele mit dem Satz «KI kann uns beim Lernen und Arbeiten enorm helfen – wenn wir selber mitdenken.» erzeugen, Sophie vorstellen, auf Stimmwahl warten.
2. Video bauen (HyperFrames), QR https://wa.me/41789005346, Frames prüfen, QR aus Videoframe decodieren.
3. Ausgabe: `KI_nutzen_selber_denken_Sophie_Hundertmark.mp4`, SRT, Beispielprompts, Projekt.
