# Universal Video Downloader

A powerful, modern, and cross-platform video and audio downloader built with Python and CustomTkinter. It leverages the robust `yt-dlp` library to provide seamless downloading capabilities from almost any platform, including YouTube, Facebook, TikTok, Instagram, Twitter (X), and SoundCloud.

![Universal Video Downloader UI](#) *(Add your screenshot here)*

## 🌟 Features

* **Multi-Platform Support**: Download videos from YouTube, TikTok, Facebook, Instagram, X (Twitter), SoundCloud, and many more sites supported by `yt-dlp`.
* **High-Quality Formats**: Choose from various resolutions (1080p, 720p, 480p, Best Video) or extract audio directly to MP3.
* **Modern GUI**: A beautiful, user-friendly interface built with `CustomTkinter`, including easy toggles for Light and Dark themes.
* **Playlist & Channel Downloads**: Easily download entire playlists or specific, filtered videos from a playlist.
* **Smart Organization**: Automatically categorizes downloaded videos into specific folders based on the source platform (e.g., `/YouTube`, `/TikTok`).
* **Advanced Options**:
  * Option to download and embed subtitles (English/Vietnamese).
  * Embed video thumbnails directly into the MP4/MP3 files.
  * Time-based cutting/cropping: Download specific parts of a video by specifying start and end times.
  * Browser Cookie integration: Bypass age-restricted or private content by using cookies from your installed browsers (Chrome, Edge, Firefox, Brave).
* **Download Queue & History**: Queue up multiple downloads at once. Easily review your download history and quickly open download folders.

## 🚀 Installation & Requirements

Ensure you have **Python 3.8+** installed on your system. 

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tridpt/UniversalVideoDownloader.git
   cd UniversalVideoDownloader
   ```

2. **Install dependencies:**
   Install required Python packages utilizing `pip`:
   ```bash
   pip install customtkinter yt-dlp Pillow requests 
   ```
   *Note: Ensure you have FFmpeg available in your PATH or update the FFmpeg binary path inside `main.py` (e.g. via `static_ffmpeg`)*.

3. **Run the App:**
   ```bash
   python main.py
   ```

## 🛠️ Usage

1. **Paste a Link**: Put the video URL in the input box. The app will fetch the video details (Title, Thumbnail, Size estimate) automatically.
2. **Choose Format**: Select your desired quality or select 'Audio (MP3)'.
3. **Save Directory**: Choose where you want to save the files. Checking 'Smart Folder' will auto-create subfolders based on the website.
4. **Download**: Hit "Tải / Tải Thêm" to queue the video. You can queue multiple links simultaneously. 

## 👨‍💻 Developer & Acknowledgments

* Developed by **Trần Đức Trí**.
* Built using [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## 📄 License

This project is open-source and available under the MIT License.
