"""
Polling Example

This example shows how to open a camera, adjust some settings, and poll for images. It also shows how 'with' statements
can be used to automatically clean up camera and SDK resources.

"""

import numpy as np
import os
import cv2
import time
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE

try:
    # if on Windows, use the provided setup script to add the DLLs folder to the PATH
    from windows_setup import configure_path
    configure_path()
except ImportError:
    configure_path = None

with TLCameraSDK() as sdk:
    available_cameras = sdk.discover_available_cameras()
    if len(available_cameras) < 1:
        print("no cameras detected")

    with sdk.open_camera(available_cameras[0]) as camera:
        camera.exposure_time_us = 2000  # set exposure to 4 ms
        camera.frames_per_trigger_zero_for_unlimited = 0  # start camera in continuous mode
        camera.image_poll_timeout_ms = 1000  # 1 second polling timeout
        camera.frame_rate_control_value = 10
        camera.is_frame_rate_control_enabled = True

        old_roi = camera.roi
        # x, y, width, height = 1000, 1200, 1000, 1000
        # new ROI for proper alignment to p axis, best pattern is the top left one
        x, y, width, height = 700, 1200, 1000, 1000
        camera.roi = (x, y, x + width, y + height)
        print(camera.roi)

        camera.arm(2)
        camera.issue_software_trigger()

        try:
            while True:
                frame = camera.get_pending_frame_or_null()
                if frame is not None:
                    print("frame #{} received!".format(frame.frame_count))
                    frame.image_buffer
                    image_buffer_copy = np.copy(frame.image_buffer)
                    numpy_shaped_image = image_buffer_copy.reshape(camera.image_height_pixels, camera.image_width_pixels)
                    nd_image_array = np.zeros((camera.image_height_pixels, camera.image_width_pixels, 1), dtype=np.uint8)
                    # Normalize 12- or 16-bit image to 0–255 8-bit
                    norm_img = cv2.normalize(numpy_shaped_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
          
                    cv2.imshow("Image From TSI Cam", norm_img)
                    cv2.waitKey(1)

                else:
                    print("Unable to acquire image, program exiting...")
                    exit()
        except KeyboardInterrupt:
            print("loop terminated")
            
        cv2.destroyAllWindows()
        camera.disarm()
        camera.roi = old_roi

#  Because we are using the 'with' statement context-manager, disposal has been taken care of.

print("program completed")