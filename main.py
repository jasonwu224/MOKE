import pyvisa

def main():

    rm = pyvisa.ResourceManager("C:/Windows/System32/visa64.dll")
    print(rm)
    print(f"Connected devices: {rm.list_resources()}")
    
    # Control a Keysight E3645A DC power supply with a GPID-USB-HS adapter
    with rm.open_resource("GPIB0::5::INSTR") as psu:
        print(f"Opened {psu}\n{psu.query('*IDN?')}")

        # max 35V giving 0.7A
        # supposedly good practice to set CURR and VOLT before OUTP ON
        psu.write("*RST")
        psu.write("CURR 0.7")  # set max current in amps
        psu.write("VOLT 5")
        psu.write("OUTP ON")
        print(psu.query("MEAS:VOLT?"))
        print(psu.query("MEAS:CURR?"))
        psu.write("VOLT 0")
        psu.write("OUTP OFF")

if __name__ == "__main__":
    main()