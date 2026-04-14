import yt_dlp

def my_hook(d):
    print("STATUS:", d['status'])
    print("TMP:", d.get('tmpfilename'))
    print("FILE:", d.get('filename'))
    if d['status'] == 'downloading':
        print("CANCELLING...")
        raise Exception("CANCELLED_BY_USER")

ydl_opts = {
    'progress_hooks': [my_hook],
    'quiet': False
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    try:
        ydl.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=True)
    except Exception as e:
        print("CAUGHT EXCEPTION:", e)
