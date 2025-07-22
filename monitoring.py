import os
import httpx
import aiosqlite
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

DATABASE_PATH = "data/audio.db"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#audio-enhancer")

async def init_database():
    """Initialize SQLite database for request logging"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS enhancement_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                preset TEXT,
                duration_seconds REAL,
                processing_time REAL,
                file_size_mb REAL,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for date queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_date 
            ON enhancement_requests(date)
        """)
        
        await db.commit()

async def log_request(
    success: bool,
    preset: str = "unknown",
    duration_seconds: float = 0,
    processing_time: float = 0,
    file_size_mb: float = 0,
    error: Optional[str] = None
):
    """Log an enhancement request to database"""
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        today = date.today().isoformat()
        timestamp = datetime.now().isoformat()
        
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """INSERT INTO enhancement_requests 
                   (date, timestamp, success, preset, duration_seconds, 
                    processing_time, file_size_mb, error_message) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (today, timestamp, success, preset, duration_seconds, 
                 processing_time, file_size_mb, error)
            )
            await db.commit()
            
    except Exception as e:
        print(f"Monitoring error: {e}")

async def get_today_stats():
    """Get today's enhancement statistics"""
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        today = date.today().isoformat()
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Basic stats
            cursor = await db.execute(
                """SELECT 
                    COUNT(*) as total,
                    SUM(success) as successful,
                    SUM(duration_seconds) as total_duration,
                    AVG(processing_time) as avg_processing_time,
                    SUM(file_size_mb) as total_size_mb
                   FROM enhancement_requests 
                   WHERE date = ?""",
                (today,)
            )
            row = await cursor.fetchone()
            
            # Preset stats
            cursor = await db.execute(
                """SELECT preset, COUNT(*) as count
                   FROM enhancement_requests 
                   WHERE date = ? AND success = 1
                   GROUP BY preset
                   ORDER BY count DESC""",
                (today,)
            )
            preset_stats = await cursor.fetchall()
            
            return {
                "total": row[0] or 0,
                "successful": row[1] or 0,
                "failed": (row[0] or 0) - (row[1] or 0),
                "total_audio_minutes": round((row[2] or 0) / 60, 2),
                "avg_processing_seconds": round(row[3] or 0, 2),
                "total_size_mb": round(row[4] or 0, 2),
                "presets": {preset: count for preset, count in preset_stats}
            }
    except Exception as e:
        print(f"Stats error: {e}")
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "total_audio_minutes": 0,
            "avg_processing_seconds": 0,
            "total_size_mb": 0,
            "presets": {}
        }

async def send_daily_summary():
    """Send end-of-day summary to Slack"""
    if not SLACK_WEBHOOK_URL:
        print("Slack webhook not configured, skipping daily summary")
        return
    
    try:
        stats = await get_today_stats()
        if stats["total"] == 0:
            return  # No requests today
        
        # Get hourly distribution
        today = date.today().isoformat()
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                """SELECT 
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as count
                   FROM enhancement_requests 
                   WHERE date = ?
                   GROUP BY hour
                   ORDER BY hour""",
                (today,)
            )
            hourly_data = await cursor.fetchall()
        
        # Find peak hour
        peak_hour = max(hourly_data, key=lambda x: x[1]) if hourly_data else ("00", 0)
        
        # Format preset statistics
        preset_lines = []
        for preset, count in stats["presets"].items():
            preset_lines.append(f"  • {preset}: {count}")
        presets_text = "\n".join(preset_lines) if preset_lines else "  Keine Preset-Daten"
        
        # Calculate success rate
        success_rate = round((stats["successful"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0
        
        # Format message
        message_text = f"""=� *Audio Enhancer Tagesbericht*

<� *Zusammenfassung:*
" Anfragen gesamt: *{stats['total']}*
" Erfolgreich: {stats['successful']} ({success_rate}%)
" Fehlgeschlagen: {stats['failed']}

=� *Statistiken:*
" Audio-Minuten verarbeitet: *{stats['total_audio_minutes']} min*
" Durchschn. Bearbeitungszeit: {stats['avg_processing_seconds']}s
" Gesamtgr��e: {stats['total_size_mb']} MB
" Hauptnutzungszeit: {peak_hour[0]}:00 Uhr ({peak_hour[1]} Anfragen)

<� *Presets verwendet:*
{presets_text}"""

        message = {
            "text": "Audio Enhancer Tagesbericht",
            "channel": SLACK_CHANNEL,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(SLACK_WEBHOOK_URL, json=message)
            if response.status_code == 200:
                print(f" Daily summary sent: {stats['total']} enhancements")
            else:
                print(f"L Daily summary failed: {response.status_code}")
                
    except Exception as e:
        print(f"L Daily summary error: {e}")

def get_seconds_until_midnight():
    """Calculate seconds until next midnight"""
    now = datetime.now()
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return int((midnight - now).total_seconds())