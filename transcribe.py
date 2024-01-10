# stream data from microphone / speakers, through whisper transcriber, to text output

MODEL_SIZE = "large-v3"  # this is the Whisper model to use. For the fastest one, use "tiny". For moderate speed, "medium". "large-v3" is accurate but slower.


# https://github.com/snakers4/silero-vad/blob/master/examples/pyaudio-streaming/pyaudio-streaming-examples.ipynb

try:
    print("Importing dependencies...")
    import sys
    import os
    import time
    from datetime import datetime, timedelta
    import numpy as np
    import torch

    # pyaudiowpatch allows recording from loopbacks/outputs
    import pyaudiowpatch as pyaudio
    import librosa

    # this was for checking waveforms while debugging how bytes are converted to floats
    # import pylab
    from faster_whisper import WhisperModel
except ImportError:
    print(
        """Import error. Please run the following command:
            pip install faster-whisper numpy torch pyaudiowpatch pydub --upgrade
        """
    )
    sys.exit(-1)

print("Completed imports")


# Above this confidence, we assume that speech is present
VAD_THRESHOLD = 0.4

# transcribe repeatedly, overwriting until silence is detected
PARTIALS = False


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


outfile = os.path.expanduser("~/transcripts/transcript.txt")

if not os.path.exists(os.path.dirname(outfile)):
    os.makedirs(os.path.dirname(outfile))
with open(outfile, "a") as f:
    print(f"\n\nStarting new transcript at {datetime.now()}", file=f)


def init_stream(input=False):
    stream = Stream()
    stream.prefix = "i" if input else "o"

    print("Printing audio devices:")
    pa = pyaudio.PyAudio()
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        print(f"{info['index']}: {info['name']} ")

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
                "Default loopback output device not found.\n\nRun `python -m pyaudiowpatch` to check available devices.\nExiting...\n"
            )
            exit()

    if input:
        print("Transcribing from default mic")
    else:
        print(
            f"Recording from: ({default_speakers['index']}){default_speakers['name']}: {default_speakers}"
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


input_stream = init_stream(input=True)
output_stream = init_stream(input=False)

torch.set_num_threads(1)

print("Loading VAD model...")
(
    vad_model,
    _,
) = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
print(f"Loading whisper model '{MODEL_SIZE}'...")
transcribe_model = WhisperModel(MODEL_SIZE, compute_type="int8")
# transcribe_model = WhisperModel("tiny", compute_type="int8")
print("Loaded whisper model")


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


last_time = datetime.now()

while input_stream.stream.is_active() or output_stream.stream.is_active():
    for stream in [input_stream, output_stream]:
        samples = stream.available_data
        stream.available_data = np.zeros((0), dtype=np.float32)
        read_data = False
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
            print(
                f"transcribing {stream.prefix} {len(stream.voice_data) / stream.SAMPLE_RATE} seconds" + " " * 30,
                end="\r",
            )
            transcribe_data = stream.voice_data
            stream.voice_data = np.zeros((0), dtype=np.int16)
            segments, info = transcribe_model.transcribe(
                transcribe_data, beam_size=6, language="en"
            )
            # walk the generator so we don't clear line "transcribing" too soon
            result = " ".join(s.text.strip() for s in segments)
            print(" " * 60, end="\r")  # clear line
            print(f"{stream.prefix}: {result}")
            # save to ~/transcripts/transcript-speakers.txt
            # if it's been more than a couple of minutes, put some newlines
            if datetime.now() - last_time > timedelta(minutes=2):
                with open(outfile, "a") as f:
                    print("\n\n", file=f)
            # if the minute has changed, log a line saying the current time.
            if last_time.minute != datetime.now().minute:
                last_time = datetime.now()
                with open(outfile, "a") as f:
                    print(f"The time is now {last_time}", file=f)
            with open(outfile, "a") as f:
                f.write(f"{stream.prefix}: {result}\n")
        elif not idle or len(stream.voice_data) == 0 or not PARTIALS:
            print(
                f"input: {len(input_stream.voice_data) / input_stream.SAMPLE_RATE:.0f}s / {input_stream.confidence:.1f}; "
                + f"output: {len(output_stream.voice_data) / output_stream.SAMPLE_RATE:.0f}s / {output_stream.confidence:.1f}; "
                + ("idle" if idle else ""),
                end="\r",
            )
        else:  # idle and voice_data is not empty
            # print partial transcription?!
            start = datetime.now()
            segments, info = transcribe_model.transcribe(
                stream.voice_data, beam_size=6, language="en"
            )
            result = " ".join(s.text.strip() for s in segments)
            print(" " * 60, end="\r")
            proctime = datetime.now() - start
            print(f"p: {result} ({proctime.total_seconds():.2f}s)", end="\r")
