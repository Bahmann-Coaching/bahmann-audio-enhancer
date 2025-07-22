import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

STORAGE_DAYS = int(os.getenv("STORAGE_DAYS", 7))
ENHANCED_DIR = Path("data/enhanced")

async def cleanup_old_files():
    """Remove enhanced files older than STORAGE_DAYS"""
    try:
        if not ENHANCED_DIR.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=STORAGE_DAYS)
        removed_count = 0
        total_size = 0
        
        for file_path in ENHANCED_DIR.glob("enhanced_*"):
            if file_path.is_file():
                # Get file modification time
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    removed_count += 1
                    total_size += file_size
        
        if removed_count > 0:
            print(f">ù Cleanup: Removed {removed_count} files ({total_size / (1024*1024):.2f} MB) older than {STORAGE_DAYS} days")
            
    except Exception as e:
        print(f"L Cleanup error: {e}")

async def start_cleanup_task():
    """Run cleanup task daily at 3 AM"""
    while True:
        try:
            # Calculate seconds until next 3 AM
            now = datetime.now()
            next_3am = now.replace(hour=3, minute=0, second=0, microsecond=0)
            
            # If it's past 3 AM today, schedule for tomorrow
            if now >= next_3am:
                next_3am += timedelta(days=1)
            
            seconds_until_3am = (next_3am - now).total_seconds()
            
            # Wait until 3 AM
            await asyncio.sleep(seconds_until_3am)
            
            # Run cleanup
            await cleanup_old_files()
            
            # Wait a bit before next iteration to avoid double execution
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"L Cleanup scheduler error: {e}")
            # Wait 1 hour before retrying
            await asyncio.sleep(3600)

if __name__ == "__main__":
    # For manual testing
    asyncio.run(cleanup_old_files())