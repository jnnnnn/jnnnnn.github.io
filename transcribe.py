substitutions = {
}

# stream data from microphone and speakers, through whisper transcriber, to text output

# https://github.com/snakers4/silero-vad/blob/master/examples/pyaudio-streaming/pyaudio-streaming-examples.ipynb

try:
    print("Importing dependencies...")
    import sys
    import os
    import subprocess
    import time
    from datetime import datetime, timedelta
    import argparse

    # interactivity -- keyboard input and output
    import pyautogui
    import msvcrt

    # pyaudiowpatch allows recording from loopbacks/outputs
    import pyaudiowpatch as pyaudio
    import librosa
    import soundfile

    import numpy as np
    import torch
    from faster_whisper import WhisperModel
except ImportError as e:
    print(
        f"""Import error {e}. 
        Please run the following command:
            pip install faster-whisper torchaudio pyautogui pyaudiowpatch librosa pysoundfile --upgrade
        """
    )
    sys.exit(-1)

print("Completed imports")

# Because we use several libraries that all have their own Intel OMP library, we have to
# disable a warning/error that it emits when it detects more than one copy of itself loaded:
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

yearmonth = datetime.now().strftime("%Y-%m")

parser = argparse.ArgumentParser(
    description="Transcribe audio from microphone and speakers to output and file."
)
parser.add_argument(
    "--outfile", default=os.path.expanduser(f"~/transcripts/transcript-{yearmonth}.txt")
)
parser.add_argument(
    "--model",
    default="tiny",
    choices=AVAILABLE_MODELS,
    help="Whisper model to use. Tiny is 39MB, Base is 74MB, Small is 244MB, Medium is 769MB, Large is 1550MB. Larger models are more accurate but use more memory and compute time",
)
parser.add_argument(
    "--partials",
    default="tiny",
    help="use a fast an inaccurate model to show partial transcriptions continuously",
)
parser.add_argument(
    "--only-while-app",
    nargs="*",
    default=["Zoom Meeting", "VideoFrameWnd"],
    help="only transcribe when this app is active, or None/blank/False to transcribe all the time",
)
parser.add_argument(
    "--keyboardout", default=False, help="Type what is said into the keyboard"
)
parser.add_argument(
    "--clip-folder",
    default=os.path.expanduser(f"~/transcripts/clips-{yearmonth}"),
    help="Folder to save clips to",
)
args = parser.parse_args()

MODEL_SIZE = args.model

# Above this confidence, we assume that speech is present
VAD_THRESHOLD = 0.4

# transcribe continuously, overwriting until silence is detected and we use the
# main model on the full utterance for the log
PARTIALS = args.partials

ONLY_WHILE_APP_TITLES = set(args.only_while_app)
ONLY_WHILE_APP = bool(ONLY_WHILE_APP_TITLES)

# if True, type what is said into the keyboard
KEYBOARDOUT = args.keyboardout

CLIPSPATH = args.clip_folder
SAVE_NEXT_CLIP = False


# dataclass for input or output stream
class Stream:
    # this is in the format whisper expects, 16khz mono
    available_data = np.zeros((0), dtype=np.float32)
    SAMPLE_RATE = 16000

    # this is the original data, at the original sample rate but mono
    original_data = np.zeros((0), dtype=np.float32)
    original_sample_rate = 0

    outfile = ""
    stream = None
    prefix = ""  # "i" for input, "o" for output, printed at the start of each line

    last_time = datetime.now()
    idles = 0.0


outfile = args.outfile

if not os.path.exists(os.path.dirname(outfile)):
    os.makedirs(os.path.dirname(outfile))
with open(outfile, "a") as f:
    print(f"\n\n\n\n\n\nStarting new transcript at {datetime.now()}", file=f)

print(f"\nSaving transcript to {outfile}\n\n")

pa = pyaudio.PyAudio()


def init_stream(input=False):
    stream = Stream()
    stream.prefix = "i" if input else "o"

    wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)

    # Get default WASAPI speakers
    default_speakers = pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

    if not default_speakers["isLoopbackDevice"]:
        for loopback in pa.get_loopback_device_info_generator():
            """
            Try to find loopback device with same name(and [Loopback suffix]).
            Unfortunately, this is the most adequate way at the moment.
            """
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break
        else:
            print(
                "Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices."
            )
            input("Press any key to exit...")
            exit()

    if input:
        default_mic = pa.get_device_info_by_index(wasapi_info["defaultInputDevice"])
        print(
            f"Transcribing from default mic: ({default_mic['index']}){default_mic['name']}"
        )
    else:
        print(
            f"Recording from: ({default_speakers['index']}){default_speakers['name']}"
        )

    # 1 second chunks, smaller means sentences keep getting split up
    CHUNK_SECONDS = 0.2
    INPUT_CHANNELS = int(default_speakers["maxInputChannels"])
    INPUT_SAMPLE_RATE = int(default_speakers["defaultSampleRate"])
    stream.original_sample_rate = INPUT_SAMPLE_RATE
    INPUT_CHUNK = int(INPUT_SAMPLE_RATE * CHUNK_SECONDS)
    # CHUNK = int(SAMPLE_RATE * CHUNK_SECONDS)

    def callback(input_data, frame_count, time_info, flags):
        # print(f"callback: {type(input_data)} - {frame_count} frames, {len(input_data)} samples, {flags}, {input_data[:20]}")
        # resample to what Whisper expects: 16khz mono f32
        if flags & ~pyaudio.paNoError:
            print(f"Error in callback: {flags}, {flags:08b}")
            stream.stream.close()
            return None, pyaudio.paAbort

        if check_active():
            floats = librosa.util.buf_to_float(input_data, n_bytes=2, dtype=np.float32)
            if INPUT_CHANNELS > 1:
                floats = np.reshape(floats, (INPUT_CHANNELS, -1), order="F")
                floats = librosa.to_mono(floats)
            stream.original_data = np.append(stream.original_data, floats)
            input_data = librosa.resample(
                floats, orig_sr=INPUT_SAMPLE_RATE, target_sr=stream.SAMPLE_RATE
            )
            stream.available_data = np.append(stream.available_data, input_data)
            stream.last_time = datetime.now()

        return input_data, pyaudio.paContinue

    stream.voice_detection = []

    stream.stream = pa.open(
        format=pyaudio.paInt16,  # taking in raw f32 was too hard, something about little-endian
        channels=INPUT_CHANNELS,
        rate=INPUT_SAMPLE_RATE,
        input=True,
        input_device_index=default_speakers["index"] if not input else None,
        stream_callback=callback,
        frames_per_buffer=INPUT_CHUNK,
    )

    return stream


KEYBOARDOUT_start = datetime.now()

torch.set_num_threads(1)

print("Loading VAD model...")
(
    vad_model,
    _,
) = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
print(f"Loading whisper model '{MODEL_SIZE}'...")
transcribe_model = WhisperModel(MODEL_SIZE, compute_type="int8")
print("Loaded whisper model")

if PARTIALS:
    print("Loading fast whisper model...")
    if PARTIALS == MODEL_SIZE:
        fast_model = transcribe_model
    else:
        fast_model = WhisperModel(PARTIALS, compute_type="int8")


def validate(model, inputs: torch.Tensor):
    with torch.no_grad():
        outs = model(inputs)
    return outs


def int2float(sound):
    abs_max = np.abs(sound).max()
    sound = sound.astype("float32")
    if abs_max > 0:
        sound *= 1 / 32768
    sound = sound.squeeze()
    return sound


last_zoom_check = datetime.now()
zoom_active = None


def check_zoom_active():
    if not ONLY_WHILE_APP:
        return True
    global last_zoom_check, zoom_active
    if datetime.now() - last_zoom_check < timedelta(seconds=10):
        return zoom_active

    last_zoom_check = datetime.now()
    new_zoom_active = bool(ONLY_WHILE_APP_TITLES.intersection(list_windows()))
    if new_zoom_active != zoom_active:
        print(
            f"\n{ONLY_WHILE_APP_TITLES} is now {'active' if new_zoom_active else 'inactive'}"
        )
    zoom_active = new_zoom_active
    return zoom_active


last_time = datetime.now()


def list_windows():
    import win32gui

    windows = set()

    def winEnumHandler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            windows.add(win32gui.GetWindowText(hwnd))

    win32gui.EnumWindows(winEnumHandler, None)
    return sorted(windows)


def transcribe_window_focus():
    import win32gui

    return "transcribe" in win32gui.GetWindowText(win32gui.GetForegroundWindow())


def on_key_event(key):
    global KEYBOARDOUT, ONLY_WHILE_APP, KEYBOARDOUT_start
    if key == "t":
        KEYBOARDOUT = not KEYBOARDOUT
        KEYBOARDOUT_start = datetime.now()
        print(f"typing: {KEYBOARDOUT}")
    if key == "z":
        ONLY_WHILE_APP = not ONLY_WHILE_APP
        print(
            f"only while app: {ONLY_WHILE_APP_TITLES if ONLY_WHILE_APP else 'always on'}"
        )
    if key == "C":
        os.system("cls" if os.name == "nt" else "clear")
    if key == "s":
        global SAVE_NEXT_CLIP
        SAVE_NEXT_CLIP = not SAVE_NEXT_CLIP
        print(f"Saving next clip: {SAVE_NEXT_CLIP}")

    # list app windows
    if key == "l":
        print(list_windows())
    # list audio devices
    if key == "a":
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            print(f"{info['index']}: {info['name']} ")
    if key == "r":
        print("Reloading streams")
        input_stream.stream.close()
        output_stream.stream.close()


def transcribe_partial(stream):
    start = datetime.now()
    last_five_seconds = stream.available_data[-stream.SAMPLE_RATE * 5 :]
    segments, info = fast_model.transcribe(
        last_five_seconds, beam_size=1, language="en"
    )
    result = " ".join(s.text.strip() for s in segments)
    print(" " * 60, end="\r")
    proctime = datetime.now() - start
    print(f"p: {result[-70:]} ({proctime.total_seconds():.2f}s)", end="\r")


def transcribe(stream, break_point):
    # remove the speech up to the break point from the available data
    speech = stream.available_data[: break_point * stream.SAMPLE_RATE]
    original = stream.original_data[: break_point * stream.original_sample_rate]
    confidences = stream.voice_detection[:break_point]
    drop_seconds(stream, break_point)

    # don't transcribe chunks that aren't speech, it's a little noisy sometimes
    if max(confidences) < VAD_THRESHOLD:
        return

    print(
        f"transcribing {len(speech) / stream.SAMPLE_RATE:.0f}s of audio" + " " * 50,
        end="\r",
    )

    global KEYBOARDOUT, KEYBOARDOUT_start, last_time
    segments, info = transcribe_model.transcribe(speech, beam_size=6, language="en")
    # walk the generator so we don't clear line "transcribing" too soon
    result = " ".join(s.text.strip() for s in segments)
    for k, v in substitutions.items():
        result = result.replace(k, v)
    print(" " * 78, end="\r")  # clear line
    clocktime = datetime.now().strftime("%H:%M")
    for line in result.split("\n"):
        print(f"{clocktime}  {stream.prefix}: {line}")
    # save to ~/transcripts/transcript-speakers.txt
    # if it's been more than a couple of minutes, put some newlines
    if datetime.now() - last_time > timedelta(minutes=2):
        with open(outfile, "a") as f:
            print("\n" * 5, file=f)
    # if the minute has changed, log a line saying the current time.
    if last_time.minute != datetime.now().minute:
        last_time = datetime.now()
        with open(outfile, "a") as f:
            print(f"t: {last_time.strftime('%Y-%m-%d %H:%M')}", file=f)
    with open(outfile, "a") as f:
        for line in result.split("\n"):
            f.write(f"{stream.prefix}: {result}\n")
    if SAVE_NEXT_CLIP:
        saveclip(original, stream.original_sample_rate, result)
    if KEYBOARDOUT and stream.prefix == "i" and not transcribe_window_focus():
        pyautogui.write(result + " ", interval=0.01)
        KEYBOARDOUT_start = datetime.now()


def saveclip(samples, sample_rate, transcript):
    """Write out a clip of audio as an ogg file, and use the transcription as the filename"""
    if not os.path.exists(CLIPSPATH):
        os.makedirs(CLIPSPATH)

    # pick the five longest words to use in the filename
    result = "".join(c for c in transcript.lower() if c.isalnum() or c.isspace())
    words = sorted(set(result.split()), key=len, reverse=True)[:5]
    # only take 50 chars because soundfile will crash if windows rejects filename too long
    result = "-".join(w for w in result.split() if w in words)[:50]
    if not result or not len(samples):
        return
    filename = os.path.join(CLIPSPATH, result + ".wav")
    duration = len(samples) / sample_rate
    print(f"Saving {duration}s clip to {filename} at {sample_rate/1000}kHz")
    soundfile.write(filename, samples, sample_rate)
    # pysoundfile's ogg support crashes after a 2-3 writes, so write as wav and convert with ffmpeg
    # capture output to hide ffmpeg's progress. use .opus extension so that metadata works.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            filename,
            "-c:a",
            "libvorbis",
            "-q:a",
            "4",
            "-metadata",
            f"Title={transcript}",
            filename.replace(".wav", ".ogg"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.remove(filename)


def find_break(stream):
    """Find a sensible index to break the audio stream at, based on voice detection confidence:
    We want sequences where the audio is at least three seconds (three values), and the last two values are below threshold.
    If the given array is more than 15 seconds, break it at the lowest confidence point to avoid very long lines of transcription."""
    MIN = 3
    MAX = 16
    probs = stream.voice_detection
    if len(probs) <= MIN:
        return None
    if len(probs) >= MAX:
        min_value = min(probs[MIN:MAX])
        return MIN + probs[MIN:MAX].index(min_value)
    for i in range(MIN, len(probs)):
        if probs[i] < VAD_THRESHOLD and probs[i - 1] < VAD_THRESHOLD:
            return i
    # if the stream has had no new data for a bit, transcribe what we've got
    delayed = stream.idles > 1.1
    if len(probs) > MIN and delayed:
        return len(probs) - 1
    else:
        return None


def detect_speech(stream):
    """Update stream.voice_detection with any new stream.available_data."""
    chunks = len(stream.available_data) // stream.SAMPLE_RATE
    detected = len(stream.voice_detection)
    # if there's more than a minute of saved data, print a warning
    if chunks - detected > 60:
        print(
            f"WARNING: detecting speech for {chunks - detected} seconds of audio data\n"
        )

    for i in range(detected, chunks):
        start = i * stream.SAMPLE_RATE
        end = start + stream.SAMPLE_RATE
        samples = stream.available_data[start:end]
        stream.voice_detection.append(
            vad_model(torch.from_numpy(samples), stream.SAMPLE_RATE).item()
        )

    new_data = chunks - detected > 0
    if new_data:
        stream.idles = 0
    return new_data


def drop_seconds(stream, seconds):
    """Remove the given number of seconds from the start of the stream"""
    stream.available_data = stream.available_data[seconds * stream.SAMPLE_RATE :]
    stream.original_data = stream.original_data[seconds * stream.original_sample_rate :]
    stream.voice_detection = stream.voice_detection[seconds:]


def truncate(stream):
    """Remove any leading non-speech from stream.available_data because
    it's probably not worth transcribing.
    """
    if not stream.voice_detection:
        return

    for i, confidence in enumerate(stream.voice_detection):
        if confidence > VAD_THRESHOLD:
            # keep one second of audio before the detected speech, in case we cut off the start of a word
            i = max(0, i - 1)
            drop_seconds(stream, i)
            break

    # if there's more than 10 minutes of audio, only keep the last nine minutes
    TRUNCATE_SECONDS = 9 * 60
    TRUNCATE_TRIGGER = 10 * 60
    if len(stream.available_data) > TRUNCATE_TRIGGER * stream.SAMPLE_RATE:
        drop_seconds(stream, TRUNCATE_SECONDS)

    # if there hasn't been any new data for a few seconds, clear the buffer
    if stream.idles > 2:
        drop_seconds(stream, len(stream.voice_detection))


def check_active():
    global KEYBOARDOUT, KEYBOARDOUT_start
    # Don't leave it in typing mode for more than five minutes because I forget
    if (
        KEYBOARDOUT
        and KEYBOARDOUT_start
        and datetime.now() - KEYBOARDOUT_start > timedelta(minutes=3)
    ):
        KEYBOARDOUT = None
        print("typing: False (3 minute timeout reached)")

    return KEYBOARDOUT or check_zoom_active()


def mainloop():
    global KEYBOARDOUT, KEYBOARDOUT_start, last_time
    streams = [input_stream, output_stream]
    while any(s.stream.is_active() for s in streams):
        if msvcrt.kbhit():
            key = msvcrt.getch().decode("utf-8")
            on_key_event(key)

        if not check_active():
            time.sleep(1)
            continue

        new_data = []

        for stream in streams:
            new_data.append(detect_speech(stream))
            truncate(stream)
            break_point = find_break(stream)
            if break_point:
                transcribe(stream, break_point)
                stream.idles = 0
            elif (
                PARTIALS
                and stream.voice_detection
                and stream.voice_detection[-1] > VAD_THRESHOLD
                and new_data[-1]
            ):
                transcribe_partial(stream)
                stream.idles = 0
        if not any(new_data):
            time.sleep(0.05)
            for s in streams:
                s.idles += 0.05


wait_time = 1
while True:
    try:
        input_stream = init_stream(input=True)
        output_stream = init_stream(input=False)
        mainloop()
    except Exception as e:
        print(f"Error: {e}")

        print("Reinitializing pyaudio to reset default devices...")
        pa.terminate()
        pa = pyaudio.PyAudio()

        wait_time = wait_time * 2  # exponential backoff
        time.sleep(wait_time)
