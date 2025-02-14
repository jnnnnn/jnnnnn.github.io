import math


substitutions = {
    # "([.?!]) ": "\\1\n",
    "^ *Thank you.$": "",  # Whisper emits this when parsing noise for some reason
    r"\s*\n[\n\s]+": "\n",
}

# stream data from microphone and speakers, through whisper transcriber, to text output

# https://github.com/snakers4/silero-vad/blob/master/examples/pyaudio-streaming/pyaudio-streaming-examples.ipynb

try:
    print("Importing dependencies...", end=" ", flush=True)
    import sys
    import os
    import time
    from datetime import datetime, timedelta
    import argparse
    import logging
    import re

    # interactivity -- keyboard input and output
    import pyautogui
    import msvcrt

    # pyaudiowpatch allows recording from loopbacks/outputs
    import pyaudiowpatch as pyaudio
    import librosa

    import numpy as np

    print("Torch..", end=" ", flush=True)
    import torch

    print("Whisper..", end=" ", flush=True)
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

# set up basic debug logging, to file and console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)s - %(message)s",
    handlers=[
        filelogger := logging.FileHandler(
            f"{os.path.expanduser('~/transcripts/transcribe.log')}", mode="w"
        ),
        consolelogger := logging.StreamHandler(sys.stdout),
    ],
)
# whisper info is noisy and unhelpful, mute it
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
consolelogger.setLevel(logging.INFO)

BLANK = " " * 100 + "\r"

# Because we use several libraries that all have their own Intel OMP library, we have to
# disable a warning/error that it emits when it detects more than one copy of itself loaded:
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

AVAILABLE_MODELS = [
    "tiny",  # fine even on cpu. used for preview transcripts. makes lots of mistakes
    "base",
    "small",  # starting to require an accelerator (GTX1060 or better)
    "distil-small.en",  # the distil models are compressed to be almost as accurate but ~5x more efficient
    "medium",
    "distil-medium.en",
    "large-v3",  # recommend 8GB GPU RAM, GTX1080 or better. very few mistakes; 90% of sentences don't require correction.
    "distil-large-v3",  # almost as good as large, 6x faster
]

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
    default="tiny.en",
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
    "--max-clip-length",
    default=16,
    help="Maximum length of a clip to transcribe, in seconds",
)

args = parser.parse_args()

MODEL_SIZE = args.model

# Above this confidence, we assume that speech is present
VAD_THRESHOLD = 0.5
VAD_RATE = 10  # 100ms chunks
VAD_WINDOW = 2.0  # 1 second window so that hesitant speech is still joined instead of cut into five-word paragraphs

# transcribe continuously, overwriting until silence is detected and we use the
# main model on the full utterance for the log
PARTIALS = args.partials

ONLY_WHILE_APP_TITLES = set(args.only_while_app)
ONLY_WHILE_APP = bool(ONLY_WHILE_APP_TITLES)

# if True, type what is said into the keyboard
KEYBOARDOUT = args.keyboardout

MAX_CLIP_LENGTH = args.max_clip_length


# dataclass for input or output stream
class Stream:
    # this is in the format whisper expects, 16khz mono
    available_data = np.zeros((0), dtype=np.float32)
    SAMPLE_RATE = 16000

    outfile = ""
    stream = None
    prefix = ""  # "i" for input, "o" for output, printed at the start of each line

    last_time = datetime.now()
    idles = 0.0

    partial_len = 0

    vad_model = None
    voice_activity = []


outfile = args.outfile

if not os.path.exists(os.path.dirname(outfile)):
    os.makedirs(os.path.dirname(outfile))
with open(outfile, "a") as f:
    print(f"\n\n\n\n\n\nStarting new transcript at {datetime.now()}", file=f)

logging.info(f"\nSaving transcript to {outfile}\n\n")

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
            logging.error(
                "Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices."
            )
            input("Press any key to exit...")
            exit()

    if input:
        default_mic = pa.get_device_info_by_index(wasapi_info["defaultInputDevice"])
        logging.info(
            f"Transcribing from default mic: ({default_mic['index']}){default_mic['name']}"
        )
    else:
        logging.info(
            f"Recording from: ({default_speakers['index']}){default_speakers['name']}"
        )

    # 1 second chunks, smaller means sentences keep getting split up
    CHUNK_SECONDS = 0.2
    INPUT_CHANNELS = int(default_speakers["maxInputChannels"])
    INPUT_SAMPLE_RATE = int(default_speakers["defaultSampleRate"])
    INPUT_CHUNK = int(INPUT_SAMPLE_RATE * CHUNK_SECONDS)
    # CHUNK = int(SAMPLE_RATE * CHUNK_SECONDS)

    def callback(input_data, frame_count, time_info, flags):
        # logging.debug(f"callback: {type(input_data)} - {frame_count} frames, {len(input_data)} samples, {flags}\r")
        # resample to what Whisper expects: 16khz mono f32
        if flags & ~pyaudio.paNoError:
            logging.error(f"Error in callback: {flags}, {flags:08b}")
            stream.stream.close()
            return None, pyaudio.paAbort

        if check_active():
            floats = librosa.util.buf_to_float(input_data, n_bytes=2, dtype=np.float32)
            if INPUT_CHANNELS > 1:
                floats = np.reshape(floats, (INPUT_CHANNELS, -1), order="F")
                floats = librosa.to_mono(floats)
            input_data = librosa.resample(
                floats, orig_sr=INPUT_SAMPLE_RATE, target_sr=stream.SAMPLE_RATE
            )
            stream.available_data = np.append(stream.available_data, input_data)
            stream.last_time = datetime.now()

        return input_data, pyaudio.paContinue

    stream.stream = pa.open(
        format=pyaudio.paInt16,  # taking in raw f32 was too hard, something about little-endian
        channels=INPUT_CHANNELS,
        rate=INPUT_SAMPLE_RATE,
        input=True,
        input_device_index=default_speakers["index"] if not input else None,
        stream_callback=callback,
        frames_per_buffer=INPUT_CHUNK,
    )

    # each stream needs its own vad model because it is stateful.
    # see utils at https://github.com/snakers4/silero-vad/blob/master/utils_vad.py
    stream.vad_model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad", model="silero_vad"
    )

    return stream


KEYBOARDOUT_start = datetime.now()

torch.set_num_threads(1)

transcribe_model = None


def load_model():
    global transcribe_model
    logging.info(f"Loading whisper model '{MODEL_SIZE}'...")
    transcribe_model = WhisperModel(MODEL_SIZE, compute_type="int8")
    logging.info("Loaded whisper model")


if PARTIALS:
    logging.info("Loading fast whisper model...")
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


last_zoom_check = datetime.now() - timedelta(hours=1)
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
        logging.info(
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


BUMP_TARGET = "WINDOW"


def on_key_event(key):
    global KEYBOARDOUT, ONLY_WHILE_APP, KEYBOARDOUT_start, BUMP_TARGET
    if key == "t":
        KEYBOARDOUT = not KEYBOARDOUT
        KEYBOARDOUT_start = datetime.now()
        logging.info(f"typing: {KEYBOARDOUT}")
    if key == "z":
        ONLY_WHILE_APP = not ONLY_WHILE_APP
        logging.info(
            f"only while app: {ONLY_WHILE_APP_TITLES if ONLY_WHILE_APP else 'always on'}"
        )
    if key == "C":
        os.system("cls" if os.name == "nt" else "clear")

    # list app windows
    if key == "l":
        logging.info(list_windows())
    if key == "o":
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        logging.info("Loggers: ", loggers)
    # list audio devices
    if key == "a":
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            logging.info(f"{info['index']}: {info['name']} ")
    if key == "r":
        logging.info("Reloading streams")
        input_stream.stream.close()
        output_stream.stream.close()
    if key == "+" or key == "-":
        bump(key)
    if key == "w":
        BUMP_TARGET = "WINDOW"
    if key == "e":
        BUMP_TARGET = "THRESHOLD"
    if key == "h":
        logging.info(
            """Commands that work while running:
            t: toggle keyboard output
            z: toggle active app detection
            C: clear screen
            h: help
            l: list windows
            o: list loggers
            a: list audio devices
            r: reload streams
            +: increase / decrease
            w: adjust window
            e: adjust threshold
            """
        )


def bump(key):
    global VAD_WINDOW, VAD_THRESHOLD
    if BUMP_TARGET == "WINDOW":
        VAD_WINDOW += 0.1 if key == "+" else -0.1
        logging.info(f"VAD_WINDOW: {VAD_WINDOW:.1f}")
    if BUMP_TARGET == "THRESHOLD":
        VAD_THRESHOLD += 0.1 if key == "+" else -0.1
        logging.info(f"VAD_THRESHOLD: {VAD_THRESHOLD:.1f}")


def transcribe_partial(stream):
    if (
        not (
            PARTIALS
            and stream.voice_activity
            and max(stream.voice_activity[-2:]) > VAD_THRESHOLD
        )
        or len(stream.available_data) == stream.partial_len
    ):
        return False

    start = datetime.now()
    last_five_seconds = stream.available_data[-stream.SAMPLE_RATE * 5 :]
    segments, _info = fast_model.transcribe(
        last_five_seconds, beam_size=1, language="en", word_timestamps=False
    )
    result = " ".join(s.text.strip() for s in segments)
    proctime = datetime.now() - start
    print(BLANK + f"p ({proctime.total_seconds():.2f}s): {result[-70:]}", end="\r")
    stream.partial_len = len(stream.available_data)
    stream.idles = 0
    return True

LAST_OUTPUT_STREAM = None

def transcribe(stream, break_point):
    global transcribe_model
    if not transcribe_model:
        load_model()
    # remove the speech up to the break point from the available data
    samplecount = int(break_point / VAD_RATE * stream.SAMPLE_RATE)
    speech = stream.available_data[:samplecount]
    trim_start(stream, break_point, "transcribing")

    print(
        BLANK + f"transcribing {len(speech) / stream.SAMPLE_RATE:.1f}s of audio",
        end="\r",
    )

    start = datetime.now()
    global KEYBOARDOUT, KEYBOARDOUT_start, last_time, LAST_OUTPUT_STREAM
    segments, _info = transcribe_model.transcribe(
        speech,
        beam_size=6,
        language="en",
        word_timestamps=False,
        task="translate"
    )
    strings = []
    for s in segments:
        logging.debug(f"segment: '{s}'")
        strings.append(s.text.strip())
    duration = datetime.now() - start
    result = "\n".join(strings)
    for pattern, replacement in substitutions.items():
        result = re.sub(pattern, replacement, result)
    speed = len(speech) / stream.SAMPLE_RATE / duration.total_seconds()
    logging.debug(f"transcribed {len(speech) / stream.SAMPLE_RATE:.1f}s in {duration.total_seconds():.1f}s ({speed:.1f}x)")
    if not result.strip():
        return  # don't emit blanks
    print(BLANK, end = "\r")
    print(result, end="\n\n")
    # save to ~/transcripts/transcript-speakers.txt
    # if it's been more than a couple of minutes, put some newlines
    if datetime.now() - last_time > timedelta(minutes=2):
        with open(outfile, "a") as f:
            print("\n" * 5, file=f)
    # if the minute or stream has changed, log a line saying the current time.
    if last_time.minute != datetime.now().minute or stream.prefix != LAST_OUTPUT_STREAM:
        last_time = datetime.now()
        with open(outfile, "a") as f:
            print(f"{stream.prefix}: {last_time.strftime('%Y-%m-%d %H:%M')}", file=f)
    with open(outfile, "a") as f:
        f.write(result + "\n\n")
    if KEYBOARDOUT and not transcribe_window_focus():
        pyautogui.write(result.replace("\n", " ") + " ", interval=0.01)
        KEYBOARDOUT_start = datetime.now()

    LAST_OUTPUT_STREAM = stream.prefix
    stream.idles = 0


def find_break(stream):
    """
    Find a sensible voice activity chunk to break the audio stream at, based on voice detection confidence.
    """
    probs = stream.voice_activity

    MIN = 3 * VAD_RATE  # at least 3 seconds
    MAX = (
        MAX_CLIP_LENGTH * VAD_RATE
    )  # waffle! break at low point++++++++--++++_+_++++--+-+-+-+-+-+++_+_+_+_+
    WINDOW = int(VAD_WINDOW * VAD_RATE)
    if len(probs) >= MAX:
        index, average = index_lowest_average(probs, start=MIN, window=WINDOW)
        logging.debug(
            f"Found break at {index/VAD_RATE:.1f}s because over max length for VAD chunks {chunkedmaxstring(probs[:index])})"
        )
        return index
    if len(probs) > 0 and stream.idles > 1.1:
        logging.debug("Found break at end because stream idle")
        return len(probs) + 100  # consume all available data
    if not MIN < len(probs) - WINDOW:
        return None

    index, average = index_lowest_average(probs, start=MIN, window=WINDOW)
    if average < VAD_THRESHOLD and sum(probs[:index]) / index > VAD_THRESHOLD:
        logging.debug(
            f"Found break at {index/VAD_RATE:.1f}s for VAD chunks {chunkedmaxstring(probs[:index])})"
        )
        return index


def index_lowest_average(probs, start=0, window=10):
    """Find the index of the lowest average confidence
    for a window of values in the given list of probabilities.
    """
    assert start < len(probs) - window
    averages = [
        sum(probs[i : i + window]) / window for i in range(start, len(probs) - window)
    ]
    smallestAverage = min(averages)
    windowStart = start + averages.index(smallestAverage)
    lowPointInWindow = min(probs[windowStart : windowStart + window])
    lowIndex = windowStart + probs[windowStart : windowStart + window].index(
        lowPointInWindow
    )
    return lowIndex, smallestAverage


def detect_speech(stream):
    """Update stream.voice_activity with any new stream.available_data."""
    CHUNK_SIZE = stream.SAMPLE_RATE // VAD_RATE
    chunks = len(stream.available_data) // CHUNK_SIZE
    detected = len(stream.voice_activity)
    # if there's more than a minute of saved data, print a warning
    seconds_to_detect = (chunks - detected) // VAD_RATE
    if seconds_to_detect > 60:
        logging.warning(
            f"WARNING: detecting speech for {seconds_to_detect} seconds of audio data\n"
        )

    for i in range(detected, chunks):
        start = i * CHUNK_SIZE
        end = start + CHUNK_SIZE
        samples = stream.available_data[start:end]
        stream.voice_activity.append(
            stream.vad_model(torch.from_numpy(samples), stream.SAMPLE_RATE).item()
        )

    new_data = chunks - detected > 0
    if new_data:
        stream.idles = 0
    return new_data


def trim_start(stream, vadchunks, because):
    """Remove the given number of seconds from the start of the stream"""
    if vadchunks <= 0:
        return

    logging.debug(f"dropping {vadchunks / VAD_RATE:.1f}s of audio because {because}")
    samples = int(vadchunks / VAD_RATE * stream.SAMPLE_RATE)
    stream.available_data = stream.available_data[samples:]
    stream.voice_activity = stream.voice_activity[vadchunks:]


def removeLeadingNonSpeech(stream):
    """Remove any leading non-speech from stream.available_data because
    it's probably not worth transcribing.
    """

    # if there's more than 10 minutes of audio, only keep the last nine minutes
    TRUNCATE_SECONDS = 9 * 60
    TRUNCATE_TRIGGER = 10 * 60
    if len(stream.available_data) > TRUNCATE_TRIGGER * stream.SAMPLE_RATE:
        trim_start(stream, TRUNCATE_SECONDS * VAD_RATE, "too much audio")

    # keep 0.2s of audio before the detected speech, so we don't cut off words
    # note: if there is no speech in the buffer, this will not trim anything
    #  - as soon as speech triggers, we'll trim the buffer back to this point
    KEEP_CHUNKS = int(0.2 * VAD_RATE)
    DUMP_SILENCE = 10 * VAD_RATE
    for i, confidence in enumerate(stream.voice_activity):
        if confidence > VAD_THRESHOLD or i > DUMP_SILENCE:
            i -= KEEP_CHUNKS
            trim_start(stream, i, "leading non-speech")
            break

    # if there hasn't been any new data for a few seconds, clear the buffer
    if stream.idles > 2:
        trim_start(stream, len(stream.voice_activity), "idle")


def check_active():
    global KEYBOARDOUT, KEYBOARDOUT_start
    # Don't leave it in typing mode for more than five minutes because I forget
    if (
        KEYBOARDOUT
        and KEYBOARDOUT_start
        and datetime.now() - KEYBOARDOUT_start > timedelta(minutes=3)
    ):
        KEYBOARDOUT = None
        logging.info("typing: False (3 minute timeout reached)")

    active = KEYBOARDOUT or check_zoom_active()

    return active


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
            removeLeadingNonSpeech(stream)
            break_point = find_break(stream)
            if break_point:
                transcribe(stream, break_point)
            else:
                transcribe_partial(stream)
        if not any(new_data):
            if all(
                all(va < VAD_THRESHOLD for va in s.voice_activity[-10 * VAD_RATE :])
                for s in streams
            ):
                print_vad_stats(streams)
            for s in streams:
                s.idles += 0.05
            time.sleep(0.05)


def chunkedmaxstring(ps):
    # outputs something like "000019998100" representing voice activity
    DISPLAY_RATE = int(VAD_RATE / 3)
    return "".join(
        f"{math.floor(10 * max(ps[i : i + DISPLAY_RATE])) :.0f}"
        for i in range(0, len(ps), DISPLAY_RATE)
    )


def print_vad_stats(streams):
    print(
        BLANK
        + "VAD: "
        + " - ".join(
            f"{s.prefix}: {chunkedmaxstring(s.voice_activity)}" for s in streams
        ),
        end="\r",
    )


wait_time = 1
while True:
    try:
        input_stream = init_stream(input=True)
        output_stream = init_stream(input=False)
        mainloop()
    except IOError as e:
        logging.error(f"IOError: {e}")

        logging.info("Reinitializing pyaudio to reset default devices...")
        pa.terminate()
        pa = pyaudio.PyAudio()

        wait_time = wait_time * 2  # exponential backoff
        time.sleep(wait_time)
    except Exception as e:
        logging.exception(e)
        input("Press any key to continue...")
