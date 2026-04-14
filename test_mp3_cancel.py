import yt_dlp
import os
import time

is_cancelled = False
temp_files = []

def my_hook(d):
    global is_cancelled
    if is_cancelled:
        raise Exception("CANCELLED_BY_USER")
    
    if d['status'] == 'downloading':
        tmp = d.get('tmpfilename')
        if tmp and tmp not in temp_files:
            temp_files.append(tmp)
            print("ADDED TMP:", tmp)
            
            # Cancel after a tiny bit
            if d.get('downloaded_bytes', 0) > 100000:
                print("TRIGGERING CANCEL!")
                is_cancelled = True

ydl_opts = {
    'progress_hooks': [my_hook],
    'quiet': False,
    'format': 'bestaudio/best',
    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    # Use existing ffmpeg if possible
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=True)
except Exception as e:
    print("Caught:", e)
    if "CANCELLED_BY_USER" in str(e):
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                print("DELETED:", f)

print("--- SECOND RUN ---")
is_cancelled = False
temp_files = []
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=True)
except Exception as e:
    print("Caught:", e)
