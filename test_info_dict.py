import yt_dlp

def my_hook(d):
    info = d.get('info_dict', {})
    print("KEYS:", info.keys())
    print("_filename:", info.get('_filename'))
    print("filename:", d.get('filename'))
    raise Exception("CANCEL!")

ydl_opts = {
    'progress_hooks': [my_hook],
    'quiet': False
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=True)
except Exception as e:
    pass
