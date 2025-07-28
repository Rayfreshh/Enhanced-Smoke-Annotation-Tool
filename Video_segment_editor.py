#!/usr/bin/env python3
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

    SMALL_MOVE = 1
    MEDIUM_MOVE = 10
    LARGE_MOVE = 64
    HUGE_MOVE = 640

    # Timing settings
    MIN_FRAME_DELAY_MS = 10  # Minimum delay to prevent system overload
    PRELOAD_DELAY_MS = 5
    MAX_SKIPPED_FRAMES = 3  # Maximum frames to skip for real-time performance
    
    # Scaled UI settings for better layout
    SCALED_canvasWidth = 480
    SCALED_canvasHeight = 320
    SCALED_TIMELINE_HEIGHT = 60
    
    # Scaled annotation button settings
    SCALED_BUTTON_HEIGHT = 4  # Reduced from 6 to save space
    SCALED_BUTTON_FONT_SIZE = 16  # Reduced from 18
    SCALED_BUTTON_PADDING = 8  # Reduced from 12
    
    # Animation settings
    LOADING_ANIMATION_DELAY_MS = 500
    GC_INTERVAL_FRAMES = 32
    
class Config:
    """Configuration settings for the application"""
    # File and directory settings
    classesFile = "classes.txt"
    summaryFile = "Annotations_summary.json"
    
    # Video file types
    VIDEO_FILETYPES = [
        ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
        ("MP4 files", "*.mp4"),
        ("All files", "*.*")
    ]

class VideoSegmentEditor:
    def __init__(self, root):
        self.root = root
        self.initWindow()
        self.initVideoProperties()
        self.initSegmentProperties()
        self.initAnnotationProperties()
        self.initPerformanceVariables()
        self.setupGui()
        self.bindEvents()
        
    def initWindow(self):
        """Initialize window properties"""
        self.root.title("Smoke detection - Annotation tool")
        # Set root window background to match dark theme
        self.root.configure(bg='#2b2b2b')
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)

        # Get screen dimensions for initial window sizing
        screenWidth = self.root.winfo_screenwidth()
        screenHeight = self.root.winfo_screenheight()

        # Set initial window size based on screen size
        if screenWidth <= 1920 and screenHeight <= 1080:
            self.windowWidth = min(1300, screenWidth - 80)
            self.windowHeight = min(850, screenHeight - 80)
        elif screenWidth <= 2560 and screenHeight <= 1440:
            self.windowWidth = min(1600, screenWidth - 100)
            self.windowHeight = min(1000, screenHeight - 100)
        else:
            self.windowWidth = min(1800, screenWidth - 100)
            self.windowHeight = min(1200, screenHeight - 100)
        
        # Set window geometry
        x = (screenWidth - self.windowWidth) // 2
        y = (screenHeight - self.windowHeight) // 2
        self.root.geometry(f"{self.windowWidth}x{self.windowHeight}+{x}+{y}")
        
        # Try to maximize on Windows, otherwise use normal state
        try:
            if self.root.tk.call('tk', 'windowingsystem') == 'win32':
                self.root.state('zoomed')
            else:
                self.root.state('normal')
        except:
            self.root.state('normal')
        
        # Bind window resize event for video display updates
        self.root.bind('<Configure>', self.onWindowResize)
        
        # Set initial panel dimensions based on window size (will be updated dynamically)
        self.rightPanelWidth = self.calculateDynamicPanelWidth()
        # ...
        
        # Calculate dynamic font sizes for right panel based on window size
        self.calculateDynamicFontSizes()
        
        self.historyTextHeight = 30  # Increased for better visibility
        
    def initVideoProperties(self):
        """Initialize video-related properties"""
        self.lastDir = os.path.expanduser("~")  # default to home
        self.videoCap = None
        self.videoName = None
        self.totalFrames = 0
        self.currentFrame = 0
        self.fps = 25
        
    def initSegmentProperties(self):
        """Initialize segment-related properties"""
        self.segmentStart = 0
        self.segmentEnd = Constants.SEGMENT_LENGTH - 1
        self.segmentLength = Constants.SEGMENT_LENGTH
        self.isPlaying = False
        self.playbackTimer = None
        self.pausedFrame = None
        self.playbackStartTime = None
        self.lastClickedTag = None
        self.lastClickedWasSmoke = None
        
    def initAnnotationProperties(self):
        """Initialize annotation-related properties"""
        self.annotations = {}
        self.currentSegmentAnnotated = False
        self.segmentWatched = False
        self.lastFrame = None
        self.allAnnotations = {}
        
    def initPerformanceVariables(self):
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
        self.temporalGenerator = TemporalAnalysisGenerator()
    
        
    def setupGui(self):
        """Setup the main GUI layout"""
        # Main container
        padding = 10
        mainFrame = tk.Frame(self.root, bg='#2b2b2b')
        mainFrame.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
        
        # Title
        titleLabel = tk.Label(mainFrame, text="Smoke detection - Annotation tool", 
                              font=('Arial', 20, 'bold'), 
                              bg='#2b2b2b', 
                              fg='white')
        titleLabel.pack(pady=(0, 15))
        
        # Main content area - horizontal split
        contentFrame = tk.Frame(mainFrame, bg='#2b2b2b')
        contentFrame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Video and timeline
        leftFrame = tk.Frame(contentFrame, bg='#2b2b2b')
        leftFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, padding))
        
        # Top section - Video display
        self.setupVideoDisplay(leftFrame)
        
        # Middle section - Timeline and controls
        self.setupTimelineControls(leftFrame)
        
        # Right side - Control panels
        self.rightFrame = tk.Frame(contentFrame, bg='#2b2b2b', width=self.rightPanelWidth)
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
        infoHeight = 40
        infoBar = tk.Frame(videoFrame, bg='#3b3b3b', height=infoHeight)
        infoBar.pack(fill=tk.X, padx=padding, pady=5)
        infoBar.pack_propagate(False)
        
        # File load button
        self.loadBtn = tk.Button(infoBar, text="Load Video File", command=self.loadVideoFile,
                                bg='#4caf50', fg='white', 
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
        canvasWidth = Constants.SCALED_canvasWidth
        canvasHeight = Constants.SCALED_canvasHeight
        self.videoCanvas = tk.Canvas(videoFrame, bg='black', 
                                   width=canvasWidth, height=canvasHeight)
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
        self.move64Back = tk.Button(centerFrame, text="<< 64", command=self.moveSegment64Back,
                bg='#607d8b', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move64Back.pack(side=tk.LEFT, padx=6)
        self.move10Back = tk.Button(centerFrame, text="< 10", command=self.moveSegment10Back,
                bg='#455a64', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move10Back.pack(side=tk.LEFT, padx=6)
        self.move1Back = tk.Button(centerFrame, text="< 1", command=self.moveSegment1Back,
                bg='#607d8b', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move1Back.pack(side=tk.LEFT, padx=6)

        # Play/Pause button for preview - reduced height
        self.previewPlayPauseBtn = tk.Button(centerFrame, text="PLAY", 
                                            command=self.togglePreviewPlayback,
                                            bg='#4caf50', fg='white', 
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
        self.move1Forward = tk.Button(centerFrame, text="1 >", command=self.moveSegment1Forward,
                bg='#607d8b', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move1Forward.pack(side=tk.LEFT, padx=6)  
        self.move10Forward = tk.Button(centerFrame, text="10 >", command=self.moveSegment10Forward,
                bg='#455a64', fg='white', font=('Arial', 11, 'bold'),
                width=8, height=2, state='disabled')
        self.move10Forward.pack(side=tk.LEFT, padx=6)             
        self.move64Forward = tk.Button(centerFrame, text="64 >>", command=self.moveSegment64Forward,
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
        
        # Draw initial timeline with 0:00 times
        self.root.after(100, self.drawTimeline)
        
    def setupControlPanels(self, parent):
        """Setup control panels for different workflow states"""
        controlFrame = tk.Frame(parent, bg='#2b2b2b')
        controlFrame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Segment Selection Controls Panel (always visible on right)
        self.selectionControlPanel = tk.LabelFrame(controlFrame, text="Segment Selection", 
                                                  font=('Arial', self.panelFonts.get('panelTitle', 12), 'bold'), 
                                                  bg='#3b3b3b', fg='white')
        
        selectionControlInner = tk.Frame(self.selectionControlPanel, bg='#3b3b3b')
        selectionControlInner.pack(padx=8, pady=8)
        
        # Detailed segment info display
        segmentInfoFrame = tk.Frame(selectionControlInner, bg='#3b3b3b')
        segmentInfoFrame.pack(fill=tk.X, pady=10)
        
        self.selectionInfoLabel = tk.Label(segmentInfoFrame, text="Current Selection:", 
                bg='#3b3b3b', fg='white', 
                font=('Arial', self.panelFonts.get('panelTitle', 12), 'bold'))
        self.selectionInfoLabel.pack(pady=(5, 2))
        
        self.segmentInfoLabel = tk.Label(segmentInfoFrame, text="Frames 0-63 (64 frames)", 
                                             bg='#3b3b3b', fg='lightgreen', 
                                             font=('Arial', self.panelFonts.get('info', 10), 'bold'))
        self.segmentInfoLabel.pack()

        self.annotationInfoLabel = tk.Label(segmentInfoFrame, text="Total annotated segments:", 
                bg='#3b3b3b', fg='white', 
                font=('Arial', self.panelFonts.get('panelTitle', 12), 'bold'))
        self.annotationInfoLabel.pack(pady=(5, 2))

        self.smokeInfoLabel = tk.Label(segmentInfoFrame, text="No annotations yet", 
                                             bg='#3b3b3b', fg='lightgreen',
                                             font=('Arial', self.panelFonts.get('info', 10), 'bold'))
        self.smokeInfoLabel.pack()
        
        # Always show selection control panel
        self.selectionControlPanel.pack(fill=tk.X, pady=10)

        # Review & Annotation Panel (moved to top)
        self.reviewAnnotationPanel = tk.LabelFrame(controlFrame, text="Smoke Annotation", 
                                                  font=('Arial', self.panelFonts.get('panelTitle', 12), 'bold'), 
                                                  bg='#3b3b3b', fg='white')
        
        reviewAnnotationInner = tk.Frame(self.reviewAnnotationPanel, bg='#3b3b3b')
        reviewAnnotationInner.pack(padx=8, pady=8)
    
        
        self.instructionSubLabel = tk.Label(reviewAnnotationInner, text="Is there smoke visible\n in this 64-frame segment?", 
                bg='#3b3b3b', fg='#00FFFF', 
                font=('Arial', self.panelFonts.get('questionSub', 14), 'bold'), state='disabled')
        self.instructionSubLabel.pack(pady=8)
        
        # Watch requirement notice
        self.watchNoticeLabel = tk.Label(reviewAnnotationInner, text="Please watch the segment first to enable annotation", 
                                        bg='#3b3b3b', fg='orange', 
                                        font=('Arial', self.panelFonts.get('notice', 10), 'italic'))
        self.watchNoticeLabel.pack(pady=6)
        
        annotationButtonsFrame = tk.Frame(reviewAnnotationInner, bg='#3b3b3b')
        annotationButtonsFrame.pack(pady=20)
        
        # Annotation buttons with scaled dimensions for more history space
        self.smokeBtn = tk.Button(annotationButtonsFrame, text="SMOKE", 
                                 command=self.markSmoke,
                                 bg='#757575', fg='white', 
                                 font=('Arial', self.panelFonts.get('button', Constants.SCALED_BUTTON_FONT_SIZE), 'bold'),
                                 width=35, height=Constants.SCALED_BUTTON_HEIGHT, state='disabled')
        self.smokeBtn.pack(pady=Constants.SCALED_BUTTON_PADDING)
        
        self.noSmokeBtn = tk.Button(annotationButtonsFrame, text="NO SMOKE", 
                                   command=self.markNoSmoke,
                                   bg='#757575', fg='white', 
                                   font=('Arial', self.panelFonts.get('button', Constants.SCALED_BUTTON_FONT_SIZE), 'bold'),
                                   width=35, height=Constants.SCALED_BUTTON_HEIGHT, state='disabled')
        self.noSmokeBtn.pack(pady=Constants.SCALED_BUTTON_PADDING)
        
        # Show annotation panel first (at top)
        self.reviewAnnotationPanel.pack(fill=tk.X, pady=10)
        
        # Annotation History Panel (moved to bottom, expanded to use freed space)
        self.historyPanel = tk.LabelFrame(controlFrame, text="Annotation History", 
                                         font=('Arial', self.panelFonts.get('panelTitle', 12), 'bold'), 
                                         bg='#3b3b3b', fg='white')
        
        historyInner = tk.Frame(self.historyPanel, bg='#3b3b3b')
        historyInner.pack(padx=20, pady=15, fill=tk.BOTH, expand=True)
        
        # History display (expanded)
        historyDisplayFrame = tk.Frame(historyInner, bg='#3b3b3b')
        historyDisplayFrame.pack(pady=5, fill=tk.BOTH, expand=True)
        
        # Create scrollable text widget for history
        self.historyText = tk.Text(historyDisplayFrame, height=self.historyTextHeight, width=50, 
                                  bg='#1e1e1e', fg='white', 
                                  font=('Arial', self.panelFonts.get('history', 12)),
                                  wrap=tk.WORD, state=tk.DISABLED)
        
        historyScrollbar = tk.Scrollbar(historyDisplayFrame, orient=tk.VERTICAL, 
                                       command=self.historyText.yview)
        self.historyText.configure(yscrollcommand=historyScrollbar.set)
        
        self.historyText.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        historyScrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        

        # Show history panel last (at bottom, takes remaining space)
        self.historyPanel.pack(fill=tk.BOTH, expand=True, pady=10)

        # Now that self.historyText exists, load annotation history
        self.loadAnnotationHistory()

    def bindEvents(self):
        """Bind keyboard events"""
        self.root.bind('<Key>', self.onKeyPress)
        self.root.focus_set()
    
    def calculateDynamicPanelWidth(self):
        """Calculate right panel width based on current window size"""
        # Get actual window dimensions
        self.root.update_idletasks()  # Ensure geometry is updated
        currentWidth = self.root.winfo_width()
        
        # Handle case where window dimensions aren't ready yet
        if currentWidth <= 1:
            # Use initial window size if current dimensions aren't available
            if hasattr(self, 'windowWidth'):
                currentWidth = self.windowWidth
            else:
                currentWidth = 1300  # Fallback
        
        # Calculate panel width as a percentage of window width with size-based tiers
        # Smaller windows get proportionally smaller panels for better balance
        if currentWidth <= 1300:
            # Small window: use ~35% for right panel (reduced from 45%)
            return max(550, int(currentWidth * 0.35))
        elif currentWidth <= 1600:
            # Medium window: use ~32% for right panel (reduced from 40%)
            return max(600, int(currentWidth * 0.32))
        else:
            # Large window: use ~28% for right panel (reduced from 35%)
            return max(650, min(800, int(currentWidth * 0.28)))
    
    def calculateDynamicFontSizes(self):
        """Calculate dynamic font sizes for right panel based on current window size"""
        # Get actual window dimensions
        self.root.update_idletasks()
        currentHeight = self.root.winfo_height()
        
        # Handle case where window dimensions aren't ready yet
        if currentHeight <= 1:
            if hasattr(self, 'windowHeight'):
                currentHeight = self.windowHeight
            else:
                currentHeight = 1300  # Fallback
        
        # Base font sizes (optimized for 4K displays)
        base4kFonts = {
            'panelTitle': 15,      # LabelFrame titles
            'instructionMain': 18, # Main instruction text
            'instructionSub': 15,  # Sub instruction text
            'questionSub': 20,     # Question subtext
            'notice': 14,           # Notice text
            'info': 15,             # Info labels
            'button': 20,           # Annotation buttons
            'history': 15           # History text
        }
        
        # Calculate scaling factor based on window width (downscaling from 4K baseline)
        if currentHeight <= 1300:
            # Small window (1080p): scale down to 80% of 4K baseline
            scaleFactor = 0.8
        elif currentHeight <= 1600:
            # Medium window (1440p): scale down to 90% of 4K baseline
            scaleFactor = 0.9
        else:
            # Large window (4K+): use full 4K baseline
            scaleFactor = 1.0
        
        # Apply scaling to create dynamic font sizes
        self.panelFonts = {}
        for fontType, baseSize in base4kFonts.items():
            scaledSize = int(baseSize * scaleFactor)
            self.panelFonts[fontType] = scaledSize
    
    
    def updatePanelWidth(self):
        """Update right panel width and font sizes dynamically based on current window size"""
        newWidth = self.calculateDynamicPanelWidth()
        
        # Recalculate font sizes for the new window size
        oldFonts = getattr(self, 'panelFonts', {})
        self.calculateDynamicFontSizes()
        
        # Check if panel width or fonts changed
        widthChanged = hasattr(self, 'rightPanelWidth') and newWidth != self.rightPanelWidth
        fontsChanged = oldFonts != self.panelFonts
        
        if widthChanged:
            self.rightPanelWidth = newWidth
            # Update the actual rightFrame width if it exists
            if hasattr(self, 'rightFrame'):
                self.rightFrame.config(width=self.rightPanelWidth)
                self.rightFrame.update_idletasks()
        
        # Update font sizes if they changed
        if fontsChanged and hasattr(self, 'panelFonts'):
            self.updatePanelFonts()
    
    def updatePanelFonts(self):
        """Update font sizes for right panel elements"""
        # Update LabelFrame titles
        if hasattr(self, 'selectionControlPanel'):
            self.selectionControlPanel.config(font=('Arial', self.panelFonts['panelTitle'], 'bold'))
        if hasattr(self, 'reviewAnnotationPanel'):
            self.reviewAnnotationPanel.config(font=('Arial', self.panelFonts['panelTitle'], 'bold'))
        if hasattr(self, 'historyPanel'):
            self.historyPanel.config(font=('Arial', self.panelFonts['panelTitle'], 'bold'))

        # Update instruction labels (we'll store references to these)
        if hasattr(self, 'instructionMainLabel'):
            self.instructionMainLabel.config(font=('Arial', self.panelFonts['instructionMain'], 'bold'))
        if hasattr(self, 'instructionSubLabel'):
            self.instructionSubLabel.config(font=('Arial', self.panelFonts['questionSub'], 'bold'))
        if hasattr(self, 'watchNoticeLabel'):
            self.watchNoticeLabel.config(font=('Arial', self.panelFonts['notice'], 'italic'))
        
        # Update info labels
        if hasattr(self, 'selectionInfoLabel'):
            self.selectionInfoLabel.config(font=('Arial', self.panelFonts['panelTitle'], 'bold'))
        if hasattr(self, 'annotationInfoLabel'):    
            self.annotationInfoLabel.config(font=('Arial', self.panelFonts['panelTitle'], 'bold'))
        if hasattr(self, 'segmentInfoLabel'):
            self.segmentInfoLabel.config(font=('Arial', self.panelFonts['info'], 'bold'))
        if hasattr(self, 'smokeInfoLabel'):
            self.smokeInfoLabel.config(font=('Arial', self.panelFonts['info'], 'bold'))

        # Update annotation buttons
        if hasattr(self, 'smokeBtn'):
            self.smokeBtn.config(font=('Arial', self.panelFonts['button'], 'bold'))
        if hasattr(self, 'noSmokeBtn'):
            self.noSmokeBtn.config(font=('Arial', self.panelFonts['button'], 'bold'))

        # Update history text
        if hasattr(self, 'historyText'):
            self.historyText.config(font=('Arial', self.panelFonts['history']))
    
    def onWindowResize(self, event):
        """Handle window resize events"""
        # Only handle resize events for the main window, not child widgets
        if event.widget == self.root:
            # Add a delay to avoid too frequent updates
            if hasattr(self, 'windowResizeTimer'):
                self.root.after_cancel(self.windowResizeTimer)
            self.windowResizeTimer = self.root.after(200, self.handleWindowResize)
    
    def handleWindowResize(self):
        """Handle window resize - refresh video display, update panel width and font scaling"""
        # Update panel width and font scaling based on new window size
        self.updatePanelWidth()
        
        # Refresh video display if video is loaded
        if hasattr(self, 'videoCap') and self.videoCap and hasattr(self, 'currentFrame'):
            # Clear canvas cache to force recalculation with new dimensions
            self.clearCanvasDimensionsCache()
            self.root.after(100, lambda: self.refreshVideoDisplay())

        
    def getIdealFrameDelayMs(self):
        """Calculate ideal frame delay in milliseconds based on video FPS"""
        if not self.videoCap or self.fps <= 0:
            return 40  # Default fallback for 25 FPS
            
        # Calculate ideal delay
        idealDelay = 1000 / self.fps
        
        # Handle edge cases for very high or very low FPS
        if idealDelay < Constants.MIN_FRAME_DELAY_MS:
            # For very high FPS videos (>100 FPS), use minimum delay
            print(f"Warning: Video FPS ({self.fps:.1f}) is very high. Using minimum delay.")
            return Constants.MIN_FRAME_DELAY_MS
        elif idealDelay > 200:
            # For very low FPS videos (<5 FPS), cap the delay
            print(f"Warning: Video FPS ({self.fps:.1f}) is very low. Capping delay at 200ms.")
            return 200
            
        return int(idealDelay)
        
    def frameToTime(self, frame):
        """Convert frame number to time format (minutes:seconds)"""
        if not self.videoCap:
            return "0:00"
        seconds = frame / self.fps if self.fps > 0 else 1
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
            
    def loadVideoFile(self):
        """Load a video file"""

        filename = filedialog.askopenfilename(
            title="Select a video file",
            initialdir=self.lastDir,
            filetypes=Config.VIDEO_FILETYPES,
        )
        
        if filename:
            # Update last directory for next file dialog
            self.lastDir = os.path.dirname(filename)
            try:
                self.loadVideo(filename)
            except Exception as e:
                print(f"Failed to load video: {e}")
            
    def loadVideo(self, filename):
        """Load video and initialize timeline"""
        try:
            self.cleanupPreviousVideo()
            
            self.videoCap = cv2.VideoCapture(filename)
            self.videoName = os.path.basename(filename)
            
            if not self.videoCap.isOpened():
                messagebox.showerror("Error", "Could not open video file")
                return
                
            self.initializeVideoProperties()
            self.resetSegmentState()
            self.resetPerformanceCache()
            self.updateVideoInfoDisplay()
            self.enableVideoControls()
            
            # Load existing annotations for this video
            self.loadExistingAnnotations()
            
            # Automatically load and display annotation history when video is loaded
            if hasattr(self, 'historyText'):
                try:
                    self.loadAnnotationHistory()
                    self.loadVideoAnnotations()
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

    def loadExistingAnnotations(self):
        """Load existing annotations for the current video from the summary file"""
        try:
            programDir = os.path.expanduser("~")
            summaryFile = os.path.join(programDir, "smoke_detection_annotations", Config.summaryFile)
            
            if not os.path.exists(summaryFile):
                # No existing annotations file, initialize empty
                if self.videoName not in self.annotations:
                    self.annotations[self.videoName] = {}
                return
            
            with open(summaryFile, 'r') as f:
                self.allAnnotations = json.load(f)
            
            videoAnnotations = None
            
            # Try exact path match first
            if self.videoName in self.allAnnotations:
                videoAnnotations = self.allAnnotations[self.videoName]
            else:
                # Try matching by filename only
                for video_path, annotations in self.allAnnotations.items():
                    if os.path.basename(video_path) == self.videoName:
                        videoAnnotations = annotations
                        break
            
            # Initialize or update annotations for current video
            if self.videoName not in self.annotations:
                self.annotations[self.videoName] = {}

            if videoAnnotations:
                self.annotations[self.videoName] = videoAnnotations.copy()
            else:
                print(f"No existing annotations found for {os.path.basename(self.videoName)}")

        except Exception as e:
            print(f"Error loading existing annotations: {e}")
            # Ensure annotations dict is initialized even if loading fails
            if self.videoName not in self.annotations:
                self.annotations[self.videoName] = {}

    def loadVideoAnnotations(self):
                # Get annotations for current video
        if not self.videoName:
            messagebox.showwarning("No Video", "Please load a video first.")
            return
        
        videoAnnotations = None
        
        # Try to find annotations by exact path or just filename
        if self.videoName in self.allAnnotations:
            videoAnnotations = self.allAnnotations[self.videoName]
        else:
            # Try matching by filename only
            current_filename = os.path.basename(self.videoName)
            for video_path, annotations in self.allAnnotations.items():
                if os.path.basename(video_path) == current_filename:
                    videoAnnotations = annotations
                    break
        
        if not videoAnnotations:
            self.displayHistoryMessage(f"No annotations found for video: {self.videoName}")
            return
        
        # Format and display the annotations
        self.displayAnnotationHistory(videoAnnotations)
        self.updateSegmentInfo()

    def loadAnnotationHistory(self):
        """Load and display annotation history for the current video."""
        try:
            # Load annotations from summary file
            programDir = os.path.expanduser("~")
            summaryFile = os.path.join(programDir, "smoke_detection_annotations", Config.summaryFile)
            
            if not os.path.exists(summaryFile):
                self.displayHistoryMessage("No annotation history found.")
                return
            
            with open(summaryFile, 'r') as f:
                self.allAnnotations = json.load(f)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load annotation history: {str(e)}")
            self.displayHistoryMessage("Error loading annotation history.")
            
    def cleanupPreviousVideo(self):
        """Clean up previous video resources"""
        if self.videoCap:
            self.videoCap.release()
            
    def initializeVideoProperties(self):
        """Initialize video properties from loaded video"""
        self.totalFrames = int(self.videoCap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.videoCap.get(cv2.CAP_PROP_FPS) or 25
        
    def resetSegmentState(self):
        """Reset segment-related state"""
        self.segmentStart = 0
        self.segmentEnd = min(Constants.SEGMENT_LENGTH - 1, self.totalFrames - 1)
        self.currentFrame = 0
        self.segmentWatched = False
        self.pausedFrame = None
        
    def resetPerformanceCache(self):
        """Reset performance optimization variables"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.targetWidth = None
        self.targetHeight = None
        self.frameCache = {}
        self.imageCache = {}
        
    def updateVideoInfoDisplay(self):
        """Update video info display"""
        duration = self.totalFrames / self.fps
        self.videoInfoLabel.config(text=f"{self.videoName} | {self.totalFrames} frames | {duration:.1f}s | {self.fps:.1f} FPS")
        
    def enableVideoControls(self):
        """Enable video control buttons"""
        controlButtons = [
            'previewPlayPauseBtn', 'replayBtn', 'move640Back', 'move64Back', 
            'move640Forward', 'move64Forward' , 'move10Forward', 'move1Forward',
            'move10Back', 'move1Back'
        ]
        
        for buttonName in controlButtons:
            if hasattr(self, buttonName):
                getattr(self, buttonName).config(state='normal')
                
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
        
        canvasWidth = self.timelineCanvas.winfo_width()
        canvasHeight = self.timelineCanvas.winfo_height()
        
        # Use minimum width if canvas isn't ready
        if canvasWidth <= 1:
            canvasWidth = 400  # Fallback width
            self.root.after(100, self.drawTimeline)
            return
            
        if canvasHeight <= 1:
            canvasHeight = 40  # Fallback height
            
        # Draw timeline background
        self.timelineCanvas.create_rectangle(0, 0, canvasWidth, canvasHeight, 
                                           fill='#1e1e1e', outline='')
        
        # Convert frames to time format (minutes:seconds)
        current_time = self.frameToTime(self.currentFrame) if self.videoCap else "0:00"
        total_time = self.frameToTime(self.totalFrames - 1) if self.videoCap and self.totalFrames > 0 else "0:00"
        
        # Use wider margins to accommodate time labels outside
        timelineLeft = 80
        timeline_right = canvasWidth - 80
        timelineWidth = timeline_right - timelineLeft
        
        # Always show time labels
        self.timelineCanvas.create_text(timelineLeft - 10, canvasHeight // 2, 
                                      text=f"{current_time}", 
                                      fill='#4caf50', anchor='e', font=('Arial', 12, 'bold'))

        self.timelineCanvas.create_text(timeline_right + 10, canvasHeight // 2, 
                                      text=f"{total_time}", 
                                      fill='#4caf50', anchor='w', font=('Arial', 12, 'bold'))

        # Always draw basic timeline background
        self.timelineCanvas.create_rectangle(timelineLeft, 10, timeline_right, canvasHeight - 10,
                                           fill='#444444', outline='#666666')
        
        # Only draw interactive timeline elements if video is loaded
        if self.videoCap and self.totalFrames > 0:
            segment_start_x = max(timelineLeft, (self.segmentStart / self.totalFrames) * timelineWidth + timelineLeft)
            segment_end_x = min(timeline_right, (self.segmentEnd / self.totalFrames) * timelineWidth + timelineLeft)
            
            # Draw selected segment
            self.timelineCanvas.create_rectangle(segment_start_x, 5, segment_end_x, canvasHeight - 5,
                                               fill='#4caf50', 
                                               outline='#2e7d32', width=2)
            
            # Add start and end markers at exact positions
            self.timelineCanvas.create_line(segment_start_x, 5, segment_start_x, canvasHeight - 5,
                                          fill='#2e7d32', width=2)
            self.timelineCanvas.create_line(segment_end_x, 5, segment_end_x, canvasHeight - 5,
                                          fill='#2e7d32', width=2)
            
        # Update segment info
        self.updateSegmentInfo()

    def extractSmokeStats(self):

        smoke = 0
        noSmoke = 0    
        totalPerVideo = 0    
        for videoFile, videoAnnotations in self.allAnnotations.items():
                for ann in videoAnnotations.values():
                    if videoFile == self.videoName:
                        totalPerVideo += 1
                    if isinstance(ann, dict) and 'hasSmoke' in ann:
                        if ann['hasSmoke']:
                            smoke += 1
                        else:
                            noSmoke += 1
        
        return smoke, noSmoke, totalPerVideo
        
    def updateSegmentInfo(self):
        """Update segment information display with smoke/no-smoke counts"""
        
        # Calculate segment info
        segmentFrames = self.segmentEnd - self.segmentStart + 1
        segmentStartTime = self.frameToTime(self.segmentStart)
        segmentEndTime = self.frameToTime(self.segmentEnd)
        segmentText = (f"Frames {self.segmentStart}-{self.segmentEnd} "
                    f"({segmentFrames} frames, {segmentStartTime}-{segmentEndTime})")
        
        smoke, noSmoke, annotationsPerVideo = self.extractSmokeStats()
        # Update annotation text
        if smoke == 0 and noSmoke == 0:
            annotationText = "No annotations yet"
        elif self.videoName == None:
            annotationText = (f"Smoke: {smoke}, No Smoke: {noSmoke}")
        else:
            annotationText = (f"Smoke: {smoke}, No Smoke: {noSmoke}\n"
                                f"Annotations in this video: {annotationsPerVideo}")
            
        # Right panel labels (if they exist)
        if hasattr(self, 'segmentInfoLabel'):
            self.segmentInfoLabel.config(text=segmentText)
        if hasattr(self, 'smokeInfoLabel'):
            self.smokeInfoLabel.config(text=annotationText)

    def resetHistorySelection(self):
        """Reset history selection to default color"""
        if hasattr(self, 'historyText') and self.lastClickedTag:
            default_color = "#d4af37" if self.lastClickedWasSmoke else "#87ceeb"
            self.historyText.tag_config(self.lastClickedTag, foreground=default_color, background="", underline=True)
            self.lastClickedTag = None
            self.lastClickedWasSmoke = False
        
    def onTimelineClick(self, event):
        """Handle timeline click for segment positioning"""

        self.resetHistorySelection()  # Reset any history selection

        if not self.videoCap:
            return
        
        # Pause any ongoing playback when user clicks timeline
        if self.isPlaying:
            self.pausePlayback()
            
        # Force canvas update to get correct dimensions
        self.timelineCanvas.update_idletasks()
        canvasWidth = self.timelineCanvas.winfo_width()
        
        # Safety check for canvas width
        if canvasWidth <= 1:
            print("Timeline canvas not ready")
            return
            
        # Account for margins (80px on each side for time labels)
        timelineLeft = 80
        timelineWidth = canvasWidth - 160  # Total width minus both margins
        clickX = event.x - timelineLeft  # Subtract left margin
        
        # Ensure click is within the timeline area
        if clickX < 0 or clickX > timelineWidth:
            return
            
        clickRatio = clickX / timelineWidth
        
        # Ensure click ratio is within bounds
        clickRatio = max(0.0, min(1.0, clickRatio))
        
        # Calculate new segment start position
        newStart = int(clickRatio * self.totalFrames)
        newStart = max(0, min(newStart, self.totalFrames - self.segmentLength))
        
        self.segmentStart = newStart
        self.segmentEnd = min(newStart + self.segmentLength - 1, self.totalFrames - 1)
        
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
            self.clearCanvasDimensionsCache()
            # Redisplay current frame with new dimensions
            self.displayFrame(self.currentFrame)
    
    def clearCanvasDimensionsCache(self):
        """Clear cached canvas dimensions and all processed images to force recalculation"""
        self.canvasWidth = None
        self.canvasHeight = None
        self.targetWidth = None
        self.targetHeight = None
        # Clear ALL processed images since they're all invalid at the new resolution
        self.imageCache.clear()
        
    def onTimelineEnter(self, event):
        """Handle mouse entering timeline - change cursor"""
        if self.videoCap:
            self.timelineCanvas.config(cursor="hand2")
            
    def onTimelineLeave(self, event):
        """Handle mouse leaving timeline - restore cursor"""
        self.timelineCanvas.config(cursor="")
        
    def moveSegment(self, frames, direction='forward'):
        """Generic method to move segment by specified number of frames"""
        if not self.videoCap:
            return
        
        # Pause any ongoing playback when user moves segment
        if self.isPlaying:
            self.pausePlayback()
            
        if direction == 'forward':
            newStart = min(self.segmentStart + frames, self.totalFrames - self.segmentLength)
        else:  # backward
            newStart = max(0, self.segmentStart - frames)
            
        self.updateSegmentPosition(newStart)
        
    def updateSegmentPosition(self, newStart):
        """Update segment position and reset related states"""
        self.segmentStart = newStart
        self.segmentEnd = min(newStart + self.segmentLength - 1, self.totalFrames - 1)
        
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
    def moveSegment1Back(self):
        """Move segment backward by 1 frame"""
        self.resetHistorySelection()
        self.moveSegment(Constants.SMALL_MOVE, 'backward')

    def moveSegment10Back(self):
        """Move segment backward by 10 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.MEDIUM_MOVE, 'backward')

    def moveSegment64Back(self):
        """Move segment backward by 64 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.LARGE_MOVE, 'backward')
        
    def moveSegment640Back(self):
        """Move segment backward by 640 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.HUGE_MOVE, 'backward')

    def moveSegment1Forward(self):
        """Move segment forward by 1 frame"""
        self.resetHistorySelection()
        self.moveSegment(Constants.SMALL_MOVE, 'forward')
    
    def moveSegment10Forward(self):
        """Move segment forward by 10 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.MEDIUM_MOVE, 'forward')
        
    def moveSegment64Forward(self):
        """Move segment forward by 64 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.LARGE_MOVE, 'forward')
        
    def moveSegment640Forward(self):
        """Move segment forward by 640 frames"""
        self.resetHistorySelection()
        self.moveSegment(Constants.HUGE_MOVE, 'forward')
    
        
    def displayFrame(self, frameNumber):
        """Display a specific frame with caching optimization"""
        if not self.videoCap:
            return
            
        try:
            frame = self.getCachedOrLoadFrame(frameNumber)
            if frame is not None:
                self.currentFrame = frameNumber
                
                # For the segment end frame, clear cached image to ensure current display
                if frameNumber == self.segmentEnd and frameNumber in self.imageCache:
                    del self.imageCache[frameNumber]
                
                self.displayVideoFrame(frame)
                self.updateFrameInfo()
                
                # Store as last frame if it's the end of segment
                if frameNumber == self.segmentEnd:
                    self.lastFrame = frame.copy()
                    
        except Exception as e:
            print(f"Error displaying frame {frameNumber}: {e}")
            
    def getCachedOrLoadFrame(self, frameNumber):
        """Get frame from cache or load from video"""
        if frameNumber in self.frameCache:
            return self.frameCache[frameNumber]
            
        # Read frame from video
        self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frameNumber)
        ret, frame = self.videoCap.read()
        
        if not ret:
            return None
        
        # Cache the frame if cache isn't too large
        if len(self.frameCache) < Constants.MAX_CACHE_SIZE:
            self.frameCache[frameNumber] = frame.copy()
            # Also pre-process and cache the image to avoid cache miss warnings
            self.preProcessImageForDisplay(frame, frameNumber)
            
        return frame
            
    def preProcessImageForDisplay(self, frame, frameNum):
        """Pre-process image for display during loading phase"""
        try:
            # Use the standard processing method for consistency
            photoImage = self.createProcessedImage(frame)
            self.imageCache[frameNum] = photoImage
            
        except Exception as e:
            print(f"Error pre-processing frame {frameNum}: {e}")
            
    def ensureCanvasDimensionsCalculated(self, frame):
        """Calculate canvas dimensions and image sizing dynamically"""
        self.videoCanvas.update_idletasks()
        canvasWidth = self.videoCanvas.winfo_width()
        canvasHeight = self.videoCanvas.winfo_height()
        
        if canvasWidth <= 1 or canvasHeight <= 1:
            canvasWidth, canvasHeight = Constants.SCALED_canvasWidth, Constants.SCALED_canvasHeight
        
        # Check if dimensions have changed significantly (more than 5 pixels)
        dimensions_changed = (
            self.canvasWidth is None or 
            self.canvasHeight is None or 
            abs(canvasWidth - self.canvasWidth) > 5 or 
            abs(canvasHeight - self.canvasHeight) > 5
        )
        
        if dimensions_changed:
            # Clear image cache when dimensions change to force re-processing
            if self.canvasWidth is not None:
                self.imageCache.clear()  # Force re-processing of all cached imag
            
            self.canvasWidth = canvasWidth
            self.canvasHeight = canvasHeight
            
            # Calculate image dimensions to fit canvas
            imgHeight, imgWidth = frame.shape[:2]
            scaleX = self.canvasWidth / imgWidth
            scaleY = self.canvasHeight / imgHeight
            scaleFactor = min(scaleX, scaleY)
            
            self.targetWidth = int(imgWidth * scaleFactor)
            self.targetHeight = int(imgHeight * scaleFactor)
            
            # Pre-calculate position dynamically
            self.imageX = (self.canvasWidth - self.targetWidth) // 2
            self.imageY = (self.canvasHeight - self.targetHeight) // 2

    def displayVideoFrame(self, frame):
        """Display frame on canvas with maximum performance optimization"""
        try:
            # Always recalculate dimensions first in case of window resize
            self.ensureCanvasDimensionsCalculated(frame)
            
            # Use pre-processed image if available and dimensions haven't changed
            if self.currentFrame in self.imageCache:
                self.currentImage = self.imageCache[self.currentFrame]
            else:
                # Process and cache image with current dimensions
                self.currentImage = self.createProcessedImage(frame)
                # Cache this processed image only if we have valid dimensions
                if self.canvasWidth and self.canvasHeight:
                    self.imageCache[self.currentFrame] = self.currentImage
            
            self.updateCanvasImage()

        except Exception as e:
            print(f"Error displaying video frame: {e}")
            # On error, try clearing cache and retry once
            if hasattr(self, 'imageCache'):
                print("Clearing image cache due to display error and retrying...")
                self.imageCache.clear()
                try:
                    self.currentImage = self.createProcessedImage(frame)
                    self.updateCanvasImage()
                except Exception as e2:
                    print(f"Retry also failed: {e2}")
            
    def createProcessedImage(self, frame):
        """Create processed image for display with current canvas dimensions"""
        frameRgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Ensure canvas dimensions are calculated
        self.ensureCanvasDimensionsCalculated(frame)
        
        # Create and resize image with current dimensions
        image = Image.fromarray(frameRgb)
        image = image.resize((self.targetWidth, self.targetHeight), Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)
        
    def updateCanvasImage(self):
        """Update canvas with current image using current positioning"""
        # Always use current positioning (imageX, imageY may have changed due to resize)
        if hasattr(self, 'imageId'):
            # Update both image and position
            self.videoCanvas.itemconfig(self.imageId, image=self.currentImage)
            self.videoCanvas.coords(self.imageId, self.imageX, self.imageY)
        else:
            # Create new image with current position
            self.imageId = self.videoCanvas.create_image(self.imageX, self.imageY, anchor=tk.NW, image=self.currentImage)
            
    def showLoadingIndicator(self):
        """Show loading indicator with animated dots"""
        if self.loadingLabel:
            # Position the loading label in the center of the video canvas
            self.videoCanvas.update_idletasks()
            canvasWidth = self.videoCanvas.winfo_width()
            canvasHeight = self.videoCanvas.winfo_height()
            
            if canvasWidth > 1 and canvasHeight > 1:
                x = canvasWidth // 2
                y = canvasHeight // 2
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
        canvasWidth = self.videoCanvas.winfo_width()
        canvasHeight = self.videoCanvas.winfo_height()
        
        if canvasWidth > 1 and canvasHeight > 1:
            x = canvasWidth // 2
            y = canvasHeight // 2
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
            framesToRemove = [f for f in self.frameCache.keys() 
                              if f < self.segmentStart or f > self.segmentEnd]
            for frameNum in framesToRemove:
                del self.frameCache[frameNum]
                if frameNum in self.imageCache:
                    del self.imageCache[frameNum]
            
            # Start asynchronous preloading
            self.preloadFramesBatch(self.segmentStart, 0)
                        
        except Exception as e:
            print(f"Error preloading frames: {e}")
            self.isPreloading = False
            self.hideLoadingIndicator()
            
    def preloadFramesBatch(self, startFrame, batch_index):
        """Preload frames in small batches to avoid UI blocking"""
        if not self.videoCap:
            self.isPreloading = False
            return
            
        current_frame = startFrame + (batch_index * Constants.BATCH_SIZE)
        
        # Stop if we've reached the end of the segment
        if current_frame > self.segmentEnd:
            self.isPreloading = False
            self.hideLoadingIndicator()
            return
            
        try:
            self.loadFrameBatch(current_frame)
            
            # Continue with next batch if there are more frames to load
            if current_frame + Constants.BATCH_SIZE <= self.segmentEnd:
                self.root.after(Constants.PRELOAD_DELAY_MS, 
                               lambda: self.preloadFramesBatch(startFrame, batch_index + 1))
            else:
                self.isPreloading = False
                self.hideLoadingIndicator()
            
        except Exception as e:
            print(f"Error in batch preloading: {e}")
            self.isPreloading = False
            self.hideLoadingIndicator()
            
    def loadFrameBatch(self, current_frame):
        """Load a batch of frames into cache"""
        for i in range(Constants.BATCH_SIZE):
            frameNum = current_frame + i
            if frameNum > self.segmentEnd or frameNum >= self.totalFrames:
                break
                
            if frameNum not in self.frameCache and len(self.frameCache) < Constants.MAX_CACHE_SIZE:
                self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
                ret, frame = self.videoCap.read()
                if ret:
                    self.frameCache[frameNum] = frame.copy()
                    # Pre-process the image for display during loading
                    self.preProcessImageForDisplay(frame, frameNum)
                else:
                    break
            
    def updateFrameInfo(self):
        """Update frame information display"""
        if self.videoCap:
            self.frameInfoLabel.config(text=f"Frame: {self.currentFrame}/{self.totalFrames-1}")
            
    def togglePreviewPlayback(self):
        """Toggle preview playback in selection mode"""
        if not self.videoCap:
            return
            
        if self.isPlaying:
            self.pausePlayback()
            self.previewPlayPauseBtn.config(text="PLAY", bg='#4caf50')
        else:
            self.playSegment()
            self.previewPlayPauseBtn.config(text="PAUSE", bg='#ff9800')
        
    def playSegment(self):
        """Play the selected segment"""
        if not self.videoCap:
            return
        
        # Check if preloading is needed and wait for completion
        if not self.isPreloading:
            # Check if segment is already fully cached
            segmentCached = all(frame in self.frameCache and frame in self.imageCache 
                               for frame in range(self.segmentStart, self.segmentEnd + 1))
            
            if not segmentCached:
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
        if hasattr(self, 'previewPlayPauseBtn'):
            self.previewPlayPauseBtn.config(text="PAUSE", bg='#ff9800')
        self.playNextFrame()
        
    def playNextFrame(self):
        """Play next frame in segment with limited frame skipping for real-time speed."""
        if not self.isPlaying or not self.videoCap:
            return

        # Calculate which frame should be shown based on elapsed time
        elapsed = time.time() - self.playbackStartTime
        targetFrame = int(self.segmentStart + elapsed * self.fps)
        targetFrame = min(targetFrame, self.segmentEnd)

        # Limit frame skipping to max 3 consecutive frames
        if targetFrame > self.currentFrame + Constants.MAX_SKIPPED_FRAMES:
            targetFrame = self.currentFrame + Constants.MAX_SKIPPED_FRAMES

        if targetFrame <= self.segmentEnd:
            frame = self.getCachedOrLoadFrame(targetFrame)
            if frame is not None:
                display_start = time.time()
                self.displayVideoFrame(frame)
                displayTime = (time.time() - display_start) * 1000
            else:
                print(f"WARNING - Frame {self.currentFrame} not cached!")
                displayTime = 0

            self.currentFrame = targetFrame

            # Update frame info and timeline for smooth user experience
            self.updateFrameInfo()

            # Adaptive timing compensation based on actual display time
            delay = max(Constants.MIN_FRAME_DELAY_MS, self.getIdealFrameDelayMs() - int(displayTime))

            # Periodic garbage collection to prevent buildup
            if self.currentFrame % Constants.GC_INTERVAL_FRAMES == 0:
                gc.collect()

            if self.currentFrame >= self.segmentEnd:
                self.handlePlaybackFinished()
            else:
                self.playbackTimer = self.root.after(delay, self.playNextFrame)
            
    def calculateFrameDelay(self, displayTime):
        """Calculate adaptive frame delay based on display performance and video FPS"""
        idealDelay = self.getIdealFrameDelayMs()
        
        if displayTime > idealDelay * 0.6:  # If display took more than 60% of ideal time
            # Reduce delay more aggressively to compensate
            delay = max(Constants.MIN_FRAME_DELAY_MS, idealDelay - int(displayTime))
        else:
            # Standard compensation
            delay = max(Constants.MIN_FRAME_DELAY_MS, idealDelay - int(displayTime))
            
        return delay
            
    def handlePlaybackFinished(self):
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
        self.resetPlayButtons()
        
        # Refresh display in case canvas was resized during playback
        self.root.after(50, self.refreshVideoDisplay)
            
    def resetPlayButtons(self):
        """Reset play buttons to initial state"""
        if hasattr(self, 'playPauseBtn'):
            self.playPauseBtn.config(text="Play Segment", bg='#4caf50')
        if hasattr(self, 'previewPlayPauseBtn'):
            self.previewPlayPauseBtn.config(text="PLAY", bg='#4caf50')

    def pausePlayback(self):
        """Pause playback"""
        self.isPlaying = False
        # Store current position for resuming
        self.pausedFrame = self.currentFrame
        if self.playbackTimer:
            self.root.after_cancel(self.playbackTimer)
        self.resetPlayButtons()
        
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
        if hasattr(self, 'smokeBtn') and hasattr(self, 'noSmokeBtn') and hasattr(self, 'instructionSubLabel'):
            if self.segmentWatched:
                self.smokeBtn.config(state='normal')
                self.noSmokeBtn.config(state='normal')
                self.instructionSubLabel.config(state='normal')
                if hasattr(self, 'watchNoticeLabel'):
                    self.watchNoticeLabel.config(text="Segment watched - annotation enabled", fg='lightgreen')
            else:
                self.smokeBtn.config(state='disabled')
                self.noSmokeBtn.config(state='disabled')
                self.instructionSubLabel.config(state='disabled')
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
        self.root.after(100, lambda: self.processAnnotation(True))
        
    def markNoSmoke(self):
        """Mark segment as no smoke"""
        if not self.segmentWatched:
            messagebox.showwarning("Watch Required", "Please watch the segment completely before making an annotation.")
            return
        
        # Show processing overlay
        self.showProcessingOverlay("Processing NO SMOKE annotation...")
        
        # Process annotation asynchronously to avoid blocking UI
        self.root.after(100, lambda: self.processAnnotation(False))
    
    def processAnnotation(self, hasSmoke):
        """Process the annotation with status updates"""
        try:
            # Update status
            self.updateProcessingStatus("Saving annotation data...")
            self.root.after(200, lambda: self.continueAnnotationProcessing(hasSmoke))
        except Exception as e:
            self.showProcessingResult(f"Error: {str(e)}", is_success=False)
    
    def continueAnnotationProcessing(self, hasSmoke):
        """Continue processing annotation"""
        try:
            # Save the annotation
            self.saveAnnotation(hasSmoke)
            
            # Show success message
            smokeStatus = "SMOKE DETECTED" if hasSmoke else "NO SMOKE"
            resultMsg = f"Frames {self.segmentStart}-{self.segmentEnd} marked as {smokeStatus}"
            self.showProcessingResult(resultMsg, is_success=True)
            
        except Exception as e:
            self.showProcessingResult(f"Failed to save annotation: {str(e)}", is_success=False)
        
    def saveAnnotation(self, hasSmoke):
        """Save annotation for current segment in the annotations dictionary"""
        if not self.videoName:
            return
            
        try:        
            if self.videoName not in self.annotations:
                self.annotations[self.videoName] = {}

            # Create segment key
            segmentKey = f"{self.segmentStart:06d}_{self.segmentEnd:06d}"
            
            # Store annotation data
            self.annotations[self.videoName][segmentKey] = {
                "startFrame": self.segmentStart,
                "endFrame": self.segmentEnd,
                "hasSmoke": hasSmoke,
            }
            
            # Update status
            self.updateProcessingStatus("Creating output directories...")
            
            # Use the user's home directory instead of the program directory
            programDir = os.path.expanduser("~")
            baseVideoName = os.path.splitext(os.path.basename(self.videoName))[0]
            
            # Create a centralized output directory for all YOLO annotations in program folder
            yoloDir = os.path.join(programDir, "smoke_detection_annotations")
            imagesDir = os.path.join(yoloDir, "images")
            labelsDir = os.path.join(yoloDir, "labels")
            
            for directory in [yoloDir, imagesDir, labelsDir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Create unique filename with video name prefix
            uniqueSegmentKey = f"{'smoke' if hasSmoke else 'nosmoke'}_{baseVideoName}_{segmentKey}"

            #delete file with oposite annotation if it exists
            oppositeSegmentKey = f"{'nosmoke' if hasSmoke else 'smoke'}_{baseVideoName}_{segmentKey}"

            # Update status
            self.updateProcessingStatus("Generating temporal analysis image...")
            
            # Generate and save temporal analysis image (192x192) for CURRENT segment only
            self.saveSegmentTemporalAnalysis(self.segmentStart, self.segmentEnd, uniqueSegmentKey, oppositeSegmentKey, imagesDir)
            
            # Update status
            self.updateProcessingStatus("Creating YOLO label file...")

            oppositeLabelFile = os.path.join(labelsDir, f"{oppositeSegmentKey}.txt")

            if os.path.exists(oppositeLabelFile):
                os.remove(oppositeLabelFile)
            
            # Create YOLO format label file for CURRENT segment only
            labelFile = os.path.join(labelsDir, f"{uniqueSegmentKey}.txt")
            
            with open(labelFile, 'w') as f:
                if hasSmoke:
                    f.write("0 0.5 0.5 1.0 1.0\n")
                else:
                    f.write("1 0.5 0.5 1.0 1.0\n")
            
            # Update status
            self.updateProcessingStatus("Updating summary files...")
            
            # Update summary file with only current segment
            self.updateSummaryFileWithCurrentSegment(yoloDir, uniqueSegmentKey, hasSmoke)
            
            # Update class names file (only if it doesn't exist)
            classesFile = os.path.join(yoloDir, Config.classesFile)
            if not os.path.exists(classesFile):
                with open(classesFile, 'w') as f:
                    f.write("smoke\n")
                    f.write("no_smoke\n")
            
            # Final status update
            self.updateProcessingStatus("Finalizing annotation...")

            
            # Automatically reload annotation history after saving (if history widget exists)
            if hasattr(self, 'historyText'):
                try:
                    self.loadAnnotationHistory()
                    self.loadVideoAnnotations()
                except Exception as history_error:
                    print(f"Note: Could not auto-reload history: {history_error}")
            
        except Exception as e:
            print(f"Error saving annotation: {e}")
            
    def updateSummaryFileWithCurrentSegment(self, yoloDir, uniqueSegmentKey, hasSmoke):
        """Update summary file with only the current segment"""
        try:
            summaryFile = os.path.join(yoloDir, Config.summaryFile)
            
            # Load existing annotations if file exists
            allAnnotations = {}
            if os.path.exists(summaryFile):
                try:
                    with open(summaryFile, 'r') as f:
                        allAnnotations = json.load(f)
                except:
                    allAnnotations = {}
            
            # Initialize current video in allAnnotations if it doesn't exist
            if self.videoName not in allAnnotations:
                allAnnotations[self.videoName] = {}

            # Add/update only the current segment annotation (preserve existing ones)
            if self.videoName in self.annotations:
                current_videoAnnotations = self.annotations[self.videoName]
                # Find the segment key that matches our current segment
                for segmentKey, annotation_data in current_videoAnnotations.items():
                    if (annotation_data.get('startFrame') == self.segmentStart and 
                        annotation_data.get('endFrame') == self.segmentEnd):
                        # Update only this specific segment, preserve all others
                        allAnnotations[self.videoName][segmentKey] = annotation_data
                        break
            
            # Save updated summary (preserves all existing annotations from all videos)
            with open(summaryFile, 'w') as f:
                json.dump(allAnnotations, f, indent=2)
                
        except Exception as e:
            print(f"Error updating summary file: {e}")

    def saveSegmentTemporalAnalysis(self, startFrame, endFrame, uniqueSegmentKey, oppositeSegmentKey, imagesDir):
        """Generate and save temporal analysis image from 64-frame segment"""
        try:            
            # Load all 64 frames from the segment
            frames = []
            for frameNum in range(startFrame, endFrame + 1):
                if frameNum in self.frameCache:
                    # Use cached frame if available
                    frame = self.frameCache[frameNum]
                else:
                    # Load frame from video
                    self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
                    ret, frame = self.videoCap.read()
                    if not ret:
                        print(f"Warning: Could not read frame {frameNum}, using previous frame")
                        if frames:  # Use last successful frame if available
                            frame = frames[-1].copy()
                        else:
                            print(f"Error: No frames available for temporal analysis")
                            return
                
                frames.append(frame)

            oppositeLabelFile = os.path.join(imagesDir, f"{oppositeSegmentKey}.png")
            if os.path.exists(oppositeLabelFile):
                os.remove(oppositeLabelFile)
            
            # Generate temporal analysis image (192x192)
            temporalImage = self.temporalGenerator.generate_from_frames(frames)

            # Save temporal analysis image
            imagePath = os.path.join(imagesDir, f"{uniqueSegmentKey}.png")
            success = cv2.imwrite(imagePath, temporalImage)
            
            if success:
                print(f"Saved temporal analysis image: {imagePath}")
            else:
                print(f"Error: Failed to save temporal analysis image to {imagePath}")
                
        except Exception as e:
            print(f"Error generating temporal analysis for segment {startFrame}-{endFrame}: {e}")
            # Fallback: save the last frame as before
            self.saveSegmentFrame(endFrame, uniqueSegmentKey, imagesDir)
            
    def saveSegmentFrame(self, frameNumber, uniqueSegmentKey, imagesDir):
        """Fallback method: Save a specific frame as an image file with unique naming"""
        try:
            # Read the frame
            self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, frameNumber)
            ret, frame = self.videoCap.read()
            
            if ret:
                # Save as PNG image with unique name (fallback)
                imagePath = os.path.join(imagesDir, f"{uniqueSegmentKey}_fallback.png")
                cv2.imwrite(imagePath, frame)
                
        except Exception as e:
            print(f"Error saving fallback frame {frameNumber}: {e}")
            
        
    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'videoCap') and self.videoCap:
                self.videoCap.release()
            if hasattr(self, 'playbackTimer') and self.playbackTimer:
                self.root.after_cancel(self.playbackTimer)
            if hasattr(self, 'loadingAnimationTimer') and self.loadingAnimationTimer:
                self.root.after_cancel(self.loadingAnimationTimer)
            self.root.destroy()
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def displayAnnotationHistory(self, annotations):
        """Display annotation history in the text widget with enhanced formatting and information."""
        self.historyText.config(state=tk.NORMAL)
        self.historyText.delete(1.0, tk.END)
        
        # Sort annotations by start frame
        sorted_annotations = []
        for segmentKey, annotation_data in annotations.items():
            sorted_annotations.append((annotation_data.get('startFrame', 0), segmentKey, annotation_data))
        
        sorted_annotations.sort(key=lambda x: x[0])
        
        # Display enhanced header with statistics
        header = f"Annotation History: {self.videoName}\n"
        header += "=" * 60 + "\n\n"
        
        # Add instructions
        header += "Instructions:\n"
        header += "  • Click any frame range below to jump to that segment\n\n"
        self.historyText.insert(tk.END, header)
        
        if not sorted_annotations:
            # Enhanced empty state message
            emptyMsg = "No annotations found for this video yet.\n\n"
            self.historyText.insert(tk.END, emptyMsg)
        else:
            # Display each annotation with simplified formatting
            for i, (startFrame, segmentKey, annotation_data) in enumerate(sorted_annotations, 1):
                startFrame = annotation_data.get('startFrame', 0)
                endFrame = annotation_data.get('endFrame', startFrame + 63)
                hasSmoke = annotation_data.get('hasSmoke', False)
                
                # Create clean entry with color coding
                smokeStatus = "SMOKE" if hasSmoke else "NO SMOKE"
                
                # Calculate time range for user convenience
                startTime = self.frameToTime(startFrame) if hasattr(self, 'frameToTime') else f"{startFrame//1500}:{(startFrame%1500)//25:02d}"
                endTime = self.frameToTime(endFrame) if hasattr(self, 'frameToTime') else f"{endFrame//1500}:{(endFrame%1500)//25:02d}"
                
                entry = f"{i:2d}. Frames {startFrame:06d}-{endFrame:06d} ({startTime}-{endTime}) | {smokeStatus}\n\n"
                
                # Insert with tag for clicking
                tagName = f"frame_{startFrame}"
                self.historyText.insert(tk.END, entry, tagName)
                
                # Bind click event
                self.historyText.tag_bind(tagName, "<Button-1>", 
                         lambda e, frame=startFrame, tag=tagName, smoke=hasSmoke: self.jumpToHistoryFrame(frame, smoke, tag))

                # Enhanced styling based on annotation type with neutral but visible colors
                if hasSmoke:
                    self.historyText.tag_config(tagName, foreground="#d4af37", underline=True)  # Gold/amber for smoke
                else:
                    self.historyText.tag_config(tagName, foreground="#87ceeb", underline=True)  # Sky blue for no smoke
    
        
        self.historyText.config(state=tk.DISABLED)
    
    def jumpToHistoryFrame(self, targetFrame, hasSmoke, tagName):
        """Jump to a frame from the annotation history."""

    # Reset previous tag style
        self.resetHistorySelection()

        # Highlight current tag with background, keep original foreground
        self.historyText.tag_config(tagName, background="#585858")

        # Update state
        self.lastClickedTag = tagName
        self.lastClickedWasSmoke = hasSmoke

        if not self.videoCap:
            return
        
        try:
            # Validate frame number
            if targetFrame < 0 or targetFrame >= self.totalFrames:
                print(f"Invalid frame number: {targetFrame}")
                return
            
            # Calculate new segment position to include the target frame
            newSegmentStart = max(0, targetFrame)
            newSegmentStart = min(newSegmentStart, self.totalFrames - Constants.SEGMENT_LENGTH)
            
            # Update segment position
            self.updateSegmentPosition(newSegmentStart)
            
            # Jump to the specific frame
            self.displayFrame(targetFrame)
            self.currentFrame = targetFrame
            
            # Update timeline to show current position
            self.drawTimeline()
            
        except Exception as e:
            print(f"Error jumping to history frame {targetFrame}: {e}")

    def displayHistoryMessage(self, message):
        """Display a simple message in the history text widget."""
        self.historyText.config(state=tk.NORMAL)
        self.historyText.delete(1.0, tk.END)
        self.historyText.insert(tk.END, message)
        self.historyText.config(state=tk.DISABLED)
    
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
            self.moveSegment10Back()
        elif key == 'right':
            self.moveSegment10Forward()

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
