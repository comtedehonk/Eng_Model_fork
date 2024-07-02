def report_diagnostics(rfm9x):
    """
    Print diagnostic data from an instance of an adafruit_rfm9x radio.
    
    Args:
    rfm9x (adafruit_rfm9x.RFM9x): Instance of the RFM9x radio.
    """
    try:
        print("RFM9x Radio Diagnostics:")
        print("------------------------")
        
        # Frequency
        print(f"Frequency: {rfm9x.frequency_mhz} MHz")
        
        # Signal bandwidth
        print(f"Signal Bandwidth: {rfm9x.signal_bandwidth} Hz")
        
        # Coding rate
        print(f"Coding Rate: {rfm9x.coding_rate}")
        
        # Spreading factor
        print(f"Spreading Factor: {rfm9x.spreading_factor}")
        
        # Signal-to-noise ratio (SNR)
        # print(f"SNR: {rfm9x.snr} dB")
        
        # Received signal strength indicator (RSSI)
        print(f"RSSI: {rfm9x.rssi()} dB")
        
        # Current transmit power
        print(f"Transmit Power: {rfm9x.tx_power} dBm")
        
        # Preamble length
        print(f"Preamble Length: {rfm9x.preamble_length}")
        
        # CRC status
        print(f"CRC Enabled: {rfm9x.enable_crc}")
        
        # Temperature (if supported by the hardware)
        # try:
        #     print(f"Temperature: {rfm9x.temperature} C")
        # except AttributeError:
        #     print("Temperature: Not available")
        
    except Exception as e:
        print(f"Error retrieving diagnostics: {e}")

def get_rssi_meaning(rssi_value):
    """
    Provide a qualitative assessment of the RSSI value.
    
    Args:
    rssi_value (int): The RSSI value.
    
    Returns:
    str: A qualitative assessment of the RSSI value.
    """
    if rssi_value > -50:
        return "Excellent"
    elif -50 >= rssi_value > -70:
        return "Good"
    elif -70 >= rssi_value > -90:
        return "Fair"
    elif -90 >= rssi_value > -110:
        return "Weak"
    else:
        return "Very Weak"

def report_rssi(rfm9x):
    """
    Reports the RSSI value and its meaning from an instance of an adafruit_rfm9x radio.
    
    Args:
    rfm9x (adafruit_rfm9x.RFM9x): Instance of the RFM9x radio.
    """
    try:
        # Get the RSSI value
        rssi_value = rfm9x.rssi()
        
        # Get the qualitative meaning of the RSSI value
        rssi_meaning = get_rssi_meaning(rssi_value)
        
        # Report the RSSI value and its meaning
        print(f"RSSI Value: {rssi_value} dB")
        print(f"Signal Strength: {rssi_meaning}")
        
    except Exception as e:
        print(f"Error retrieving RSSI: {e}")

# Example usage:
# Assuming you have created an RFM9x instance called 'rfm9x'
# rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, frequency)
# report_diagnostics(rfm9x)
# report_rssi(rfm9x)