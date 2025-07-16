#!/usr/bin/env python3
"""
Complete 3x3 Temporal Analysis Generator

This single file contains everything needed to generate 192x192 temporal analysis images 
from 64 standardized video frames (1920x1080). Designed as a backend for annotation GUI systems.

Key Features:
- Processes 64 frames from video segments
- Standardizes all frames to 1920x1080
- Generates 3x3 grid temporal analysis (192x192 output)
- 9 overlapping regions (R1-R9) with 40% coverage, 20% overlap
- Ready for integration with annotation GUI

Author: Saturation Analysis Team
Date: 2025-07-16
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Union
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TemporalAnalysisGenerator:
    """
    Complete temporal analysis generator for annotation GUI backend.
    
    This class processes 64 standardized video frames (1920x1080) and creates
    192x192 temporal analysis images with 9 overlapping regions in a 3x3 grid.
    """
    
    def __init__(self, 
                 frame_size: Tuple[int, int] = (1920, 1080),
                 num_regions: int = 9,
                 num_bins: int = 32,
                 temporal_length: int = 64,
                 brightness_scale: float = 6.0):
        """
        Initialize the temporal analysis generator.
        
        Args:
            frame_size: Target frame dimensions (width, height)
            num_regions: Number of regions in 3x3 grid (must be 9)
            num_bins: Number of saturation histogram bins
            temporal_length: Number of frames to process (should be 64)
            brightness_scale: Brightness enhancement factor
        """
        self.frame_size = frame_size
        self.num_regions = num_regions
        self.num_bins = num_bins
        self.temporal_length = temporal_length
        self.brightness_scale = brightness_scale
        
        # Validate parameters
        if self.num_regions != 9:
            raise ValueError("num_regions must be 9 for 3x3 grid")
        if self.temporal_length != 64:
            logger.warning(f"Recommended temporal_length is 64, got {temporal_length}")
            
        logger.info(f"Initialized TemporalAnalysisGenerator with {frame_size} frames")
    
    def define_overlapping_regions(self) -> List[Dict]:
        """
        Define 9 overlapping regions in a 3x3 grid with 40% coverage and 20% overlap.
        
        Returns:
            List of region dictionaries with name and bounds
        """
        regions = []
        frame_width, frame_height = self.frame_size
        
        # Each region covers 40% of frame dimensions
        region_width = int(frame_width * 0.4)
        region_height = int(frame_height * 0.4)
        
        # Grid positions with 30% spacing (creates 20% overlap)
        x_positions = [0, int(frame_width * 0.3), int(frame_width * 0.6)]
        y_positions = [0, int(frame_height * 0.3), int(frame_height * 0.6)]
        
        for row in range(3):
            for col in range(3):
                x_start = x_positions[col]
                y_start = y_positions[row]
                x_end = min(x_start + region_width, frame_width)
                y_end = min(y_start + region_height, frame_height)
                
                regions.append({
                    'name': f'R{row*3 + col + 1}',
                    'bounds': (x_start, y_start, x_end, y_end),
                    'row': row,
                    'col': col
                })
        
        logger.debug(f"Defined {len(regions)} overlapping regions")
        return regions
    
    def compute_saturation_histogram(self, frame: np.ndarray, region_bounds: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Compute normalized saturation histogram for a region.
        
        Args:
            frame: Input frame (BGR format)
            region_bounds: (x_start, y_start, x_end, y_end)
            
        Returns:
            Normalized histogram array (32 bins)
        """
        x_start, y_start, x_end, y_end = region_bounds
        
        # Extract region and convert to HSV
        region_frame = frame[y_start:y_end, x_start:x_end]
        hsv = cv2.cvtColor(region_frame, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1] / 255.0
        
        # Compute histogram
        hist, _ = np.histogram(saturation, bins=self.num_bins, range=(0, 1))
        
        # Normalize histogram
        hist_norm = hist / (hist.sum() + 1e-6)
        
        return hist_norm
    
    def process_frame_sequence(self, frames: List[np.ndarray]) -> List[List[np.ndarray]]:
        """
        Process a sequence of frames to extract regional saturation histograms.
        
        Args:
            frames: List of BGR frames (should be 64 frames)
            
        Returns:
            List of region histories, each containing temporal histograms
        """
        if len(frames) != self.temporal_length:
            logger.warning(f"Expected {self.temporal_length} frames, got {len(frames)}")
        
        # Ensure all frames are standardized to target size
        standardized_frames = []
        for frame in frames:
            if frame.shape[:2] != (self.frame_size[1], self.frame_size[0]):
                frame_resized = cv2.resize(frame, self.frame_size)
                standardized_frames.append(frame_resized)
            else:
                standardized_frames.append(frame)
        
        # Define 3x3 overlapping regions
        regions = self.define_overlapping_regions()
        
        # Initialize region histories
        region_histories = [[] for _ in range(self.num_regions)]
        
        # Process each frame
        for frame_idx, frame in enumerate(standardized_frames):
            for region_idx, region in enumerate(regions):
                hist = self.compute_saturation_histogram(frame, region['bounds'])
                region_histories[region_idx].append(hist)
        
        logger.info(f"Processed {len(standardized_frames)} frames across {len(regions)} regions")
        return region_histories
    
    def create_3x3_temporal_grid(self, region_histories: List[List[np.ndarray]]) -> np.ndarray:
        """
        Create a 192x192 temporal analysis image with 3x3 grid layout.
        
        Each cell is 64x64 pixels representing one region's temporal data:
        - 64 frames (temporal axis)
        - 32 histogram bins (saturation axis)
        - Scaled to 64x64 using nearest neighbor interpolation
        - Brightness enhanced for visibility
        
        Args:
            region_histories: List of temporal histograms for each region
            
        Returns:
            192x192 grayscale temporal analysis image
        """
        # Create 192x192 output image
        output_image = np.zeros((192, 192), dtype=np.uint8)
        
        # Each region gets 64x64 pixels
        region_size = 64
        
        for i, region_history in enumerate(region_histories):
            # Calculate grid position (3x3)
            row = i // 3  # 0, 1, 2
            col = i % 3   # 0, 1, 2
            
            # Calculate pixel coordinates in output image
            y_start = row * region_size
            y_end = y_start + region_size
            x_start = col * region_size
            x_end = x_start + region_size
            
            # Process region data
            region_data = np.array(region_history)  # Shape: (temporal_length, num_bins)
            region_scaled = np.clip(region_data * self.brightness_scale * 255, 0, 255).astype(np.uint8)
            
            # Ensure we have exactly temporal_length frames
            if region_scaled.shape[0] < self.temporal_length:
                # Pad with zeros if less than temporal_length frames
                padding_needed = self.temporal_length - region_scaled.shape[0]
                padding = np.zeros((padding_needed, region_scaled.shape[1]), dtype=np.uint8)
                region_padded = np.vstack([region_scaled, padding])
            else:
                region_padded = region_scaled[:self.temporal_length]  # Take first temporal_length frames
            
            # Scale from temporal_length x num_bins to 64x64 using nearest neighbor interpolation
            region_resized = cv2.resize(region_padded, (region_size, region_size), 
                                      interpolation=cv2.INTER_NEAREST)
            
            # Place in grid
            output_image[y_start:y_end, x_start:x_end] = region_resized
        
        logger.info("Generated 192x192 temporal analysis grid")
        return output_image
    
    def load_video_frames(self, video_path: Union[str, Path], start_frame: int, frame_count: int = 64) -> List[np.ndarray]:
        """
        Load exactly 64 frames from video file starting at specified frame.
        
        Args:
            video_path: Path to video file
            start_frame: Starting frame index
            frame_count: Number of frames to load (default 64)
            
        Returns:
            List of BGR frames
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise IOError(f"Cannot open video: {video_path}")
        
        # Check if we have enough frames
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if start_frame + frame_count > total_frames:
            cap.release()
            raise ValueError(f"Not enough frames. Requested: {start_frame + frame_count}, Available: {total_frames}")
        
        # Set starting position
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        frames = []
        for i in range(frame_count):
            ret, frame = cap.read()
            if not ret:
                cap.release()
                raise RuntimeError(f"Failed to read frame {start_frame + i}")
            
            frames.append(frame)
        
        cap.release()
        
        logger.info(f"Loaded {len(frames)} frames from {video_path}")
        return frames
    
    def generate_from_frames(self, frames: List[np.ndarray]) -> np.ndarray:
        """
        Main interface: Generate temporal analysis from frame list.
        
        Args:
            frames: List of BGR frames (preferably 64 frames)
            
        Returns:
            192x192 temporal analysis image
        """
        try:
            # Process frames to get regional histories
            region_histories = self.process_frame_sequence(frames)
            
            # Generate 3x3 grid temporal analysis
            temporal_image = self.create_3x3_temporal_grid(region_histories)
            
            return temporal_image
            
        except Exception as e:
            logger.error(f"Error generating temporal analysis: {e}")
            raise
    
    def generate_from_video_segment(self, 
                                  video_path: Union[str, Path], 
                                  start_frame: int) -> np.ndarray:
        """
        Generate temporal analysis from a 64-frame video segment.
        
        Args:
            video_path: Path to video file
            start_frame: Starting frame index
            
        Returns:
            192x192 temporal analysis image
        """
        # Load 64 frames from video
        frames = self.load_video_frames(video_path, start_frame, self.temporal_length)
        
        # Generate temporal analysis
        return self.generate_from_frames(frames)
    
    def save_temporal_analysis(self, 
                             temporal_image: np.ndarray, 
                             output_path: Union[str, Path],
                             metadata: Optional[Dict] = None) -> None:
        """
        Save temporal analysis image and optional metadata.
        
        Args:
            temporal_image: 192x192 temporal analysis image
            output_path: Output file path
            metadata: Optional metadata to save alongside image
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save image
        success = cv2.imwrite(str(output_path), temporal_image)
        if not success:
            raise IOError(f"Failed to save image to {output_path}")
        
        logger.info(f"Saved temporal analysis to {output_path}")
        
        # Save metadata if provided
        if metadata is not None:
            metadata_path = output_path.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved metadata to {metadata_path}")


# ==================================================================================
# ANNOTATION GUI BACKEND INTEGRATION
# ==================================================================================

class AnnotationGUIBackend:
    """
    Complete backend for annotation GUI that integrates temporal analysis generation.
    
    This class provides all functionality needed for a GUI annotation system:
    - Load video and extract 64-frame segments
    - Generate temporal analysis for annotation
    - Save annotation results with metadata
    - Manage annotation workflow
    """
    
    def __init__(self, video_path: Union[str, Path]):
        """
        Initialize annotation backend with video file.
        
        Args:
            video_path: Path to the video file for annotation
        """
        self.video_path = Path(video_path)
        self.generator = TemporalAnalysisGenerator()
        self.current_segment_start = 0
        self.current_temporal_image = None
        
        # Validate video file
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        # Get video information
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise IOError(f"Cannot open video: {self.video_path}")
            
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        self.frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        print(f"📹 Loaded video: {self.video_path.name}")
        print(f"📊 Total frames: {self.total_frames}")
        print(f"🎬 FPS: {self.fps:.2f}")
        print(f"📐 Resolution: {self.frame_width}x{self.frame_height}")
    
    def get_available_segments(self) -> List[int]:
        """
        Get list of available 64-frame segments in the video.
        
        Returns:
            List of starting frame indices for valid 64-frame segments
        """
        available_segments = []
        segment_length = 64
        
        for start_frame in range(0, self.total_frames - segment_length + 1, segment_length):
            available_segments.append(start_frame)
        
        print(f"📊 Found {len(available_segments)} available 64-frame segments")
        return available_segments
    
    def load_segment_for_annotation(self, start_frame: int) -> np.ndarray:
        """
        Load a 64-frame segment and generate temporal analysis for annotation.
        
        Args:
            start_frame: Starting frame index for the segment
            
        Returns:
            192x192 temporal analysis image ready for annotation
        """
        # Validate frame range
        if start_frame + 64 > self.total_frames:
            raise ValueError(f"Not enough frames remaining. Start: {start_frame}, Total: {self.total_frames}")
        
        # Generate temporal analysis
        self.current_temporal_image = self.generator.generate_from_video_segment(
            self.video_path, start_frame
        )
        self.current_segment_start = start_frame
        
        print(f"🎯 Loaded segment for annotation: frames {start_frame}-{start_frame + 63}")
        return self.current_temporal_image
    
    def save_annotation(self, 
                       annotation_data: Dict,
                       output_dir: Union[str, Path] = "../output/annotations") -> str:
        """
        Save current temporal analysis with annotation data in organized folder structure.
        
        Creates folder structure:
        output_dir/
        ├── {video_name}/
        │   ├── temporal_analysis/
        │   │   ├── {video_name}_frames_{start:06d}_{end:06d}_temporal.png
        │   ├── metadata/
        │   │   ├── {video_name}_frames_{start:06d}_{end:06d}_annotation.json
        │   └── summary/
        │       └── {video_name}_segments_summary.json
        
        Args:
            annotation_data: Dictionary containing annotation information
            output_dir: Base directory to save annotation results
            
        Returns:
            Path to saved temporal analysis image
        """
        if self.current_temporal_image is None:
            raise RuntimeError("No temporal image loaded. Call load_segment_for_annotation() first.")
        
        # Create organized folder structure
        base_output_dir = Path(output_dir)
        video_name = self.video_path.stem
        
        # Create video-specific directory structure
        video_dir = base_output_dir / video_name
        temporal_dir = video_dir / "temporal_analysis"
        metadata_dir = video_dir / "metadata"
        summary_dir = video_dir / "summary"
        
        # Create all directories
        temporal_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename based on video and frame range
        filename = f"{video_name}_frames_{self.current_segment_start:06d}_{self.current_segment_start + 63:06d}"
        
        # Save temporal analysis image
        image_path = temporal_dir / f"{filename}_temporal.png"
        cv2.imwrite(str(image_path), self.current_temporal_image)
        
        # Create comprehensive metadata
        metadata = {
            "video_info": {
                "video_path": str(self.video_path),
                "video_name": self.video_path.name,
                "total_frames": self.total_frames,
                "fps": self.fps,
                "resolution": f"{self.frame_width}x{self.frame_height}"
            },
            "segment_info": {
                "start_frame": self.current_segment_start,
                "end_frame": self.current_segment_start + 63,
                "frame_count": 64
            },
            "temporal_analysis": {
                "image_path": str(image_path),
                "dimensions": "192x192",
                "regions": 9,
                "type": "3x3_grid",
                "region_layout": {
                    "R1": "Top-left", "R2": "Top-center", "R3": "Top-right",
                    "R4": "Middle-left", "R5": "Middle-center", "R6": "Middle-right", 
                    "R7": "Bottom-left", "R8": "Bottom-center", "R9": "Bottom-right"
                }
            },
            "annotation": annotation_data,
            "processing_info": {
                "generated_timestamp": "2025-07-16T10:30:00Z",
                "generator_version": "1.0.0"
            },
            "folder_structure": {
                "video_directory": str(video_dir),
                "temporal_analysis_dir": str(temporal_dir),
                "metadata_dir": str(metadata_dir),
                "summary_dir": str(summary_dir)
            }
        }
        
        # Save metadata in metadata directory
        metadata_path = metadata_dir / f"{filename}_annotation.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update or create segment summary
        self._update_segment_summary(summary_dir, video_name, self.current_segment_start, annotation_data)
        
        print(f"📁 Created folder structure: {video_dir}")
        print(f"💾 Saved temporal analysis: {image_path}")
        print(f"📋 Saved metadata: {metadata_path}")
        print(f"📊 Updated summary: {summary_dir / f'{video_name}_segments_summary.json'}")
        
        return str(image_path)
    
    def _update_segment_summary(self, summary_dir: Path, video_name: str, start_frame: int, annotation_data: Dict) -> None:
        """
        Update or create a summary of all processed segments for this video.
        
        Args:
            summary_dir: Directory to save summary
            video_name: Name of the video
            start_frame: Starting frame of current segment
            annotation_data: Current annotation data
        """
        summary_path = summary_dir / f"{video_name}_segments_summary.json"
        
        # Load existing summary or create new one
        if summary_path.exists():
            with open(summary_path, 'r') as f:
                summary = json.load(f)
        else:
            summary = {
                "video_name": video_name,
                "total_segments_processed": 0,
                "segments": [],
                "statistics": {
                    "smoke_detected_count": 0,
                    "no_smoke_count": 0,
                    "average_confidence": 0.0
                }
            }
        
        # Add current segment
        segment_info = {
            "segment_id": len(summary["segments"]) + 1,
            "start_frame": start_frame,
            "end_frame": start_frame + 63,
            "smoke_detected": annotation_data.get("smoke_detected", False),
            "confidence": annotation_data.get("confidence", 0.0),
            "annotator": annotation_data.get("annotator", "unknown"),
            "timestamp": annotation_data.get("timestamp", "2025-07-16T10:30:00Z")
        }
        
        summary["segments"].append(segment_info)
        summary["total_segments_processed"] = len(summary["segments"])
        
        # Update statistics
        smoke_count = sum(1 for s in summary["segments"] if s.get("smoke_detected", False))
        summary["statistics"]["smoke_detected_count"] = smoke_count
        summary["statistics"]["no_smoke_count"] = len(summary["segments"]) - smoke_count
        
        confidences = [s.get("confidence", 0.0) for s in summary["segments"] if s.get("confidence", 0.0) > 0]
        if confidences:
            summary["statistics"]["average_confidence"] = sum(confidences) / len(confidences)
        
        # Save updated summary
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
    
    def get_segment_info(self) -> Dict:
        """
        Get information about the currently loaded segment.
        
        Returns:
            Dictionary with segment information
        """
        if self.current_temporal_image is None:
            return {"status": "no_segment_loaded"}
        
        return {
            "status": "segment_loaded",
            "start_frame": self.current_segment_start,
            "end_frame": self.current_segment_start + 63,
            "image_shape": self.current_temporal_image.shape,
            "ready_for_annotation": True
        }


# ==================================================================================
# USAGE EXAMPLES AND HELPER FUNCTIONS
# ==================================================================================

def simple_generate_temporal_analysis(video_path: str, start_frame: int) -> np.ndarray:
    """
    Simple function to generate temporal analysis - use this for basic integration.
    
    Args:
        video_path: Path to video file
        start_frame: Starting frame index
        
    Returns:
        192x192 temporal analysis image
    """
    generator = TemporalAnalysisGenerator()
    return generator.generate_from_video_segment(video_path, start_frame)


def batch_process_video_segments(video_path: str, 
                                segment_starts: List[int], 
                                output_dir: Union[str, Path] = "../output/batch_processing") -> List[str]:
    """
    Process multiple video segments in batch with organized folder structure.
    
    Creates structure:
    output_dir/
    ├── {video_name}/
    │   ├── temporal_analysis/
    │   ├── metadata/
    │   ├── summary/
    │   └── batch_processing/
    │       └── batch_report.json
    
    Args:
        video_path: Path to video file
        segment_starts: List of starting frame indices
        output_dir: Output directory for results
        
    Returns:
        List of paths to generated temporal analysis images
    """
    backend = AnnotationGUIBackend(video_path)
    base_output_dir = Path(output_dir)
    video_name = Path(video_path).stem
    
    # Create batch-specific directory
    batch_dir = base_output_dir / video_name / "batch_processing"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    batch_report = {
        "video_name": video_name,
        "batch_start_time": "2025-07-16T10:30:00Z",
        "segments_requested": len(segment_starts),
        "segments_processed": 0,
        "segments_failed": 0,
        "results": []
    }
    
    for i, start_frame in enumerate(segment_starts):
        print(f"\n🔄 Processing segment {i+1}/{len(segment_starts)}: frames {start_frame}-{start_frame + 63}")
        
        try:
            # Load segment and generate temporal analysis
            temporal_image = backend.load_segment_for_annotation(start_frame)
            
            # Create automatic annotation data
            auto_annotation = {
                "type": "auto_generated",
                "batch_id": f"batch_{i+1:03d}",
                "processing_timestamp": "2025-07-16T10:30:00Z",
                "ready_for_manual_review": True,
                "auto_generated": True,
                "batch_index": i + 1
            }
            
            # Save with organized structure
            saved_path = backend.save_annotation(auto_annotation, base_output_dir)
            results.append(saved_path)
            
            # Add to batch report
            batch_report["results"].append({
                "segment_index": i + 1,
                "start_frame": start_frame,
                "end_frame": start_frame + 63,
                "status": "success",
                "temporal_analysis_path": saved_path
            })
            batch_report["segments_processed"] += 1
            
            print(f"   ✅ Saved: {Path(saved_path).name}")
            
        except Exception as e:
            print(f"   ❌ Error processing segment {start_frame}: {e}")
            batch_report["results"].append({
                "segment_index": i + 1,
                "start_frame": start_frame,
                "end_frame": start_frame + 63,
                "status": "failed",
                "error": str(e)
            })
            batch_report["segments_failed"] += 1
            continue
    
    # Save batch report
    batch_report["batch_end_time"] = "2025-07-16T10:30:00Z"
    batch_report_path = batch_dir / "batch_report.json"
    with open(batch_report_path, 'w') as f:
        json.dump(batch_report, f, indent=2)
    
    print(f"\n🎉 Batch processing complete!")
    print(f"📊 Processed: {batch_report['segments_processed']} segments")
    print(f"❌ Failed: {batch_report['segments_failed']} segments")
    print(f"📁 Organized in: {base_output_dir / video_name}")
    print(f"📋 Batch report: {batch_report_path}")
    
    return results


# ==================================================================================
# DEMO AND TESTING
# ==================================================================================

def demo_complete_workflow():
    """
    Demonstrate the complete annotation workflow.
    """
    print("🚀 Starting Complete Temporal Analysis Demo")
    print("=" * 60)
    
    # Test video path
    video_path = "../data/video33.mp4"
    
    try:
        # Initialize backend
        backend = AnnotationGUIBackend(video_path)
        
        # Get available segments
        segments = backend.get_available_segments()
        
        # Test with first segment
        start_frame = segments[0]
        print(f"\n📝 Testing with segment starting at frame {start_frame}")
        
        # Load segment for annotation
        temporal_image = backend.load_segment_for_annotation(start_frame)
        print(f"   ✅ Generated temporal analysis: {temporal_image.shape}")
        
        # Create sample annotation
        sample_annotation = {
            "annotator": "demo_user",
            "timestamp": "2025-07-16T10:30:00Z",
            "smoke_detected": True,
            "confidence": 0.92,
            "regions_with_smoke": [1, 3, 5, 7],
            "smoke_density": "heavy",
            "notes": "Clear smoke visible in multiple regions",
            "review_status": "completed"
        }
        
        # Save annotation
        saved_path = backend.save_annotation(sample_annotation)
        print(f"   💾 Annotation saved to: {Path(saved_path).name}")
        
        # Show segment info
        info = backend.get_segment_info()
        print(f"   📊 Segment info: {info['status']}")
        
        print("\n✅ Demo completed successfully!")
        print(f"📁 Check output/annotations directory for results")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Video file not found: {video_path}")
        print("   Please ensure video33.mp4 exists in the data directory")
        return False
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        return False


def test_simple_interface():
    """
    Test the simple interface function.
    """
    print("\n" + "=" * 60)
    print("🧪 Testing Simple Interface")
    print("=" * 60)
    
    video_path = "../data/video33.mp4"
    
    try:
        # Test simple function
        temporal_image = simple_generate_temporal_analysis(video_path, 1000)
        print(f"✅ Simple interface test: {temporal_image.shape}")
        
        # Save result
        output_path = "../output/simple_test.png"
        cv2.imwrite(output_path, temporal_image)
        print(f"💾 Saved test result: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Simple interface test failed: {e}")
        return False


if __name__ == "__main__":
    """
    Main execution - run demos and tests.
    """
    print("🎯 Complete 3x3 Temporal Analysis Generator")
    print("=" * 60)
    print("This single file contains everything needed for annotation GUI backend:")
    print("- TemporalAnalysisGenerator: Core temporal analysis")
    print("- AnnotationGUIBackend: Complete annotation workflow")
    print("- Helper functions: Simple integration and batch processing")
    print("=" * 60)
    
    # Run demo
    demo_success = demo_complete_workflow()
    
    # Test simple interface
    simple_success = test_simple_interface()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 INTEGRATION SUMMARY")
    print("=" * 60)
    
    if demo_success and simple_success:
        print("✅ All tests passed! Ready for GUI integration.")
        print("\n🎯 For GUI Integration:")
        print("1. Import this file: from temporal_analysis_complete import AnnotationGUIBackend")
        print("2. Initialize: backend = AnnotationGUIBackend('video.mp4')")
        print("3. Load segment: temporal_image = backend.load_segment_for_annotation(frame_start)")
        print("4. Save annotation: backend.save_annotation(annotation_data)")
        print("\n📊 Output: 192x192 temporal analysis images ready for annotation")
    else:
        print("❌ Some tests failed. Check error messages above.")
        
    print("=" * 60)
