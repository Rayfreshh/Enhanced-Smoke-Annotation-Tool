
# Smoke Annotation Tool Guide

This guide explains how to use the Smoke Annotation Tool to efficiently label video segments for smoke detection datasets. The tool is designed for speed, usability, and high-quality dataset creation.

---


## Features

- **Video Loading:** Supports MP4, AVI, MOV, MKV, WMV, and more.
- **Segmented Annotation:** Videos are split into 64-frame segments for consistent labeling.
- **Playback Controls:** Play, pause, replay, and navigate segments with buttons or keyboard shortcuts.
- **Annotation Buttons:** Mark each segment as "SMOKE" or "NO SMOKE" after watching.
- **Annotation History:** View, navigate, and jump to previously annotated segments.
- **Keyboard Shortcuts:**
  - `Spacebar`: Play/Pause segment
  - `Enter`: Replay segment
  - `Up Arrow`: Mark SMOKE
  - `Down Arrow`: Mark NO SMOKE
  - `Left Arrow`: Previous segment
  - `Right Arrow`: Next segment
- **Automatic Saving:** Annotations are saved in YOLO format and a summary JSON file.
- **Temporal Analysis:** Generates a temporal saturation histogram image for each segment.

---

------


## Quick Start

1. **Load a Video:**
   - Click "Load Video File" and select your video.
2. **Navigate Segments:**
   - Use the timeline, navigation buttons, or arrow keys to select 64-frame segments.
3. **Watch the Segment:**
   - Press "Play" (or `Spacebar`) to watch the current segment. You must watch the entire segment before annotating.
4. **Annotate:**
   - After watching, the "SMOKE" and "NO SMOKE" buttons become active. Click the appropriate button or use the `Up`/`Down` arrow keys.
5. **Review History:**
   - The right panel shows annotation history. Click any entry to jump to that segment.
6. **Save & Export:**
   - Annotations and temporal analysis images are saved automatically in your home directory under `smoke_detection_annotations`.

---

------


## Folder Structure

When you annotate videos, the following folder structure is created in your home directory under `smoke_detection_annotations`:

```
smoke_detection_annotations/
├── images/         # Temporal histogram images for each segment
│   ├── <class>_<video_name>_<segment>.png
│   └── ...
├── labels/         # YOLO annotation files for each segment
│   ├── <class>__<video_name>_<segment>.txt
│   └── ...
├── Annotations_summary.json   # JSON file with all annotation metadata
└── classes.txt    # List of class names (e.g., SMOKE, NO SMOKE)
```

Each segment you annotate will generate:
- A histogram image in `images/`
- A YOLO label file in `labels/`
- An entry in `Annotations_summary.json`

---

------


## Annotation Labels

For every histogram image, an annotation label is included. This label contains the choice that the user made: either "SMOKE" or "NO SMOKE". The tool uses YOLO format for classification, marking the whole frame as a single class.

- **YOLO Files:**
  - For every image, a `.txt` file is created with the same name (but `.txt` extension).
  - The YOLO annotation for classification is always a single line:
    - `0 0.5 0.5 1.0 1.0` for "SMOKE"
    - `1 0.5 0.5 1.0 1.0` for "NO SMOKE"
  - Format: `<class> <x_center> <y_center> <width> <height>` (all normalized, so the box covers the whole image)
- **Summary File:**
  - All annotations are also stored in `Annotations_summary.json` for easy review and dataset management. This file contains metadata such as video name, segment index, annotation, and file paths.

---

------


## Temporal Saturation Histogram

For each 64-frame segment, the tool generates a **temporal saturation histogram** image:

- Each frame is divided into a 3x3 grid (9 regions) with 20% overlap between regions.
  <img src="Documentation images/overlap_grid.png" alt="overlap_grid" style="zoom: 50%;" />
- For each region, the saturation channel (from HSV color space) is extracted for all 64 frames.
  <img src="Documentation images/saturation_overlap_grid.png" alt="saturation_overlap_grid" style="zoom:50%;" />
- For each region, a histogram of saturation values is computed over time, resulting in a temporal profile of color saturation.
- The result is a 192x192 grayscale image:
  - Each region is represented as a 64x64 block (so 3x3 blocks in total).
  - Pixel intensity in each block encodes the normalized histogram value for that region and time.
- This image is saved in the `images/` folder and can be used as input for machine learning models.
  <img src="Documentation images/smoke_video38-3x-RIFE-RIFE4.0-60fps_012283_012346.png" alt="smoke_video38-3x-RIFE-RIFE4.0-60fps_012283_012346" style="zoom: 200%;" />

---

------


## Technical Information

- **Segment Length:** 64 frames per segment (configurable in `Constants`).
- **Grid:** Each frame is divided into a 3x3 grid with 20% overlap for temporal analysis.
- **Caching:** Frames and processed images are cached for smooth playback.
- **Performance:**
  - Playback speed is dynamically adjusted to match real-time, skipping frames if necessary.
  - Maximum of 3 consecutive frames can be skipped to maintain smoothness.
- **Output Directory:**
  - All annotation files and images are saved in `~/smoke_detection_annotations/` on Linux or `C:/users/<name>/smoke_detection_annotations/` in Windows.
  - Subfolders: `images/` (temporal analysis images), `labels/` (YOLO labels).
- **Dependencies:**
  - Python 3.x
  - Tkinter (for GUI)
  - OpenCV (`cv2`) (for video and image processing)
  - Pillow (`PIL`) (for image handling)
  - Numpy (for numerical operations)

---

------


## Troubleshooting

- If the annotation buttons are disabled, make sure you have watched the entire segment.
- If you encounter errors loading videos, check that the file format is supported and that all dependencies are installed.
- For best performance, use videos with standard frame rates (25–60 FPS).

---

For more details or technical questions, see the source code or contact the developer.