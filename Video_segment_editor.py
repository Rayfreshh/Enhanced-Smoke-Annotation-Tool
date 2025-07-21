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
from tkinter import filedialog, messagebox
import os
import json
import time
import gc
from datetime import datetime
from PIL import Image, ImageTk
import cv2

# Import temporal analysis functionality
from temporal_analysis_complete import TemporalAnalysisGenerator

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
    
    # Scaled UI settings for better layout
    SCALED_CANVAS_WIDTH = 480
    SCALED_CANVAS_HEIGHT = 320
    SCALED_TIMELINE_HEIGHT = 60
    
    # Scaled annotation button settings
    SCALED_BUTTON_HEIGHT = 4  # Reduced from 6 to save space
    SCALED_BUTTON_FONT_SIZE = 16  # Reduced from 18
    SCALED_BUTTON_PADDING = 8  # Reduced from 12
    
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
        # Set root window background to match dark theme
        try:
            self.root.configure(bg=Constants.COLORS['bg_dark'])
        except Exception:
            self.root.configure(bg='#232323')  # fallback if Constants not ready

        # Get screen dimensions for initial window sizing
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Set initial window size based on screen size
        if screen_width <= 1920 and screen_height <= 1080:
            self.window_width = min(1300, screen_width - 80)
            self.window_height = min(850, screen_height - 80)
        elif screen_width <= 2560 and screen_height <= 1440:
            self.window_width = min(1600, screen_width - 100)
            self.window_height = min(1000, screen_height - 100)
        else:
            self.window_width = min(1800, screen_width - 100)
            self.window_height = min(1200, screen_height - 100)
        
        # Set window geometry
        x = (screen_width - self.window_width) // 2
        y = (screen_height - self.window_height) // 2
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        
        # Try to maximize on Windows, otherwise use normal state
        try:
            if self.root.tk.call('tk', 'windowingsystem') == 'win32':
                self.root.state('zoomed')
            else:
                self.root.state('normal')
        except:
            self.root.state('normal')
        
        # Bind window resize event for video display updates
        self.root.bind('<Configure>', self._on_window_resize)
        
        # Set initial panel dimensions based on window size (will be updated dynamically)
        self.right_panel_width = self._calculate_dynamic_panel_width()
        # ...
        
        # Calculate dynamic font sizes for right panel based on window size
        self._calculate_dynamic_font_sizes()
        
        self.history_text_height = 30  # Increased for better visibility
    
    def _calculate_dynamic_panel_width(self):
        """Calculate right panel width based on current window size"""
        # Get actual window dimensions
        self.root.update_idletasks()  # Ensure geometry is updated
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        
        # Handle case where window dimensions aren't ready yet
        if current_width <= 1 or current_height <= 1:
            # Use initial window size if current dimensions aren't available
            if hasattr(self, 'window_width'):
                current_width = self.window_width
            else:
                current_width = 1300  # Fallback
        
        # Calculate panel width as a percentage of window width with size-based tiers
        # Smaller windows get proportionally smaller panels for better balance
        if current_width <= 1300:
            # Small window: use ~35% for right panel (reduced from 45%)
            return max(550, int(current_width * 0.35))
        elif current_width <= 1600:
            # Medium window: use ~32% for right panel (reduced from 40%)
            return max(600, int(current_width * 0.32))
        else:
            # Large window: use ~28% for right panel (reduced from 35%)
            return max(650, min(800, int(current_width * 0.28)))
    
    def _calculate_dynamic_font_sizes(self):
        """Calculate dynamic font sizes for right panel based on current window size"""
        # Get actual window dimensions
        self.root.update_idletasks()
        current_height = self.root.winfo_height()
        
        # Handle case where window dimensions aren't ready yet
        if current_height <= 1 or current_height <= 1:
            if hasattr(self, 'window_width'):
                current_height = self.current_height
            else:
                current_height = 1300  # Fallback
        
        # Base font sizes (optimized for 4K displays)
        base_4k_fonts = {
            'panel_title': 15,      # LabelFrame titles
            'instruction_main': 18, # Main instruction text
            'instruction_sub': 15,  # Sub instruction text
            'notice': 14,           # Notice text
            'info': 15,             # Info labels
            'button': 20,           # Annotation buttons
            'history': 15           # History text
        }
        
        # Calculate scaling factor based on window width (downscaling from 4K baseline)
        if current_height <= 1300:
            # Small window (1080p): scale down to 80% of 4K baseline
            scale_factor = 0.8
        elif current_height <= 1600:
            # Medium window (1440p): scale down to 90% of 4K baseline
            scale_factor = 0.9
        else:
            # Large window (4K+): use full 4K baseline
            scale_factor = 1.0
        
        # Apply scaling to create dynamic font sizes
        self.panel_fonts = {}
        for font_type, base_size in base_4k_fonts.items():
            scaled_size = int(base_size * scale_factor)
            self.panel_fonts[font_type] = scaled_size
    
    
    def _update_panel_width(self):
        """Update right panel width and font sizes dynamically based on current window size"""
        new_width = self._calculate_dynamic_panel_width()
        
        # Recalculate font sizes for the new window size
        old_fonts = getattr(self, 'panel_fonts', {})
        self._calculate_dynamic_font_sizes()
        
        # Check if panel width or fonts changed
        width_changed = hasattr(self, 'right_panel_width') and new_width != self.right_panel_width
        fonts_changed = old_fonts != self.panel_fonts
        
        if width_changed:
            self.right_panel_width = new_width
            # Update the actual rightFrame width if it exists
            if hasattr(self, 'rightFrame'):
                self.rightFrame.config(width=self.right_panel_width)
                self.rightFrame.update_idletasks()
        
        # Update font sizes if they changed
        if fonts_changed and hasattr(self, 'panel_fonts'):
            self._update_panel_fonts()
    
    def _update_panel_fonts(self):
        """Update font sizes for right panel elements"""
        # Update LabelFrame titles
        if hasattr(self, 'selectionControlPanel'):
            self.selectionControlPanel.config(font=('Arial', self.panel_fonts['panel_title'], 'bold'))
        if hasattr(self, 'reviewAnnotationPanel'):
            self.reviewAnnotationPanel.config(font=('Arial', self.panel_fonts['panel_title'], 'bold'))
        if hasattr(self, 'historyPanel'):
            self.historyPanel.config(font=('Arial', self.panel_fonts['panel_title'], 'bold'))

        # Update instruction labels (we'll store references to these)
        if hasattr(self, 'instructionMainLabel'):
            self.instructionMainLabel.config(font=('Arial', self.panel_fonts['instruction_main'], 'bold'))
        if hasattr(self, 'instructionSubLabel'):
            self.instructionSubLabel.config(font=('Arial', self.panel_fonts['instruction_sub']))
        if hasattr(self, 'watchNoticeLabel'):
            self.watchNoticeLabel.config(font=('Arial', self.panel_fonts['notice'], 'italic'))

        # Update info labels
        if hasattr(self, 'selectionInfoLabel'):
            self.selectionInfoLabel.config(font=('Arial', self.panel_fonts['panel_title'], 'bold'))
        if hasattr(self, 'rightSegmentInfoLabel'):
            self.rightSegmentInfoLabel.config(font=('Arial', self.panel_fonts['info'], 'bold'))
        if hasattr(self, 'rightAnnotationInfoLabel'):
            self.rightAnnotationInfoLabel.config(font=('Arial', self.panel_fonts['info'], 'bold'))

        # Update annotation buttons
        if hasattr(self, 'smokeBtn'):
            self.smokeBtn.config(font=('Arial', self.panel_fonts['button'], 'bold'))
        if hasattr(self, 'noSmokeBtn'):
            self.noSmokeBtn.config(font=('Arial', self.panel_fonts['button'], 'bold'))

        # Update history text
        if hasattr(self, 'historyText'):
            self.historyText.config(font=('Arial', self.panel_fonts['history']))
    
    def _on_window_resize(self, event):
        """Handle window resize events"""
        # Only handle resize events for the main window, not child widgets
        if event.widget == self.root:
            # Add a delay to avoid too frequent updates
            if hasattr(self, '_window_resize_timer'):
                self.root.after_cancel(self._window_resize_timer)
            self._window_resize_timer = self.root.after(200, self._handle_window_resize)
    
    def _handle_window_resize(self):
        """Handle window resize - refresh video display, update panel width and font scaling"""
        # Update panel width and font scaling based on new window size
        self._update_panel_width()
        
        # Refresh video display if video is loaded
        if hasattr(self, 'videoCap') and self.videoCap and hasattr(self, 'currentFrame'):
            # Clear canvas cache to force recalculation with new dimensions
            self._clear_canvas_dimensions_cache()
            self.root.after(100, lambda: self.refreshVideoDisplay())
        
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
        self.all_annotations = {}
        
    def _init_gui_state(self):
        """Initialize GUI state properties"""
        self.workflowState = "selection"
        
    def _init_performance_variables(self):
        """Initialize performance optimization variables"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.targetWidth = None
        self.targetHeight = None
        self.frameCache = {}
        self.imageCache = {}
        self.isPreloading = False
        self.loadingLabel = None
        self.loadingAnimationTimer = None
        self.loadingDots = 0
        
        # Initialize temporal analysis generator
        self.temporal_generator = TemporalAnalysisGenerator()
        
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
        padding = 10
        mainFrame = tk.Frame(self.root, bg=Constants.COLORS['bg_dark'])
        mainFrame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        
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
        leftFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, padding))
        
        # Top section - Video display
        self.setupVideoDisplay(leftFrame)
        
        # Middle section - Timeline and controls
        self.setupTimelineControls(leftFrame)
        
        # Right side - Control panels
        self.rightFrame = tk.Frame(contentFrame, bg=Constants.COLORS['bg_dark'], width=self.right_panel_width)
        self.rightFrame.pack(side=tk.RIGHT, fill=tk.Y)
        self.rightFrame.pack_propagate(False)
        
        # Bottom section - Control panels on right
        self.setupControlPanels(self.rightFrame)
        
    def setupVideoDisplay(self, parent):
        """Setup video display area"""
        padding = 10
        videoFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        videoFrame.pack(fill=tk.BOTH, expand=True, pady=(0, padding))
        
        # Video info bar
        info_height = 40
        infoBar = tk.Frame(videoFrame, bg='#3b3b3b', height=info_height)
        infoBar.pack(fill=tk.X, padx=padding, pady=5)
        infoBar.pack_propagate(False)
        
        # File load button
        self.loadBtn = tk.Button(infoBar, text="Load Video File", command=self.loadVideoFile,
                                bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                font=('Arial', 12, 'bold'), 
                                width=15, height=2)
        self.loadBtn.pack(side=tk.LEFT, padx=(0, padding))
        
        # Video info labels
        self.videoInfoLabel = tk.Label(infoBar, text="No video loaded", 
                                      bg='#3b3b3b', fg='white', 
                                      font=('Arial', 12))
        self.videoInfoLabel.pack(side=tk.LEFT, padx=padding)
        
        self.frameInfoLabel = tk.Label(infoBar, text="Frame: 0/0", 
                                      bg='#3b3b3b', fg='lightgray', 
                                      font=('Arial', 12))
        self.frameInfoLabel.pack(side=tk.RIGHT, padx=padding)
        
        # Video canvas - scaled for better layout
        canvas_width = Constants.SCALED_CANVAS_WIDTH
        canvas_height = Constants.SCALED_CANVAS_HEIGHT
        self.videoCanvas = tk.Canvas(videoFrame, bg='black', 
                                   width=canvas_width, height=canvas_height)
        self.videoCanvas.pack(fill=tk.BOTH, expand=True, padx=padding, pady=(0, padding))
        
        # Bind canvas resize event for dynamic resolution updates
        self.videoCanvas.bind('<Configure>', self.onCanvasResize)
        
        # Loading indicator label (initially hidden)
        self.loadingLabel = tk.Label(videoFrame, text="Loading segment frames", 
                                    bg='black', fg='#4caf50', 
                                    font=('Arial', 16, 'bold'))
        self.loadingLabel.place_forget()  # Hide initially
        
        
        # Video control buttons under the canvas - reduced height
        videoControlsFrame = tk.Frame(videoFrame, bg='#3b3b3b', height=50)
        videoControlsFrame.pack(fill=tk.X, padx=10, pady=(0, 10))
        videoControlsFrame.pack_propagate(False)
        
        # Center frame for buttons
        centerFrame = tk.Frame(videoControlsFrame, bg='#3b3b3b')
        centerFrame.pack(expand=True)
        
        # Move Back buttons - reduced height
        self.move640Back = tk.Button(centerFrame, text="<< 640", command=self.moveSegment640Back,
                bg='#455a64', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move640Back.pack(side=tk.LEFT, padx=6)
        self.move64Back = tk.Button(centerFrame, text="< 64", command=self.moveSegment64Back,
                bg='#607d8b', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move64Back.pack(side=tk.LEFT, padx=6)
        
        # Play/Pause button for preview - reduced height
        self.previewPlayPauseBtn = tk.Button(centerFrame, text="PLAY", 
                                            command=self.togglePreviewPlayback,
                                            bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                            font=('Arial', 11, 'bold'),
                                            width=8, height=2, state='disabled')
        self.previewPlayPauseBtn.pack(side=tk.LEFT, padx=6)
        
        # Replay button - reduced height
        self.replayBtn = tk.Button(centerFrame, text="REPLAY", 
                                  command=self.replaySegment,
                                  bg='#ff9800', fg='white', 
                                  font=('Arial', 11, 'bold'),
                                  width=8, height=2, state='disabled')
        self.replayBtn.pack(side=tk.LEFT, padx=6)
        
        # Move Forward buttons - reduced height
        self.move64Forward = tk.Button(centerFrame, text="64 >", command=self.moveSegment64Forward,
                bg='#607d8b', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move64Forward.pack(side=tk.LEFT, padx=6)
        self.move640Forward = tk.Button(centerFrame, text="640 >>", command=self.moveSegment640Forward,
                bg='#455a64', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move640Forward.pack(side=tk.LEFT, padx=6)
        
    def setupTimelineControls(self, parent):
        """Setup timeline and playback controls"""
        timelineFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2, height=100)
        timelineFrame.pack(fill=tk.X, pady=(0, 10))
        timelineFrame.pack_propagate(False)
        
        # Timeline canvas for visual representation - scaled
        self.timelineCanvas = tk.Canvas(timelineFrame, bg='#1e1e1e', height=Constants.SCALED_TIMELINE_HEIGHT)
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
        
        # Single Play/Pause button - reduced height for better layout
        self.playPauseBtn = tk.Button(controlsFrame, text="PLAY Segment", command=self.togglePlayPause,
                                     bg=Constants.COLORS['button_green'], fg=Constants.COLORS['text_white'], 
                                     font=('Arial', 11, 'bold'), width=16, height=1)
        self.playPauseBtn.pack(side=tk.LEFT, padx=10)
        
        # Segment info
        tk.Label(controlsFrame, text="Segment:", bg='#3b3b3b', fg='white', 
                font=('Arial', 11)).pack(side=tk.LEFT, padx=(20, 5))
        
        self.segmentInfoLabel = tk.Label(controlsFrame, text="Frames 0-63 (64 frames)", 
                                        bg='#3b3b3b', fg='lightgreen', 
                                        font=('Arial', 11, 'bold'))
        self.segmentInfoLabel.pack(side=tk.LEFT, padx=5)
        
        # Draw initial timeline with 0:00 times
        self.root.after(100, self.drawTimeline)
        
    def setupControlPanels(self, parent):
        """Setup control panels for different workflow states"""
        controlFrame = tk.Frame(parent, bg='#2b2b2b')
        controlFrame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Segment Selection Controls Panel (always visible on right)
        self.selectionControlPanel = tk.LabelFrame(controlFrame, text="Segment Selection", 
                                                  font=('Arial', self.panel_fonts.get('panel_title', 12), 'bold'), 
                                                  bg='#3b3b3b', fg='white')
        
        selectionControlInner = tk.Frame(self.selectionControlPanel, bg='#3b3b3b')
        selectionControlInner.pack(padx=20, pady=20)
        
        # Detailed segment info display
        segmentInfoFrame = tk.Frame(selectionControlInner, bg='#3b3b3b')
        segmentInfoFrame.pack(pady=5)
        
        self.selectionInfoLabel = tk.Label(segmentInfoFrame, text="Current Selection:", 
                bg='#3b3b3b', fg='white', 
                font=('Arial', self.panel_fonts.get('panel_title', 12), 'bold'))
        self.selectionInfoLabel.pack()
        
        self.rightSegmentInfoLabel = tk.Label(segmentInfoFrame, text="Frames 0-63 (64 frames)", 
                                             bg='#3b3b3b', fg='lightgreen', 
                                             font=('Arial', self.panel_fonts.get('info', 10), 'bold'))
        self.rightSegmentInfoLabel.pack(pady=2)

        self.annotationInfoLabel = tk.Label(segmentInfoFrame, text="Annotation information:", 
                bg='#3b3b3b', fg='white', 
                font=('Arial', self.panel_fonts.get('panel_title', 12), 'bold'))
        self.annotationInfoLabel.pack()

        self.rightAnnotationInfoLabel = tk.Label(segmentInfoFrame, text="No annotations yet", 
                                            bg='#3b3b3b', fg='lightgray', 
                                            font=('Arial', self.panel_fonts.get('info', 10)))
        self.rightAnnotationInfoLabel.pack(pady=2)
        
        
        # Always show selection control panel
        self.selectionControlPanel.pack(fill=tk.X, pady=10)

        # Review & Annotation Panel (moved to top)
        self.reviewAnnotationPanel = tk.LabelFrame(controlFrame, text="Smoke Annotation", 
                                                  font=('Arial', self.panel_fonts.get('panel_title', 12), 'bold'), 
                                                  bg='#3b3b3b', fg='white')
        
        reviewAnnotationInner = tk.Frame(self.reviewAnnotationPanel, bg='#3b3b3b')
        reviewAnnotationInner.pack(padx=8, pady=8)
        
        # Instructions
        self.instructionMainLabel = tk.Label(reviewAnnotationInner, text="After reviewing the segment:", 
                bg='#3b3b3b', fg='white', 
                font=('Arial', self.panel_fonts.get('instruction_main', 14), 'bold'))
        self.instructionMainLabel.pack(pady=8)
        
        self.instructionSubLabel = tk.Label(reviewAnnotationInner, text="Is there smoke visible at the end\n of this 64-frame segment?", 
                bg='#3b3b3b', fg='lightgray', 
                font=('Arial', self.panel_fonts.get('instruction_sub', 12)))
        self.instructionSubLabel.pack(pady=8)
        
        # Watch requirement notice
        self.watchNoticeLabel = tk.Label(reviewAnnotationInner, text="Please watch the segment first to enable annotation", 
                                        bg='#3b3b3b', fg='orange', 
                                        font=('Arial', self.panel_fonts.get('notice', 10), 'italic'))
        self.watchNoticeLabel.pack(pady=6)
        
        annotationButtonsFrame = tk.Frame(reviewAnnotationInner, bg='#3b3b3b')
        annotationButtonsFrame.pack(pady=20)
        
        # Annotation buttons with scaled dimensions for more history space
        self.smokeBtn = tk.Button(annotationButtonsFrame, text="SMOKE", 
                                 command=self.markSmoke,
                                 bg='#757575', fg='white', 
                                 font=('Arial', self.panel_fonts.get('button', Constants.SCALED_BUTTON_FONT_SIZE), 'bold'),
                                 width=35, height=Constants.SCALED_BUTTON_HEIGHT, state='disabled')
        self.smokeBtn.pack(pady=Constants.SCALED_BUTTON_PADDING)
        
        self.noSmokeBtn = tk.Button(annotationButtonsFrame, text="NO SMOKE", 
                                   command=self.markNoSmoke,
                                   bg='#757575', fg='white', 
                                   font=('Arial', self.panel_fonts.get('button', Constants.SCALED_BUTTON_FONT_SIZE), 'bold'),
                                   width=35, height=Constants.SCALED_BUTTON_HEIGHT, state='disabled')
        self.noSmokeBtn.pack(pady=Constants.SCALED_BUTTON_PADDING)
        
        # Show annotation panel first (at top)
        self.reviewAnnotationPanel.pack(fill=tk.X, pady=10)
        
        # Annotation History Panel (moved to bottom, expanded to use freed space)
        self.historyPanel = tk.LabelFrame(controlFrame, text="Annotation History", 
                                         font=('Arial', self.panel_fonts.get('panel_title', 12), 'bold'), 
                                         bg='#3b3b3b', fg='white')
        
        historyInner = tk.Frame(self.historyPanel, bg='#3b3b3b')
        historyInner.pack(padx=20, pady=15, fill=tk.BOTH, expand=True)
        
        # History display (expanded)
        historyDisplayFrame = tk.Frame(historyInner, bg='#3b3b3b')
        historyDisplayFrame.pack(pady=5, fill=tk.BOTH, expand=True)
        
        # Create scrollable text widget for history
        self.historyText = tk.Text(historyDisplayFrame, height=self.history_text_height, width=50, 
                                  bg='#1e1e1e', fg='white', 
                                  font=('Arial', self.panel_fonts.get('history', 12)),
                                  wrap=tk.WORD, state=tk.DISABLED)
        
        historyScrollbar = tk.Scrollbar(historyDisplayFrame, orient=tk.VERTICAL, 
                                       command=self.historyText.yview)
        self.historyText.configure(yscrollcommand=historyScrollbar.set)
        
        self.historyText.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        historyScrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Show history panel last (at bottom, takes remaining space)
        self.historyPanel.pack(fill=tk.BOTH, expand=True, pady=10)
        
    def setWorkflowState(self, state):
        """Switch between different workflow states"""
        self.workflowState = state
        # Note: All panels are now always visible, no need to hide/show
            
    def loadVideoFile(self):
        """Load a video file"""

        filename = filedialog.askopenfilename(
            title="Select a video file",
            initialdir=os.path.expanduser("~"),
            filetypes=Config.VIDEO_FILETYPES,
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
            
            # Load existing annotations for this video
            self.loadExistingAnnotations()
            
            # Automatically load and display annotation history when video is loaded
            if hasattr(self, 'historyText'):
                try:
                    self.loadAnnotationHistory()
                except Exception as history_error:
                    print(f"Note: Could not auto-load annotation history: {history_error}")
                    # Fallback to showing a message
                    self.displayHistoryMessage("No annotation history found for this video.")
            
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
    
    def loadExistingAnnotations(self):
        """Load existing annotations for the current video from the summary file"""
        try:
            program_dir = os.path.expanduser("~")
            summary_file = os.path.join(program_dir, "smoke_detection_annotations", "annotations_summary.json")
            
            if not os.path.exists(summary_file):
                # No existing annotations file, initialize empty
                if self.currentVideoFile not in self.annotations:
                    self.annotations[self.currentVideoFile] = {}
                return
            
            with open(summary_file, 'r') as f:
                self.all_annotations = json.load(f)
            
            # Load annotations for current video if they exist
            current_video_path = self.currentVideoFile
            video_annotations = None
            
            # Try exact path match first
            if current_video_path in self.all_annotations:
                video_annotations = self.all_annotations[current_video_path]
            else:
                # Try matching by filename only
                current_filename = os.path.basename(current_video_path)
                for video_path, annotations in self.all_annotations.items():
                    if os.path.basename(video_path) == current_filename:
                        video_annotations = annotations
                        break
            
            # Initialize or update annotations for current video
            if self.currentVideoFile not in self.annotations:
                self.annotations[self.currentVideoFile] = {}
            
            if video_annotations:
                self.annotations[self.currentVideoFile] = video_annotations.copy()
                print(f"Loaded {len(video_annotations)} existing annotations for {os.path.basename(self.currentVideoFile)}")
            else:
                print(f"No existing annotations found for {os.path.basename(self.currentVideoFile)}")
                
        except Exception as e:
            print(f"Error loading existing annotations: {e}")
            # Ensure annotations dict is initialized even if loading fails
            if self.currentVideoFile not in self.annotations:
                self.annotations[self.currentVideoFile] = {}
            
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

    def extractSmokeStats(self):

        smoke = 0
        no_smoke = 0        
        for video_file, video_annotations in self.all_annotations.items():
                for ann in video_annotations.values():
                    if isinstance(ann, dict) and 'has_smoke' in ann:
                        if ann['has_smoke']:
                            smoke += 1
                        else:
                            no_smoke += 1
        
        return smoke, no_smoke
        
    def updateSegmentInfo(self):
        """Update segment information display with smoke/no-smoke counts"""
        
        # Calculate segment info
        segment_frames = self.segmentEnd - self.segmentStart + 1
        segment_start_time = self._frame_to_time(self.segmentStart)
        segment_end_time = self._frame_to_time(self.segmentEnd)
        segment_text = (f"Frames {self.segmentStart}-{self.segmentEnd} "
                    f"({segment_frames} frames, {segment_start_time}-{segment_end_time})")
        
        smoke, no_smoke = self.extractSmokeStats()
        annotation_text =  (f"Annotations: {smoke} smoke, {no_smoke} no-smoke")
        
        # Debug output
        print(f"Segment info: {segment_text} | {annotation_text}")
              
        # Main segment info
        self.segmentInfoLabel.config(text=segment_text)
        
        # Right panel labels (if they exist)
        if hasattr(self, 'rightSegmentInfoLabel'):
            self.rightSegmentInfoLabel.config(text=segment_text)
        if hasattr(self, 'rightAnnotationInfoLabel'):
            self.rightAnnotationInfoLabel.config(text=annotation_text)
        
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
        
    def onTimelineDrag(self, event):
        """Handle timeline drag for segment positioning"""
        self.onTimelineClick(event)
        
    def onTimelineResize(self, event=None):
        """Handle timeline canvas resize"""
        # Redraw timeline when canvas is resized
        self.root.after(50, self.drawTimeline)
        
    def onCanvasResize(self, event=None):
        """Handle video canvas resize events for dynamic resolution updates"""
        # Skip resize handling during intensive playback to maintain performance
        if self.isPlaying:
            return
            
        # Add a small delay to avoid too frequent updates during resize
        if hasattr(self, '_resize_timer'):
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(100, self.refreshVideoDisplay)
        
    def refreshVideoDisplay(self):
        """Refresh the current video frame display after canvas resize"""
        if self.videoCap and hasattr(self, 'currentFrame'):
            # Force recalculation of canvas dimensions by clearing cached values
            self._clear_canvas_dimensions_cache()
            # Redisplay current frame with new dimensions
            self.displayFrame(self.currentFrame)
    
    def _clear_canvas_dimensions_cache(self):
        """Clear cached canvas dimensions and all processed images to force recalculation"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.targetWidth = None
        self.targetHeight = None
        # Clear ALL processed images since they're all invalid at the new resolution
        self.imageCache.clear()
        
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
                
                # For the segment end frame, clear cached image to ensure current display
                if frame_number == self.segmentEnd and frame_number in self.imageCache:
                    del self.imageCache[frame_number]
                
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
            # Use the standard processing method for consistency
            photo_image = self._create_processed_image(frame)
            self.imageCache[frame_num] = photo_image
            
        except Exception as e:
            print(f"Error pre-processing frame {frame_num}: {e}")
            
    def _ensure_canvas_dimensions_calculated(self, frame):
        """Calculate canvas dimensions and image sizing dynamically"""
        self.videoCanvas.update_idletasks()
        canvas_width = self.videoCanvas.winfo_width()
        canvas_height = self.videoCanvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = Constants.SCALED_CANVAS_WIDTH, Constants.SCALED_CANVAS_HEIGHT
        
        # Check if dimensions have changed significantly (more than 5 pixels)
        dimensions_changed = (
            self.canvasWidth is None or 
            self.canvasHeight is None or 
            abs(canvas_width - self.canvasWidth) > 5 or 
            abs(canvas_height - self.canvasHeight) > 5
        )
        
        if dimensions_changed:
            # Clear image cache when dimensions change to force re-processing
            if self.canvasWidth is not None:
                self.imageCache.clear()  # Force re-processing of all cached imag
            
            self.canvasWidth = canvas_width
            self.canvasHeight = canvas_height
            
            # Calculate image dimensions to fit canvas
            img_height, img_width = frame.shape[:2]
            scale_x = self.canvasWidth / img_width
            scale_y = self.canvasHeight / img_height
            scale_factor = min(scale_x, scale_y)
            
            self.targetWidth = int(img_width * scale_factor)
            self.targetHeight = int(img_height * scale_factor)
            
            # Pre-calculate position dynamically
            self.imageX = (self.canvasWidth - self.targetWidth) // 2
            self.imageY = (self.canvasHeight - self.targetHeight) // 2

    def displayVideoFrame(self, frame):
        """Display frame on canvas with maximum performance optimization"""
        try:
            # Always recalculate dimensions first in case of window resize
            self._ensure_canvas_dimensions_calculated(frame)
            
            # Use pre-processed image if available and dimensions haven't changed
            if self.currentFrame in self.imageCache:
                self.currentImage = self.imageCache[self.currentFrame]
            else:
                # Process and cache image with current dimensions
                self.currentImage = self._create_processed_image(frame)
                # Cache this processed image only if we have valid dimensions
                if self.canvasWidth and self.canvasHeight:
                    self.imageCache[self.currentFrame] = self.currentImage
            
            self._update_canvas_image()

        except Exception as e:
            print(f"Error displaying video frame: {e}")
            # On error, try clearing cache and retry once
            if hasattr(self, 'imageCache'):
                print("Clearing image cache due to display error and retrying...")
                self.imageCache.clear()
                try:
                    self.currentImage = self._create_processed_image(frame)
                    self._update_canvas_image()
                except Exception as e2:
                    print(f"Retry also failed: {e2}")
            
    def _create_processed_image(self, frame):
        """Create processed image for display with current canvas dimensions"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Ensure canvas dimensions are calculated
        self._ensure_canvas_dimensions_calculated(frame)
        
        # Create and resize image with current dimensions
        image = Image.fromarray(frame_rgb)
        image = image.resize((self.targetWidth, self.targetHeight), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)
            
    def _create_emergency_image(self, frame):
        """Create emergency image for cache misses - delegates to main processing method"""
        print(f"WARNING - Image cache miss for frame {self.currentFrame}!")
        return self._create_processed_image(frame)
        
    def _update_canvas_image(self):
        """Update canvas with current image using current positioning"""
        # Always use current positioning (imageX, imageY may have changed due to resize)
        if hasattr(self, '_image_id'):
            # Update both image and position
            self.videoCanvas.itemconfig(self._image_id, image=self.currentImage)
            self.videoCanvas.coords(self._image_id, self.imageX, self.imageY)
        else:
            # Create new image with current position
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
    
    def showProcessingOverlay(self, message="Processing annotation..."):
        """Show processing overlay on video canvas"""
        if not hasattr(self, 'processingOverlay'):
            # Create processing overlay frame
            self.processingOverlay = tk.Frame(self.videoCanvas, bg='black', relief=tk.RAISED, bd=2)
            
            # Processing label with larger font
            self.processingLabel = tk.Label(self.processingOverlay, 
                                          text=message,
                                          bg='black', fg='#4caf50', 
                                          font=('Arial', 18, 'bold'),
                                          padx=20, pady=15)
            self.processingLabel.pack()
            
            # Status label for updates
            self.processingStatusLabel = tk.Label(self.processingOverlay,
                                                text="Generating temporal analysis...",
                                                bg='black', fg='lightblue',
                                                font=('Arial', 14),
                                                padx=20, pady=5)
            self.processingStatusLabel.pack()
        
        # Update the main message
        self.processingLabel.config(text=message)
        self.processingStatusLabel.config(text="Generating temporal analysis...")
        
        # Position overlay in center of video canvas
        self.videoCanvas.update_idletasks()
        canvas_width = self.videoCanvas.winfo_width()
        canvas_height = self.videoCanvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            x = canvas_width // 2
            y = canvas_height // 2
            self.processingOverlay.place(in_=self.videoCanvas, x=x, y=y, anchor='center')
        else:
            # Fallback positioning
            self.processingOverlay.place(in_=self.videoCanvas, relx=0.5, rely=0.5, anchor='center')
    
    def updateProcessingStatus(self, status_text):
        """Update the status text in the processing overlay"""
        if hasattr(self, 'processingStatusLabel'):
            self.processingStatusLabel.config(text=status_text)
            self.root.update_idletasks()  # Force UI update
    
    def showProcessingResult(self, result_message, is_success=True):
        """Show the result message on the processing overlay"""
        if hasattr(self, 'processingLabel') and hasattr(self, 'processingStatusLabel'):
            # Update colors based on success/failure
            if is_success:
                self.processingLabel.config(text="Annotation Saved!", fg='#4caf50')
                self.processingStatusLabel.config(text=result_message, fg='lightgreen')
            else:
                self.processingLabel.config(text="Error", fg='#f44336')
                self.processingStatusLabel.config(text=result_message, fg='#ff9800')
            
            self.root.update_idletasks()
            
            # Hide the overlay after 2.5 seconds
            self.root.after(1500, self.hideProcessingOverlay)
    
    def hideProcessingOverlay(self):
        """Hide processing overlay"""
        if hasattr(self, 'processingOverlay'):
            self.processingOverlay.place_forget()
    
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
        
        # Clear cached image for starting frame to ensure it displays with current canvas size
        if self.currentFrame in self.imageCache:
            del self.imageCache[self.currentFrame]
        
        # Record start time for performance tracking
        self.playbackStartTime = time.time()
        
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
        
        # Clear cached image for the last frame to ensure it's displayed with current window size
        if self.segmentEnd in self.imageCache:
            del self.imageCache[self.segmentEnd]
        
        # Display last frame and update timeline
        self.displayFrame(self.segmentEnd)
        self.drawTimeline()
        
        # Reset buttons to play state
        self._reset_play_buttons()
        
        # Refresh display in case canvas was resized during playback
        self.root.after(50, self.refreshVideoDisplay)
            
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
        
        # Refresh display in case canvas was resized during playback
        self.root.after(50, self.refreshVideoDisplay)
            
    def replaySegment(self):
        """Replay the segment"""
        self.pausePlayback()
        self.pausedFrame = None  # Clear any paused position for full replay
        self.currentFrame = self.segmentStart
        
        # Clear cached image for start frame to ensure it displays with current canvas size
        if self.segmentStart in self.imageCache:
            del self.imageCache[self.segmentStart]
        
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
        
        # Show processing overlay
        self.showProcessingOverlay("Processing SMOKE annotation...")
        
        # Process annotation asynchronously to avoid blocking UI
        self.root.after(100, lambda: self._process_annotation(True))
        
    def markNoSmoke(self):
        """Mark segment as no smoke"""
        if not self.segmentWatched:
            messagebox.showwarning("Watch Required", "Please watch the segment completely before making an annotation.")
            return
        
        # Show processing overlay
        self.showProcessingOverlay("Processing NO SMOKE annotation...")
        
        # Process annotation asynchronously to avoid blocking UI
        self.root.after(100, lambda: self._process_annotation(False))
    
    def _process_annotation(self, has_smoke):
        """Process the annotation with status updates"""
        try:
            # Update status
            self.updateProcessingStatus("Saving annotation data...")
            self.root.after(200, lambda: self._continue_annotation_processing(has_smoke))
        except Exception as e:
            self.showProcessingResult(f"Error: {str(e)}", is_success=False)
    
    def _continue_annotation_processing(self, has_smoke):
        """Continue processing annotation"""
        try:
            # Save the annotation
            self.saveAnnotation(has_smoke)
            
            # Show success message
            smoke_status = "SMOKE DETECTED" if has_smoke else "NO SMOKE"
            result_msg = f"Frames {self.segmentStart}-{self.segmentEnd} marked as {smoke_status}"
            self.showProcessingResult(result_msg, is_success=True)
            
        except Exception as e:
            self.showProcessingResult(f"Failed to save annotation: {str(e)}", is_success=False)
        
    def saveAnnotation(self, has_smoke):
        """Save annotation for current segment in the annotations dictionary"""
        if not self.currentVideoFile:
            return
            
        try:        
            if self.currentVideoFile not in self.annotations:
                self.annotations[self.currentVideoFile] = {}
            
            # Create segment key
            segment_key = f"frames_{self.segmentStart:06d}_{self.segmentEnd:06d}"
            
            # Store annotation data
            self.annotations[self.currentVideoFile][segment_key] = {
                "start_frame": self.segmentStart,
                "end_frame": self.segmentEnd,
                "has_smoke": has_smoke,
            }
            
            # Save ONLY the current segment (not all segments)
            self.saveCurrentSegmentOnly(has_smoke, segment_key)
            
            # Automatically reload annotation history after saving (if history widget exists)
            if hasattr(self, 'historyText'):
                try:
                    self.loadAnnotationHistory()
                except Exception as history_error:
                    print(f"Note: Could not auto-reload history: {history_error}")
            
        except Exception as e:
            print(f"Error saving annotation: {e}")
            
    def saveCurrentSegmentOnly(self, has_smoke, segment_key):
        """Save only the current segment annotation and temporal analysis"""
        try:
            # Update status
            self.updateProcessingStatus("Creating output directories...")
            
            # Use the user's home directory instead of the program directory
            program_dir = os.path.expanduser("~")
            video_name = os.path.splitext(os.path.basename(self.currentVideoFile))[0] if self.currentVideoFile else "annotations"
            
            # Create a centralized output directory for all YOLO annotations in program folder
            central_yolo_dir = os.path.join(program_dir, "smoke_detection_annotations")
            images_dir = os.path.join(central_yolo_dir, "images")
            labels_dir = os.path.join(central_yolo_dir, "labels")
            
            for directory in [central_yolo_dir, images_dir, labels_dir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Create unique filename with video name prefix
            unique_segment_key = f"{video_name}_{segment_key}"
            
            # Update status
            self.updateProcessingStatus("Generating temporal analysis image...")
            
            # Generate and save temporal analysis image (192x192) for CURRENT segment only
            self.saveSegmentTemporalAnalysis(self.segmentStart, self.segmentEnd, unique_segment_key, images_dir)
            
            # Update status
            self.updateProcessingStatus("Creating YOLO label file...")
            
            # Create YOLO format label file for CURRENT segment only
            label_file = os.path.join(labels_dir, f"{unique_segment_key}.txt")
            
            with open(label_file, 'w') as f:
                if has_smoke:
                    f.write("0 0.5 0.5 1.0 1.0\n")
                else:
                    f.write("1 0.5 0.5 1.0 1.0\n")
            
            # Update status
            self.updateProcessingStatus("Updating summary files...")
            
            # Update summary file with only current segment
            self.updateSummaryFileWithCurrentSegment(central_yolo_dir, unique_segment_key, has_smoke)
            
            # Update class names file (only if it doesn't exist)
            classes_file = os.path.join(central_yolo_dir, "classes.txt")
            if not os.path.exists(classes_file):
                with open(classes_file, 'w') as f:
                    f.write("smoke\n")
                    f.write("no_smoke\n")
            
            # Final status update
            self.updateProcessingStatus("Finalizing annotation...")
            
        except Exception as e:
            print(f"Error saving current segment: {e}")
            raise  # Re-raise to be caught by the calling method
            
    def updateSummaryFileWithCurrentSegment(self, central_yolo_dir, unique_segment_key, has_smoke):
        """Update summary file with only the current segment"""
        try:
            summary_file = os.path.join(central_yolo_dir, "all_annotations_summary.json")
            
            # Load existing annotations if file exists
            all_annotations = {}
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r') as f:
                        all_annotations = json.load(f)
                except:
                    all_annotations = {}
            
            # Initialize current video in all_annotations if it doesn't exist
            if self.currentVideoFile not in all_annotations:
                all_annotations[self.currentVideoFile] = {}
            
            # Add/update only the current segment annotation (preserve existing ones)
            if self.currentVideoFile and self.currentVideoFile in self.annotations:
                current_video_annotations = self.annotations[self.currentVideoFile]
                # Find the segment key that matches our current segment
                for segment_key, annotation_data in current_video_annotations.items():
                    if (annotation_data.get('start_frame') == self.segmentStart and 
                        annotation_data.get('end_frame') == self.segmentEnd):
                        # Update only this specific segment, preserve all others
                        all_annotations[self.currentVideoFile][segment_key] = annotation_data
                        break
            
            # Save updated summary (preserves all existing annotations from all videos)
            with open(summary_file, 'w') as f:
                json.dump(all_annotations, f, indent=2)
                
        except Exception as e:
            print(f"Error updating summary file: {e}")
            
    def saveAnnotationsToFile(self):
        """Save all annotations to YOLO format text files in a centralized folder"""
        try:
            # Use the program directory instead of video directory
            program_dir = os.path.expanduser("~")
            video_name = os.path.splitext(os.path.basename(self.currentVideoFile))[0] if self.currentVideoFile else "annotations"
            
            # Create a centralized output directory for all YOLO annotations in program folder
            central_yolo_dir = os.path.join(program_dir, "smoke_detection_annotations")
            images_dir = os.path.join(central_yolo_dir, "images")
            labels_dir = os.path.join(central_yolo_dir, "labels")
            
            for directory in [central_yolo_dir, images_dir, labels_dir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Save each segment as YOLO annotation and corresponding temporal analysis image
            if self.currentVideoFile in self.annotations:
                for segment_key, annotation in self.annotations[self.currentVideoFile].items():
                    start_frame = annotation["start_frame"]
                    end_frame = annotation["end_frame"]
                    has_smoke = annotation["has_smoke"]
                    
                    # Create unique filenames with video name prefix
                    unique_segment_key = f"{video_name}_{segment_key}"
                    
                    # Generate and save temporal analysis image (192x192) instead of single frame
                    self.saveSegmentTemporalAnalysis(start_frame, end_frame, unique_segment_key, images_dir)
                    
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
                f.write("Smoke Detection YOLO Dataset - Temporal Analysis\n")
                f.write("="*50 + "\n\n")
                f.write("Directory Structure:\n")
                f.write("- images/: Contains 192x192 temporal analysis images from 64-frame segments\n")
                f.write("- labels/: Contains YOLO format annotation files\n")
                f.write("- classes.txt: Class names (smoke, no_smoke)\n\n")
                f.write("Image Format:\n")
                f.write("- Size: 192x192 pixels\n")
                f.write("- Type: Temporal saturation analysis (grayscale)\n")
                f.write("- Source: 64 consecutive video frames per image\n")
                f.write("- Grid: 3x3 regions with 40% coverage and 20% overlap\n")
                f.write("- Each cell: 64x64 pixels representing temporal saturation histogram\n\n")
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
            print(f"Dataset contains annotations from {len(all_annotations)} video(s)")
            
        except Exception as e:
            print(f"Error saving YOLO annotations: {e}")
            
    def saveSegmentTemporalAnalysis(self, start_frame, end_frame, unique_segment_key, images_dir):
        """Generate and save temporal analysis image from 64-frame segment"""
        try:            
            # Load all 64 frames from the segment
            frames = []
            for frame_num in range(start_frame, end_frame + 1):
                if frame_num in self.frameCache:
                    # Use cached frame if available
                    frame = self.frameCache[frame_num]
                else:
                    # Load frame from video
                    self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = self.videoCap.read()
                    if not ret:
                        print(f"Warning: Could not read frame {frame_num}, using previous frame")
                        if frames:  # Use last successful frame if available
                            frame = frames[-1].copy()
                        else:
                            print(f"Error: No frames available for temporal analysis")
                            return
                
                frames.append(frame)
            
            # Generate temporal analysis image (192x192)
            temporal_image = self.temporal_generator.generate_from_frames(frames)
            
            # Save temporal analysis image
            image_path = os.path.join(images_dir, f"{unique_segment_key}.png")
            success = cv2.imwrite(image_path, temporal_image)
            
            if success:
                print(f"Saved temporal analysis image: {image_path}")
            else:
                print(f"Error: Failed to save temporal analysis image to {image_path}")
                
        except Exception as e:
            print(f"Error generating temporal analysis for segment {start_frame}-{end_frame}: {e}")
            # Fallback: save the last frame as before
            self.saveSegmentFrame(end_frame, unique_segment_key, images_dir)
            
    def saveSegmentFrame(self, frame_number, unique_segment_key, images_dir):
        """Fallback method: Save a specific frame as an image file with unique naming"""
        try:
            # Read the frame
            self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.videoCap.read()
            
            if ret:
                # Save as PNG image with unique name (fallback)
                image_path = os.path.join(images_dir, f"{unique_segment_key}_fallback.png")
                cv2.imwrite(image_path, frame)
                
        except Exception as e:
            print(f"Error saving fallback frame {frame_number}: {e}")
            
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
    
    def loadAnnotationHistory(self):
        """Load and display annotation history for the current video."""
        if not self.currentVideoFile:
            messagebox.showwarning("No Video", "Please load a video first.")
            return
        
        try:
            # Load annotations from summary file
            program_dir = os.path.expanduser("~")
            summary_file = os.path.join(program_dir, "smoke_detection_annotations", "all_annotations_summary.json")
            
            if not os.path.exists(summary_file):
                self.displayHistoryMessage("No annotation history found.")
                return
            
            with open(summary_file, 'r') as f:
                self.all_annotations = json.load(f)
            
            # Get annotations for current video
            current_video_path = self.currentVideoFile
            video_annotations = None
            
            # Try to find annotations by exact path or just filename
            if current_video_path in self.all_annotations:
                video_annotations = self.all_annotations[current_video_path]
            else:
                # Try matching by filename only
                current_filename = os.path.basename(current_video_path)
                for video_path, annotations in self.all_annotations.items():
                    if os.path.basename(video_path) == current_filename:
                        video_annotations = annotations
                        break
            
            if not video_annotations:
                self.displayHistoryMessage(f"No annotations found for video: {os.path.basename(current_video_path)}")
                return
            
            # Format and display the annotations
            self.displayAnnotationHistory(video_annotations)
            self.updateSegmentInfo()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load annotation history: {str(e)}")
            self.displayHistoryMessage("Error loading annotation history.")
    
    def displayAnnotationHistory(self, annotations):
        """Display annotation history in the text widget with enhanced formatting and information."""
        self.historyText.config(state=tk.NORMAL)
        self.historyText.delete(1.0, tk.END)
        
        # Sort annotations by start frame
        sorted_annotations = []
        for segment_key, annotation_data in annotations.items():
            sorted_annotations.append((annotation_data.get('start_frame', 0), segment_key, annotation_data))
        
        sorted_annotations.sort(key=lambda x: x[0])
        
        # Display enhanced header with statistics
        video_name = os.path.basename(self.currentVideoFile) if self.currentVideoFile else "Unknown"
        header = f"Annotation History: {video_name}\n"
        header += "=" * 60 + "\n\n"
        
        # Add instructions
        header += "Instructions:\n"
        header += "  • Click any frame range below to jump to that segment\n\n"
        self.historyText.insert(tk.END, header)
        
        if not sorted_annotations:
            # Enhanced empty state message
            empty_msg = "No annotations found for this video yet.\n\n"
            self.historyText.insert(tk.END, empty_msg)
        else:
            # Display each annotation with simplified formatting
            for i, (start_frame, segment_key, annotation_data) in enumerate(sorted_annotations, 1):
                start_frame = annotation_data.get('start_frame', 0)
                end_frame = annotation_data.get('end_frame', start_frame + 63)
                has_smoke = annotation_data.get('has_smoke', False)
                
                # Create clean entry with color coding
                smoke_status = "SMOKE" if has_smoke else "NO SMOKE"
                
                # Calculate time range for user convenience
                start_time = self._frame_to_time(start_frame) if hasattr(self, '_frame_to_time') else f"{start_frame//1500}:{(start_frame%1500)//25:02d}"
                end_time = self._frame_to_time(end_frame) if hasattr(self, '_frame_to_time') else f"{end_frame//1500}:{(end_frame%1500)//25:02d}"
                
                entry = f"{i:2d}. Frames {start_frame:06d}-{end_frame:06d} ({start_time}-{end_time}) | {smoke_status}\n\n"
                
                # Insert with tag for clicking
                tag_name = f"frame_{start_frame}"
                self.historyText.insert(tk.END, entry, tag_name)
                
                # Bind click event
                self.historyText.tag_bind(tag_name, "<Button-1>", 
                                         lambda e, frame=start_frame: self.jumpToHistoryFrame(frame))
                
                # Enhanced styling based on annotation type with neutral but visible colors
                if has_smoke:
                    self.historyText.tag_config(tag_name, foreground="#d4af37", underline=True)  # Gold/amber for smoke
                else:
                    self.historyText.tag_config(tag_name, foreground="#87ceeb", underline=True)  # Sky blue for no smoke
    
        
        self.historyText.config(state=tk.DISABLED)
    
    def displayHistoryMessage(self, message):
        """Display a simple message in the history text widget."""
        self.historyText.config(state=tk.NORMAL)
        self.historyText.delete(1.0, tk.END)
        self.historyText.insert(tk.END, message)
        self.historyText.config(state=tk.DISABLED)
    
    def jumpToHistoryFrame(self, target_frame):
        """Jump to a frame from the annotation history."""
        if not self.videoCap:
            return
        
        try:
            # Validate frame number
            if target_frame < 0 or target_frame >= self.totalFrames:
                print(f"Invalid frame number: {target_frame}")
                return
            
            # Calculate new segment position to include the target frame
            new_segment_start = max(0, target_frame)
            new_segment_start = min(new_segment_start, self.totalFrames - Constants.SEGMENT_LENGTH)
            
            # Update segment position
            self._update_segment_position(new_segment_start)
            
            # Jump to the specific frame
            self.displayFrame(target_frame)
            self.currentFrame = target_frame
            
            # Update timeline to show current position
            self.drawTimeline()
            
        except Exception as e:
            print(f"Error jumping to history frame {target_frame}: {e}")
    
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
