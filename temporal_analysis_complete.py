#!/usr/bin/env python3

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
    def __init__(self, 
                 frame_size: Tuple[int, int] = (1920, 1080),
                 num_regions: int = 9,
                 num_bins: int = 64,
                 temporal_length: int = 64):
        

        self.frame_size = frame_size
        self.num_regions = num_regions
        self.num_bins = num_bins
        self.temporal_length = temporal_length
        
        # Validate parameters
        if self.num_regions != 9:
            raise ValueError("num_regions must be 9 for 3x3 grid")
        if self.temporal_length != 64:
            logger.warning(f"Recommended temporal_length is 64, got {temporal_length}")
        
    
    def define_overlapping_regions(self) -> List[Dict]:

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
        
        return regions
    
    def compute_saturation_histogram(self, frame: np.ndarray, region_bounds: Tuple[int, int, int, int]) -> np.ndarray:

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
        

        return region_histories
    
    def create_3x3_temporal_grid(self, region_histories: List[List[np.ndarray]]) -> np.ndarray:

        # Input validation
        if not region_histories:
            raise ValueError("region_histories cannot be empty")
        
        if len(region_histories) != self.num_regions:
            raise ValueError(f"Expected {self.num_regions} regions, got {len(region_histories)}")
        
        # Input validation
        if not region_histories:
            raise ValueError("region_histories cannot be empty")
        
        if len(region_histories) != self.num_regions:
            raise ValueError(f"Expected {self.num_regions} regions, got {len(region_histories)}")
        
        # Data shape validation and conversion (no brightness scale validation needed)
        validated_regions = []
        for i, region_history in enumerate(region_histories):
            if not region_history:
                logger.warning(f"Region {i+1}: Empty history, using zero array")
                # Create zero array with expected shape
                zero_array = np.zeros((self.temporal_length, self.num_bins), dtype=np.float64)
                validated_regions.append([zero_array[j] for j in range(self.temporal_length)])
                continue
            
            try:
                # Validate each histogram entry
                validated_history = []
                for j, hist in enumerate(region_history):
                    if not isinstance(hist, np.ndarray):
                        raise ValueError(f"Region {i+1}, frame {j}: Expected numpy array, got {type(hist)}")
                    
                    if hist.ndim != 1:
                        raise ValueError(f"Region {i+1}, frame {j}: Expected 1D array, got {hist.ndim}D")
                    
                    if len(hist) == 0:
                        logger.warning(f"Region {i+1}, frame {j}: Empty histogram, using zeros")
                        hist = np.zeros(self.num_bins, dtype=np.float64)
                    
                    validated_history.append(hist.astype(np.float64))
                
                validated_regions.append(validated_history)
                
            except Exception as e:
                raise ValueError(f"Region {i+1}: Invalid data structure - {e}")
        
        # Create 192x192 output image
        output_image = np.zeros((192, 192), dtype=np.uint8)
        
        # Each region gets exactly 64x64 pixels
        region_size = 64
        
        # Process each region independently for optimal AI training
        all_processed_regions = []
    
        
        for i, region_history in enumerate(validated_regions):
            try:
                region_data = np.array(region_history)  # Shape: (temporal_length, num_bins)
                
                # Additional safety checks
                if region_data.size == 0:
                    logger.warning(f"Region {i+1}: Empty region data, using zeros")
                    region_data = np.zeros((self.temporal_length, self.num_bins), dtype=np.float64)
                
                # Keep raw histogram data - no artificial scaling for AI training
                # Only ensure non-negative values (histograms should already be non-negative)
                region_raw = np.clip(region_data, 0.0, None)
                
                all_processed_regions.append(region_raw)
                
            except Exception as e:
                logger.error(f"Region {i+1}: Error during processing - {e}")
                # Use zero array as fallback
                zero_array = np.zeros((self.temporal_length, self.num_bins), dtype=np.float64)
                all_processed_regions.append(zero_array)
        
        # Apply independent normalization per region - each region treated as separate temporal data
        for i, region_raw in enumerate(all_processed_regions):
            try:
                # Calculate grid position (3x3)
                row = i // 3  # 0, 1, 2
                col = i % 3   # 0, 1, 2
                
                # Calculate exact pixel coordinates ensuring 64x64 regions
                y_start = row * region_size 
                y_end = y_start + region_size
                x_start = col * region_size 
                x_end = x_start + region_size
                
                # Apply INDEPENDENT normalization per region for maximum contrast
                # Each region is treated as a separate temporal data source
                region_min = region_raw.min()
                region_max = region_raw.max()
                
                if not np.isfinite(region_max) or not np.isfinite(region_min):
                    logger.warning(f"Region {i+1}: Invalid range min={region_min}, max={region_max}, using fallback")
                    # Use uniform fallback values
                    region_normalized = np.full(region_raw.shape, 128, dtype=np.float64)  # Mid-gray fallback
                elif region_max == region_min:
                    # Handle uniform regions: if all values are the same
                    if region_max > 0:
                        logger.debug(f"Region {i+1}: Uniform region (all values = {region_max:.6f}), setting to 255")
                        region_normalized = np.ones(region_raw.shape, dtype=np.float64)  # All 255
                    else:
                        logger.debug(f"Region {i+1}: Empty region (all zeros), keeping as 0")
                        region_normalized = np.zeros(region_raw.shape, dtype=np.float64)  # All 0
                else:
                    # Normal case: normalize so min->0, max->255 (each region uses full dynamic range)
                    region_normalized = (region_raw - region_min) / (region_max - region_min)
                
                # Convert to uint8 - each region independently normalized
                region_uint8 = (region_normalized * 255).astype(np.uint8)

                # DIMENSION VALIDATION AND PADDING/CLAMPING
                # Ensure we have exactly temporal_length frames (rows dimension)
                if region_uint8.shape[0] < self.temporal_length:
                    # Pad with zeros if fewer frames than expected
                    padding_needed = self.temporal_length - region_uint8.shape[0]
                    padding = np.zeros((padding_needed, region_uint8.shape[1]), dtype=np.uint8)
                    region_temporal_fixed = np.vstack([region_uint8, padding])
                    logger.warning(f"Region {i+1}: Padded {padding_needed} temporal frames (had {region_uint8.shape[0]}, expected {self.temporal_length})")
                else:
                    region_temporal_fixed = region_uint8[:self.temporal_length]  # Clamp to expected frame count
                    if region_uint8.shape[0] > self.temporal_length:
                        logger.warning(f"Region {i+1}: Clamped temporal frames (had {region_uint8.shape[0]}, expected {self.temporal_length})")
                
                # Ensure we have exactly num_bins histogram bins (columns dimension)
                if region_temporal_fixed.shape[1] < self.num_bins:
                    # Pad with zeros if fewer bins than expected
                    padding_needed = self.num_bins - region_temporal_fixed.shape[1]
                    padding = np.zeros((region_temporal_fixed.shape[0], padding_needed), dtype=np.uint8)
                    region_padded = np.hstack([region_temporal_fixed, padding])
                    logger.warning(f"Region {i+1}: Padded {padding_needed} histogram bins (had {region_temporal_fixed.shape[1]}, expected {self.num_bins})")
                elif region_temporal_fixed.shape[1] > self.num_bins:
                    # Clamp to expected number of bins if too many
                    region_padded = region_temporal_fixed[:, :self.num_bins]
                    logger.warning(f"Region {i+1}: Clamped histogram bins (had {region_temporal_fixed.shape[1]}, expected {self.num_bins})")
                else:
                    region_padded = region_temporal_fixed
                
                # Verify final dimensions
                expected_shape = (self.temporal_length, self.num_bins)
                if region_padded.shape != expected_shape:
                    raise ValueError(f"Region {i+1}: Shape mismatch after padding/clamping. Got {region_padded.shape}, expected {expected_shape}")
                
                # No resize needed - data is already exactly 64x64
                region_resized = region_padded

                # Place in grid using safe indexing (never exceeds bounds)
                output_image[y_start:y_end, x_start:x_end] = region_resized
                
            except Exception as e:
                logger.error(f"Region {i+1}: Error during processing - {e}")
                # Fill with zeros as fallback
                y_start = (i // 3) * region_size 
                y_end = y_start + region_size
                x_start = (i % 3) * region_size 
                x_end = x_start + region_size
                output_image[y_start:y_end, x_start:x_end] = 0
        
        return output_image
    
    def generate_from_frames(self, frames: List[np.ndarray]) -> np.ndarray:
        try:
            # Process frames to get regional histories
            region_histories = self.process_frame_sequence(frames)
            
            # Generate 3x3 grid temporal analysis
            temporal_image = self.create_3x3_temporal_grid(region_histories)
            
            return temporal_image
            
        except Exception as e:
            logger.error(f"Error generating temporal analysis: {e}")
            raise