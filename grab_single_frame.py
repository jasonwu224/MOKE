import numpy as np
import os
import cv2
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE

def SNR(image):
    signal_power = np.mean(image)
    noise_power = np.std(image)
    # return SNR in decibels
    snr = 10*np.log10(signal_power/noise_power)
    return snr

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
        camera.exposure_time_us = 2000  # set exposure to 2 ms
        camera.frames_per_trigger_zero_for_unlimited = 0  # start camera in continuous mode
        camera.image_poll_timeout_ms = 1000  # 1 second polling timeout

        old_roi = camera.roi
        x, y, width, height = 1000, 1200, 1000, 1000
        camera.roi = (x, y, x + width, y + height)
        print(camera.roi)
        camera.arm(2)

        camera.issue_software_trigger()

        # average many images to smooth out noise

        NUM_FRAMES_TO_AVG = 100
        avg_image_buffer = np.zeros((camera.image_height_pixels, camera.image_width_pixels), dtype=np.float64)  # 64 bit for high precision

        for i in range(NUM_FRAMES_TO_AVG):
            frame = camera.get_pending_frame_or_null()
            if frame is not None:
                print("frame #{} received!".format(frame.frame_count))
                shaped_image_buffer = np.copy(frame.image_buffer).reshape(camera.image_height_pixels, camera.image_width_pixels)
                avg_image_buffer += shaped_image_buffer.astype(np.float64)
                print("Max pixel value:", shaped_image_buffer.max())
                print(f"Signal-to-Noise ratio: {SNR(shaped_image_buffer)}")

                # Normalize 12-bit image to 0–255 8-bit
                # norm_img = cv2.normalize(numpy_shaped_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
                # cv2.imshow("Image From TSI Cam", norm_img)
            else:
                print("Unable to acquire image, program exiting...")
                exit()
        avg_image = (avg_image_buffer / NUM_FRAMES_TO_AVG).astype(np.uint16)
        norm_avg_image = cv2.normalize(avg_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
        print("Averaged image computed")
        print("Max pixel value:", shaped_image_buffer.max())
        print(f"Signal-to-Noise ratio: {SNR(shaped_image_buffer)}")
        cv2.imshow("Image From TSI Cam", norm_avg_image)
        cv2.waitKey(0)
        camera.disarm()
        camera.roi = old_roi

#  Because we are using the 'with' statement context-manager, disposal has been taken care of.

print("program completed")