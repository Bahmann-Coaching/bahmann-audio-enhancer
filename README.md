# <µ Bahmann Audio Enhancer

Ein professionelles Audio-Enhancement-Tool für Social Media Teams, basierend auf der ai-coustics API.

## Features

- **Audio Enhancement**: Professionelle Audio-Verbesserung mit KI
- **Social Media Presets**: Vorgefertigte Einstellungen für Instagram, YouTube, TikTok und Podcasts
- **Parallele Verarbeitung**: Mehrere Dateien können gleichzeitig verarbeitet werden
- **7-Tage Speicherung**: Automatisches Cleanup alter Dateien
- **Monitoring**: Tägliche Slack-Reports über Nutzung und Statistiken
- **Drag & Drop**: Einfache Bedienung über Web-Interface

## Installation

### Lokale Entwicklung

1. Repository klonen:
```bash
git clone https://github.com/Bahmann-Coaching/bahmann-audio-enhancer.git
cd bahmann-audio-enhancer
```

2. Virtuelle Umgebung erstellen:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows
```

3. Dependencies installieren:
```bash
pip install -r requirements.txt
```

4. Environment-Variablen konfigurieren:
```bash
cp .env.example .env
# .env Datei mit API Keys ausfüllen
```

5. Anwendung starten:
```bash
python main.py
```

Die Anwendung ist dann unter http://localhost:8000 erreichbar.

### Docker Deployment

```bash
docker-compose up -d
```

## Konfiguration

Erstellen Sie eine `.env` Datei basierend auf `.env.example`:

```env
# ai-coustics API
AI_COUSTICS_API_KEY=your_api_key_here

# Slack Integration (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#audio-enhancer

# Server Configuration
UPLOAD_MAX_SIZE_MB=100
STORAGE_DAYS=7
MAX_CONCURRENT_ENHANCEMENTS=5
```

## API Endpoints

- `GET /` - Web-Interface
- `POST /api/enhance` - Audio Enhancement
- `GET /api/download/{filename}` - Download enhanced file
- `GET /api/stats` - Tagesstatistiken
- `GET /api/presets` - Verfügbare Presets

## Presets

| Preset | Loudness Target | Peak Limit | Enhancement Level | Verwendung |
|--------|----------------|------------|-------------------|------------|
| Instagram Story | -14 LUFS | -1 dbTP | 80% | Instagram Stories |
| YouTube | -14 LUFS | -1 dbTP | 100% | YouTube Videos |
| TikTok | -14 LUFS | -1 dbTP | 90% | TikTok Videos |
| Podcast | -16 LUFS | -1 dbTP | 100% | Podcasts & Sprache |
| Custom | Variabel | Variabel | Variabel | Eigene Einstellungen |

## Monitoring

Das Tool sendet täglich um 23:50 Uhr einen Report an Slack mit:
- Anzahl der Enhancements
- Verarbeitete Audio-Minuten
- Durchschnittliche Bearbeitungszeit
- Beliebteste Presets
- Erfolgsrate

## Wartung

- **Automatisches Cleanup**: Täglich um 3:00 Uhr werden Dateien älter als 7 Tage gelöscht
- **Logs**: Alle Anfragen werden in `data/audio.db` gespeichert
- **Speicherplatz**: Enhanced Audio-Dateien in `data/enhanced/`

## Technologie-Stack

- **Backend**: FastAPI, Python 3.11
- **API**: ai-coustics Audio Enhancement API
- **Datenbank**: SQLite für Logging
- **Audio-Processing**: pydub, ffmpeg
- **Monitoring**: Slack Webhooks
- **Deployment**: Docker

## Support

Bei Fragen oder Problemen wenden Sie sich an das IT-Team.