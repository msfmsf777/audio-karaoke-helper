<p align="center">
  <strong>English</strong> | <a href="#-traditional-chinese">繁體中文</a>
</p>

---

# The Karaoke Accompaniment Helper

A simple tool designed for streamers who love to sing! This application solves a common problem: *how to listen to a vocal guide track while your audience only hears the instrumental and your live voice.*

## ✨ Features

* **Split Audio Routing:** Plays two audio files simultaneously to two different audio devices.
* **Designed for Singing Streamers:**
    * **Your Headphones:** You hear the instrumental + the original vocals, so you can follow along.
    * **Your Stream (OBS, etc.):** Your audience hears only the instrumental, ready to be mixed with your live microphone input.
* **Full Playback Controls:** Includes play, pause, a scrubbable progress bar, volume control, and skip buttons.
* **Portable:** Can be packaged into a single, all-in-one executable that runs without installation.
* **CURRENTLY ONLY SUPPORTS TRADITIONAL CHINESE**
* **CURRENTLY ONLY TESTED ON WINDOWS SYSTEMS**

## 🚀 How to Use (For End-Users)

1.  Go to the [**Releases Page**](https://github.com/msfmsf777/audio-karaoke-helper/releases) for this project.
2.  Download the latest `.zip` file from the "Assets" section.
3.  Unzip the folder.
4.  Double-click the `白芙妮的伴唱小幫手V1.0.exe` file to run the application. No installation is needed!

## 💻 How to Use (For Developers)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/msfmsf777/audio-karaoke-helper.git](https://github.com/msfmsf777/audio-karaoke-helper.git)
    cd audio-karaoke-helper
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Get FFmpeg:** The `pydub` library requires FFmpeg to process audio files like MP3s.
    * Download the "essentials" build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip).
    * Unzip the file and find `ffmpeg.exe` and `ffprobe.exe` inside the `bin` folder.
    * Place these two `.exe` files in the root of the project folder.

5.  **Run the script:**
    ```bash
    python main.py
    ```

## 🙏 Acknowledgements

* Built with [FreeSimpleGUI](https://github.com/FreeSimpleGUI/FreeSimpleGUI), a community-maintained fork of PySimpleGUI version 4.
* Audio processing powered by [pydub](https://github.com/jiaaro/pydub).
* Audio playback handled by [sounddevice](https://python-sounddevice.readthedocs.io/).
* Created by MSF神鋒, follow my [Twitter (X)](https://x.com/msfmsf777) to report your experience or bug.

---

# <a name="-traditional-chinese"></a>歌回伴唱小幫手 (繁體中文)

一款專為喜歡唱歌的直播主設計的簡單工具！本應用程式解決了一個常見問題：*如何在聽取人聲引導音軌的同時，讓您的觀眾只聽到伴奏和您的現場歌聲。*

## ✨ 功能

* **音訊分離路由：** 將兩個音訊檔案同時播放到兩個不同的音訊裝置。
* **專為歌唱直播主設計：**
    * **您的耳機：** 您會聽到伴奏＋原唱人聲，方便您跟唱。
    * **您的直播（OBS等）：** 您的觀眾只會聽到伴奏，可與您的麥克風現場輸入混合。
* **完整的播放控制：** 包含播放、暫停、可拖動的進度條、音量控制和快進/快退按鈕。
* **便攜式設計：** 可打包成單一、整合的執行檔（`.exe`），無需安裝即可運行。
* **目前僅支援繁體中文**
* **目前僅在WINDOWS系統上測試**

## 🚀 如何使用（給一般使用者）

1.  前往本專案的 [**Releases 發佈頁面**](https://github.com/msfmsf777/audio-karaoke-helper/releases)。
2.  在 "Assets" 區塊下載最新的 `.zip` 檔案。
3.  解壓縮該資料夾。
4.  雙擊 `白芙妮的伴唱小幫手V1.0.exe` 檔案即可運行本應用程式。無需任何安裝！

## 💻 如何使用（給開發者）

1.  **克隆儲存庫：**
    ```bash
    git clone [https://github.com/msfmsf777/audio-karaoke-helper.git](https://github.com/msfmsf777/audio-karaoke-helper.git)
    cd audio-karaoke-helper
    ```

2.  **建立虛擬環境（建議）：**
    ```bash
    python -m venv .venv
    # 在 Windows 上
    .venv\Scripts\activate
    # 在 macOS/Linux 上
    source .venv/bin/activate
    ```

3.  **安裝所需的函式庫：**
    ```bash
    pip install -r requirements.txt
    ```

4.  **取得 FFmpeg：** `pydub` 函式庫需要 FFmpeg 來處理 MP3 等音訊檔案。
    * 從 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip) 下載 "essentials" 版本。
    * 解壓縮檔案，並在 `bin` 資料夾中找到 `ffmpeg.exe` 和 `ffprobe.exe`。
    * 將這兩個 `.exe` 檔案放置在專案的根目錄下。

5.  **運行腳本：**
    ```bash
    python main.py
    ```

## 🙏 致謝

* 使用 [FreeSimpleGUI](https://github.com/FreeSimpleGUI/FreeSimpleGUI)（由社群維護的 PySimpleGUI 第4版分支）建構。
* 音訊處理由 [pydub](https://github.com/jiaaro/pydub) 提供支援。
* 音訊播放由 [sounddevice](https://python-sounddevice.readthedocs.io/) 處理。
* 作者：MSF神鋒，歡迎追隨我的 [Twitter (X)](https://x.com/msfmsf777) 來回報您的使用體驗或錯誤。
