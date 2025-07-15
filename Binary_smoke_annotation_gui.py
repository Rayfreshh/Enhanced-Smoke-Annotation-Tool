#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import glob
import json
from datetime import datetime
from PIL import Image, ImageTk
import cv2

class SmokeAnnotationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smoke Detection Annotation Tool")
        # Start in maximized state for better fullscreen experience
        self.root.state('zoomed' if self.root.tk.call('tk', 'windowingsystem') == 'win32' else 'normal')
        self.root.geometry("1400x900")
        self.root.configure(bg='#2b2b2b')
        
        # Initialize core variables
        self.currentFrameIndex = 0
        self.currentMinivideoIndex = 0
        self.frameFiles = []
        self.videoFolders = []
        self.minivideoFolders = []
        self.currentVideoFolder = None
        self.currentMinivideoFolder = None
        self.currentImage = None
        
        # Workflow variables
        self.currentVideoFile = None
        self.videoCap = None
        self.videoPlaying = False
        self.workflowState = "videoReview"  # "videoReview" or "frameAnnotation"
        self.frameAnnotations = {}  # Store binary smoke/no-smoke annotations for each frame
        
        # Initialize GUI components
        self.setupGui()
        self.loadDefaultVideos()
        
        # Bind keyboard shortcuts
        self.setupKeyboardShortcuts()
        
        # Bind resize event to refresh frame display
        self.root.bind('<Configure>', self.onWindowResize)
        
    def onWindowResize(self, event=None):
        """Handle window resize events to dynamically scale buttons"""
        # Only trigger on the main window resize, not child widgets
        if event and event.widget != self.root:
            return
            
        # Add a small delay to avoid too frequent updates during dragging
        if hasattr(self, '_resizeTimer'):
            self.root.after_cancel(self._resizeTimer)
        
        self._resizeTimer = self.root.after(100, self._doResizeUpdate)
        
    def _doResizeUpdate(self):
        """Actually perform the resize update after delay"""
        # Scale buttons based on new window size
        self.scaleAnnotationButtons()
        
        # Refresh frame display after resize
        self.root.after(50, self.refreshFrameDisplay)

    def onCanvasResize(self, event=None):
        """Handle canvas resize events"""
        # Add a small delay to avoid too frequent updates during resize
        self.root.after(50, self.refreshFrameDisplay)
        
    def refreshFrameDisplay(self):
        """Refresh the current frame display after window changes"""
        if self.frameFiles and hasattr(self, 'currentFrameIndex'):
            self.displayCurrentFrame()
        
    def setupGui(self):
        """Setup the main GUI layout with simplified design"""
        # Main container with better padding for fullscreen
        mainFrame = tk.Frame(self.root, bg='#2b2b2b')
        mainFrame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Top menu bar
        self.createMenuBar()
        
        # Title with better scaling
        titleLabel = tk.Label(mainFrame, text="Smoke Detection Annotation Tool", 
                              font=('Arial', 18, 'bold'), bg='#2b2b2b', fg='white')
        titleLabel.pack(pady=(0, 15))
        
        # Main content area
        contentFrame = tk.Frame(mainFrame, bg='#2b2b2b')
        contentFrame.pack(fill=tk.BOTH, expand=True)
        
        # Left side container for video and navigation
        leftContainer = tk.Frame(contentFrame, bg='#2b2b2b')
        leftContainer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        # Video display on top
        self.setupVideoDisplay(leftContainer)
        
        # Navigation menu under the video
        self.setupNavigationPanel(leftContainer)
        
        # Right side - Simplified control panel 
        self.setupControlPanel(contentFrame)
        
        # Scale buttons based on current fullscreen state
        self.root.after(100, self.scaleAnnotationButtons)
        
    def createMenuBar(self):
        """Create menu bar for file operations"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        fileMenu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=fileMenu)
        fileMenu.add_command(label="Load Video Folder", command=self.loadVideoFolder)
        fileMenu.add_separator()
        fileMenu.add_command(label="Exit", command=self.root.quit)
        
    def setupVideoDisplay(self, parent):
        """Setup video display area"""
        # Video display frame
        videoFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        videoFrame.pack(fill=tk.BOTH, expand=True)
        
        # Video title
        videoTitle = tk.Label(videoFrame, text="Video Display", 
                              font=('Arial', 14, 'bold'), bg='#3b3b3b', fg='white')
        videoTitle.pack(pady=8)
        
        # Video canvas - Further reduced size for smaller display
        self.videoCanvas = tk.Canvas(videoFrame, bg='black', width=500, height=300)
        self.videoCanvas.pack(padx=15, pady=15, fill=tk.BOTH, expand=True)
        
        # Bind canvas resize to refresh frame display
        self.videoCanvas.bind('<Configure>', self.onCanvasResize)
        
        # Video info frame
        infoFrame = tk.Frame(videoFrame, bg='#3b3b3b')
        infoFrame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        self.frameInfoLabel = tk.Label(infoFrame, text="No video loaded", 
                                        font=('Arial', 11), bg='#3b3b3b', fg='lightgray')
        self.frameInfoLabel.pack()
        
    def setupNavigationPanel(self, parent):
        """Setup navigation controls under the video frame"""
        navFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        navFrame.pack(fill=tk.X, pady=(10, 0))
        
        # Create a centered container for all navigation elements
        navContainer = tk.Frame(navFrame, bg='#3b3b3b')
        navContainer.pack(expand=True)
        
        # Video selection - Enlarged for better usability
        videoFrame = tk.LabelFrame(navContainer, text="Video Selection", 
                                   font=('Arial', 14, 'bold'), bg='#3b3b3b', fg='white')
        videoFrame.pack(side=tk.LEFT, padx=15, pady=10)
        
        self.videoVar = tk.StringVar()
        self.videoCombo = ttk.Combobox(videoFrame, textvariable=self.videoVar, 
                                       state='readonly', width=35, font=('Arial', 12))
        self.videoCombo.pack(padx=12, pady=12)
        self.videoCombo.bind('<<ComboboxSelected>>', self.onVideoSelected)
        
        # Mini-video navigation - Optimized size, removed counter
        minivideoFrame = tk.LabelFrame(navContainer, text="Mini-Video Navigation", 
                                       font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        minivideoFrame.pack(side=tk.LEFT, padx=10, pady=8)
        
        minivideoButtons = tk.Frame(minivideoFrame, bg='#3b3b3b')
        minivideoButtons.pack(padx=8, pady=6)
        
        self.prevMinivideoBtn = tk.Button(minivideoButtons, text="←", command=self.previousMinivideo,
                 font=('Arial', 14, 'bold'), bg='#555', fg='white', width=5, height=2, state='disabled')
        self.prevMinivideoBtn.pack(side=tk.LEFT, padx=3)
        
        self.nextMinivideoBtn = tk.Button(minivideoButtons, text="→", command=self.nextMinivideo,
                 font=('Arial', 14, 'bold'), bg='#555', fg='white', width=5, height=2, state='disabled')
        self.nextMinivideoBtn.pack(side=tk.LEFT, padx=3)
        
        # Frame navigation - Optimized size
        frameFrame = tk.LabelFrame(navContainer, text="Frame Navigation", 
                                   font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        frameFrame.pack(side=tk.LEFT, padx=10, pady=8)
        
        frameButtons = tk.Frame(frameFrame, bg='#3b3b3b')
        frameButtons.pack(padx=8, pady=6)
        
        self.prevFrameBtn = tk.Button(frameButtons, text="←", command=self.previousFrame,
                 font=('Arial', 14, 'bold'), bg='#555', fg='white', width=5, height=2, state='disabled')
        self.prevFrameBtn.pack(side=tk.LEFT, padx=3)
        
        self.nextFrameBtn = tk.Button(frameButtons, text="→", command=self.nextFrame,
                 font=('Arial', 14, 'bold'), bg='#555', fg='white', width=5, height=2, state='disabled')
        self.nextFrameBtn.pack(side=tk.LEFT, padx=3)
        
    def setupControlPanel(self, parent):
        """Setup the simplified right side control panel"""
        # Control panel frame - fixed width for layout stability
        self.controlFrame = tk.Frame(parent, bg='#3b3b3b', relief=tk.RAISED, bd=2, width=750)
        self.controlFrame.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        self.controlFrame.pack_propagate(False)
        
        # Control panel title
        self.controlTitle = tk.Label(self.controlFrame, text="Smoke Detection Annotation", 
                                font=('Arial', 18, 'bold'), bg='#3b3b3b', fg='white')
        self.controlTitle.pack(pady=25)
        
        # Video Review Panel (initially shown)
        self.videoReviewFrame = tk.LabelFrame(self.controlFrame, text="Video Review", 
                                               font=('Arial', 16, 'bold'), bg='#3b3b3b', fg='white')
        
        # Video info
        videoInfoFrame = tk.LabelFrame(self.videoReviewFrame, text="Video Information", 
                                        bg='#3b3b3b', fg='white', font=('Arial', 14, 'bold'), height=100)
        videoInfoFrame.pack(fill=tk.X, padx=0, pady=(10, 20))
        videoInfoFrame.pack_propagate(False)
        
        self.videoCurrentLabel = tk.Label(videoInfoFrame, text="Video: 0/0", 
                                           bg='#3b3b3b', fg='lightgray', font=('Arial', 13))
        self.videoCurrentLabel.pack(pady=8)

        # Get button dimensions using the new scaling function
        buttonWidth, buttonHeight, buttonFont = self.calculateButtonDimensions()
        
        # Video playback controls
        videoControlsFrame = tk.Frame(self.videoReviewFrame, bg='#3b3b3b')
        videoControlsFrame.pack(pady=20)
        
        self.playPauseBtn = tk.Button(videoControlsFrame, text="Play Video", 
                                       command=self.toggleVideoPlayback,
                                       bg='#4caf50', fg='white', font=('Arial', buttonFont, 'bold'),
                                       width=buttonWidth, height=buttonHeight)
        self.playPauseBtn.pack(pady=10)
        
        self.startAnnotationBtn = tk.Button(videoControlsFrame, text="Start Frame Annotation", 
                                            command=self.startFrameAnnotation,
                                            bg='#2196f3', fg='white', font=('Arial', buttonFont, 'bold'),
                                            width=buttonWidth, height=buttonHeight)
        self.startAnnotationBtn.pack(pady=10)
        
        # Frame Annotation Panel (initially hidden)
        self.frameAnnotationFrame = tk.LabelFrame(self.controlFrame, text="Frame Annotation", 
                                                   font=('Arial', 16, 'bold'), bg='#3b3b3b', fg='white')
        
        # Frame info
        frameInfoFrame = tk.LabelFrame(self.frameAnnotationFrame, text="Frame Information", 
                                        bg='#3b3b3b', fg='white', font=('Arial', 14, 'bold'), height=100)
        frameInfoFrame.pack(fill=tk.X, padx=0, pady=(10, 20))
        frameInfoFrame.pack_propagate(False)
        
        self.currentFrameLabel = tk.Label(frameInfoFrame, text="Frame: 0/0", 
                                           bg='#3b3b3b', fg='lightgray', font=('Arial', 13))
        self.currentFrameLabel.pack(pady=5)
        
        self.progressLabel = tk.Label(frameInfoFrame, text="Progress: 0%", 
                                      bg='#3b3b3b', fg='lightgray', font=('Arial', 13))
        self.progressLabel.pack(pady=5)
        
        # Instructions for annotation
        instructionsLabel = tk.Label(self.frameAnnotationFrame, 
                                     text="Click Smoke or No Smoke \nfor each frame", 
                                     bg='#3b3b3b', fg='white', font=('Arial', 18, 'bold'))
        instructionsLabel.pack(pady=(10, 20))
        
        # Annotation buttons - two large buttons stacked vertically
        annotationFrame = tk.Frame(self.frameAnnotationFrame, bg='#3b3b3b')
        annotationFrame.pack(pady=20)

        # Smoke button (top)
        self.smokeBtn = tk.Button(annotationFrame, text="SMOKE", 
                                  command=self.markSmoke,
                                  bg='#666666', fg='white', font=('Arial', buttonFont, 'bold'),
                                  width=buttonWidth, height=buttonHeight)
        self.smokeBtn.pack(pady=10)
        
        # No Smoke button (bottom) 
        self.noSmokeBtn = tk.Button(annotationFrame, text="NO SMOKE", 
                                     command=self.markNoSmoke,
                                     bg='#666666', fg='white', font=('Arial', buttonFont, 'bold'),
                                     width=buttonWidth, height=buttonHeight)
        self.noSmokeBtn.pack(pady=10)
        
        # Return to video button
        self.returnToVideoBtn = tk.Button(self.frameAnnotationFrame, text="← Back to Video", 
                                           command=self.returnToVideoReview,
                                           bg='#795548', fg='white', font=('Arial', buttonFont, 'bold'),
                                           width=buttonWidth, height=buttonHeight)
        self.returnToVideoBtn.pack(pady=10)
        
        # Initially show video review mode
        self.setVideoReviewMode()

    def loadDefaultVideos(self):
        """Load default video folders from the workspace"""
        try:
            generatedVideosPath = "/home/desigai/smartcam/generated_videos"
            if os.path.exists(generatedVideosPath):
                self.videoFolders = []
                for videoDir in os.listdir(generatedVideosPath):
                    videoPath = os.path.join(generatedVideosPath, videoDir)
                    if os.path.isdir(videoPath):
                        # Check if this directory contains mini video folders
                        miniVideos = [d for d in os.listdir(videoPath) 
                                     if os.path.isdir(os.path.join(videoPath, d)) and d.startswith('mini_video')]
                        if miniVideos:
                            self.videoFolders.append(videoPath)
                
                # Update combo box
                folderNames = [os.path.basename(folder) for folder in self.videoFolders]
                self.videoCombo['values'] = folderNames
                
                if folderNames:
                    # Find first video folder with incomplete annotations
                    selectedIndex = self.findFirstIncompleteVideoFolder()
                    self.videoCombo.current(selectedIndex)
                    self.onVideoSelected(None)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load videos: {str(e)}")
            
    def loadVideoFolder(self):
        """Load a custom video folder"""
        folder = filedialog.askdirectory(title="Select video folder with mini-video folders")
        if folder:
            self.videoFolders.append(folder)
            folderNames = [os.path.basename(folder) for folder in self.videoFolders]
            self.videoCombo['values'] = folderNames
            self.videoCombo.set(os.path.basename(folder))
            self.loadMinivideos(folder)
            
    def onVideoSelected(self, event):
        """Handle video folder selection"""
        if self.videoCombo.current() >= 0:
            selectedFolder = self.videoFolders[self.videoCombo.current()]
            self.loadMinivideos(selectedFolder)
            
    def loadMinivideos(self, videoFolderPath):
        """Load mini-video folders from the selected video folder"""
        try:
            self.currentVideoFolder = videoFolderPath
            
            # Find all mini-video folders
            self.minivideoFolders = []
            for item in os.listdir(videoFolderPath):
                itemPath = os.path.join(videoFolderPath, item)
                if os.path.isdir(itemPath) and item.startswith('mini_video'):
                    self.minivideoFolders.append(itemPath)
            
            # Sort mini-video folders naturally
            self.minivideoFolders.sort(key=lambda x: int(os.path.basename(x).split('_')[-1]))
            
            if self.minivideoFolders:
                # Find first non-completely annotated mini-video
                self.currentMinivideoIndex = self.findFirstIncompleteMinivideo()
                self.loadFrames(self.minivideoFolders[self.currentMinivideoIndex])
                self.updateMinivideoInfo()
                self.updateNavigationButtons()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mini-videos: {str(e)}")
            
    def loadFrames(self, folderPath):
        """Load frame files from the selected mini-video folder and start video review"""
        try:
            self.currentMinivideoFolder = folderPath
            
            # Clear previous frame annotations when switching mini-videos
            self.frameAnnotations = {}
            
            # Load existing annotations for this mini-video
            self.loadExistingAnnotations()
            
            # Find the MP4 video file
            minivideoName = os.path.basename(folderPath)
            videoFile = os.path.join(folderPath, f"{minivideoName}.mp4")
            
            if os.path.exists(videoFile):
                self.currentVideoFile = videoFile
                self.startVideoReview()
            else:
                # No video file, go directly to frame annotation
                self.setFrameAnnotationMode()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mini-video: {str(e)}")
            
    def loadFrameFiles(self):
        """Load individual frame files for annotation"""
        try:
            # Find all image files
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
            self.frameFiles = []
            for ext in extensions:
                self.frameFiles.extend(glob.glob(os.path.join(self.currentMinivideoFolder, ext)))
            
            # Sort files naturally
            if self.frameFiles:
                self.frameFiles.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0].split('_')[1]))
            
            # Load existing annotations
            self.loadExistingAnnotations()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load frames: {str(e)}")
            
    def loadExistingAnnotations(self):
        """Load existing annotations for the current video if they exist"""
        if not self.currentMinivideoFolder:
            return
            
        try:
            # Try to load from JSON format (backup/temporary)
            videoName = os.path.basename(self.currentVideoFolder) if self.currentVideoFolder else "unknown"
            minivideoName = os.path.basename(self.currentMinivideoFolder)
            autoSavePath = os.path.join(os.path.dirname(self.currentMinivideoFolder), f"auto_save_{videoName}_{minivideoName}.json")
            
            if os.path.exists(autoSavePath):
                with open(autoSavePath, 'r') as f:
                    annotationData = json.load(f)
                    # Check if this is old format with region_annotations or new format with frame_annotations
                    if "frame_annotations" in annotationData:
                        self.frameAnnotations = annotationData.get("frame_annotations", {})
                    elif "region_annotations" in annotationData:
                        # Convert old format to new format
                        oldAnnotations = annotationData.get("region_annotations", {})
                        for frameName, regions in oldAnnotations.items():
                            # Convert region list to binary: hasSmoke = len(regions) > 0
                            self.frameAnnotations[frameName] = len(regions) > 0
                
        except Exception as e:
            # Silent fail for loading existing annotations
            pass
            
    def updateMinivideoInfo(self):
        """Update mini-video navigation info"""
        pass
            
    def updateInfoDisplay(self):
        """Update the information display based on current workflow state"""
        if self.workflowState == "videoReview":
            self.updateVideoInfoDisplay()
        elif self.workflowState == "frameAnnotation":
            self.updateFrameInfoDisplay()
            
    def updateVideoInfoDisplay(self):
        """Update the video information display"""
        if self.minivideoFolders:
            currentMinivideo = self.currentMinivideoIndex + 1
            totalMinivideos = len(self.minivideoFolders)
            self.videoCurrentLabel.config(text=f"Video: {currentMinivideo}/{totalMinivideos}")
        else:
            self.videoCurrentLabel.config(text="Video: 0/0")
    
    def updateFrameInfoDisplay(self):
        """Update the frame information display"""
        if not self.frameFiles:
            return
            
        totalFrames = len(self.frameFiles)
        currentFrame = self.currentFrameIndex + 1
        annotatedFrames = len(self.frameAnnotations)
        progress = (annotatedFrames / totalFrames * 100) if totalFrames > 0 else 0
        
        self.currentFrameLabel.config(text=f"Frame: {currentFrame}/{totalFrames}")
        self.progressLabel.config(text=f"Progress: {progress:.1f}% ({annotatedFrames}/{totalFrames})")
        
    def previousFrame(self):
        """Navigate to previous frame"""
        if (self.workflowState != "frameAnnotation" or not self.frameFiles or 
            self.currentFrameIndex <= 0):
            return
        
        self.currentFrameIndex -= 1
        
        self.displayCurrentFrame()
        self.updateInfoDisplay()
        self.updateNavigationButtons()
            
    def nextFrame(self):
        """Navigate to next frame"""
        if (self.workflowState != "frameAnnotation" or not self.frameFiles or
            self.currentFrameIndex >= len(self.frameFiles) - 1):
            return
        
        # Check if current frame is annotated before allowing navigation
        if not self.isCurrentFrameAnnotated():
            messagebox.showwarning("Annotation Required", 
                                 "Please annotate the current frame before moving to the next frame.\n"
                                 "Click 'Smoke' or 'No Smoke' to continue.")
            return
            
        self.currentFrameIndex += 1
        self.displayCurrentFrame()
        self.updateInfoDisplay()
        self.updateNavigationButtons()
            
    def previousMinivideo(self):
        """Navigate to previous mini-video"""
        if self.minivideoFolders and self.currentMinivideoIndex > 0:
            self.currentMinivideoIndex -= 1
            self.workflowState = "videoReview"
            self.loadFrames(self.minivideoFolders[self.currentMinivideoIndex])
            self.updateMinivideoInfo()
            self.updateNavigationButtons()
            
    def nextMinivideo(self):
        """Navigate to next mini-video"""
        if self.minivideoFolders and self.currentMinivideoIndex < len(self.minivideoFolders) - 1:
            # Check if current mini-video is fully annotated before allowing navigation
            if not self.isCurrentMinivideoFullyAnnotated():
                messagebox.showwarning("Annotation Required", 
                                     "Please complete annotation of all frames in the current mini-video before moving to the next one.\n"
                                     "Use 'Start Frame Annotation' to annotate remaining frames.")
                return
                
            self.currentMinivideoIndex += 1
            self.workflowState = "videoReview"
            self.loadFrames(self.minivideoFolders[self.currentMinivideoIndex])
            self.updateMinivideoInfo()
            self.updateNavigationButtons()
            
    def autoSave(self):
        """Auto-save annotations in both JSON (temporary) and YOLO format"""
        if not self.currentMinivideoFolder:
            return
            
        try:
            # Save in JSON format for temporary storage/backup
            videoName = os.path.basename(self.currentVideoFolder) if self.currentVideoFolder else "unknown"
            minivideoName = os.path.basename(self.currentMinivideoFolder)
            autoSavePath = os.path.join(os.path.dirname(self.currentMinivideoFolder), f"auto_save_{videoName}_{minivideoName}.json")
            
            annotationData = {
                "video_folder": self.currentVideoFolder,
                "minivideo_folder": self.currentMinivideoFolder,
                "total_frames": len(self.frameFiles) if self.frameFiles else 0,
                "annotated_frames": len(self.frameAnnotations),
                "timestamp": datetime.now().isoformat(),
                "frame_annotations": self.frameAnnotations  # New binary format
            }
            
            with open(autoSavePath, 'w') as f:
                json.dump(annotationData, f, indent=2)
            
            # Save in YOLO format (main output format) - only if we have annotations
            if self.frameAnnotations:
                self.saveYoloAnnotations()
                
        except Exception as e:
            print(f"Error in auto-save: {e}")  # Show errors for debugging

    def setVideoReviewMode(self):
        """Switch to video review mode"""
        self.workflowState = "videoReview"
        self.videoReviewFrame.pack(fill=tk.X, padx=20, pady=15)
        self.frameAnnotationFrame.pack_forget()
        self.stopVideoPlayback()
        self.updateInfoDisplay()
        self.updateNavigationButtons()
        
    def setFrameAnnotationMode(self):
        """Switch to frame annotation mode"""
        self.workflowState = "frameAnnotation"
        self.videoReviewFrame.pack_forget()
        self.frameAnnotationFrame.pack(fill=tk.X, padx=20, pady=15)
        self.stopVideoPlayback()
        
        # Load frame files and start annotation
        self.loadFrameFiles()
        if self.frameFiles:
            # Go to first unannotated frame
            self.currentFrameIndex = self.findFirstUnannotatedFrame()
            self.displayCurrentFrame()
            self.updateInfoDisplay()
            self.updateNavigationButtons()
            self.updateAnnotationButtonColors()

    def startFrameAnnotation(self):
        """Start the frame annotation process"""
        self.setFrameAnnotationMode()
        
        # Show helpful message if starting at a non-zero frame
        if hasattr(self, 'currentFrameIndex') and self.currentFrameIndex > 0:
            firstUnannotated = self.currentFrameIndex + 1
            totalFrames = len(self.frameFiles) if self.frameFiles else 0
            messagebox.showinfo("Auto-positioned", 
                              f"Automatically start where you left: {firstUnannotated}/{totalFrames}")

    def markSmoke(self):
        """Mark current frame as having smoke and advance to next frame"""
        if self.workflowState != "frameAnnotation" or not self.frameFiles:
            return
            
        framePath = self.frameFiles[self.currentFrameIndex]
        frameName = os.path.basename(framePath)
        
        # Save annotation as smoke
        self.frameAnnotations[frameName] = True
        
        # Update button colors to show selection
        self.updateAnnotationButtonColors()
        
        self.autoSave()
        self.updateNavigationButtons()
        
        # Small delay to show the selection before advancing
        self.root.after(300, self.advanceToNextFrame)

    def markNoSmoke(self):
        """Mark current frame as no smoke and advance to next frame"""
        if self.workflowState != "frameAnnotation" or not self.frameFiles:
            return
            
        framePath = self.frameFiles[self.currentFrameIndex]
        frameName = os.path.basename(framePath)
        
        # Save annotation as no smoke
        self.frameAnnotations[frameName] = False
        
        # Update button colors to show selection
        self.updateAnnotationButtonColors()
        
        self.autoSave()
        self.updateNavigationButtons()
        
        # Small delay to show the selection before advancing
        self.root.after(300, self.advanceToNextFrame)
        
    def advanceToNextFrame(self):
        """Advance to the next frame or next mini-video (only if current frame is annotated)"""
        # Check if current frame is annotated before allowing auto-advance
        if not self.isCurrentFrameAnnotated():
            # This shouldn't happen since buttons call this after annotation,
            # but safety check in case of race conditions
            return
            
        if self.currentFrameIndex < len(self.frameFiles) - 1:
            self.currentFrameIndex += 1
            self.displayCurrentFrame()
            self.updateInfoDisplay()
            self.updateNavigationButtons()
        else:
            # At last frame, check if ALL frames in current mini-video are annotated
            if self.minivideoFolders and self.currentMinivideoIndex < len(self.minivideoFolders) - 1:
                # Only show completion message, do NOT auto-advance
                # User must manually navigate using the arrow button after completing all frames
                messagebox.showinfo("Mini-Video Complete", 
                                  "All frames in this mini-video have been annotated!\n"
                                  "Use the → button to navigate to the next mini-video.")
                self.updateNavigationButtons()  # This will enable the next mini-video button
            else:
                # This is the last mini-video
                messagebox.showinfo("Complete", "All frames in all mini-videos have been annotated!")
                
    def returnToVideoReview(self):
        """Return to video review mode"""
        self.setVideoReviewMode()

    def displayCurrentFrame(self):
        """Display current frame without grid overlay"""
        if not self.frameFiles or self.currentFrameIndex >= len(self.frameFiles):
            return
            
        try:
            # Load and resize image
            framePath = self.frameFiles[self.currentFrameIndex]
            image = Image.open(framePath)
            
            # Force canvas to update its size information
            self.videoCanvas.update_idletasks()
            
            # Calculate display size while maintaining aspect ratio
            canvasWidth = self.videoCanvas.winfo_width()
            canvasHeight = self.videoCanvas.winfo_height()
            
            # Better default sizes for different scenarios
            if canvasWidth <= 1 or canvasHeight <= 1:
                windowWidth = self.root.winfo_width()
                windowHeight = self.root.winfo_height()
                canvasWidth = max(600, windowWidth - 650)
                canvasHeight = max(450, windowHeight - 200)
            
            # Get original image dimensions
            imgWidth, imgHeight = image.size
            
            # Calculate scale factor
            scaleX = canvasWidth / imgWidth
            scaleY = canvasHeight / imgHeight
            scale = min(scaleX, scaleY) * 0.95
            
            # Calculate new dimensions
            newWidth = int(imgWidth * scale)
            newHeight = int(imgHeight * scale)
            
            # Resize image
            if newWidth != imgWidth or newHeight != imgHeight:
                image = image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)
            
            self.currentImage = ImageTk.PhotoImage(image)
            
            # Clear canvas and display image centered
            self.videoCanvas.delete("all")
            x = (canvasWidth - newWidth) // 2
            y = (canvasHeight - newHeight) // 2
            self.videoCanvas.create_image(x, y, anchor=tk.NW, image=self.currentImage)
            
            # Update frame info and show current annotation status
            frameName = os.path.basename(framePath)
            annotationText = ""
            if frameName in self.frameAnnotations:
                annotationText = " (SMOKE)" if self.frameAnnotations[frameName] else " (NO SMOKE)"
            self.frameInfoLabel.config(text=f"Frame: {frameName}{annotationText}")
            
            # Update button colors to show current annotation
            self.updateAnnotationButtonColors()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display frame: {str(e)}")

    def updateAnnotationButtonColors(self):
        """Update button colors to show current frame's annotation"""
        if self.workflowState != "frameAnnotation" or not self.frameFiles:
            return
            
        framePath = self.frameFiles[self.currentFrameIndex]
        frameName = os.path.basename(framePath)
        
        # Reset buttons to default gray
        if hasattr(self, 'smokeBtn'):
            self.smokeBtn.config(bg='#666666')
        if hasattr(self, 'noSmokeBtn'):
            self.noSmokeBtn.config(bg='#666666')
            
        # Highlight the button corresponding to the current annotation in orange
        if frameName in self.frameAnnotations:
            if self.frameAnnotations[frameName]:  # Smoke
                if hasattr(self, 'smokeBtn'):
                    self.smokeBtn.config(bg='#FF8C00')  # Orange for selected smoke
            else:  # No smoke
                if hasattr(self, 'noSmokeBtn'):
                    self.noSmokeBtn.config(bg='#FF8C00')  # Orange for selected no smoke

    # Simplify existing methods - remove complex workflow logic
    def startVideoReview(self):
        """Start video review - just display the video"""
        self.setVideoReviewMode()
        if self.currentVideoFile:
            try:
                self.videoCap = cv2.VideoCapture(self.currentVideoFile)
                ret, frame = self.videoCap.read()
                if ret:
                    self.displayVideoFrame(frame)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load video: {str(e)}")

    def toggleVideoPlayback(self):
        """Toggle video play/pause"""
        if not self.currentVideoFile:
            return
            
        if self.videoPlaying:
            self.videoPlaying = False
            self.playPauseBtn.config(text="Play Video")
        else:
            self.videoPlaying = True
            self.playPauseBtn.config(text="Pause Video")
            self.playVideo()

    def stopVideoPlayback(self):
        """Stop video playback"""
        self.videoPlaying = False
        if hasattr(self, 'playPauseBtn'):
            self.playPauseBtn.config(text="Play Video")

    def calculateButtonDimensions(self):
        """Calculate button dimensions based on proportional window size with 4K as baseline
        
        Returns:
            tuple: (buttonWidth, buttonHeight, buttonFont)
        """
        # Get current window dimensions for proportional scaling
        self.root.update_idletasks()
        windowWidth = self.root.winfo_width()
        windowHeight = self.root.winfo_height()
        
        # Use fallback dimensions if window not yet sized
        if windowWidth <= 1 or windowHeight <= 1:
            windowWidth = 1920  # Default to 1920x1080
            windowHeight = 1080

        # Base button dimensions optimized for 4K fullscreen/borderless (3840x2160)
        BASE_BUTTON_WIDTH = 40
        BASE_BUTTON_HEIGHT = 15
        BASE_BUTTON_FONT = 18
        REF_WIDTH = 3840 
        REF_HEIGHT = 2002

        # Calculate scaling factors - perfect at 4K proportional size, scaled for smaller
        scaleFactorW = windowWidth / REF_WIDTH
        scaleFactorH = windowHeight / REF_HEIGHT

        # Use minimum scaling factor to maintain proportions and ensure buttons fit
        scaleFactor = min(scaleFactorW, scaleFactorH) ** 0.4

        # Calculate scaled button dimensions with reasonable minimums
        buttonWidth = max(15, int(BASE_BUTTON_WIDTH * scaleFactor))
        buttonHeight = max(2, int(BASE_BUTTON_HEIGHT * scaleFactor))
        buttonFont = max(8, int(BASE_BUTTON_FONT * scaleFactor))
        
        return buttonWidth, buttonHeight, buttonFont

    def scaleAnnotationButtons(self):
        """Scale annotation buttons based on proportional window size with 4K as baseline"""
        try:
            # Get button dimensions using the reusable function
            buttonWidth, buttonHeight, buttonFont = self.calculateButtonDimensions()

            # Update video control buttons if they exist
            if hasattr(self, 'playPauseBtn'):
                self.playPauseBtn.config(width=buttonWidth, height=buttonHeight,
                                         font=('Arial', buttonFont, 'bold'))
            if hasattr(self, 'startAnnotationBtn'):
                self.startAnnotationBtn.config(width=buttonWidth, height=buttonHeight,
                                                font=('Arial', buttonFont, 'bold'))
            if hasattr(self, 'returnToVideoBtn'):
                self.returnToVideoBtn.config(width=buttonWidth - 10, height=buttonHeight - 10,
                                              font=('Arial', buttonFont, 'bold'))
                
            # Update annotation control buttons if they exist
            if hasattr(self, 'smokeBtn'):
                self.smokeBtn.config(width=buttonWidth, height=buttonHeight,
                                     font=('Arial', buttonFont, 'bold'))
            if hasattr(self, 'noSmokeBtn'):
                self.noSmokeBtn.config(width=buttonWidth, height=buttonHeight,
                                       font=('Arial', buttonFont, 'bold'))
                
        except Exception as e:
            # Silent fail for button scaling
            pass

    def updateNavigationButtons(self):
        """Update the state of navigation buttons"""
        if not hasattr(self, 'prevFrameBtn') or not hasattr(self, 'nextFrameBtn'):
            return
            
        # Enable/disable frame navigation buttons
        if self.frameFiles:
            # Previous frame button
            if self.currentFrameIndex > 0:
                self.prevFrameBtn.config(state='normal')
            else:
                self.prevFrameBtn.config(state='disabled')
                
            # Next frame button - only enable if current frame is annotated
            if (self.currentFrameIndex < len(self.frameFiles) - 1 and 
                self.isCurrentFrameAnnotated()):
                self.nextFrameBtn.config(state='normal')
            else:
                self.nextFrameBtn.config(state='disabled')
        else:
            self.prevFrameBtn.config(state='disabled')
            self.nextFrameBtn.config(state='disabled')
            
        # Enable/disable mini-video navigation buttons
        if self.minivideoFolders:
            # Previous mini-video button
            if self.currentMinivideoIndex > 0:
                self.prevMinivideoBtn.config(state='normal')
            else:
                self.prevMinivideoBtn.config(state='disabled')
                
            # Next mini-video button - only enable if current mini-video is fully annotated
            if (self.currentMinivideoIndex < len(self.minivideoFolders) - 1 and 
                self.isCurrentMinivideoFullyAnnotated()):
                self.nextMinivideoBtn.config(state='normal')
            else:
                self.nextMinivideoBtn.config(state='disabled')
        else:
            self.prevMinivideoBtn.config(state='disabled')
            self.nextMinivideoBtn.config(state='disabled')

    def displayVideoFrame(self, frame):
        """Display a video frame on the canvas"""
        try:
            # Convert frame from BGR to RGB
            frameRgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            image = Image.fromarray(frameRgb)
            
            # Force canvas to update its size information
            self.videoCanvas.update_idletasks()
            
            # Calculate display size while maintaining aspect ratio
            canvasWidth = self.videoCanvas.winfo_width()
            canvasHeight = self.videoCanvas.winfo_height()
            
            if canvasWidth <= 1 or canvasHeight <= 1:
                canvasWidth = 640
                canvasHeight = 480
            
            # Get original image dimensions
            imgWidth, imgHeight = image.size
            
            # Calculate scale factor
            scaleX = canvasWidth / imgWidth
            scaleY = canvasHeight / imgHeight
            scale = min(scaleX, scaleY) * 0.95
            
            # Calculate new dimensions
            newWidth = int(imgWidth * scale)
            newHeight = int(imgHeight * scale)
            
            # Resize image
            if newWidth != imgWidth or newHeight != imgHeight:
                image = image.resize((newWidth, newHeight), Image.Resampling.LANCZOS)
            
            self.currentImage = ImageTk.PhotoImage(image)
            
            # Clear canvas and display image centered
            self.videoCanvas.delete("all")
            x = (canvasWidth - newWidth) // 2
            y = (canvasHeight - newHeight) // 2
            self.videoCanvas.create_image(x, y, anchor=tk.NW, image=self.currentImage)
            
        except Exception as e:
            pass  # Silent fail for video display

    def playVideo(self):
        """Play video continuously"""
        if not self.videoPlaying or not self.videoCap:
            return
            
        ret, frame = self.videoCap.read()
        if ret:
            self.displayVideoFrame(frame)
            # Schedule next frame (about 30 FPS)
            fps = 25
            millisecondPerVideo = int(1000 / fps)
            self.root.after(millisecondPerVideo, self.playVideo)
        else:
            # End of video, reset
            self.videoPlaying = False
            self.playPauseBtn.config(text="Play Video")
            if self.videoCap:
                self.videoCap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to beginning

    def onClosing(self):
        """Handle window closing event"""
        # Clean up video capture
        if hasattr(self, 'videoCap') and self.videoCap:
            self.videoCap.release()
        
        # Destroy the window
        self.root.quit()
        self.root.destroy()

    def isMinivideoFullyAnnotated(self, minivideoIndex):
        """Check if a mini-video is fully annotated"""
        # For simplified version, just return True to allow navigation
        return True

    def isCurrentMinivideoFullyAnnotated(self):
        """Check if the current mini-video is fully annotated"""
        if not self.currentMinivideoFolder:
            return False
            
        # Get all frame files for current mini-video
        try:
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
            allFrameFiles = []
            for ext in extensions:
                allFrameFiles.extend(glob.glob(os.path.join(self.currentMinivideoFolder, ext)))
            
            if not allFrameFiles:
                return True  # No frames to annotate
                
            # Check if all frames are annotated
            totalFrames = len(allFrameFiles)
            annotatedFrames = len(self.frameAnnotations)
            
            # Verify each frame file is actually annotated
            for frameFile in allFrameFiles:
                frameName = os.path.basename(frameFile)
                if frameName not in self.frameAnnotations:
                    return False
                    
            return annotatedFrames >= totalFrames
            
        except Exception as e:
            return False

    def isCurrentFrameAnnotated(self):
        """Check if current frame is annotated"""
        if not self.frameFiles:
            return False
            
        framePath = self.frameFiles[self.currentFrameIndex]
        frameName = os.path.basename(framePath)
        isAnnotated = frameName in self.frameAnnotations
        
        return isAnnotated

    def checkAllFramesAnnotated(self):
        """Check if all frames are annotated and handle completion"""
        if not self.frameFiles:
            return
            
        totalFrames = len(self.frameFiles)
        annotatedFrames = len(self.frameAnnotations)
        
        if annotatedFrames >= totalFrames:
            messagebox.showinfo("Complete", "All frames have been annotated!")
            self.workflowState = "completed"

    def autoAdvanceFrame(self):
        """Auto advance to next frame"""
        self.advanceToNextFrame()

    def setupKeyboardShortcuts(self):
        """Setup keyboard shortcuts for the application"""
        self.root.bind('<Key>', self.onKeyPress)
        self.root.focus_set()  # Ensure the root window can receive key events
        
    def onKeyPress(self, event):
        """Handle keyboard shortcuts"""
        if self.workflowState != "frameAnnotation":
            return
            
        key = event.keysym.lower()
        
        # 's' for smoke
        if key == 's':
            self.markSmoke()
        # 'n' for no smoke
        elif key == 'n':
            self.markNoSmoke()
        # Left/Right arrows for navigation
        elif key == 'left':
            self.previousFrame()
        elif key == 'right':
            self.nextFrame()
    
    def getFrameNumberFromFilename(self, filename):
        """Extract frame number from filename (e.g., 'Frame_08128_43326.jpg' -> relative index)"""
        try:
            # Remove extension and split by underscore
            baseName = os.path.splitext(filename)[0]
            parts = baseName.split('_')
            
            # For filenames like "Frame_08128_43326.jpg", we want the middle number (08128)
            if len(parts) >= 2 and parts[1].isdigit():
                frameNumber = int(parts[1])
                
                # Convert absolute frame number to relative index (0-63)
                # We need to find the minimum frame number in this mini-video to calculate relative position
                if hasattr(self, 'frameFiles') and self.frameFiles:
                    minFrameNumber = min([int(os.path.splitext(os.path.basename(f))[0].split('_')[1]) 
                                         for f in self.frameFiles if '_' in os.path.basename(f)])
                    relativeIndex = frameNumber - minFrameNumber
                    return relativeIndex
                
                return 0  # Fallback if we can't calculate relative position
            
            # If no proper number found, try to extract any number
            import re
            numbers = re.findall(r'\d+', baseName)
            if numbers:
                return int(numbers[0])  # Take the first number found
            return 0  # Default fallback
        except:
            return 0  # Default fallback
    
    def saveYoloAnnotations(self):
        if not self.currentMinivideoFolder or not self.frameAnnotations:
            return

        try:
            minivideoName = os.path.basename(self.currentMinivideoFolder)
            yoloFilePath = os.path.join(self.currentMinivideoFolder, f"{minivideoName}.txt")

            resolutionWidth = 192
            resolutionHeight = 192
            regionWidth = resolutionWidth // 3   # 64
            regionHeight = resolutionHeight // 3 # 64

            with open(yoloFilePath, 'w') as f:
                for frameName, hasSmoke in self.frameAnnotations.items():
                    frameNumber = self.getFrameNumberFromFilename(frameName)
                    if not (0 <= frameNumber < regionHeight):
                        print(f"Warning: Frame number {frameNumber} out of range for {frameName}")
                        continue  # Only frames 0-63 valid

                    # classId: 0 for smoke, 1 for no smoke
                    classId = 0 if hasSmoke else 1

                    bboxHeight = 1 / resolutionHeight  # 1 pixel height
                    bboxWidth = regionWidth / resolutionWidth  # 1/3

                    for regionRow in range(3):
                        for regionCol in range(3):
                            centerX = (regionCol * regionWidth + regionWidth / 2) / resolutionWidth
                            centerY = (regionRow * regionHeight + frameNumber + 0.5) / resolutionHeight

                            f.write(f"{classId} {centerX:.6f} {centerY:.6f} {bboxWidth:.6f} {bboxHeight:.6f}\n")

            print(f"YOLO annotations saved: {yoloFilePath} with {len(self.frameAnnotations)} annotations")

        except Exception as e:
            print(f"Error saving YOLO annotations: {e}")

    def findFirstIncompleteMinivideo(self):
        """Find the index of the first mini-video that is not completely annotated"""
        for i, minivideoFolder in enumerate(self.minivideoFolders):
            # Temporarily set current folder to check annotations
            tempCurrentFolder = self.currentMinivideoFolder
            tempAnnotations = self.frameAnnotations.copy()
            
            self.currentMinivideoFolder = minivideoFolder
            self.frameAnnotations = {}
            self.loadExistingAnnotations()
            
            isComplete = self.isCurrentMinivideoFullyAnnotated()
            
            # Restore original state
            self.currentMinivideoFolder = tempCurrentFolder
            self.frameAnnotations = tempAnnotations
            
            if not isComplete:
                return i
                
        # If all are complete, return 0 (first video)
        return 0

    def findFirstUnannotatedFrame(self):
        """Find the index of the first frame that is not annotated"""
        if not self.frameFiles:
            return 0
            
        for i, frameFile in enumerate(self.frameFiles):
            frameName = os.path.basename(frameFile)
            if frameName not in self.frameAnnotations:
                return i
                
        # If all frames are annotated, return 0 (first frame)
        return 0

    def findFirstIncompleteVideoFolder(self):
        """Find the index of the first video folder that has incomplete annotations"""
        for i, videoFolder in enumerate(self.videoFolders):
            # Check if this video folder has any incomplete mini-videos
            miniVideoFolders = []
            try:
                for item in os.listdir(videoFolder):
                    itemPath = os.path.join(videoFolder, item)
                    if os.path.isdir(itemPath) and item.startswith('mini_video'):
                        miniVideoFolders.append(itemPath)
                
                miniVideoFolders.sort(key=lambda x: int(os.path.basename(x).split('_')[-1]))
                
                # Check each mini-video in this folder
                for minivideoFolder in miniVideoFolders:
                    # Temporarily check if this mini-video is complete
                    tempCurrentFolder = self.currentMinivideoFolder
                    tempAnnotations = self.frameAnnotations.copy()
                    
                    self.currentMinivideoFolder = minivideoFolder
                    self.frameAnnotations = {}
                    self.loadExistingAnnotations()
                    
                    isComplete = self.isCurrentMinivideoFullyAnnotated()
                    
                    # Restore original state
                    self.currentMinivideoFolder = tempCurrentFolder
                    self.frameAnnotations = tempAnnotations
                    
                    if not isComplete:
                        return i  # Found incomplete mini-video in this folder
                        
            except Exception as e:
                continue  # Skip this folder if there's an error
                
        # If all video folders are complete, return 0 (first folder)
        return 0

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = SmokeAnnotationGUI(root)
    
    # Bind window closing event
    root.protocol("WM_DELETE_WINDOW", app.onClosing)
    
    root.mainloop()

if __name__ == "__main__":
    main()