import numpy as np
import time
import cv2
import os
from datetime import datetime
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE
import pyvisa
import matplotlib.pyplot as plt
import pandas as pd

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

##########################################
# Experimental Constants 
##########################################
# VOLTAGES should be here but since the DC power is unidirectional, I have to
# manually swap the voltages for negative side of sweep lol
EXPERIMENT_TIME = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
EXPOSURE_TIME_MS = 2
NUM_FRAMES_TO_AVG = 15
DWELL_TIME = 0.3  # time in sec to wait between each voltage jump for magnetization to settle
IMG_SETTING = "data"
PROGRAM_ACTION = "sweep"  # picture/sweep
images_saved = 0  # I'm really sorry lol this is for labeling data at overlapping voltages
# create data folders
DATA_DIR = f"data/{EXPERIMENT_TIME}"
IMG_DIR = f"images/{EXPERIMENT_TIME}"

# takes a picture by averaging many frames and cropping the camera's image (if desired)
def take_avg_picture(camera, roi=None, verbose=False):
    if roi is None:  # no cropping
        roi_x, roi_y, roi_width, roi_height = 0, 0, camera.image_width_pixels, camera.image_height_pixels
    else:
        roi_x, roi_y, roi_width, roi_height = roi
    # average many images to smooth out noise
    avg_image_buffer = np.zeros((roi_height, roi_width), dtype=np.float64)  # 64 bit for high precision

    print(f"Averaging {NUM_FRAMES_TO_AVG} images")
    for _ in range(NUM_FRAMES_TO_AVG):
        frame = camera.get_pending_frame_or_null()
        if frame is not None:
            # print("frame #{} received!".format(frame.frame_count))
            # shaped to the camera ROI
            raw_image = np.copy(frame.image_buffer).reshape(camera.image_height_pixels, camera.image_width_pixels)
            # reshape again to our ROI since there's a minimum camera image width
            cropped_image = raw_image[roi_y:(roi_y + roi_height), roi_x:(roi_x + roi_width)]
            avg_image_buffer += cropped_image.astype(np.float64)
        else:
            print("Unable to acquire image, program exiting...")
            exit()

    avg_image = (avg_image_buffer / NUM_FRAMES_TO_AVG).astype(np.uint16)
    mean = avg_image.mean()
    total = avg_image.sum()
    snr = SNR(avg_image)

    if verbose:
        print("Averaged image computed")
        print("Image size:", avg_image.shape)
        print("Max pixel value:", avg_image.max())
        print("Total pixel sum:", total)
        print("Mean pixel value:", mean)
        print("Signal-to-Noise ratio", snr)
        print()
    return avg_image, mean, total, snr


# sweep out a magnetic field, v_multiplier is just used to make the voltage negative on reverse sweep
def sweep(data, v_multiplier, VOLTAGES, psu, camera, roi):
    for volt in VOLTAGES:
        psu.write(f"VOLT {volt}")
        time.sleep(DWELL_TIME)  # Allow settling
        voltage = float(psu.query("MEAS:VOLT?").strip())
        current = float(psu.query("MEAS:CURR?").strip())
        print(f"V = {v_multiplier*voltage} V, I = {current} A")

        avg_image, mean, total, snr = take_avg_picture(camera, roi, verbose=True)
        # save data to corresponding lists
        # as of Python 3.7, insertion order in dictionaries is preserved
        collected_data = [v_multiplier*voltage, current, mean, total, snr]
        for key, value in zip(data.keys(), collected_data):
            data[key].append(value)
        # save image array just in case
        global images_saved
        np.save(f"{IMG_DIR}/avg_image_{volt}V_{images_saved}.npy", avg_image)
        images_saved += 1


def main(action):
    ##########################################
    # Try connecting DC power supply
    ##########################################
    rm = pyvisa.ResourceManager("C:/Windows/System32/visa64.dll")
    print(rm)
    print(f"Connected devices: {rm.list_resources()}")

    # Control a Keysight E3645A DC power supply with a GPID-USB-HS adapter
    # max 35V giving 0.7A
    with rm.open_resource("GPIB0::5::INSTR") as psu:
        print(f"Opened {psu}\n{psu.query('*IDN?')}")

        ##########################################
        # Try connecting camera
        ##########################################
        with TLCameraSDK() as sdk:
            available_cameras = sdk.discover_available_cameras()
            if len(available_cameras) < 1:
                print("no cameras detected")

            with sdk.open_camera(available_cameras[0]) as camera:
                ##########################################
                # Set camera settings and arm camera
                ##########################################
                print(f"Camera successfully connected {camera.name}")
                camera.exposure_time_us = EXPOSURE_TIME_MS * 1000  # set exposure to 2 ms
                camera.frames_per_trigger_zero_for_unlimited = 0  # start camera in continuous mode
                camera.image_poll_timeout_ms = 1000  # 1 second polling timeout

                old_roi = camera.roi
                
                # the spacing width-wise between patterns is about 200 pixels
                match IMG_SETTING:
                    # this ROI sees a 3x3 grid of patterns clearly 
                    case "grid":
                        x, y, width, height = 800, 1400, 1800, 1100
                        roi_x, roi_y, roi_width, roi_height = 0, 0, width, height
                    # this camera ROI focuses on just one (top left of the 3x3 grid)
                    case "single":
                        x, y, width, height = 1600, 2100, 300, 300
                        # this real ROI (which will crop the image smaller than the camera can take it) fits the entire pattern
                        roi_x, roi_y, roi_width, roi_height = 0, 0, 300, 300
                    case "data":
                        # x, y, width, height = 1860, 1790, 300, 300
                        x, y, width, height = 1600, 2100, 300, 300
                        # this real ROI fits (mostly) within the pattern, so it's pure signal
                        roi_x, roi_y, roi_width, roi_height = 95, 75, 60, 85

                camera.roi = (x, y, x + width, y + height)
                # TODO: This should be its own struct/datatype but bear with me lol I'm tired
                real_roi = (roi_x, roi_y, roi_width, roi_height)
                print(camera.roi)
                camera.arm(2)

                camera.issue_software_trigger()

                match action:
                    case "sweep":
                        os.makedirs(DATA_DIR, exist_ok=True)
                        os.makedirs(IMG_DIR, exist_ok=True)
                        ##########################################
                        # Sweep a magnetic field and collect image data
                        ##########################################

                        # prepare power supply
                        psu.write("*RST")
                        psu.write("CURR 0.7")  # set max current in amps
                        psu.write("VOLT 0")
                        psu.write("OUTP ON")

                        data = {
                            "Voltage (V)": [],
                            "Current (A)": [],
                            "Average Intensity": [],
                            "Total Intensity": [],
                            "SNR (dB)": [],
                        }
                        
                        START_TIME = time.time()
                        # VOLTAGES_FORWARD = np.arange(0, 36, 0.5)  
                        # VOLTAGES_BACK = np.arange(35, -0.1, -0.5)
                        VOLTAGES_FORWARD = np.arange(0, 15, 0.25)  
                        VOLTAGES_BACK = np.arange(14.75, -0.1, -0.25)
                        
                        # 0 to H+
                        sweep(data, 1, VOLTAGES_FORWARD, psu, camera, real_roi)
                        # H+ to 0
                        sweep(data, 1, VOLTAGES_BACK, psu, camera, real_roi)
                        # manually switch voltages
                        input("Swap the voltages now, press enter when ready")
                        # 0 to H-
                        sweep(data, -1, VOLTAGES_FORWARD, psu, camera, real_roi)
                        # H- to 0
                        sweep(data, -1, VOLTAGES_BACK, psu, camera, real_roi)

                        input("Swap the voltages now, press enter when ready")
                        # 0 to H+
                        sweep(data, 1, VOLTAGES_FORWARD, psu, camera, real_roi)
                        # we don't want to linger at high voltage and melt the magnets lol
                        psu.write("VOLT 0")


                        STOP_TIME = time.time()
                        TIME_ELAPSED = STOP_TIME - START_TIME
                        print(f"Data collection finished\nTime elapsed: {TIME_ELAPSED} seconds")

                        # save data
                        df = pd.DataFrame(data)
                        metadata = {
                            "Exposure time (ms)": EXPOSURE_TIME_MS,
                            "Camera ROI": camera.roi,
                            "Real ROI": (roi_x, roi_y, roi_width - roi_x, roi_height - roi_y),
                            "Images averaged": NUM_FRAMES_TO_AVG,
                            "Time elapsed": TIME_ELAPSED,
                        }
                        with open(f"{DATA_DIR}/data_{EXPERIMENT_TIME}.csv", "w") as f:
                            for key, value in metadata.items():
                                f.write(f"# {key}: {value}\n")
                            df.to_csv(f, index=False)
                        # plot data
                        plt.scatter(data["Voltage (V)"], data["Average Intensity"])
                        plt.title("Average Intensity vs Applied Voltage")
                        plt.xlabel("Voltage (V)")
                        plt.ylabel("Intensity (Counts)")
                        plt.savefig(f"data/{EXPERIMENT_TIME}/plot")

                    case "picture":
                        avg_image, _, _, _ = take_avg_picture(camera, real_roi, verbose=True)
                        # show/save an image 
                        norm_avg_image = cv2.normalize(avg_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)

                        # callback to dynamically display pixel coordinates of mouse
                        def mouse_callback(event, x, y, flags, param):
                            if event == cv2.EVENT_MOUSEMOVE:
                                text = f"X: {x}, Y: {y}"
                                img_copy = norm_avg_image.copy()
                                cv2.putText(img_copy, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                cv2.imshow('Image Viewer', img_copy)

                        cv2.namedWindow('Image Viewer')
                        cv2.setMouseCallback('Image Viewer', mouse_callback)
                        cv2.imshow("Image Viewer", norm_avg_image)
                        cv2.waitKey(0)
                        # cv2.imwrite("example_data_0V.png", norm_avg_image)
                
                # turn off camera and power supply
                psu.write("VOLT 0")
                psu.write("OUTP OFF")

                camera.disarm()
                camera.roi = old_roi
                print("Equipment turned off")
                print("Data saved")


#  Because we are using the 'with' statement context-manager, disposal has been taken care of.
if __name__ == "__main__":
    main(PROGRAM_ACTION)
    print("program completed")