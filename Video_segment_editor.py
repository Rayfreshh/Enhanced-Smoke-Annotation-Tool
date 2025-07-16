#!/usr/bin/env python3
"""
Video Segment Editor for Smoke Detection Annotation Tool

This application provides a GUI for annotating video segments for smoke detection.
Users can load videos, select 64-frame segments, watch them, and annotate
whether smoke is present at the end of each segment.

Optimizations implemented:
- Consolidated duplicate code for segment movement operations
- Improved frame caching and display performance
- Added constants for magic numbers and colors
- Better error handling and resource cleanup
- Modular method design with separation of concerns
- Performance optimizations for video playback
- Memory management for frame and image caches

Author: Optimized version
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import time
import gc
from datetime import datetime
from PIL import Image, ImageTk
import cv2
import numpy as np

# Constants
class Constants:
    # Segment settings
    SEGMENT_LENGTH = 64
    BATCH_SIZE = 16
    MAX_CACHE_SIZE = 128
    
    # Movement increments
    SMALL_MOVE = 32
    MEDIUM_MOVE = 64
    LARGE_MOVE = 640
    
    # Timing settings
    # Note: Frame delay is calculated dynamically based on video FPS
    # using _get_ideal_frame_delay_ms() method
    MIN_FRAME_DELAY_MS = 10  # Minimum delay to prevent system overload
    PRELOAD_DELAY_MS = 5
    
    # UI settings
    CANVAS_FALLBACK_WIDTH = 700
    CANVAS_FALLBACK_HEIGHT = 400
    TIMELINE_MARGIN = 80
    SCALE_FACTOR = 0.95
    
    # Animation settings
    LOADING_ANIMATION_DELAY_MS = 500
    GC_INTERVAL_FRAMES = 32
    
    # Colors
    COLORS = {
        'bg_dark': '#2b2b2b',
        'bg_medium': '#3b3b3b',
        'bg_light': '#1e1e1e',
        'text_white': 'white',
        'text_gray': 'lightgray',
        'text_green': 'lightgreen',
        'text_orange': 'orange',
        'button_green': '#4caf50',
        'button_orange': '#ff9800',
        'button_gray': '#757575',
        'button_blue': '#607d8b',
        'button_dark_blue': '#455a64',
        'timeline_active': '#4caf50',
        'timeline_border': '#2e7d32',
        'timeline_bg': '#444444',
        'timeline_border_light': '#666666',
        'position_line': '#ff5722'
    }

class Config:
    """Configuration settings for the application"""
    # File and directory settings
    ANNOTATIONS_DIR = "smoke_detection_annotations"
    IMAGES_SUBDIR = "images"
    LABELS_SUBDIR = "labels"
    CLASSES_FILE = "classes.txt"
    SUMMARY_FILE = "all_annotations_summary.json"
    DATASET_INFO_FILE = "dataset_info.txt"
    
    # Video file types
    VIDEO_FILETYPES = [
        ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
        ("MP4 files", "*.mp4"),
        ("All files", "*.*")
    ]
    
    # Class definitions
    CLASS_NAMES = ["smoke", "no_smoke"]

class VideoSegmentEditor:
    def __init__(self, root):
        self.root = root
        self._init_window()
        self._init_video_properties()
        self._init_segment_properties()
        self._init_annotation_properties()
        self._init_gui_state()
        self._init_performance_variables()
        
        self.setupGui()
        self._bind_events()
        
    def _init_window(self):
        """Initialize window properties"""
        self.root.title("Smoke detection - Annotation tool")
        self.root.state('zoomed' if self.root.tk.call('tk', 'windowingsystem') == 'win32' else 'normal')
        self.root.geometry("1600x1000")
        self.root.configure(bg=Constants.COLORS['bg_dark'])
        
    def _init_video_properties(self):
        """Initialize video-related properties"""
        self.videoCap = None
        self.currentVideoFile = None
        self.totalFrames = 0
        self.currentFrame = 0
        self.fps = 25
        
    def _init_segment_properties(self):
        """Initialize segment-related properties"""
        self.segmentStart = 0
        self.segmentEnd = Constants.SEGMENT_LENGTH - 1
        self.segmentLength = Constants.SEGMENT_LENGTH
        self.isPlaying = False
        self.playbackTimer = None
        self.pausedFrame = None
        self.playbackStartTime = None
        
    def _init_annotation_properties(self):
        """Initialize annotation-related properties"""
        self.annotations = {}
        self.currentSegmentAnnotated = False
        self.segmentWatched = False
        self.lastFrame = None
        
    def _init_gui_state(self):
        """Initialize GUI state properties"""
        self.workflowState = "selection"
        
    def _init_performance_variables(self):
        """Initialize performance optimization variables"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.scaleFactor = None
        self.targetWidth = None
        self.targetHeight = None
        self.frameCache = {}
        self.imageCache = {}
        self.isPreloading = False
        self.loadingLabel = None
        self.loadingAnimationTimer = None
        self.loadingDots = 0
        
    def _bind_events(self):
        """Bind keyboard events"""
        self.root.bind('<Key>', self.onKeyPress)
        self.root.focus_set()
        
    def _handle_error(self, error_msg, exception=None):
        """Centralized error handling"""
        if exception:
            print(f"Error: {error_msg} - {str(exception)}")
        else:
            print(f"Error: {error_msg}")
        messagebox.showerror("Error", error_msg)
        
    def _get_ideal_frame_delay_ms(self):
        """Calculate ideal frame delay in milliseconds based on video FPS"""
        if not self.videoCap or self.fps <= 0:
            return 40  # Default fallback for 25 FPS
            
        # Calculate ideal delay
        ideal_delay = 1000 / self.fps
        
        # Handle edge cases for very high or very low FPS
        if ideal_delay < Constants.MIN_FRAME_DELAY_MS:
            # For very high FPS videos (>100 FPS), use minimum delay
            print(f"Warning: Video FPS ({self.fps:.1f}) is very high. Using minimum delay.")
            return Constants.MIN_FRAME_DELAY_MS
        elif ideal_delay > 200:
            # For very low FPS videos (<5 FPS), cap the delay
            print(f"Warning: Video FPS ({self.fps:.1f}) is very low. Capping delay at 200ms.")
            return 200
            
        return int(ideal_delay)
        
    def _frame_to_time(self, frame):
        """Convert frame number to time format (minutes:seconds)"""
        if not self.videoCap:
            return "0:00"
        seconds = frame / self.fps
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
        
    def setupGui(self):
        """Setup the main GUI layout"""
        # Main container
        mainFrame = tk.Frame(self.root, bg=Constants.COLORS['bg_dark'])
        mainFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        titleLabel = tk.Label(mainFrame, text="Smoke detection - Annotation tool", 
                              font=('Arial', 20, 'bold'), 
                              bg=Constants.COLORS['bg_dark'], 
                              fg=Constants.COLORS['text_white'])
        titleLabel.pack(pady=(0, 15))
        
        # Main content area - horizontal split
        contentFrame = tk.Frame(mainFrame, bg=Constants.COLORS['bg_dark'])
        contentFrame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Video and timeline
        leftFrame = tk.Frame(contentFrame, bg=Constants.COLORS['bg_dark'])
        leftFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Top section - Video display
        self.setupVideoDisplay(leftFrame)
        
        # Middle section - Timeline and controls
        self.setupTimelineControls(leftFrame)
        
        # Right side - Control panels
        rightFrame = tk.Frame(contentFrame, bg=Constants.COLORS['bg_dark'], width=600)
        rightFrame.pack(side=tk.RIGHT, fill=tk.Y)
        rightFrame.pack_propagate(False)
        
        # Bottom section - Control panels on right
        self.setupControlPanels(rightFrame)
        
    def setupVideoDisplay(self, parent):
        """Setup video display area"""
        videoFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        videoFrame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Video info bar
        infoBar = tk.Frame(videoFrame, bg='#3b3b3b', height=40)
        infoBar.pack(fill=tk.X, padx=10, pady=5)
        infoBar.pack_propagate(False)
        
        # File load button
        self.loadBtn = tk.Button(infoBar, text="Load Video File", command=self.loadVideoFile,
                                bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                font=('Arial', 12, 'bold'), width=15, height=2)
        self.loadBtn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Video info labels
        self.videoInfoLabel = tk.Label(infoBar, text="No video loaded", 
                                      bg='#3b3b3b', fg='white', font=('Arial', 12))
        self.videoInfoLabel.pack(side=tk.LEFT, padx=10)
        
        self.frameInfoLabel = tk.Label(infoBar, text="Frame: 0/0", 
                                      bg='#3b3b3b', fg='lightgray', font=('Arial', 12))
        self.frameInfoLabel.pack(side=tk.RIGHT, padx=10)
        
        # Video canvas
        self.videoCanvas = tk.Canvas(videoFrame, bg='black', width=700, height=400)
        self.videoCanvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Loading indicator label (initially hidden)
        self.loadingLabel = tk.Label(videoFrame, text="Loading segment frames", 
                                    bg='black', fg='#4caf50', 
                                    font=('Arial', 16, 'bold'))
        self.loadingLabel.place_forget()  # Hide initially
        
        # Video control buttons under the canvas
        videoControlsFrame = tk.Frame(videoFrame, bg='#3b3b3b', height=60)
        videoControlsFrame.pack(fill=tk.X, padx=10, pady=(0, 10))
        videoControlsFrame.pack_propagate(False)
        
        # Center frame for buttons
        centerFrame = tk.Frame(videoControlsFrame, bg='#3b3b3b')
        centerFrame.pack(expand=True)
        
        # Move Back buttons
        self.move640Back = tk.Button(centerFrame, text="← 640", command=self.moveSegment640Back,
                bg='#455a64', fg='white', font=('Arial', 12, 'bold'), width=8, height=3, state='disabled')
        self.move640Back.pack(side=tk.LEFT, padx=8)
        self.move64Back = tk.Button(centerFrame, text="← 64", command=self.moveSegment64Back,
                bg='#607d8b', fg='white', font=('Arial', 12, 'bold'), width=8, height=3, state='disabled')
        self.move64Back.pack(side=tk.LEFT, padx=8)
        
        # Play/Pause button for preview
        self.previewPlayPauseBtn = tk.Button(centerFrame, text="PLAY", 
                                            command=self.togglePreviewPlayback,
                                            bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                            font=('Arial', 12, 'bold'), width=8, height=3, state='disabled')
        self.previewPlayPauseBtn.pack(side=tk.LEFT, padx=8)
        
        # Replay button
        self.replayBtn = tk.Button(centerFrame, text="REPLAY", 
                                  command=self.replaySegment,
                                  bg='#ff9800', fg='white', font=('Arial', 12, 'bold'),
                                  width=8, height=3, state='disabled')
        self.replayBtn.pack(side=tk.LEFT, padx=8)
        
        # Move Forward buttons
        self.move64Forward = tk.Button(centerFrame, text="64 →", command=self.moveSegment64Forward,
                bg='#607d8b', fg='white', font=('Arial', 12, 'bold'), width=8, height=3, state='disabled')
        self.move64Forward.pack(side=tk.LEFT, padx=8)
        self.move640Forward =tk.Button(centerFrame, text="640 →", command=self.moveSegment640Forward,
                bg='#455a64', fg='white', font=('Arial', 12, 'bold'), width=8, height=3, state='disabled')
        self.move640Forward.pack(side=tk.LEFT, padx=8)
        
    def setupTimelineControls(self, parent):
        """Setup timeline and playback controls"""
        timelineFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2, height=120)
        timelineFrame.pack(fill=tk.X, pady=(0, 10))
        timelineFrame.pack_propagate(False)
        
        # Timeline canvas for visual representation
        self.timelineCanvas = tk.Canvas(timelineFrame, bg='#1e1e1e', height=80)
        self.timelineCanvas.pack(fill=tk.X, padx=20, pady=15)
        
        # Bind timeline events
        self.timelineCanvas.bind('<Button-1>', self.onTimelineClick)
        self.timelineCanvas.bind('<B1-Motion>', self.onTimelineDrag)
        self.timelineCanvas.bind('<Configure>', self.onTimelineResize)
        self.timelineCanvas.bind('<Enter>', self.onTimelineEnter)
        self.timelineCanvas.bind('<Leave>', self.onTimelineLeave)
        
        # Control buttons row
        controlsFrame = tk.Frame(timelineFrame, bg='#3b3b3b')
        controlsFrame.pack(pady=5)
        
        # Single Play/Pause button
        self.playPauseBtn = tk.Button(controlsFrame, text="▶ Play Segment", command=self.togglePlayPause,
                                     bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                     font=('Arial', 12, 'bold'), width=18, height=2)
        self.playPauseBtn.pack(side=tk.LEFT, padx=10)
        
        # Segment info
        tk.Label(controlsFrame, text="Segment:", bg='#3b3b3b', fg='white', 
                font=('Arial', 11)).pack(side=tk.LEFT, padx=(20, 5))
        
        self.segmentInfoLabel = tk.Label(controlsFrame, text="Frames 0-63 (64 frames)", 
                                        bg='#3b3b3b', fg='lightgreen', font=('Arial', 11, 'bold'))
        self.segmentInfoLabel.pack(side=tk.LEFT, padx=5)
        
        # Draw initial timeline with 0:00 times
        self.root.after(100, self.drawTimeline)
        
    def setupControlPanels(self, parent):
        """Setup control panels for different workflow states"""
        controlFrame = tk.Frame(parent, bg='#2b2b2b')
        controlFrame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Segment Selection Controls Panel (always visible on right)
        self.selectionControlPanel = tk.LabelFrame(controlFrame, text="Segment Selection & Controls", 
                                                  font=('Arial', 14, 'bold'), bg='#3b3b3b', fg='white')
        
        selectionControlInner = tk.Frame(self.selectionControlPanel, bg='#3b3b3b')
        selectionControlInner.pack(padx=20, pady=20)
        
        # Segment selection instructions
        tk.Label(selectionControlInner, text="Select a 64-frame segment from the video timeline", 
                bg='#3b3b3b', fg='lightgray', font=('Arial', 12)).pack(pady=5)
        
        tk.Label(selectionControlInner, text="Click and drag on the timeline \nor use arrow buttons to position", 
                bg='#3b3b3b', fg='lightgray', font=('Arial', 11)).pack(pady=5)
        
        # Segment info display
        segmentInfoFrame = tk.Frame(selectionControlInner, bg='#3b3b3b')
        segmentInfoFrame.pack(pady=10)
        
        tk.Label(segmentInfoFrame, text="Current Selection:", 
                bg='#3b3b3b', fg='white', font=('Arial', 12, 'bold')).pack()
        
        self.rightSegmentInfoLabel = tk.Label(segmentInfoFrame, text="Frames 0-63 (64 frames)", 
                                             bg='#3b3b3b', fg='lightgreen', font=('Arial', 11, 'bold'))
        self.rightSegmentInfoLabel.pack(pady=5)
        
        # Control buttons
        tk.Label(selectionControlInner, text="Use the controls below the video to preview and replay segments", 
                bg='#3b3b3b', fg='lightgray', font=('Arial', 12)).pack(pady=(15, 8))
        
        # Always show selection control panel
        self.selectionControlPanel.pack(fill=tk.X, pady=10)
        
        # Review & Annotation Panel (always visible)
        self.reviewAnnotationPanel = tk.LabelFrame(controlFrame, text="Smoke Annotation", 
                                                  font=('Arial', 14, 'bold'), bg='#3b3b3b', fg='white')
        
        reviewAnnotationInner = tk.Frame(self.reviewAnnotationPanel, bg='#3b3b3b')
        reviewAnnotationInner.pack(padx=20, pady=20)
        
        # Instructions
        tk.Label(reviewAnnotationInner, text="After reviewing the segment:", 
                bg='#3b3b3b', fg='white', font=('Arial', 16, 'bold')).pack(pady=10)
        
        tk.Label(reviewAnnotationInner, text="Is there smoke visible at the end\n of this 64-frame segment?", 
                bg='#3b3b3b', fg='lightgray', font=('Arial', 14)).pack(pady=10)
        
        # Watch requirement notice
        self.watchNoticeLabel = tk.Label(reviewAnnotationInner, text="Please watch the segment first to enable annotation", 
                                        bg='#3b3b3b', fg='orange', font=('Arial', 12, 'italic'))
        self.watchNoticeLabel.pack(pady=8)
        
        annotationButtonsFrame = tk.Frame(reviewAnnotationInner, bg='#3b3b3b')
        annotationButtonsFrame.pack(pady=25)
        
        self.smokeBtn = tk.Button(annotationButtonsFrame, text="SMOKE", 
                                 command=self.markSmoke,
                                 bg='#757575', fg='white', font=('Arial', 18, 'bold'),
                                   width=35, height=6, state='disabled')
        self.smokeBtn.pack(pady=12)
        
        self.noSmokeBtn = tk.Button(annotationButtonsFrame, text="NO SMOKE", 
                                   command=self.markNoSmoke,
                                   bg='#757575', fg='white', font=('Arial', 18, 'bold'),
                                   width=35, height=6, state='disabled')
        self.noSmokeBtn.pack(pady=12)
        
        # Always show the annotation panel
        self.reviewAnnotationPanel.pack(fill=tk.X, pady=10)
        
    def setWorkflowState(self, state):
        """Switch between different workflow states"""
        self.workflowState = state
        # Note: All panels are now always visible, no need to hide/show
            
    def loadVideoFile(self):
        """Load a video file"""
        filename = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=Config.VIDEO_FILETYPES
        )
        
        if filename:
            self.loadVideo(filename)
            
    def loadVideo(self, filename):
        """Load video and initialize timeline"""
        try:
            self._cleanup_previous_video()
            
            self.videoCap = cv2.VideoCapture(filename)
            self.currentVideoFile = filename
            
            if not self.videoCap.isOpened():
                messagebox.showerror("Error", "Could not open video file")
                return
                
            self._initialize_video_properties()
            self._reset_segment_state()
            self._reset_performance_cache()
            self._update_video_info_display(filename)
            self._enable_video_controls()
            
            # Draw timeline and load first frame
            self.drawTimeline()
            self.displayFrame(0)
            self.updateFrameInfo()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load video: {str(e)}")
            
    def _cleanup_previous_video(self):
        """Clean up previous video resources"""
        if self.videoCap:
            self.videoCap.release()
            
    def _initialize_video_properties(self):
        """Initialize video properties from loaded video"""
        self.totalFrames = int(self.videoCap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.videoCap.get(cv2.CAP_PROP_FPS) or 25
        
    def _reset_segment_state(self):
        """Reset segment-related state"""
        self.segmentStart = 0
        self.segmentEnd = min(Constants.SEGMENT_LENGTH - 1, self.totalFrames - 1)
        self.currentFrame = 0
        self.segmentWatched = False
        self.pausedFrame = None
        
    def _reset_performance_cache(self):
        """Reset performance optimization variables"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.scaleFactor = None
        self.targetWidth = None
        self.targetHeight = None
        self.frameCache = {}
        self.imageCache = {}
        
    def _update_video_info_display(self, filename):
        """Update video info display"""
        video_name = os.path.basename(filename)
        duration = self.totalFrames / self.fps
        self.videoInfoLabel.config(text=f"{video_name} | {self.totalFrames} frames | {duration:.1f}s | {self.fps:.1f} FPS")
        
    def _enable_video_controls(self):
        """Enable video control buttons"""
        control_buttons = [
            'previewPlayPauseBtn', 'replayBtn', 'move640Back', 'move64Back', 
            'move640Forward', 'move64Forward'
        ]
        
        for button_name in control_buttons:
            if hasattr(self, button_name):
                getattr(self, button_name).config(state='normal')
                
        # Keep annotation buttons disabled until segment is watched
        if hasattr(self, 'smokeBtn'):
            self.smokeBtn.config(state='disabled')
        if hasattr(self, 'noSmokeBtn'):
            self.noSmokeBtn.config(state='disabled')
            
    def drawTimeline(self):
        """Draw the timeline with segment selection"""
        if not hasattr(self, 'timelineCanvas'):
            return
            
        # Force canvas update to get correct dimensions
        self.timelineCanvas.update_idletasks()
        self.timelineCanvas.delete("all")
        
        canvas_width = self.timelineCanvas.winfo_width()
        canvas_height = self.timelineCanvas.winfo_height()
        
        # Use minimum width if canvas isn't ready
        if canvas_width <= 1:
            canvas_width = 400  # Fallback width
            self.root.after(100, self.drawTimeline)
            return
            
        if canvas_height <= 1:
            canvas_height = 40  # Fallback height
            
        # Draw timeline background
        self.timelineCanvas.create_rectangle(0, 0, canvas_width, canvas_height, 
                                           fill='#1e1e1e', outline='')
        
        # Convert frames to time format (minutes:seconds)
        current_time = self._frame_to_time(self.currentFrame) if self.videoCap else "0:00"
        total_time = self._frame_to_time(self.totalFrames - 1) if self.videoCap and self.totalFrames > 0 else "0:00"
        
        # Use wider margins to accommodate time labels outside
        timeline_left = 80
        timeline_right = canvas_width - 80
        timeline_width = timeline_right - timeline_left
        
        # Always show time labels
        self.timelineCanvas.create_text(timeline_left - 10, canvas_height // 2, 
                                      text=f"{current_time}", 
                                      fill=Constants.COLORS['timeline_active'], anchor='e', font=('Arial', 12, 'bold'))
        
        self.timelineCanvas.create_text(timeline_right + 10, canvas_height // 2, 
                                      text=f"{total_time}", 
                                      fill=Constants.COLORS['timeline_active'], anchor='w', font=('Arial', 12, 'bold'))
        
        # Always draw basic timeline background
        self.timelineCanvas.create_rectangle(timeline_left, 10, timeline_right, canvas_height - 10,
                                           fill='#444444', outline='#666666')
        
        # Only draw interactive timeline elements if video is loaded
        if self.videoCap and self.totalFrames > 0:
            segment_start_x = max(timeline_left, (self.segmentStart / self.totalFrames) * timeline_width + timeline_left)
            segment_end_x = min(timeline_right, (self.segmentEnd / self.totalFrames) * timeline_width + timeline_left)
            
            # Draw selected segment
            self.timelineCanvas.create_rectangle(segment_start_x, 5, segment_end_x, canvas_height - 5,
                                               fill=Constants.COLORS['timeline_active'], 
                                               outline=Constants.COLORS['timeline_border'], width=2)
            
            # Draw current position indicator
            if hasattr(self, 'currentFrame'):
                current_x = (self.currentFrame / self.totalFrames) * timeline_width + timeline_left
                current_x = max(timeline_left, min(timeline_right, current_x))
                self.timelineCanvas.create_line(current_x, 0, current_x, canvas_height,
                                              fill='#ff5722', width=3)
            
            # Add start and end markers at exact positions
            self.timelineCanvas.create_line(segment_start_x, 5, segment_start_x, canvas_height - 5,
                                          fill='#2e7d32', width=2)
            self.timelineCanvas.create_line(segment_end_x, 5, segment_end_x, canvas_height - 5,
                                          fill='#2e7d32', width=2)
            
        # Update segment info
        self.updateSegmentInfo()
        
    def updateSegmentInfo(self):
        """Update segment information display"""
        segment_frames = self.segmentEnd - self.segmentStart + 1
        segment_duration = segment_frames / self.fps
        
        segment_start_time = self._frame_to_time(self.segmentStart)
        segment_end_time = self._frame_to_time(self.segmentEnd)
        
        segment_text = f"Frames {self.segmentStart}-{self.segmentEnd} ({segment_frames} frames, {segment_start_time}-{segment_end_time})"
        
        # Update timeline segment info
        self.segmentInfoLabel.config(text=segment_text)
        
        # Update right panel segment info if it exists
        if hasattr(self, 'rightSegmentInfoLabel'):
            self.rightSegmentInfoLabel.config(text=segment_text)
        
    def onTimelineClick(self, event):
        """Handle timeline click for segment positioning"""
        if not self.videoCap or self.workflowState != "selection":
            return
        
        # Pause any ongoing playback when user clicks timeline
        if self.isPlaying:
            self.pausePlayback()
            
        # Force canvas update to get correct dimensions
        self.timelineCanvas.update_idletasks()
        canvas_width = self.timelineCanvas.winfo_width()
        
        # Safety check for canvas width
        if canvas_width <= 1:
            print("Timeline canvas not ready")
            return
            
        # Account for margins (80px on each side for time labels)
        timeline_left = 80
        timeline_width = canvas_width - 160  # Total width minus both margins
        click_x = event.x - timeline_left  # Subtract left margin
        
        # Ensure click is within the timeline area
        if click_x < 0 or click_x > timeline_width:
            return
            
        click_ratio = click_x / timeline_width
        
        # Ensure click ratio is within bounds
        click_ratio = max(0.0, min(1.0, click_ratio))
        
        # Calculate new segment start position
        new_start = int(click_ratio * self.totalFrames)
        new_start = max(0, min(new_start, self.totalFrames - self.segmentLength))
        
        self.segmentStart = new_start
        self.segmentEnd = min(new_start + self.segmentLength - 1, self.totalFrames - 1)
        
        # Reset watched status when segment changes
        self.segmentWatched = False
        self.pausedFrame = None  # Reset paused position when segment changes
        self.updateAnnotationButtons()
        
        # Clear any preloading for the old segment
        self.isPreloading = False
        self.hideLoadingIndicator()
        
        # Immediately update display for instant feedback
        self.drawTimeline()
        self.displayFrame(self.segmentStart)
        
        # No preloading here - only when user clicks play
        
        print(f"Timeline clicked at {event.x}, effective click: {click_x}, ratio: {click_ratio:.3f}, new segment: {self.segmentStart}-{self.segmentEnd}")
        
    def onTimelineDrag(self, event):
        """Handle timeline drag for segment positioning"""
        self.onTimelineClick(event)
        
    def onTimelineResize(self, event=None):
        """Handle timeline canvas resize"""
        # Redraw timeline when canvas is resized
        self.root.after(50, self.drawTimeline)
        
    def onTimelineEnter(self, event):
        """Handle mouse entering timeline - change cursor"""
        if self.workflowState == "selection" and self.videoCap:
            self.timelineCanvas.config(cursor="hand2")
            
    def onTimelineLeave(self, event):
        """Handle mouse leaving timeline - restore cursor"""
        self.timelineCanvas.config(cursor="")
        
    def moveSegment(self, frames, direction='forward'):
        """Generic method to move segment by specified number of frames"""
        if not self.videoCap or self.workflowState != "selection":
            return
        
        # Pause any ongoing playback when user moves segment
        if self.isPlaying:
            self.pausePlayback()
            
        if direction == 'forward':
            new_start = min(self.segmentStart + frames, self.totalFrames - self.segmentLength)
        else:  # backward
            new_start = max(0, self.segmentStart - frames)
            
        self._update_segment_position(new_start)
        
    def _update_segment_position(self, new_start):
        """Update segment position and reset related states"""
        self.segmentStart = new_start
        self.segmentEnd = min(new_start + self.segmentLength - 1, self.totalFrames - 1)
        
        # Reset watched status when segment changes
        self.segmentWatched = False
        self.pausedFrame = None
        self.updateAnnotationButtons()
        
        # Clear any preloading for the old segment
        self.isPreloading = False
        self.hideLoadingIndicator()
        
        # Immediately update display for instant feedback
        self.drawTimeline()
        self.displayFrame(self.segmentStart)
        
    # Specific movement methods using the generic method
    def moveSegment64Back(self):
        """Move segment backward by 64 frames"""
        self.moveSegment(Constants.MEDIUM_MOVE, 'backward')
        
    def moveSegment640Back(self):
        """Move segment backward by 640 frames"""
        self.moveSegment(Constants.LARGE_MOVE, 'backward')
        
    def moveSegment64Forward(self):
        """Move segment forward by 64 frames"""
        self.moveSegment(Constants.MEDIUM_MOVE, 'forward')
        
    def moveSegment640Forward(self):
        """Move segment forward by 640 frames"""
        self.moveSegment(Constants.LARGE_MOVE, 'forward')
        
    def moveSegmentBack(self):
        """Move segment backward by 32 frames"""
        self.moveSegment(Constants.SMALL_MOVE, 'backward')
        
    def moveSegmentForward(self):
        """Move segment forward by 32 frames"""
        self.moveSegment(Constants.SMALL_MOVE, 'forward')
        
    def displayFrame(self, frame_number):
        """Display a specific frame with caching optimization"""
        if not self.videoCap:
            return
            
        try:
            frame = self._get_cached_or_load_frame(frame_number)
            if frame is not None:
                self.currentFrame = frame_number
                self.displayVideoFrame(frame)
                self.updateFrameInfo()
                
                # Store as last frame if it's the end of segment
                if frame_number == self.segmentEnd:
                    self.lastFrame = frame.copy()
                    
        except Exception as e:
            print(f"Error displaying frame {frame_number}: {e}")
            
    def _get_cached_or_load_frame(self, frame_number):
        """Get frame from cache or load from video"""
        if frame_number in self.frameCache:
            return self.frameCache[frame_number]
            
        # Read frame from video
        self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.videoCap.read()
        
        if not ret:
            return None
        
        # Cache the frame if cache isn't too large
        if len(self.frameCache) < Constants.MAX_CACHE_SIZE:
            self.frameCache[frame_number] = frame.copy()
            # Also pre-process and cache the image to avoid cache miss warnings
            self.preProcessImageForDisplay(frame, frame_number)
            
        return frame
            
    def preProcessImageForDisplay(self, frame, frame_num):
        """Pre-process image for display during loading phase"""
        try:
            self._ensure_canvas_dimensions_calculated(frame)
            
            # Convert frame from BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Create and resize image
            image = Image.fromarray(frame_rgb)
            image = image.resize((self.targetWidth, self.targetHeight), Image.Resampling.NEAREST)
            
            # Convert to PhotoImage and cache it
            photo_image = ImageTk.PhotoImage(image)
            self.imageCache[frame_num] = photo_image
            
        except Exception as e:
            print(f"Error pre-processing frame {frame_num}: {e}")
            
    def _ensure_canvas_dimensions_calculated(self, frame):
        """Calculate canvas dimensions and scaling if not done yet"""
        if self.canvasWidth is not None and self.canvasHeight is not None:
            return
            
        self.videoCanvas.update_idletasks()
        canvas_width = self.videoCanvas.winfo_width()
        canvas_height = self.videoCanvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = Constants.CANVAS_FALLBACK_WIDTH, Constants.CANVAS_FALLBACK_HEIGHT
        
        self.canvasWidth = canvas_width
        self.canvasHeight = canvas_height
        
        # Calculate scaling once
        img_height, img_width = frame.shape[:2]
        scale_x = self.canvasWidth / img_width
        scale_y = self.canvasHeight / img_height
        self.scaleFactor = min(scale_x, scale_y) * Constants.SCALE_FACTOR
        
        self.targetWidth = int(img_width * self.scaleFactor)
        self.targetHeight = int(img_height * self.scaleFactor)
        
        # Pre-calculate position once
        self.imageX = (self.canvasWidth - self.targetWidth) // 2
        self.imageY = (self.canvasHeight - self.targetHeight) // 2

    def displayVideoFrame(self, frame):
        """Display frame on canvas with maximum performance optimization"""
        try:
            # Use pre-processed image if available, otherwise minimal fallback
            if self.currentFrame in self.imageCache:
                self.currentImage = self.imageCache[self.currentFrame]
            else:
                # Emergency fallback for cache miss
                print(f"WARNING - Image cache miss for frame {self.currentFrame}!")
                self.currentImage = self._create_emergency_image(frame)
                # Immediately cache this processed image to avoid repeated processing
                self.imageCache[self.currentFrame] = self.currentImage
            
            self._update_canvas_image()

        except Exception as e:
            print(f"Error displaying video frame: {e}")
            
    def _create_emergency_image(self, frame):
        """Create emergency image for cache misses"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Calculate canvas dimensions if needed (should be rare)
        if self.canvasWidth is None:
            self._ensure_canvas_dimensions_calculated(frame)
        
        # Fast emergency resize - minimal quality for rare cache misses
        image = Image.fromarray(frame_rgb)
        image = image.resize((self.targetWidth, self.targetHeight), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)
        
    def _update_canvas_image(self):
        """Update canvas with current image"""
        # Fastest possible canvas update - minimize all operations during playback
        if self.isPlaying:
            # During playback: absolute minimum operations
            if hasattr(self, '_image_id'):
                # Use the most direct method possible
                self.videoCanvas.itemconfigure(self._image_id, image=self.currentImage)
            else:
                self._image_id = self.videoCanvas.create_image(self.imageX, self.imageY, anchor=tk.NW, image=self.currentImage)
        else:
            # Non-playback: normal operations
            if hasattr(self, '_image_id'):
                self.videoCanvas.itemconfig(self._image_id, image=self.currentImage)
            else:
                self._image_id = self.videoCanvas.create_image(self.imageX, self.imageY, anchor=tk.NW, image=self.currentImage)
            
    def showLoadingIndicator(self):
        """Show loading indicator with animated dots"""
        if self.loadingLabel:
            # Position the loading label in the center of the video canvas
            self.videoCanvas.update_idletasks()
            canvas_width = self.videoCanvas.winfo_width()
            canvas_height = self.videoCanvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                x = canvas_width // 2
                y = canvas_height // 2
                self.loadingLabel.place(in_=self.videoCanvas, x=x, y=y, anchor='center')
            else:
                # Fallback positioning
                self.loadingLabel.place(in_=self.videoCanvas, relx=0.5, rely=0.5, anchor='center')
            
            # Start the loading animation
            self.animateLoadingText()
    
    def hideLoadingIndicator(self):
        """Hide loading indicator"""
        if self.loadingLabel:
            self.loadingLabel.place_forget()
        if self.loadingAnimationTimer:
            self.root.after_cancel(self.loadingAnimationTimer)
            self.loadingAnimationTimer = None
    
    def animateLoadingText(self):
        """Animate the loading text with dots"""
        if not self.isPreloading or not self.loadingLabel:
            return
            
        # Cycle through different numbers of dots (0-3)
        self.loadingDots = (self.loadingDots + 1) % 4
        dots = "." * self.loadingDots
        
        # Update text with animated dots
        self.loadingLabel.config(text=f"Loading segment frames{dots}")
        
        # Schedule next animation frame
        self.loadingAnimationTimer = self.root.after(Constants.LOADING_ANIMATION_DELAY_MS, 
                                                    self.animateLoadingText)
    
    def preloadSegmentFrames(self):
        """Preload frames for the current segment to improve playback performance"""
        if not self.videoCap or self.isPreloading:
            return
            
        try:
            self.isPreloading = True
            
            # Show loading indicator
            self.showLoadingIndicator()
            
            # Clear cache for old frames to manage memory
            frames_to_remove = [f for f in self.frameCache.keys() 
                              if f < self.segmentStart or f > self.segmentEnd]
            for frame_num in frames_to_remove:
                del self.frameCache[frame_num]
                if frame_num in self.imageCache:
                    del self.imageCache[frame_num]
            
            # Start asynchronous preloading
            self.preloadFramesBatch(self.segmentStart, 0)
                        
        except Exception as e:
            print(f"Error preloading frames: {e}")
            self.isPreloading = False
            self.hideLoadingIndicator()
            
    def preloadFramesBatch(self, start_frame, batch_index):
        """Preload frames in small batches to avoid UI blocking"""
        if not self.videoCap:
            self.isPreloading = False
            return
            
        current_frame = start_frame + (batch_index * Constants.BATCH_SIZE)
        
        # Stop if we've reached the end of the segment
        if current_frame > self.segmentEnd:
            self.isPreloading = False
            self.hideLoadingIndicator()
            return
            
        try:
            self._load_frame_batch(current_frame)
            
            # Continue with next batch if there are more frames to load
            if current_frame + Constants.BATCH_SIZE <= self.segmentEnd:
                self.root.after(Constants.PRELOAD_DELAY_MS, 
                               lambda: self.preloadFramesBatch(start_frame, batch_index + 1))
            else:
                self.isPreloading = False
                self.hideLoadingIndicator()
            
        except Exception as e:
            print(f"Error in batch preloading: {e}")
            self.isPreloading = False
            self.hideLoadingIndicator()
            
    def _load_frame_batch(self, current_frame):
        """Load a batch of frames into cache"""
        for i in range(Constants.BATCH_SIZE):
            frame_num = current_frame + i
            if frame_num > self.segmentEnd or frame_num >= self.totalFrames:
                break
                
            if frame_num not in self.frameCache and len(self.frameCache) < Constants.MAX_CACHE_SIZE:
                self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = self.videoCap.read()
                if ret:
                    self.frameCache[frame_num] = frame.copy()
                    # Pre-process the image for display during loading
                    self.preProcessImageForDisplay(frame, frame_num)
                else:
                    break
            
    def updateFrameInfo(self):
        """Update frame information display"""
        if self.videoCap:
            self.frameInfoLabel.config(text=f"Frame: {self.currentFrame}/{self.totalFrames-1}")
            
    def togglePreviewPlayback(self):
        """Toggle preview playback in selection mode"""
        if not self.videoCap or self.workflowState != "selection":
            return
            
        if self.isPlaying:
            self.pausePlayback()
            self.previewPlayPauseBtn.config(text="PLAY", bg='#4caf50')
        else:
            self.playSegment()
            self.previewPlayPauseBtn.config(text="PAUSE", bg='#ff9800')
        
    def togglePlayPause(self):
        """Toggle between play and pause"""
        if not self.videoCap:
            return
            
        if self.isPlaying:
            self.pausePlayback()
            self.playPauseBtn.config(text="Play Segment", bg='#4caf50')
        else:
            self.playSegment()
            self.playPauseBtn.config(text="Pause Segment", bg='#ff9800')
        
    def playSegment(self):
        """Play the selected segment"""
        if not self.videoCap:
            return
        
        # Check if preloading is needed and wait for completion
        if not self.isPreloading:
            # Check if segment is already fully cached
            segment_cached = all(frame in self.frameCache and frame in self.imageCache 
                               for frame in range(self.segmentStart, self.segmentEnd + 1))
            
            if not segment_cached:
                self.preloadSegmentFrames()
                # Schedule playback to start after preloading
                self.root.after(100, self.checkPreloadingAndPlay)
                return
        
        # Start actual playback
        self.startPlayback()
        
    def checkPreloadingAndPlay(self):
        """Check if preloading is complete and start playback"""
        if self.isPreloading:
            # Still preloading, check again in 50ms
            self.root.after(50, self.checkPreloadingAndPlay)
        else:
            # Preloading complete, start playback
            self.startPlayback()
    
    def startPlayback(self):
        """Start actual playback after preloading is complete"""
        self.isPlaying = True
        # Resume from paused position or start from beginning
        if self.pausedFrame is not None and self.pausedFrame >= self.segmentStart and self.pausedFrame <= self.segmentEnd:
            self.currentFrame = self.pausedFrame
        else:
            self.currentFrame = self.segmentStart
        self.pausedFrame = None  # Clear paused position
        
        # Record start time for performance tracking
        self.playbackStartTime = time.time()
        
        # Log FPS information for debugging
        ideal_delay = self._get_ideal_frame_delay_ms()
        print(f"Starting playback: Video FPS={self.fps:.1f}, Ideal frame delay={ideal_delay}ms")
        
        if hasattr(self, 'playPauseBtn'):
            self.playPauseBtn.config(text="Pause Segment", bg='#ff9800')
        if hasattr(self, 'previewPlayPauseBtn') and self.workflowState == "selection":
            self.previewPlayPauseBtn.config(text="PAUSE", bg='#ff9800')
        self.playNextFrame()
        
    def playNextFrame(self):
        """Play next frame in segment with maximum performance optimization"""
        if not self.isPlaying or not self.videoCap:
            return
            
        if self.currentFrame <= self.segmentEnd:
            frame_start_time = time.time()
            
            # Ultra-fast frame display - minimal overhead
            frame = self._get_cached_or_load_frame(self.currentFrame)
            if frame is not None:
                display_start = time.time()
                self.displayVideoFrame(frame)
                display_time = (time.time() - display_start) * 1000
            else:
                print(f"WARNING - Frame {self.currentFrame} not cached!")
                display_time = 0
            
            # Update frame info and timeline for smooth user experience
            self.updateFrameInfo()
            self.drawTimeline()
            
            self.currentFrame += 1
            
            # Adaptive timing compensation based on actual display time
            delay = self._calculate_frame_delay(display_time)
            
            # Periodic garbage collection to prevent buildup
            if self.currentFrame % Constants.GC_INTERVAL_FRAMES == 0:
                gc.collect()
            
            self.playbackTimer = self.root.after(delay, self.playNextFrame)
        else:
            # Segment finished
            self._handle_playback_finished()
            
    def _calculate_frame_delay(self, display_time):
        """Calculate adaptive frame delay based on display performance and video FPS"""
        ideal_delay = self._get_ideal_frame_delay_ms()
        
        if display_time > ideal_delay * 0.6:  # If display took more than 60% of ideal time
            # Reduce delay more aggressively to compensate
            delay = max(Constants.MIN_FRAME_DELAY_MS, ideal_delay - int(display_time))
        else:
            # Standard compensation
            delay = max(Constants.MIN_FRAME_DELAY_MS, ideal_delay - int(display_time))
            
        return delay
            
    def _handle_playback_finished(self):
        """Handle end of segment playback"""
        self.isPlaying = False
        
        # Mark segment as watched when it finishes playing
        self.segmentWatched = True
        self.updateAnnotationButtons()
        
        # Display last frame and update timeline
        self.displayFrame(self.segmentEnd)
        self.drawTimeline()
        
        # Reset buttons to play state
        self._reset_play_buttons()
            
    def _reset_play_buttons(self):
        """Reset play buttons to initial state"""
        if hasattr(self, 'playPauseBtn'):
            self.playPauseBtn.config(text="Play Segment", bg=Constants.COLORS['button_green'])
        if hasattr(self, 'previewPlayPauseBtn'):
            self.previewPlayPauseBtn.config(text="PLAY", bg=Constants.COLORS['button_green'])
            
    def pausePlayback(self):
        """Pause playback"""
        self.isPlaying = False
        # Store current position for resuming
        self.pausedFrame = self.currentFrame
        if self.playbackTimer:
            self.root.after_cancel(self.playbackTimer)
        self._reset_play_buttons()
            
    def replaySegment(self):
        """Replay the segment"""
        self.pausePlayback()
        self.pausedFrame = None  # Clear any paused position for full replay
        self.currentFrame = self.segmentStart
        self.displayFrame(self.segmentStart)
        # Don't redraw timeline unnecessarily during replay setup
        # Start playing the segment again
        self.playSegment()
        
    def updateAnnotationButtons(self):
        """Update annotation button states based on whether segment has been watched"""
        if hasattr(self, 'smokeBtn') and hasattr(self, 'noSmokeBtn'):
            if self.segmentWatched:
                self.smokeBtn.config(state='normal')
                self.noSmokeBtn.config(state='normal')
                if hasattr(self, 'watchNoticeLabel'):
                    self.watchNoticeLabel.config(text="Segment watched - annotation enabled", fg='lightgreen')
            else:
                self.smokeBtn.config(state='disabled')
                self.noSmokeBtn.config(state='disabled')
                if hasattr(self, 'watchNoticeLabel'):
                    self.watchNoticeLabel.config(text="Please watch the segment first to enable annotation", fg='orange')
                    
    def markSmoke(self):
        """Mark segment as containing smoke"""
        if not self.segmentWatched:
            messagebox.showwarning("Watch Required", "Please watch the segment completely before making an annotation.")
            return
            
        self.saveAnnotation(True)
        messagebox.showinfo("Annotation Saved", 
                           f"Segment frames {self.segmentStart}-{self.segmentEnd} marked as SMOKE DETECTED")
        
    def markNoSmoke(self):
        """Mark segment as no smoke"""
        if not self.segmentWatched:
            messagebox.showwarning("Watch Required", "Please watch the segment completely before making an annotation.")
            return
            
        self.saveAnnotation(False)
        messagebox.showinfo("Annotation Saved", 
                           f"Segment frames {self.segmentStart}-{self.segmentEnd} marked as NO SMOKE")
        
    def saveAnnotation(self, has_smoke):
        """Save annotation for current segment in YOLO format"""
        if not self.currentVideoFile:
            return
            
        try:        
            if self.currentVideoFile not in self.annotations:
                self.annotations[self.currentVideoFile] = {}
            
            # Save to file in YOLO format
            self.saveAnnotationsToFile()
            
        except Exception as e:
            print(f"Error saving annotation: {e}")
            
    def saveAnnotationsToFile(self):
        """Save all annotations to YOLO format text files in a centralized folder"""
        try:
            # Use the program directory instead of video directory
            program_dir = os.path.dirname(os.path.abspath(__file__))
            video_name = os.path.splitext(os.path.basename(self.currentVideoFile))[0] if self.currentVideoFile else "annotations"
            
            # Create a centralized output directory for all YOLO annotations in program folder
            central_yolo_dir = os.path.join(program_dir, "smoke_detection_annotations")
            images_dir = os.path.join(central_yolo_dir, "images")
            labels_dir = os.path.join(central_yolo_dir, "labels")
            
            for directory in [central_yolo_dir, images_dir, labels_dir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Save each segment as YOLO annotation and corresponding image
            if self.currentVideoFile in self.annotations:
                for segment_key, annotation in self.annotations[self.currentVideoFile].items():
                    end_frame = annotation["end_frame"]
                    has_smoke = annotation["has_smoke"]
                    
                    # Create unique filenames with video name prefix
                    unique_segment_key = f"{video_name}_{segment_key}"
                    
                    # Save the last frame of the segment as the representative image
                    self.saveSegmentFrame(end_frame, unique_segment_key, images_dir)
                    
                    # Create YOLO format label file
                    label_file = os.path.join(labels_dir, f"{unique_segment_key}.txt")
                    
                    with open(label_file, 'w') as f:
                        if has_smoke:
                            f.write("0 0.5 0.5 1.0 1.0\n")
                        else:
                            f.write("1 0.5 0.5 1.0 1.0\n")
                    
            
            # Save or update class names file
            classes_file = os.path.join(central_yolo_dir, "classes.txt")
            with open(classes_file, 'w') as f:
                f.write("smoke\n")
                f.write("no_smoke\n")
            
            # Save or update comprehensive summary JSON file with all videos
            summary_file = os.path.join(central_yolo_dir, "all_annotations_summary.json")
            
            # Load existing annotations if file exists
            all_annotations = {}
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r') as f:
                        all_annotations = json.load(f)
                except:
                    all_annotations = {}
            
            # Update with current video annotations
            if self.currentVideoFile:
                all_annotations[self.currentVideoFile] = self.annotations[self.currentVideoFile]
            
            
            # Create a simple dataset info file
            dataset_info_file = os.path.join(central_yolo_dir, "dataset_info.txt")
            with open(dataset_info_file, 'w') as f:
                f.write("Smoke Detection YOLO Dataset\n")
                f.write("="*40 + "\n\n")
                f.write("Directory Structure:\n")
                f.write("- images/: Contains frame images from video segments\n")
                f.write("- labels/: Contains YOLO format annotation files\n")
                f.write("- classes.txt: Class names (smoke)\n")
                f.write("YOLO Format:\n")
                f.write("- Class 0: smoke\n")
                f.write("- Class 1: no_smoke\n")
                
                # Count total annotations
                total_segments = 0
                smoke_segments = 0
                no_smoke_segments = 0
                videos_processed = len(all_annotations)
                
                for video_annotations in all_annotations.values():
                    for annotation in video_annotations.values():
                        total_segments += 1
                        if annotation.get("has_smoke", False):
                            smoke_segments += 1
                        else:
                            no_smoke_segments += 1
                
                f.write(f"Dataset Statistics:\n")
                f.write(f"- Videos processed: {videos_processed}\n")
                f.write(f"- Total segments: {total_segments}\n")
                f.write(f"- Smoke segments: {smoke_segments}\n")
                f.write(f"- No smoke segments: {no_smoke_segments}\n")
                
            print(f"YOLO annotations saved to centralized folder: {central_yolo_dir}")
            print(f"Images saved to: {images_dir}")
            print(f"Labels saved to: {labels_dir}")
            print(f"Dataset contains annotations from {len(all_annotations)} video(s)")
            
        except Exception as e:
            print(f"Error saving YOLO annotations: {e}")
            
    def saveSegmentFrame(self, frame_number, unique_segment_key, images_dir):
        """Save a specific frame as an image file with unique naming"""
        try:
            # Read the frame
            self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.videoCap.read()
            
            if ret:
                # Save as JPEG image with unique name
                image_path = os.path.join(images_dir, f"{unique_segment_key}.jpg")
                cv2.imwrite(image_path, frame)
                
        except Exception as e:
            print(f"Error saving frame {frame_number}: {e}")
            
    def __del__(self):
        """Destructor to ensure proper cleanup"""
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'videoCap') and self.videoCap:
                self.videoCap.release()
            if hasattr(self, 'playbackTimer') and self.playbackTimer:
                self.root.after_cancel(self.playbackTimer)
            if hasattr(self, 'loadingAnimationTimer') and self.loadingAnimationTimer:
                self.root.after_cancel(self.loadingAnimationTimer)
        except Exception as e:
            print(f"Cleanup error: {e}")
            
    def onKeyPress(self, event):
        """Handle keyboard shortcuts"""
        key = event.keysym.lower()
        
        if key == 'space':
            self.togglePreviewPlayback()
        elif key == 's':
            self.markSmoke()
        elif key == 'n':
            self.markNoSmoke()
        elif key == 'r':
            self.replaySegment()
        elif key == 'left':
            self.moveSegmentBack()
        elif key == 'right':
            self.moveSegmentForward()

def main():
    """Main function to run the application"""
    try:
        root = tk.Tk()
        app = VideoSegmentEditor(root)
        root.mainloop()
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
    finally:
        # Cleanup
        if 'app' in locals() and hasattr(app, 'videoCap') and app.videoCap:
            app.videoCap.release()

if __name__ == "__main__":
    main()
