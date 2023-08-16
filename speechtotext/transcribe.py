# A script that takes in an audio/video file and outputs a transcript of the audio.
# See https://github.com/guillaumekln/faster-whisper.

# Setup:
# pip install faster-whisper tqdm

import os
import sys
import subprocess
try:
    from tqdm import tqdm
    from faster_whisper import WhisperModel
except ImportError:
    print("Import error. Please run the following command:\n\n    pip install faster-whisper tqdm\n")
    sys.exit(-1)

def show_exception_and_exit(exc_type, exc_value, tb):
    import traceback

    traceback.print_exception(exc_type, exc_value, tb)
    input("Press key to exit.")
    sys.exit(-1)


sys.excepthook = show_exception_and_exit

print("Finding file to transcribe", sys.argv)
sys.stdout.flush()

if len(sys.argv) > 1:
    path = sys.argv[1]
else:
    # Launching without a specified file means we want to find the most recent file
    # in the default capture directories.
    search_roots = [r"G:\videos\Captures"]
    # also add home directory
    search_roots.append(os.path.expanduser("~/videos/Captures"))
    # filter out non-existent directories
    search_roots = [root for root in search_roots if os.path.exists(root)]

    path = max(
        (
            os.path.join(folder, f)
            for root in search_roots
            for folder, _, files in os.walk(root)
            for f in files
        ),
        key=os.path.getmtime,
    )

print(f"Found {path}")

available_models = ["tiny", "small", "medium", "large-v2"]
model_name = "medium"
print(f"Loading model {model_name}")
model = WhisperModel(model_name, compute_type="int8")

print(f"Transcribing {path}")

cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.1\bin"
os.environ["PATH"] += os.pathsep + cuda_path
segments, info = model.transcribe(path, beam_size=5)

print("Duration:", info.duration)

predicted_segments_count = info.duration / 3
outfile = r"C:\Users\J\Desktop\transcript.txt"
srtfile = outfile + ".srt"

# Open the file with VSCode
subprocess.run(["code.cmd", outfile])

with open(outfile, "w") as f:
    with open(srtfile, "w") as srt:
        n = 0
        for segment in tqdm(segments, total=predicted_segments_count):
            f.write(f"[{segment.start: >4.0f}s] {segment.text}\n")
            f.flush()

            # also write SRT format for embedding in transcoded video:
            start = f"{segment.start // 3600:02.0f}:{(segment.start // 60) % 60:02.0f}:{segment.start % 60:02.0f},0"
            end = f"{segment.end // 3600:02.0f}:{(segment.end // 60) % 60:02.0f}:{segment.end % 60:02.0f},0"
            n += 1
            srt.write(f"{n}\n{start} --> {end}\n{segment.text}\n\n")
