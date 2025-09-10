import os
import sys
import time
import threading
import PySimpleGUI as sg
import tempfile
from pydub import AudioSegment
import sounddevice as sd
import numpy as np
import webbrowser
from math import exp
import platform

# --- DPI Awareness Fix for Windows ---
# This is the standard solution to prevent blurry fonts on high-DPI displays.
# It tells Windows that the application can handle its own scaling.
if platform.system() == "Windows":
    try:
        import ctypes
        # Set process DPI awareness to "System Aware"
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        print("DEBUG: DPI awareness set to System Aware.")
    except Exception as e:
        print(f"Warning: Could not set DPI awareness. Fonts may appear blurry. Error: {e}")


# --- Helper function to find bundled files (for PyInstaller) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Font Loading Logic ---
CUSTOM_FONT_NAME = "GenSenRounded2 TW R"
CUSTOM_FONT_FILE = "GenSenRounded2TW-R.otf"

try:
    font_path = resource_path(os.path.join("assets", CUSTOM_FONT_FILE))
    print(f"DEBUG: Attempting to load font from path: {font_path}")
    if not os.path.exists(font_path):
        print(f"ERROR: Font file not found. Please check 'assets' folder.")
        raise FileNotFoundError("Font file not found")

    if platform.system() == "Windows":
        import ctypes
        gdi32 = ctypes.WinDLL('gdi32')
        fonts_added = gdi32.AddFontResourceW(font_path)
        if fonts_added > 0:
            print(f"Successfully registered {fonts_added} font(s) from: {CUSTOM_FONT_FILE}")
            sg.set_options(font=(CUSTOM_FONT_NAME, 11))
        else:
            print(f"Warning: Windows failed to register font.")
            raise OSError("Windows GDI failed to add font resource")
    else:
        sg.set_options(font=(CUSTOM_FONT_NAME, 11))
except Exception as e:
    print(f"Font loading error: {e}. Falling back to default font.")
    sg.set_options(font=("Helvetica", 10))

# --- Robust Custom Tooltip Manager ---
class TooltipManager:
    _tooltip_window = None
    _show_timer = None
    _tk_root = None

    @classmethod
    def init(cls, window):
        cls._tk_root = window.TKroot

    @classmethod
    def bind(cls, widget, text):
        widget.bind("<Enter>", lambda e, w=widget, t=text: cls._schedule_show(w, t))
        widget.bind("<Leave>", lambda e: cls._hide())

    @classmethod
    def _schedule_show(cls, widget, text):
        cls._hide()  # Cancel any previous tooltip
        cls._show_timer = cls._tk_root.after(500, lambda: cls._show(widget, text))

    @classmethod
    def _hide(cls):
        if cls._show_timer:
            cls._tk_root.after_cancel(cls._show_timer)
            cls._show_timer = None
        if cls._tooltip_window:
            cls._tooltip_window.hide()

    @classmethod
    def _show(cls, widget, text):
        if not cls._tk_root: return

        x = widget.winfo_rootx() + 25
        y = widget.winfo_rooty() + 20

        if not cls._tooltip_window:
            bg_color = sg.theme_background_color()
            text_color = sg.theme_text_color()
            layout = [[sg.Text("", key='-TOOLTIP_TEXT-', background_color=bg_color, text_color=text_color)]]
            cls._tooltip_window = sg.Window("", layout,
                                            no_titlebar=True, keep_on_top=True,
                                            background_color=bg_color, finalize=True,
                                            grab_anywhere=False)
            cls._tooltip_window.hide()

        cls._tooltip_window['-TOOLTIP_TEXT-'].update(text)
        cls._tooltip_window.move(x, y)
        cls._tooltip_window.un_hide()
        cls._tooltip_window.bring_to_front()

    @classmethod
    def close(cls):
        """Safely close the tooltip window resource."""
        if cls._tooltip_window:
            cls._tooltip_window.close()
            cls._tooltip_window = None

# ---------------- Configuration / Tuning ----------------
UI_TIMEOUT_MS = 100
AUDIO_BLOCKSIZE = 1024
FADE_MS = 300
FADE_STEP_MS = 25
SCRUB_DEBOUNCE = 0.15

# ---------------- Global state ----------------
audio_loaded = False
mixed_file = None
background_file = None
playing = False
position = 0
duration = 0.0
mixed_audio_data = None
background_audio_data = None
sample_rate = 44100
headphone_device_id = None
virtual_device_id = None
master_volume = 0.7
fade_gain = 1.0
mixed_stream = None
background_stream = None
current_bg_path = ""
current_vocal_path = ""
files_enabled = True
play_session = 0
streams_running = False
last_tick = None
fade_lock = threading.Lock()
fade_thread = None
stop_after_fade = threading.Event()
playback_lock = threading.RLock()
is_seeking = False
seek_lock = threading.Lock()
pending_seek_active = False
pending_seek_value = 0
pending_seek_time = 0.0

# ---------------- Helpers ----------------
def format_time(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_output_devices():
    try:
        devices = sd.query_devices()
        output_devices = [
            (i, f"{d['name']} - {int(d['default_samplerate'])} Hz")
            for i, d in enumerate(devices)
            if d['max_output_channels'] > 0
        ]
        if output_devices:
            return output_devices
        # Fallback if no devices are found
        return []
    except Exception as e:
        print(f"ERROR: Could not query audio devices: {e}")
        return []

# ---------------- Worker: load audio ----------------
def load_worker(bg_path, vocal_path, window):
    global mixed_file, background_file, audio_loaded, duration, mixed_audio_data, background_audio_data, \
           sample_rate, current_bg_path, current_vocal_path, files_enabled, position, last_tick
    try:
        window.write_event_value("-LOAD_PROGRESS_EVENT-", 0)
        bg_audio = AudioSegment.from_file(bg_path).set_channels(2).set_frame_rate(44100)
        window.write_event_value("-LOAD_PROGRESS_EVENT-", 25)
        vocal_audio = AudioSegment.from_file(vocal_path).set_channels(2).set_frame_rate(44100)
        window.write_event_value("-LOAD_PROGRESS_EVENT-", 50)
        mixed_audio = bg_audio.overlay(vocal_audio, gain_during_overlay=-6)
        window.write_event_value("-LOAD_PROGRESS_EVENT-", 75)
        mixed_file = tempfile.mktemp(suffix='.wav')
        background_file = tempfile.mktemp(suffix='.wav')
        mixed_audio.export(mixed_file, format="wav")
        bg_audio.export(background_file, format="wav")
        mixed_samples = np.array(mixed_audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        background_samples = np.array(bg_audio.get_array_of_samples(), dtype=np.float32) / 32768.0
        mixed_audio_data = mixed_samples.reshape(-1, 2)
        background_audio_data = background_samples.reshape(-1, 2)
        sample_rate = mixed_audio.frame_rate
        duration = len(bg_audio) / 1000.0
        audio_loaded = True
        current_bg_path = bg_path
        current_vocal_path = vocal_path
        files_enabled = False
        position = 0
        last_tick = None
        window.write_event_value("-LOAD_PROGRESS_EVENT-", 100)
        window.write_event_value("-LOAD_DONE-", True)
    except Exception as e:
        window.write_event_value("-LOAD_DONE-", f"ERROR: {e}")

# ---------------- Audio Playback Callback ----------------
def play_callback(outdata, frames, time_info, status, audio_data, start_frame):
    global fade_gain, master_volume
    try:
        end_frame = start_frame[0] + frames
        if start_frame[0] >= len(audio_data):
            outdata[:] = np.zeros((frames, 2), dtype=np.float32)
            raise sd.CallbackStop
        if end_frame > len(audio_data):
            end_frame = len(audio_data)
            outdata[:end_frame - start_frame[0]] = audio_data[start_frame[0]:end_frame] * (master_volume * fade_gain)
            outdata[end_frame - start_frame[0]:] = 0
            start_frame[0] = end_frame
            raise sd.CallbackStop
        else:
            outdata[:] = audio_data[start_frame[0]:end_frame] * (master_volume * fade_gain)
            start_frame[0] = end_frame
    except Exception:
        raise sd.CallbackStop

# ---------------- Exponential fade helper ----------------
def expo_curve(t, alpha=5.0):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return (exp(alpha * t) - 1.0) / (exp(alpha) - 1.0)

# ---------------- Fade logic (session-aware) ----------------
def ramp_fade(target_gain, duration_ms, session_id):
    global fade_gain, stop_after_fade, mixed_stream, background_stream, playing, last_tick, streams_running, play_session
    step = FADE_STEP_MS / 1000.0
    steps = max(1, int(duration_ms / FADE_STEP_MS))
    with fade_lock:
        start_gain = fade_gain
    for i in range(1, steps + 1):
        if session_id != play_session: return
        t = i / steps
        factor = expo_curve(t, alpha=5.0)
        new_gain = float(start_gain + (target_gain - start_gain) * factor)
        with fade_lock:
            fade_gain = new_gain
        time.sleep(step)
    with fade_lock:
        fade_gain = float(target_gain)
    if target_gain == 0.0 and stop_after_fade.is_set() and session_id == play_session:
        with playback_lock:
            try:
                if mixed_stream and mixed_stream.active: mixed_stream.stop(); mixed_stream.close()
            except Exception: pass
            try:
                if background_stream and background_stream.active: background_stream.stop(); background_stream.close()
            except Exception: pass
            if session_id == play_session:
                playing = False
                streams_running = False
            stop_after_fade.clear()
            last_tick = None

# ---------------- Playback start/stop (session-managed) ----------------
def start_playback_fast():
    global mixed_stream, background_stream, last_tick, fade_thread, fade_gain, stop_after_fade, streams_running, play_session, playing
    with playback_lock:
        play_session += 1
        my_session = play_session
        try: stop_after_fade.clear()
        except Exception: pass

        try:
            if mixed_stream is not None:
                try:
                    if mixed_stream.active: mixed_stream.stop()
                except Exception: pass
                try: mixed_stream.close()
                except Exception: pass
        except Exception: pass
        try:
            if background_stream is not None:
                try:
                    if background_stream.active: background_stream.stop()
                except Exception: pass
                try: background_stream.close()
                except Exception: pass
        except Exception: pass

        mixed_stream, background_stream, streams_running = None, None, False
        start_frame_mixed = [int(position * sample_rate)]
        start_frame_background = [int(position * sample_rate)]
        try:
            mixed_stream = sd.OutputStream(samplerate=sample_rate, channels=2, device=headphone_device_id, callback=lambda o, f, t, s: play_callback(o, f, t, s, mixed_audio_data, start_frame_mixed), blocksize=AUDIO_BLOCKSIZE)
            background_stream = sd.OutputStream(samplerate=sample_rate, channels=2, device=virtual_device_id, callback=lambda o, f, t, s: play_callback(o, f, t, s, background_audio_data, start_frame_background), blocksize=AUDIO_BLOCKSIZE)
            fade_gain = 0.0
            mixed_stream.start()
            background_stream.start()
            streams_running = True
            last_tick = time.time()
            fade_thread = threading.Thread(target=ramp_fade, args=(1.0, FADE_MS, my_session), daemon=True)
            fade_thread.start()
        except Exception as e:
            streams_running = playing = False
            try:
                if mixed_stream and mixed_stream.active: mixed_stream.stop(); mixed_stream.close()
            except Exception: pass
            try:
                if background_stream and background_stream.active: background_stream.stop(); background_stream.close()
            except Exception: pass
            mixed_stream, background_stream = None, None
            print(f"ERROR: Playback start error: {e}")
            sg.popup_error(f"無法開始播放。請檢查您的音訊裝置設定。\n\n錯誤: {e}", title="播放錯誤")


def stop_playback_fast_with_fade():
    global fade_thread, stop_after_fade, play_session
    with playback_lock:
        session_at_request = play_session
        stop_after_fade.set()
        fade_thread = threading.Thread(target=ramp_fade, args=(0.0, FADE_MS, session_at_request), daemon=True)
        fade_thread.start()

# ---------------- High-level controls (thread-safe) ----------------
def play_pause():
    global playing
    if playing:
        stop_playback_fast_with_fade()
    else:
        if not audio_loaded: return
        playing = True
        threading.Thread(target=start_playback_fast, daemon=True).start()

def stop_immediate():
    global playing, position, mixed_stream, background_stream, last_tick, fade_gain, stop_after_fade, streams_running, play_session
    print("DEBUG: stop_immediate() called!")
    with playback_lock:
        play_session += 1
        try:
            if mixed_stream and mixed_stream.active: mixed_stream.stop(); mixed_stream.close()
        except Exception: pass
        try:
            if background_stream and background_stream.active: background_stream.stop(); background_stream.close()
        except Exception: pass
        mixed_stream, background_stream = None, None
        playing = False
        position = 0
        fade_gain = 1.0
        last_tick = None
        streams_running = False
        try: stop_after_fade.clear()
        except Exception: pass

def seek(new_position):
    global position, stop_after_fade, is_seeking
    print(f"DEBUG: seek() called with new_position: {new_position}")
    
    with seek_lock:
        is_seeking = True

    position = int(max(0, min(new_position, int(duration))))
    try: stop_after_fade.clear()
    except Exception: pass
    
    if playing:
        threading.Thread(target=_restart_playback_at_position, args=(position,), daemon=True).start()
    else: # If paused, just update position and reset flag
        global last_tick
        last_tick = None # Reset tick timer
        with seek_lock:
            is_seeking = False

def _restart_playback_at_position(pos):
    global position, is_seeking
    print(f"DEBUG: _restart thread started for position: {pos}")
    try:
        with playback_lock:
            position = pos
            start_playback_fast()
    except Exception as e:
        print(f"ERROR: Error restarting playback: {e}")
        global playing
        playing = False
    finally:
        with seek_lock:
            is_seeking = False

def update_progress_time_based():
    global position, last_tick
    if not playing: return position
    now = time.time()
    if last_tick is None:
        last_tick = now
        return position
    elapsed = now - last_tick
    if elapsed >= 1.0:
        inc = int(elapsed)
        position += inc
        last_tick += inc
        if position >= duration: stop_immediate()
    return position

def rewind_5sec():
    global position, pending_seek_active, pending_seek_value, pending_seek_time, window
    if not audio_loaded: return
    new_pos = max(0, int(position - 5))
    window['-PROGRESS-'].update(value=new_pos)
    window['-TIME_DISPLAY-'].update(f"{format_time(new_pos)} / {format_time(duration)}")
    if not playing:
        seek(new_pos)
    else:
        pending_seek_value = new_pos
        pending_seek_time = time.time()
        pending_seek_active = True

def forward_5sec():
    global position, pending_seek_active, pending_seek_value, pending_seek_time, window
    if not audio_loaded: return
    new_pos = min(int(duration), int(position + 5))
    window['-PROGRESS-'].update(value=new_pos)
    window['-TIME_DISPLAY-'].update(f"{format_time(new_pos)} / {format_time(duration)}")
    if not playing:
        seek(new_pos)
    else:
        pending_seek_value = new_pos
        pending_seek_time = time.time()
        pending_seek_active = True

# ---------------- Mark "needs reload" ----------------
def mark_needs_reload(window):
    global audio_loaded, files_enabled, playing, streams_running, position, duration
    audio_loaded = False
    files_enabled = True
    duration = 0.0
    
    window['-LOAD-'].update(disabled=False)
    window['-LOAD_PROGRESS-'].update(0)
    window['-LOAD_STATUS-'].update("")
    
    try: 
        stop_immediate()
    except Exception: 
        pass
    
    window['-PROGRESS-'].update(disabled=True, value=0)
    window['-PLAY_PAUSE-'].update(disabled=True, text="播放/暫停")
    window['-STOP-'].update(disabled=True)
    window['-REWIND-'].update(disabled=True)
    window['-FORWARD-'].update(disabled=True)
    window['-TIME_DISPLAY-'].update(f"{format_time(0)} / {format_time(duration)}")

# ---------------- GUI Layout ----------------
output_devices = get_output_devices()
device_names = [d[1] for d in output_devices]
device_ids = {d[1]: d[0] for d in output_devices}

# Gracefully handle systems with < 2 audio devices
default_headphone = ""
default_virtual = ""
if len(device_names) >= 2:
    default_headphone = device_names[0]
    default_virtual = device_names[1]
elif len(device_names) == 1:
    default_headphone = device_names[0]
    default_virtual = device_names[0] # Use the same device if only one is available

layout = [
    [sg.Text("歌回伴唱小幫手", font=(CUSTOM_FONT_NAME, 20), justification="center", expand_x=True)],
    [sg.Text("直播唱歌需要伴唱但又不想讓觀衆聽到原唱人聲？那這就是爲尼專門打造的小程式~\n這是能將伴奏與人聲分離並路由到不同輸出裝置的工具。選擇伴奏，人聲檔，輸出裝置後按 加載。\n注意: 請確保伴奏和人聲檔案拍子一致。"),],
    [sg.Text("伴奏儅"), sg.Input(key="-BG-", expand_x=True, enable_events=True), sg.FileBrowse(file_types=(("Audio Files", "*.mp3 *.wav"),), key="-BG_BROWSE-")],
    [sg.Text("人聲檔"), sg.Input(key="-VOCAL-", expand_x=True, enable_events=True), sg.FileBrowse(file_types=(("Audio Files", "*.mp3 *.wav"),), key="-VOCAL_BROWSE-")],
    [sg.Text("耳機輸出設備"), sg.Text('ⓘ', key='-INFO1-'), sg.Combo(device_names, default_value=default_headphone, key="-HEADPHONE-", readonly=True, size=(58,1), enable_events=True)],
    [sg.Text("虛擬輸出設備"), sg.Text('ⓘ', key='-INFO2-'), sg.Combo(device_names, default_value=default_virtual, key="-VIRTUAL-", readonly=True, size=(58,1), enable_events=True)],
    [sg.Button("加載", key="-LOAD-", tooltip="加載所選的音頻檔案並準備播放。"), sg.ProgressBar(max_value=100, orientation='h', size=(40, 15), key='-LOAD_PROGRESS-'), sg.Text("", key="-LOAD_STATUS-")],
    [sg.HSep()],
    [sg.Text("播放器", font=(CUSTOM_FONT_NAME, 14))],
    [sg.Slider(range=(0, 0), orientation='h', size=(60, 15), key="-PROGRESS-", enable_events=True, resolution=1, disabled=True, disable_number_display=True),
     sg.Text("00:00:00 / 00:00:00", key="-TIME_DISPLAY-")],
    [sg.Button("<<5秒", key="-REWIND-", disabled=True), sg.Button("播放/暫停", key="-PLAY_PAUSE-", disabled=True), sg.Button("5秒>>", key="-FORWARD-", disabled=True), sg.Button("停止", key="-STOP-", disabled=True)],
    [sg.Text("音量 (%)"), sg.Slider(range=(0, 100), default_value=int(master_volume*100), orientation='h', size=(50, 15), key="-VOLUME-", enable_events=True)],
    [sg.HSep()],
    [sg.Text("窩的第一個程式可能有Bug，歡迎追隨推特回饋使用體驗~"), sg.Text("[推特傳送門]", key="-TW_LINK-", enable_events=True, text_color="purple", tooltip="別忘了追隨我~")],
]
window = sg.Window("白芙妮的伴唱小幫手", layout, finalize=True, return_keyboard_events=True)

# --- Initialize and Attach Custom Tooltips ---
TooltipManager.init(window)
tooltip1_text = '這是您自己會聽到的輸出，\n該軌道會輸出伴奏和人聲。\n請確認選擇的兩個輸出設備采樣率相同。'
tooltip2_text = '這是直播軟體(如OBS)應擷取的輸出，\n通常是一個虛擬音源線(例如VB-CABLE)。\n該軌道僅輸出伴奏。\n請確認選擇的兩個輸出設備采樣率相同。'
TooltipManager.bind(window['-INFO1-'].Widget, tooltip1_text)
TooltipManager.bind(window['-INFO2-'].Widget, tooltip2_text)


TWITTER_URL = "https://x.com/msfmsf777"
window["-TW_LINK-"].update("[推特傳送門]")

# ---------------- Main Loop ----------------
while True:
    event, values = window.read(timeout=UI_TIMEOUT_MS)
    if event != sg.TIMEOUT_KEY:
        print(f"DEBUG Event: {event}, Position: {int(position)}")

    if event == sg.WIN_CLOSED:
        stop_immediate()
        break

    if event == "-LOAD_PROGRESS_EVENT-":
        prog = values.get(event, 0)
        window['-LOAD_PROGRESS-'].update(int(prog))
        window['-LOAD_STATUS-'].update("加載中..." if prog < 100 else "就緒")

    if event == "-LOAD_DONE-":
        done_val = values.get(event)
        if isinstance(done_val, str) and done_val.startswith("ERROR"):
            sg.popup_error(done_val, title="載入錯誤")
            window['-LOAD_PROGRESS-'].update(0); window['-LOAD_STATUS-'].update("")
            window['-LOAD-'].update(disabled=False); window['-PROGRESS-'].update(disabled=True, value=0)
        else:
            window['-LOAD_PROGRESS-'].update(100); window['-LOAD_STATUS-'].update("就緒")
            window['-LOAD-'].update(disabled=True)
            window['-PROGRESS-'].update(range=(0, int(duration)), value=int(position), disabled=False)
            window['-PLAY_PAUSE-'].update(disabled=False, text="播放")
            window['-STOP-'].update(disabled=False)
            window['-REWIND-'].update(disabled=False)
            window['-FORWARD-'].update(disabled=False)
            window['-TIME_DISPLAY-'].update(f"{format_time(position)} / {format_time(duration)}")

    old_pos = position
    if playing and not pending_seek_active:
        position = update_progress_time_based()
        if int(position) != int(old_pos):
            window["-PROGRESS-"].update(value=int(position))
            window["-TIME_DISPLAY-"].update(f"{format_time(position)} / {format_time(duration)}")

    if pending_seek_active:
        if (time.time() - pending_seek_time) >= SCRUB_DEBOUNCE:
            seek(pending_seek_value)
            pending_seek_active = False
            window["-PROGRESS-"].update(value=int(position))
            window["-TIME_DISPLAY-"].update(f"{format_time(position)} / {format_time(duration)}")

    window["-PLAY_PAUSE-"].update(text="暫停" if playing else "播放")
    for key in ['-HEADPHONE-', '-VIRTUAL-', '-BG-', '-VOCAL-', '-BG_BROWSE-', '-VOCAL_BROWSE-']: window[key].update(disabled=playing)
    for key in ['-PROGRESS-', '-PLAY_PAUSE-', '-REWIND-', '-FORWARD-', '-STOP-']: window[key].update(disabled=not audio_loaded)

    if event in ("-BG-", "-VOCAL-") and (values.get("-BG-", "") != current_bg_path or values.get("-VOCAL-", "") != current_vocal_path):
        mark_needs_reload(window)
    if event in ("-HEADPHONE-", "-VIRTUAL-"):
        mark_needs_reload(window)

    if event == "-LOAD-":
        if not all(values.get(k) for k in ["-BG-", "-VOCAL-", "-HEADPHONE-", "-VIRTUAL-"]):
            sg.popup_error("請選擇所有檔案和輸出設備", title="錯誤")
            continue

        # Add user-friendly warning if devices are the same
        if values.get("-HEADPHONE-") == values.get("-VIRTUAL-"):
            response = sg.popup_yes_no(
                "警告：您為兩個輸出選擇了相同的設備。這將導致兩個音軌混合在一起發送到同一個地方。\n\n這不是此應用程式的預期用途。您確定要繼續嗎？",
                title="設備選擇警告"
            )
            if response == 'No':
                continue # Allow user to change selection

        headphone_device_id = device_ids.get(values.get("-HEADPHONE-"))
        virtual_device_id = device_ids.get(values.get("-VIRTUAL-"))
        
        window['-LOAD-'].update(disabled=True)
        threading.Thread(target=load_worker, args=(values["-BG-"], values["-VOCAL-"], window), daemon=True).start()

    if event == "-PLAY_PAUSE-": play_pause()
    
    if event == "-STOP-":
        stop_immediate()
        window["-PROGRESS-"].update(value=position)
        window["-TIME_DISPLAY-"].update(f"{format_time(position)} / {format_time(duration)}")
        window["-PLAY_PAUSE-"].update(text="播放")

    if event == "-VOLUME-": master_volume = float(values.get("-VOLUME-", 70)) / 100.0

    if event == "-PROGRESS-":
        val = int(values.get("-PROGRESS-", position))
        window["-TIME_DISPLAY-"].update(f"{format_time(val)} / {format_time(duration)}")
        if not playing:
            seek(val)
        else:
            pending_seek_active, pending_seek_value, pending_seek_time = True, val, time.time()

    if event == "-REWIND-": rewind_5sec()
    if event == "-FORWARD-": forward_5sec()

    if isinstance(event, str):
        if (event == ' ' or 'space' in event.lower()) and not window['-PLAY_PAUSE-'].Disabled: play_pause()
        elif event.lower().startswith('left') and not window['-REWIND-'].Disabled: rewind_5sec()
        elif event.lower().startswith('right') and not window['-FORWARD-'].Disabled: forward_5sec()

    if event == "-TW_LINK-": webbrowser.open(TWITTER_URL)

    try:
        is_currently_seeking = False
        with seek_lock:
            is_currently_seeking = is_seeking

        if playing and streams_running and not stop_after_fade.is_set() and not is_currently_seeking:
            if (mixed_stream and not mixed_stream.active) or \
               (background_stream and not background_stream.active):
                print(f"DEBUG: Natural end of stream detected.")
                stop_immediate()
                window["-PROGRESS-"].update(value=0)
                window["-PLAY_PAUSE-"].update(text="播放")
                window["-TIME_DISPLAY-"].update(f"{format_time(0)} / {format_time(duration)}")
    except Exception: pass

# --- Final Cleanup ---
TooltipManager.close()
window.close()

