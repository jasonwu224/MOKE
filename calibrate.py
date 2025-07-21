import pyvisa
import pandas as pd
import matplotlib.pyplot as plt
import os

# calibrates the external magnetic field near the sample as a function of voltage, requires manual input of gaussmeter readings
def main():
    os.makedirs("data/calibration/", exist_ok=True)

    rm = pyvisa.ResourceManager("C:/Windows/System32/visa64.dll")
    print(rm)
    print(f"Connected devices: {rm.list_resources()}")
    
    # Control a Keysight E3645A DC power supply with a GPID-USB-HS adapter
    with rm.open_resource("GPIB0::5::INSTR") as psu:
        print(f"Opened {psu}\n{psu.query('*IDN?')}")

        data = {
            "Magnetic Flux Density (G)": [],
            "Voltage (V)": [],
            "Current (A)": [],
        }
        # max 35V giving 0.7A
        # supposedly good practice to set CURR and VOLT before OUTP ON
        psu.write("*RST")
        psu.write("CURR 0.7")  # set max current in amps
        psu.write("OUTP ON")

        for volts in range(0, 36):
            # write the volts
            psu.write(f"VOLT {volts}")
            voltage = float(psu.query("MEAS:VOLT?").strip())
            current = float(psu.query("MEAS:CURR?").strip())
            print(f"V = {voltage} V, I = {current} A")
            # user manually inputs field reading, no time to setup the gaussmeter to PC
            magnetic_flux = input("Enter the magnetic field reading (Gauss): ")
            print()
            # add to data dict
            data["Magnetic Flux Density (G)"].append(magnetic_flux)
            data["Voltage (V)"].append(voltage)
            data["Current (A)"].append(current)

        # turn machine off
        psu.write("VOLT 0")
        psu.write("OUTP OFF")

        print("Equipment off")

        # save data and plot it
        print(data)
        df = pd.DataFrame(data)
        print(df)
        df.to_csv("data/calibration/Volts_to_Gauss_Calibration.csv")
        plt.scatter(df["Magnetic Flux Density (G)"], df["Voltage (V)"])
        plt.show()

if __name__ == "__main__":
    main()