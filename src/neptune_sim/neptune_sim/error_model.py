"""Seeded moderate pixel and timing errors; ideal mode bypasses this module."""
import hashlib
import cv2
import numpy as np


class ErrorModel:
    def __init__(self, settings):
        self.settings=settings; self.rng=np.random.default_rng(settings['seed']); self.maps={}

    def stamp_offset(self, stream, stamp):
        timing=self.settings['timing']
        # Deterministic per capture: matching camera image/info share a timestamp.
        digest=hashlib.sha256(f"{self.settings['seed']}:{stream}:{stamp}".encode()).digest()
        unit=int.from_bytes(digest[:4],'big')/(2**32-1)
        fixed=timing['right_offset_s'] if stream=='right' else timing['dvl_offset_s'] if stream=='dvl' else 0
        return fixed+(2*unit-1)*timing['timestamp_jitter_s']

    def camera(self, image, stamp, stream, angular_speed=0.):
        cfg=self.settings['camera']; h,w=image.shape[:2]
        if (h,w) not in self.maps:
            focal=w/(2*np.tan(np.deg2rad(40)))
            K=np.array([[focal,0,w/2],[0,focal,h/2],[0,0,1]],dtype=np.float64)
            self.maps[h,w]=cv2.initUndistortRectifyMap(K,np.array([cfg['radial_k1'],0,0,0,0]),None,K,(w,h),cv2.CV_32FC1)
        frame=cv2.remap(image,*self.maps[h,w],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        if stream=='right':
            frame=cv2.warpAffine(frame,np.float32([[1,0,cfg['right_shift_px']],[0,1,0]]),(w,h),borderMode=cv2.BORDER_REFLECT_101)
        frame=cv2.GaussianBlur(frame,(cfg['blur_kernel'],cfg['blur_kernel']),0).astype(np.float32)
        length=min(cfg['max_motion_blur_px'],max(1,int(w/(2*np.tan(np.deg2rad(40)))*angular_speed*cfg['exposure_s'])))
        if length>1: frame=cv2.filter2D(frame,-1,np.ones((1,length),np.float32)/length)
        frame[:,:,2]*=cfg['red_gain']
        frame=frame*cfg['contrast']*(1+cfg['exposure_variation']*np.sin(stamp*.7))+cfg['backscatter']
        frame+=self.rng.standard_normal(frame.shape,dtype=np.float32)*cfg['pixel_sigma']
        return np.clip(frame,0,255).astype(np.uint8)

    def sonar(self, image):
        cfg=self.settings['sonar']
        result=image.astype(np.float32)*(1+self.rng.normal(0,cfg['multiplicative_sigma'],image.shape))
        result+=self.rng.normal(0,cfg['additive_sigma'],image.shape)
        shift=cfg['ghost_shift_px']
        if image.shape[0]>shift: result[shift:]+=cfg['ghost_gain']*image[:-shift]
        return np.clip(result,0,255).astype(np.uint8)
