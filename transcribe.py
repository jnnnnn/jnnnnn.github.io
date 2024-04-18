# stream data from microphone, through whisper transcriber, to text output

# https://github.com/snakers4/silero-vad/blob/master/examples/pyaudio-streaming/pyaudio-streaming-examples.ipynb

try:
    print("Importing dependencies...")
    import sys
    import os
    import time
    from datetime import datetime, timedelta
    import argparse

    # interactivity -- keyboard input and output
    import pyautogui
    import msvcrt

    # pyaudiowpatch allows recording from loopbacks/outputs
    import pyaudiowpatch as pyaudio
    import librosa

    # this was for checking waveforms while debugging how bytes are converted to floats
    # import pylab

    import numpy as np
    import torch
    from faster_whisper import WhisperModel
except ImportError:
    print(
        """Import error. Please run the following command:
            pip install faster-whisper torchaudio pyautogui pyaudiowpatch librosa --upgrade
        """
    )
    sys.exit(-1)

print("Completed imports")

AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

substitutions = {
}

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


# dataclass for input or output stream
class Stream:
    # this is in the format whisper expects, 16khz mono
    available_data = np.zeros((0), dtype=np.float32)
    outfile = ""
    stream = None
    prefix = ""

    # this data has made it through VAD, may not be complete yet
    voice_data = np.zeros((0), dtype=np.float32)
    # Silero-Voice-Activity-Detector's reported "Confidence" that speech is present
    confidence = 0.0

    # keep in case voice activity starts
    prev_confidence = confidence
    prev_audio = np.zeros((0), dtype=np.float32)


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
    CHUNK_SECONDS = 1
    INPUT_CHANNELS = int(default_speakers["maxInputChannels"])
    INPUT_SAMPLE_RATE = int(default_speakers["defaultSampleRate"])
    INPUT_CHUNK = int(INPUT_SAMPLE_RATE * CHUNK_SECONDS)
    stream.SAMPLE_RATE = 16000
    # CHUNK = int(SAMPLE_RATE * CHUNK_SECONDS)

    def callback(input_data, frame_count, time_info, flags):
        # print(f"callback: {type(input_data)} - {frame_count} frames, {len(input_data)} samples, {flags}, {input_data[:20]}")
        # resample to what Whisper expects: 16khz mono f32
        if flags & ~pyaudio.paNoError:
            print(f"Error in callback: {flags}, {flags:08b}")
            stream.stream.close()
            return None, pyaudio.paAbort
        floats = librosa.util.buf_to_float(input_data, n_bytes=2, dtype=np.float32)
        if INPUT_CHANNELS > 1:
            floats = np.reshape(floats, (INPUT_CHANNELS, -1), order="F")
            floats = librosa.to_mono(floats)
        input_data = librosa.resample(
            floats, orig_sr=INPUT_SAMPLE_RATE, target_sr=stream.SAMPLE_RATE
        )
        stream.available_data = np.append(stream.available_data, input_data)

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


def on_key_event(key):
    global KEYBOARDOUT, ONLY_WHILE_APP, KEYBOARDOUT_start
    if key == "T":
        KEYBOARDOUT = not KEYBOARDOUT
        KEYBOARDOUT_start = datetime.now()
        print(f"typing: {KEYBOARDOUT}")
    if key == "Z":
        ONLY_WHILE_APP = not ONLY_WHILE_APP
        print(
            f"only while app: {ONLY_WHILE_APP_TITLES if ONLY_WHILE_APP else 'always on'}"
        )
    if key == "C":
        os.system("cls" if os.name == "nt" else "clear")
    # list app windows
    if key == "L":
        print(list_windows())
    # list audio devices
    if key == "A":
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            print(f"{info['index']}: {info['name']} ")
    if key == "R":
        print("Reloading streams")
        input_stream.stream.close()
        output_stream.stream.close()


def mainloop():
    global KEYBOARDOUT, KEYBOARDOUT_start, last_time
    while input_stream.stream.is_active() or output_stream.stream.is_active():
        if msvcrt.kbhit():
            key = msvcrt.getch().decode("utf-8")
            on_key_event(key)

        for stream in [input_stream, output_stream]:
            samples = stream.available_data
            stream.available_data = np.zeros((0), dtype=np.float32)

            # Don't leave it in typing mode for more than five minutes because I forget
            if (
                KEYBOARDOUT
                and KEYBOARDOUT_start
                and datetime.now() - KEYBOARDOUT_start > timedelta(minutes=3)
            ):
                KEYBOARDOUT = None
                print("typing: False (3 minute timeout reached)")

            if not (KEYBOARDOUT or check_zoom_active()):
                continue

            if len(samples):
                stream.confidence = vad_model(torch.from_numpy(samples), 16000).item()
                # when confidence starts to be above the threshold,
                # we want to keep the chunk before (incase there was part of a word in it),
                if (
                    stream.confidence > VAD_THRESHOLD
                    and stream.prev_confidence < VAD_THRESHOLD
                ):
                    # keep the previous audio after all
                    stream.voice_data = np.append(stream.voice_data, stream.prev_audio)
                # and the chunk after it drops (just to be sure we don't cut off a word)
                if (
                    stream.confidence > VAD_THRESHOLD
                    or stream.prev_confidence > VAD_THRESHOLD
                ):
                    stream.voice_data = np.append(stream.voice_data, samples)
                    stream.prev_audio = np.zeros((0), dtype=np.float32)
                else:
                    # we only want to keep previous audio if we haven't already
                    # added it to voice_data, to make sure we don't add it twice
                    stream.prev_audio = samples

                stream.prev_confidence = stream.confidence
                idle = False
            else:
                # if we didn't read any data, sleep for a bit to avoid busy-waiting
                idle = True
                time.sleep(0.1)

            # transcribe once confidence that someone is still speaking drops below 0.5
            if (
                stream.confidence < VAD_THRESHOLD
                and stream.prev_confidence < VAD_THRESHOLD
                and len(stream.voice_data) > 0
            ):
                # print(" " * 60, end="\r")  # clear line
                if not PARTIALS:
                    print(
                        f"transcribing {stream.prefix} {len(stream.voice_data) / stream.SAMPLE_RATE} seconds"
                        + " " * 30,
                        end="\r",
                    )
                transcribe_data = stream.voice_data
                stream.voice_data = np.zeros((0), dtype=np.int16)
                segments, info = transcribe_model.transcribe(
                    transcribe_data, beam_size=6, language="en"
                )
                # walk the generator so we don't clear line "transcribing" too soon
                result = " ".join(s.text.strip() for s in segments)
                for k, v in substitutions.items():
                    result = result.replace(k, v)
                print(" " * 78, end="\r")  # clear line
                clocktime = datetime.now().strftime("%H:%M")
                print(f"{clocktime}  {stream.prefix}: {result}")
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
                    f.write(f"{stream.prefix}: {result}\n")
                if KEYBOARDOUT and stream.prefix == "i":
                    pyautogui.write(result + " ", interval=0.01)
                    KEYBOARDOUT_start = datetime.now()
            elif PARTIALS:
                if len(stream.voice_data) > 0:
                    start = datetime.now()
                    last_five_seconds = stream.voice_data[-stream.SAMPLE_RATE * 5 :]
                    segments, info = fast_model.transcribe(
                        last_five_seconds, beam_size=1, language="en"
                    )
                    result = " ".join(s.text.strip() for s in segments)
                    print(" " * 60, end="\r")
                    proctime = datetime.now() - start
                    print(
                        f"p: {result[-70:]} ({proctime.total_seconds():.2f}s)", end="\r"
                    )
            else:
                print(
                    f"input: {len(input_stream.voice_data) / input_stream.SAMPLE_RATE:.0f}s / {input_stream.confidence:.1f}; "
                    + f"output: {len(output_stream.voice_data) / output_stream.SAMPLE_RATE:.0f}s / {output_stream.confidence:.1f}; "
                    + ("idle" if idle else ""),
                    end="\r",
                )


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
