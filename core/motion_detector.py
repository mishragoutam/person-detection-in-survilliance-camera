import cv2
import numpy as np

class CameraMotionDetector:
    """
    Detects camera PTZ movements by tracking background features.
    """
    def __init__(self, max_corners=100, quality_level=0.3, min_distance=7, block_size=7):
        self.max_corners = max_corners
        self.quality_level = quality_level
        self.min_distance = min_distance
        self.block_size = block_size
        
        self.prev_gray = None
        self.prev_pts = None

    def detect_motion(self, frame):
        """
        Returns (has_moved, zoom_scale).
        has_moved: True if translation (pan/tilt) > threshold.
        zoom_scale: The scaling factor between frames (1.0 = no zoom).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        has_moved = False
        zoom_scale = 1.0

        if self.prev_gray is None or self.prev_pts is None or len(self.prev_pts) < 10:
            # Need to find new features
            self.prev_pts = cv2.goodFeaturesToTrack(
                gray, maxCorners=self.max_corners, 
                qualityLevel=self.quality_level, 
                minDistance=self.min_distance, 
                blockSize=self.block_size
            )
            self.prev_gray = gray
            return False, 1.0

        # Calculate optical flow
        curr_pts, status, err = cv2.calcOpticalFlowPyrLK(self.prev_gray, gray, self.prev_pts, None)
        
        if curr_pts is not None and status is not None:
            # Filter valid points
            good_new = curr_pts[status == 1]
            good_old = self.prev_pts[status == 1]
            
            if len(good_new) > 10:
                # Calculate affine transform to find translation and scaling
                # Estimate a partial 2D affine transformation (scale, rotation, translation)
                matrix, inliers = cv2.estimateAffinePartial2D(good_old, good_new)
                
                if matrix is not None:
                    # Translation components
                    tx = matrix[0, 2]
                    ty = matrix[1, 2]
                    
                    # Compute translation magnitude
                    translation = np.sqrt(tx**2 + ty**2)
                    if translation > 8.0: # threshold for camera move
                        has_moved = True
                    
                    # Scaling factor (zoom)
                    # For matrix [[a, -b, tx], [b, a, ty]], scale s = sqrt(a^2 + b^2)
                    a = matrix[0, 0]
                    b = matrix[1, 0]
                    zoom_scale = np.sqrt(a**2 + b**2)
                    
                    # Clamp scale to prevent wild jumps
                    zoom_scale = max(0.9, min(1.1, zoom_scale))

                # Update features every few frames to avoid losing them
                # But for simplicity, we just keep tracking the surviving ones until they drop below 10
                self.prev_pts = good_new.reshape(-1, 1, 2)
            else:
                self.prev_pts = None # trigger re-detect
        else:
            self.prev_pts = None # trigger re-detect
            
        self.prev_gray = gray
        return has_moved, zoom_scale
