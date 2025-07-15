import sys
import cv2
import os
import shutil

if len(sys.argv) < 2:
    print("Usage: frame_extract.py <video_path> [--frame-skip N] [--start-frame N] [--consecutive-frames N] [--total-frames]")
    sys.exit()

vid_adr = sys.argv[1]
vid_name = os.path.basename(vid_adr)
vid_base = vid_name.split('.')[0]

print(f"Video file: {vid_adr}")
print(f"Video name: {vid_name}")

if not os.path.isfile(vid_adr):
    print("File does not exist!")
    sys.exit()

# Create folders
mini_videos_folder = f"./generated_videos/{vid_base}/"

try:
    os.makedirs(mini_videos_folder, exist_ok=True)
except Exception as e:
    print(f"Directory creation failed: {e}")
    sys.exit()

# Open video
cap = cv2.VideoCapture(vid_adr)
if not cap.isOpened():
    print("File exists, but error opening the file!")
    sys.exit()

length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
leading_zeros_count = len(str(length))

print(f"Total Frames: {length}, FPS: {fps}, Resolution: {width}x{height}")

# Handle options
args = sys.argv[2:]
options = {
    '--frame-skip': None,
    '--start-frame': None,
    '--total-frames': False,
    '--consecutive-frames': None
}

i = 0
while i < len(args):
    if args[i] in options:
        if args[i] == '--total-frames':
            print(f"Total number of frames: {length}")
            sys.exit()
        else:
            if i + 1 >= len(args):
                print(f"Expected value after {args[i]}")
                sys.exit()
            options[args[i]] = args[i + 1]
            i += 2
    else:
        i += 1

cur_ix = int(options['--start-frame']) if options['--start-frame'] and options['--start-frame'].isdigit() else 0
skip_frames = int(options['--frame-skip']) if options['--frame-skip'] and options['--frame-skip'].isdigit() else 0
consecutive_frames = int(options['--consecutive-frames']) if options['--consecutive-frames'] and options['--consecutive-frames'].isdigit() else 1

cap.set(cv2.CAP_PROP_POS_FRAMES, cur_ix)
batch_index = 0

while cur_ix < length:
    frames = []
    batch_folder = os.path.join(mini_videos_folder, f"mini_video_{str(batch_index).zfill(4)}")
    os.makedirs(batch_folder, exist_ok=True)

    for i in range(consecutive_frames):
        frame_idx = cur_ix + i
        if frame_idx >= length:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"Failed to read frame at index {frame_idx}. Exiting.")
            break

        frame_name = f"Frame_{str(frame_idx).zfill(leading_zeros_count)}_{length}.jpg"
        frame_path = os.path.join(batch_folder, frame_name)
        cv2.imwrite(frame_path, frame)
        print(f"Saved Frame No: {frame_idx} / {length} → {frame_path}")
        frames.append(frame)

    if frames:
        video_path = os.path.join(batch_folder, f"mini_video_{str(batch_index).zfill(4)}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        for frame in frames:
            out.write(frame)
        out.release()
        print(f"Created mini video: {video_path}")
        batch_index += 1

    cur_ix += consecutive_frames + skip_frames

cap.release()
print("Video processing complete.")
