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

def main():
    with TLCameraSDK() as sdk:
        available_cameras = sdk.discover_available_cameras()
        if len(available_cameras) < 1:
            print("no cameras detected")

        with sdk.open_camera(available_cameras[0]) as camera:
            camera.exposure_time_us = 2000  # set exposure to 2 ms
            camera.frames_per_trigger_zero_for_unlimited = 0  # start camera in continuous mode
            camera.image_poll_timeout_ms = 1000  # 1 second polling timeout

            old_roi = camera.roi

            # this ROI sees a 3x3 grid of patterns clearly 
            # x, y, width, height = 1000, 1200, 1000, 1000
            # this camera ROI focuses on just one (top left of the 3x3 grid)
            x, y, width, height = 1190, 1370, 260, 200
            # this real ROI (which will crop the image smaller than the camera can take it) fits the entire pattern
            # roi_x, roi_y, roi_width, roi_height = 10, 10, 80, 115
            # this real ROI fits (mostly) within the pattern, so it's pure signal
            roi_x, roi_y, roi_width, roi_height = 25, 25, 55, 90
            camera.roi = (x, y, x + width, y + height)
            print(camera.roi)
            camera.arm(2)

            camera.issue_software_trigger()

            # average many images to smooth out noise
            # it seems that increasing this hardly increased avg SNR, but maybe it decreases the variance?
            NUM_FRAMES_TO_AVG = 50
            avg_image_buffer = np.zeros((roi_height, roi_width), dtype=np.float64)  # 64 bit for high precision

            for i in range(NUM_FRAMES_TO_AVG):
                frame = camera.get_pending_frame_or_null()
                if frame is not None:
                    print("frame #{} received!".format(frame.frame_count))
                    # shaped to the camera ROI
                    raw_image = np.copy(frame.image_buffer).reshape(camera.image_height_pixels, camera.image_width_pixels)
                    # reshape again to our ROI since there's a minimum camera image width
                    cropped_image = raw_image[roi_y:(roi_y + roi_height), roi_x:(roi_x + roi_width)]
                    avg_image_buffer += cropped_image.astype(np.float64)
                    print("Max pixel value:", cropped_image.max())
                    print(f"Signal-to-Noise ratio: {SNR(cropped_image)}")

                    # Normalize 12-bit image to 0–255 8-bit
                    # norm_img = cv2.normalize(numpy_shaped_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
                    # cv2.imshow("Image From TSI Cam", norm_img)
                else:
                    print("Unable to acquire image, program exiting...")
                    exit()
            avg_image = (avg_image_buffer / NUM_FRAMES_TO_AVG).astype(np.uint16)
            norm_avg_image = cv2.normalize(avg_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
            print("Averaged image computed")
            print(f"Image size: {avg_image.shape}")
            print("Max pixel value:", avg_image.max())
            print(f"Signal-to-Noise ratio: {SNR(avg_image)}")
            cv2.imshow("Image From TSI Cam", norm_avg_image)
            cv2.waitKey(0)
            camera.disarm()
            camera.roi = old_roi

#  Because we are using the 'with' statement context-manager, disposal has been taken care of.
if __name__ == "__main__":
    main()
    print("program completed")