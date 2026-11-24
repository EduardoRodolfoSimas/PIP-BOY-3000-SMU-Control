import os
import time
import math
import csv
import datetime
import pyvisa
import numpy as np
import matplotlib

matplotlib.use('Qt5Agg')  # Use Qt5Agg backend for stability
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from colorama import init, Fore, Back, Style
import re
import socket

# Initialize colorama for PIP-BOY styling
init(autoreset=True, convert=True)  # Convert=True for Windows compatibility
GREEN = Fore.GREEN + Style.BRIGHT + Back.BLACK
RED = Fore.RED + Style.BRIGHT + Back.BLACK

# Set black background and green text on Windows console
if os.name == 'nt':
    os.system("color 02")


# Check if VISA backend is installed
def check_visa_backend():
    try:
        rm = pyvisa.ResourceManager()
        rm.list_resources()  # Test resource discovery
        return True
    except pyvisa.VisaIOError as e:
        print(RED + f"VISA backend error: {e}")
        return False


# Validate IPv4 address format
def is_valid_ip(ip):
    pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return bool(re.match(pattern, ip))


# Check if IP is reachable (basic ping test)
def is_ip_reachable(ip, timeout=2):
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, 5025))  # Try port 5025 (common for VISA instruments)
        sock.close()
        return True
    except (socket.timeout, socket.error):
        return False


# Initialize VISA and connect to SMU
rm = None
smu = None
try:
    clear_screen = lambda: os.system('cls' if os.name == 'nt' else 'clear')
    clear_screen()
    if os.name == 'nt':
        os.system("color 02")  # Reapply black background, green text
    # Enhanced welcome interface
    print(GREEN + "=" * 60)
    print(GREEN + "|" + " " * 58 + "|")
    print(GREEN + "|" + "  PIP-BOY 3000 SMU CONTROL INTERFACE  ".center(58) + "|")
    print(GREEN + "|" + "  Control your Keysight B2912A ".center(58) + "|")
    print(GREEN + "|" + " " * 58 + "|")
    print(GREEN + "=" * 60)
    print(GREEN + "Select connection type:")
    print(GREEN + " [1] VISA USB")
    print(GREEN + " [2] VISA LAN (TCPIP)")
    conn_type = input(GREEN + "Enter 1 or 2: ").strip()

    if conn_type not in ['1', '2']:
        raise ValueError("Invalid connection type. Choose 1 (USB) or 2 (LAN).")

    if not check_visa_backend():
        print(RED + "Error: No VISA backend found. Install Keysight IO Libraries:")
        print(
            RED + "https://www.keysight.com/us/en/lib/software-detail/computer-software/io-libraries-suite-downloads.html")
        print(RED + "Ensure the B2912A is powered on and connected via USB or LAN.")
        print(RED + "Exiting program.")
        exit(1)

    rm = pyvisa.ResourceManager()
    print(GREEN + "Scanning for instruments...")
    try:
        resources = rm.list_resources()
    except pyvisa.VisaIOError as e:
        print(RED + f"Error listing resources: {e}")
        resources = []

    prefix = 'USB' if conn_type == '1' else 'TCPIP'
    filtered_resources = [res for res in resources if res.startswith(prefix)]

    if not filtered_resources:
        print(GREEN + f"No {prefix} instruments found.")
        if resources:
            print(GREEN + "Other detected resources (for debugging):")
            for res in resources:
                print(GREEN + f" - {res}")
        print(GREEN + f"Please check {prefix} connection and try again.")
    else:
        print(GREEN + f"{prefix} instruments found:")
        for i, res in enumerate(filtered_resources):
            print(GREEN + f" [{i}] {res}")

    print(GREEN + f"Enter the resource number, 'm' to manually input a VISA address, or 'ip' for LAN IP input.")
    choice = input(GREEN + "Selection: ").strip().lower()

    if choice == 'm':
        if conn_type == '1':
            print(GREEN + "Example USB address: USB0::0x2A8D::0x0398::MY12345678::INSTR")
        else:
            print(GREEN + "Example LAN address: TCPIP0::192.168.1.100::inst0::INSTR")
            print(GREEN + "Simulator address: TCPIP0::127.0.0.1::5025::SOCKET")
        visa_address = input(GREEN + f"Enter VISA address ({prefix}...): ").strip()
        if not visa_address.startswith(prefix):
            raise ValueError(f"VISA address must start with '{prefix}'.")
    elif choice == 'ip' and conn_type == '2':
        ip_address = input(GREEN + "Enter instrument IP address (e.g., 192.168.1.100): ").strip()
        if not is_valid_ip(ip_address):
            raise ValueError("Invalid IP address format. Use xxx.xxx.xxx.xxx.")
        if not is_ip_reachable(ip_address):
            print(RED + f"Warning: IP {ip_address} may not be reachable. Proceeding anyway.")
        # Try INSTR first (B2912A standard), then SOCKET (simulator)
        visa_address = f"TCPIP0::{ip_address}::inst0::INSTR"
        try:
            smu = rm.open_resource(visa_address)
            idn = smu.query("*IDN?")
            if "Keysight" not in idn or "B2912A" not in idn:
                raise ValueError("Not a B2912A")
        except (pyvisa.VisaIOError, ValueError):
            visa_address = f"TCPIP0::{ip_address}::5025::SOCKET"
    elif choice.isdigit() and 0 <= int(choice) < len(filtered_resources):
        visa_address = filtered_resources[int(choice)]
    else:
        raise ValueError("Invalid selection. Use a resource number, 'm', or 'ip' for LAN.")

    smu = rm.open_resource(visa_address)
    smu.timeout = 20000  # 20 seconds for B2912A
    smu.chunk_size = 102400  # 100 kB for reliable data transfer
    smu.write_termination = '\n'
    smu.read_termination = '\n'
    # Verify connection with *IDN? (retry once)
    for attempt in range(2):
        try:
            idn = smu.query("*IDN?")
            if "Keysight" in idn and "B2912A" in idn:
                print(GREEN + f"Connected to Keysight B2912A: {idn}")
                break
            else:
                raise ValueError(f"Unknown instrument: {idn}")
        except pyvisa.VisaIOError:
            if attempt == 1:
                raise ValueError("Failed to communicate with instrument after retry.")
            time.sleep(1)  # Wait before retry
    smu.write("*CLS")  # Clear status
    smu.write("*RST")  # Reset instrument
    error = smu.query(":SYST:ERR?")
    if "+0" not in error:
        print(RED + f"Error after reset: {error}")
        raise ValueError("Instrument reset failed.")
except (pyvisa.VisaIOError, ValueError) as e:
    print(RED + f"Error connecting to SMU: {e}")
    print(RED + "Ensure the B2912A is powered on, connected, and configured for remote control.")
    print(RED + "For LAN, verify the IP address and network settings.")
    print(RED + "For USB, ensure the USBTMC driver is installed.")
    print(RED + "Exiting program.")
    if rm is not None:
        rm.close()
    exit(1)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    if os.name == 'nt':
        os.system("color 02")  # Reapply black background, green text


def print_header():
    title = "PIP-BOY 3000 SMU CONTROL INTERFACE"
    width = 60
    padding = (width - len(title)) // 2
    print(GREEN + "=" * width)
    print(GREEN + " " * padding + title + " " * (width - len(title) - padding))
    print(GREEN + "=" * width)


def print_menu():
    print(GREEN + " [1] Inject Voltage")
    print(GREEN + " [2] Inject Current")
    print(GREEN + " [3] Measure & Log")
    print(GREEN + " [4] Generate PWM")
    print(GREEN + " [5] Generate Waveform")
    print(GREEN + " [6] Act as Load")
    print(GREEN + " [7] Battery Characterization")
    print(GREEN + " [8] Continuous Set Points with Measurement (2 channels)")
    print(GREEN + " [9] Act as Battery")
    print(GREEN + " [10] Turn Off Output")
    print(GREEN + " [0] Exit")
    print(GREEN + "=" * 60)


def validate_float(prompt, min_val=None, max_val=None):
    while True:
        try:
            value = input(GREEN + prompt).strip()
            if not value:
                print(GREEN + "Empty input. Try again.")
                continue
            value = float(value)
            if min_val is not None and value < min_val:
                print(GREEN + f"Value must be >= {min_val}. Try again.")
                continue
            if max_val is not None and value > max_val:
                print(GREEN + f"Value must be <= {max_val}. Try again.")
                continue
            return value
        except ValueError:
            print(GREEN + "Invalid input. Enter a valid number.")


def select_channel():
    print(GREEN + "Select channel:")
    print(GREEN + " [1] Channel 1")
    print(GREEN + " [2] Channel 2")
    print(GREEN + " [3] Both Channels")
    while True:
        choice = input(GREEN + "Enter 1, 2, or 3: ").strip()
        if choice in ['1', '2', '3']:
            return choice
        print(GREEN + "Invalid choice. Enter 1, 2, or 3.")


def configure_channel(channel, func, value, prot_type, prot_value, is_voltage=True):
    prefix = f":SOUR{channel}"
    sense_prefix = f":SENS{channel}"
    smu.write(f"{prefix}:FUNC {func}")
    smu.write(f"{prefix}:{'VOLT' if is_voltage else 'CURR'} {value}")
    smu.write(f"{sense_prefix}:{prot_type}:PROT {prot_value}")
    smu.write(f"{sense_prefix}:FUNC \"{'VOLT' if not is_voltage else 'CURR'}\"")
    smu.write(f"{sense_prefix}:VOLT:APER 0.001")
    smu.write(f"{sense_prefix}:CURR:APER 0.001")
    error = smu.query(":SYST:ERR?")
    if "+0" not in error:
        print(RED + f"Error configuring channel {channel}: {error}")
        return False
    return True


def measure_channel(channel):
    v = float(smu.query(f":MEAS:VOLT? (@{channel})"))
    c = float(smu.query(f":MEAS:CURR? (@{channel})"))
    error = smu.query(":SYST:ERR?")
    if "+0" not in error:
        print(RED + f"Measurement error on channel {channel}: {error}")
        return None, None
    return v, c


def inject_voltage():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        voltage = validate_float("Voltage to inject (V): ", -210, 210)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "VOLT", voltage, "CURR", 0.1, is_voltage=True):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        time.sleep(1.0)  # Stabilization delay
        for ch in channels:
            v, c = measure_channel(ch)
            if v is None or c is None:
                smu.write(f":OUTP{ch} OFF")
                return
            print(GREEN + f"Channel {ch} Measured: {v:.6f} V | {c:.6f} A")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def inject_current():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        current = validate_float("Current to inject (A): ", -3, 3)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "CURR", current, "VOLT", 5, is_voltage=False):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        time.sleep(1.0)
        for ch in channels:
            v, c = measure_channel(ch)
            if v is None or c is None:
                smu.write(f":OUTP{ch} OFF")
                return
            print(GREEN + f"Channel {ch} Measured: {v:.6f} V | {c:.6f} A")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def measure_log():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        duration = validate_float("Measurement duration (s): ", 0.1)
        interval = validate_float("Interval between measurements (s): ", 0.01)
        save_to_csv = input(GREEN + "Save measurements to CSV? [y/n]: ").strip().lower() == 'y'
        plot_data = input(GREEN + "Show real-time plot? [y/n]: ").strip().lower() == 'y'

        # Set up CSV file
        csv_file = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if save_to_csv:
            filename = f"measurements_{timestamp}.csv"
            try:
                csv_file = open(filename, 'w', newline='')
                headers = ['Time (s)'] + [f'Voltage CH{ch} (V)' for ch in channels] + [f'Current CH{ch} (A)' for ch in
                                                                                       channels]
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(headers)
                print(GREEN + f"Saving measurements to {filename}")
            except IOError as e:
                print(RED + f"Error opening CSV file: {e}")
                save_to_csv = False

        # Set up real-time plot
        times, data = [], {ch: {'voltages': [], 'currents': []} for ch in channels}
        ani = None
        if plot_data:
            plt.rcParams['font.family'] = 'Courier New'
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
            fig.patch.set_facecolor('black')
            ax1.set_facecolor('black')
            ax2.set_facecolor('black')
            ax1.set_title('PIP-BOY 3000 Voltage Monitor', color='limegreen')
            ax2.set_title('PIP-BOY 3000 Current Monitor', color='limegreen')
            ax1.set_xlabel('Time (s)', color='limegreen')
            ax1.set_ylabel('Voltage (V)', color='limegreen')
            ax2.set_xlabel('Time (s)', color='limegreen')
            ax2.set_ylabel('Current (A)', color='limegreen')
            ax1.grid(True, color='limegreen', linestyle='--', alpha=0.3)
            ax2.grid(True, color='limegreen', linestyle='--', alpha=0.3)
            ax1.tick_params(axis='both', colors='limegreen')
            ax2.tick_params(axis='both', colors='limegreen')
            lines_v = {ch: ax1.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in channels}
            lines_c = {ch: ax2.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in channels}
            if len(channels) > 1:
                ax1.legend()
                ax2.legend()
            plt.tight_layout()

            def update_plot(data_frame):
                if data_frame is None:
                    return list(lines_v.values()) + list(lines_c.values())
                t = data_frame[0]
                times.append(t)
                for ch in channels:
                    lines_v[ch].set_data(times, data[ch]['voltages'])
                    lines_c[ch].set_data(times, data[ch]['currents'])
                ax1.relim()
                ax1.autoscale_view()
                ax2.relim()
                ax2.autoscale_view()
                return list(lines_v.values()) + list(lines_c.values())

            def data_gen():
                for _ in range(int(duration / interval) + 1):
                    yield [times[-1] if times else 0] + [data[ch]['voltages'][-1] if data[ch]['voltages'] else 0 for ch
                                                         in channels]
                yield None

            ani = animation.FuncAnimation(
                fig,
                update_plot,
                frames=data_gen,
                interval=interval * 1000,
                blit=True,
                cache_frame_data=False
            )
            try:
                plt.show(block=False)
            except Exception as e:
                print(RED + f"Plotting error: {e}")
                plot_data = False

        # Measurement loop
        for ch in channels:
            smu.write(f":SENS{ch}:FUNC \"VOLT\"")
            smu.write(f":SENS{ch}:FUNC \"CURR\"")
            smu.write(f":SENS{ch}:VOLT:APER 0.001")
            smu.write(f":SENS{ch}:CURR:APER 0.001")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error setting measurement for channel {ch}: {error}")
                return
        print(GREEN + "Time (s) | " + " | ".join(f"Voltage CH{ch} (V) | Current CH{ch} (A)" for ch in channels))
        t = 0
        while t <= duration:
            row = [f"{t:.2f}"]
            for ch in channels:
                v, c = measure_channel(ch)
                if v is None or c is None:
                    return
                row.extend([f"{v:.6f}", f"{c:.6f}"])
                data[ch]['voltages'].append(v)
                data[ch]['currents'].append(c)
            print(GREEN + "       ".join(row))
            if save_to_csv and csv_file:
                try:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(row)
                except IOError as e:
                    print(RED + f"Error writing to CSV: {e}")
                    save_to_csv = False
            times.append(t)
            time.sleep(interval)
            t += interval

        if save_to_csv and csv_file:
            try:
                csv_file.close()
                print(GREEN + f"Measurements saved to {filename}")
            except Exception as e:
                print(RED + f"Error closing CSV file: {e}")
        if plot_data and input(GREEN + "Save plot as PNG? [y/n]: ").strip().lower() == 'y':
            plt.savefig(f"plot_{timestamp}.png", facecolor='black', edgecolor='none')
            print(GREEN + f"Plot saved to plot_{timestamp}.png")
        if plot_data:
            try:
                plt.close(fig)
            except Exception as e:
                print(RED + f"Error closing plot: {e}")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except KeyboardInterrupt:
        print(RED + "Measurement interrupted by user.")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def generate_pwm():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        amplitude = validate_float("Amplitude (V): ", -210, 210)
        frequency = validate_float("Frequency (Hz): ", 0.1, 1000)
        duty_cycle = validate_float("Duty Cycle (0-100%): ", 0, 100) / 100
        duration = validate_float("Total duration (s): ", 0.1)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        period = 1 / frequency
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "VOLT", 0, "CURR", 0.1, is_voltage=True):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        t = 0
        while t < duration:
            for ch in channels:
                smu.write(f":SOUR{ch}:VOLT {amplitude}")
            time.sleep(period * duty_cycle)
            for ch in channels:
                smu.write(f":SOUR{ch}:VOLT 0")
            time.sleep(period * (1 - duty_cycle))
            t += period
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except ValueError as e:
        print(RED + f"Invalid input data: {e}")
    input(GREEN + "[Press Enter to continue]")


def generate_waveform():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        print(GREEN + "Waveform types: [1] Sine, [2] Square, [3] Triangular")
        wave_type = input(GREEN + "Select waveform type (1-3): ").strip()
        if wave_type not in ['1', '2', '3']:
            print(RED + "Invalid waveform type.")
            input(GREEN + "[Press Enter to continue]")
            return
        amplitude = validate_float("Amplitude (V): ", -210, 210)
        frequency = validate_float("Frequency (Hz): ", 0.1, 1000)
        duration = validate_float("Total duration (s): ", 0.1)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        period = 1 / frequency
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "VOLT", 0, "CURR", 0.1, is_voltage=True):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        t = 0
        while t < duration:
            if wave_type == '1':  # Sine
                value = amplitude * math.sin(2 * math.pi * frequency * t)
            elif wave_type == '2':  # Square
                value = amplitude if math.sin(2 * math.pi * frequency * t) >= 0 else 0
            elif wave_type == '3':  # Triangular
                value = amplitude * (2 * abs((frequency * t) % 1 - 0.5) - 0.5)
            for ch in channels:
                smu.write(f":SOUR{ch}:VOLT {value}")
            time.sleep(period / 100)
            t += period / 100
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except ValueError as e:
        print(RED + f"Invalid input data: {e}")
    input(GREEN + "[Press Enter to continue]")


def act_as_load():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        current = validate_float("Load current (A): ", -3, 3)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "CURR", current * -1, "VOLT", 5, is_voltage=False):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        time.sleep(1.0)
        for ch in channels:
            v, c = measure_channel(ch)
            if v is None or c is None:
                smu.write(f":OUTP{ch} OFF")
                return
            print(GREEN + f"Channel {ch} Measured: {v:.6f} V | {c:.6f} A")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def characterize_battery():
    clear_screen()
    print_header()
    try:
        channel = select_channel()
        discharge_current = validate_float("Discharge current (A): ", 0, 3)
        min_voltage = validate_float("Minimum voltage (V): ", 0)
        interval = validate_float("Interval between measurements (s): ", 0.01)
        channels = [1] if channel == '1' else [2] if channel == '2' else [1, 2]
        save_to_csv = input(GREEN + "Save measurements to CSV? [y/n]: ").strip().lower() == 'y'
        plot_data = input(GREEN + "Show real-time plot? [y/n]: ").strip().lower() == 'y'

        # Set up CSV file
        csv_file = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if save_to_csv:
            filename = f"battery_{timestamp}.csv"
            try:
                csv_file = open(filename, 'w', newline='')
                headers = ['Time (s)'] + [f'Voltage CH{ch} (V)' for ch in channels] + [f'Current CH{ch} (A)' for ch in
                                                                                       channels]
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(headers)
                print(GREEN + f"Saving measurements to {filename}")
            except IOError as e:
                print(RED + f"Error opening CSV file: {e}")
                save_to_csv = False

        # Set up real-time plot
        times, data = [], {ch: {'voltages': [], 'currents': []} for ch in channels}
        ani = None
        if plot_data:
            plt.rcParams['font.family'] = 'Courier New'
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
            fig.patch.set_facecolor('black')
            ax1.set_facecolor('black')
            ax2.set_facecolor('black')
            ax1.set_title('PIP-BOY 3000 Battery Voltage', color='limegreen')
            ax2.set_title('PIP-BOY 3000 Battery Current', color='limegreen')
            ax1.set_xlabel('Time (s)', color='limegreen')
            ax1.set_ylabel('Voltage (V)', color='limegreen')
            ax2.set_xlabel('Time (s)', color='limegreen')
            ax2.set_ylabel('Current (A)', color='limegreen')
            ax1.grid(True, color='limegreen', linestyle='--', alpha=0.3)
            ax2.grid(True, color='limegreen', linestyle='--', alpha=0.3)
            ax1.tick_params(axis='both', colors='limegreen')
            ax2.tick_params(axis='both', colors='limegreen')
            lines_v = {ch: ax1.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in channels}
            lines_c = {ch: ax2.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in channels}
            if len(channels) > 1:
                ax1.legend()
                ax2.legend()
            plt.tight_layout()

            def update_plot(data_frame):
                if data_frame is None:
                    return list(lines_v.values()) + list(lines_c.values())
                t = data_frame[0]
                times.append(t)
                for ch in channels:
                    lines_v[ch].set_data(times, data[ch]['voltages'])
                    lines_c[ch].set_data(times, data[ch]['currents'])
                ax1.relim()
                ax1.autoscale_view()
                ax2.relim()
                ax2.autoscale_view()
                return list(lines_v.values()) + list(lines_c.values())

            def data_gen():
                while times:
                    yield [times[-1]] + [data[ch]['voltages'][-1] if data[ch]['voltages'] else 0 for ch in channels]
                yield None

            ani = animation.FuncAnimation(
                fig,
                update_plot,
                frames=data_gen,
                interval=interval * 1000,
                blit=True,
                cache_frame_data=False
            )
            try:
                plt.show(block=False)
            except Exception as e:
                print(RED + f"Plotting error: {e}")
                plot_data = False

        # Measurement loop
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "CURR", discharge_current * -1, "VOLT", 10, is_voltage=False):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return
        print(GREEN + "Time (s) | " + " | ".join(f"Voltage CH{ch} (V) | Current CH{ch} (A)" for ch in channels))
        t = 0
        while True:
            row = [f"{t:.2f}"]
            stop = False
            for ch in channels:
                v, c = measure_channel(ch)
                if v is None or c is None:
                    stop = True
                    break
                row.extend([f"{v:.6f}", f"{c:.6f}"])
                data[ch]['voltages'].append(v)
                data[ch]['currents'].append(c)
                if v <= min_voltage:
                    stop = True
            print(GREEN + "       ".join(row))
            if save_to_csv and csv_file:
                try:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(row)
                except IOError as e:
                    print(RED + f"Error writing to CSV: {e}")
                    save_to_csv = False
            times.append(t)
            if stop:
                break
            time.sleep(interval)
            t += interval
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")

        if save_to_csv and csv_file:
            try:
                csv_file.close()
                print(GREEN + f"Measurements saved to {filename}")
            except Exception as e:
                print(RED + f"Error closing CSV file: {e}")
        if plot_data and input(GREEN + "Save plot as PNG? [y/n]: ").strip().lower() == 'y':
            plt.savefig(f"battery_plot_{timestamp}.png", facecolor='black', edgecolor='none')
            print(GREEN + f"Plot saved to battery_plot_{timestamp}.png")
        if plot_data:
            try:
                plt.close(fig)
            except Exception as e:
                print(RED + f"Error closing plot: {e}")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except KeyboardInterrupt:
        print(RED + "Measurement interrupted by user.")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def continuous_set_points():
    clear_screen()
    print_header()
    try:
        voltage1 = validate_float("Channel 1 Voltage to inject (V): ", -210, 210)
        voltage2 = validate_float("Channel 2 Voltage to inject (V): ", -210, 210)
        interval = validate_float("Interval between measurements (s): ", 0.01)
        duration = validate_float("Total duration (s): ", 0.1)
        save_to_csv = input(GREEN + "Save measurements to CSV? [y/n]: ").strip().lower() == 'y'
        plot_data = input(GREEN + "Show real-time plot? [y/n]: ").strip().lower() == 'y'

        # Set up CSV file
        csv_file = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if save_to_csv:
            filename = f"setpoints_{timestamp}.csv"
            try:
                csv_file = open(filename, 'w', newline='')
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(
                    ['Time (s)', 'Voltage CH1 (V)', 'Current CH1 (A)', 'Voltage CH2 (V)', 'Current CH2 (A)'])
                print(GREEN + f"Saving measurements to {filename}")
            except IOError as e:
                print(RED + f"Error opening CSV file: {e}")
                save_to_csv = False

        # Set up real-time plot
        times, v1s, c1s, v2s, c2s = [], [], [], [], []
        ani = None
        if plot_data:
            plt.rcParams['font.family'] = 'Courier New'
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(10, 8))
            fig.patch.set_facecolor('black')
            for ax in [ax1, ax2, ax3, ax4]:
                ax.set_facecolor('black')
            ax1.set_title('PIP-BOY 3000 Voltage CH1', color='limegreen')
            ax2.set_title('PIP-BOY 3000 Current CH1', color='limegreen')
            ax3.set_title('PIP-BOY 3000 Voltage CH2', color='limegreen')
            ax4.set_title('PIP-BOY 3000 Current CH2', color='limegreen')
            ax1.set_xlabel('Time (s)', color='limegreen')
            ax1.set_ylabel('Voltage (V)', color='limegreen')
            ax2.set_xlabel('Time (s)', color='limegreen')
            ax2.set_ylabel('Current (A)', color='limegreen')
            ax3.set_xlabel('Time (s)', color='limegreen')
            ax3.set_ylabel('Voltage (V)', color='limegreen')
            ax4.set_xlabel('Time (s)', color='limegreen')
            ax4.set_ylabel('Current (A)', color='limegreen')
            for ax in [ax1, ax2, ax3, ax4]:
                ax.grid(True, color='limegreen', linestyle='--', alpha=0.3)
                ax.tick_params(axis='both', colors='limegreen')
            line1, = ax1.plot([], [], 'limegreen', linewidth=2)
            line2, = ax2.plot([], [], 'limegreen', linewidth=2)
            line3, = ax3.plot([], [], 'limegreen', linewidth=2)
            line4, = ax4.plot([], [], 'limegreen', linewidth=2)
            plt.tight_layout()

            def update_plot(data):
                if data is None:
                    return line1, line2, line3, line4
                t, v1, c1, v2, c2 = data
                times.append(t)
                v1s.append(v1)
                c1s.append(c1)
                v2s.append(v2)
                c2s.append(c2)
                line1.set_data(times, v1s)
                line2.set_data(times, c1s)
                line3.set_data(times, v2s)
                line4.set_data(times, c2s)
                for ax in [ax1, ax2, ax3, ax4]:
                    ax.relim()
                    ax.autoscale_view()
                return line1, line2, line3, line4

            def data_gen():
                for _ in range(int(duration / interval) + 1):
                    yield times[-1] if times else 0, v1s[-1] if v1s else 0, c1s[-1] if c1s else 0, v2s[
                        -1] if v2s else 0, c2s[-1] if c2s else 0
                yield None

            ani = animation.FuncAnimation(
                fig,
                update_plot,
                frames=data_gen,
                interval=interval * 1000,
                blit=True,
                cache_frame_data=False
            )
            try:
                plt.show(block=False)
            except Exception as e:
                print(RED + f"Plotting error: {e}")
                plot_data = False

        # Measurement loop
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        if not configure_channel(1, "VOLT", voltage1, "CURR", 0.1, is_voltage=True):
            smu.write(":OUTP1 OFF")
            return
        if not configure_channel(2, "VOLT", voltage2, "CURR", 0.1, is_voltage=True):
            smu.write(":OUTP2 OFF")
            return
        smu.write(":OUTP1 ON")
        smu.write(":OUTP2 ON")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error setting voltages: {error}")
            smu.write(":OUTP1 OFF")
            smu.write(":OUTP2 OFF")
            return
        print(GREEN + "Time (s) | Voltage CH1 (V) | Current CH1 (A) | Voltage CH2 (V) | Current CH2 (A)")
        t = 0
        while t <= duration:
            v1, c1 = measure_channel(1)
            v2, c2 = measure_channel(2)
            if v1 is None or c1 is None or v2 is None or c2 is None:
                smu.write(":OUTP1 OFF")
                smu.write(":OUTP2 OFF")
                return
            print(GREEN + f"{t:.2f}       {v1:.6f}         {c1:.6f}         {v2:.6f}         {c2:.6f}")
            if save_to_csv and csv_file:
                try:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow([f"{t:.2f}", f"{v1:.6f}", f"{c1:.6f}", f"{v2:.6f}", f"{c2:.6f}"])
                except IOError as e:
                    print(RED + f"Error writing to CSV: {e}")
                    save_to_csv = False
            if plot_data:
                times.append(t)
                v1s.append(v1)
                c1s.append(c1)
                v2s.append(v2)
                c2s.append(c2)
            time.sleep(interval)
            t += interval
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")

        if save_to_csv and csv_file:
            try:
                csv_file.close()
                print(GREEN + f"Measurements saved to {filename}")
            except Exception as e:
                print(RED + f"Error closing CSV file: {e}")
        if plot_data and input(GREEN + "Save plot as PNG? [y/n]: ").strip().lower() == 'y':
            plt.savefig(f"setpoints_plot_{timestamp}.png", facecolor='black', edgecolor='none')
            print(GREEN + f"Plot saved to setpoints_plot_{timestamp}.png")
        if plot_data:
            try:
                plt.close(fig)
            except Exception as e:
                print(RED + f"Error closing plot: {e}")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except KeyboardInterrupt:
        print(RED + "Measurement interrupted by user.")
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def act_as_battery():
    clear_screen()
    print_header()
    try:
        # Connection instructions
        print(GREEN + "Connection Instructions:")
        print(GREEN + " - Channel 1: Connect board positive to CH1 High, negative to CH1 Low")
        print(GREEN + " - Channel 2: Connect board positive to CH2 High, negative to CH2 Low")

        # Input parameters for Channel 1
        print(GREEN + "\nChannel 1 Battery Parameters:")
        nominal_voltage1 = validate_float("Nominal battery voltage (V): ", 0, 210)
        internal_resistance1 = validate_float("Internal resistance (mΩ): ", 0, 10000) / 1000  # Convert mΩ to Ω
        capacity1 = validate_float("Battery capacity (mAh): ", 0, 100000)  # Keep in mAh for plotting
        min_voltage1 = validate_float("Minimum voltage (V): ", 0, nominal_voltage1)

        # Input parameters for Channel 2
        print(GREEN + "\nChannel 2 Battery Parameters:")
        nominal_voltage2 = validate_float("Nominal battery voltage (V): ", 0, 210)
        internal_resistance2 = validate_float("Internal resistance (mΩ): ", 0, 10000) / 1000  # Convert mΩ to Ω
        capacity2 = validate_float("Battery capacity (mAh): ", 0, 100000)  # Keep in mAh
        min_voltage2 = validate_float("Minimum voltage (V): ", 0, nominal_voltage2)

        # Shared parameters
        duration = validate_float("Maximum emulation duration (s): ", 0.1)
        save_to_csv = input(GREEN + "Save measurements to CSV? [y/n]: ").strip().lower() == 'y'
        plot_data = input(GREEN + "Show real-time plot? [y/n]: ").strip().lower() == 'y'

        # Set up CSV file
        csv_file = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        if save_to_csv:
            filename = f"battery_emulation_{timestamp}.csv"
            try:
                csv_file = open(filename, 'w', newline='')
                headers = ['Time (s)', 'Voltage CH1 (V)', 'Current CH1 (A)', 'SoC CH1 (%)',
                           'Discharged Capacity CH1 (mAh)',
                           'Voltage CH2 (V)', 'Current CH2 (A)', 'SoC CH2 (%)', 'Discharged Capacity CH2 (mAh)']
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(headers)
                print(GREEN + f"Saving measurements to {filename}")
            except IOError as e:
                print(RED + f"Error opening CSV file: {e}")
                save_to_csv = False

        # Set up real-time plot
        times, data = [], {1: {'voltages': [], 'currents': [], 'soc': [], 'discharged': []},
                           2: {'voltages': [], 'currents': [], 'soc': [], 'discharged': []}}
        ani = None
        if plot_data:
            plt.rcParams['font.family'] = 'Courier New'
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(10, 8))
            fig.patch.set_facecolor('black')
            for ax in [ax1, ax2, ax3, ax4]:
                ax.set_facecolor('black')
            ax1.set_title('PIP-BOY 3000 Battery Voltage', color='limegreen')
            ax2.set_title('PIP-BOY 3000 Battery Current', color='limegreen')
            ax3.set_title('PIP-BOY 3000 Battery SoC', color='limegreen')
            ax4.set_title('PIP-BOY 3000 Battery Discharged Capacity', color='limegreen')
            ax1.set_xlabel('Time (s)', color='limegreen')
            ax1.set_ylabel('Voltage (V)', color='limegreen')
            ax2.set_xlabel('Time (s)', color='limegreen')
            ax2.set_ylabel('Current (A)', color='limegreen')
            ax3.set_xlabel('Time (s)', color='limegreen')
            ax3.set_ylabel('SoC (%)', color='limegreen')
            ax4.set_xlabel('Time (s)', color='limegreen')
            ax4.set_ylabel('Discharged Capacity (mAh)', color='limegreen')
            for ax in [ax1, ax2, ax3, ax4]:
                ax.grid(True, color='limegreen', linestyle='--', alpha=0.3)
                ax.tick_params(axis='both', colors='limegreen')
            lines_v = {ch: ax1.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in [1, 2]}
            lines_c = {ch: ax2.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in [1, 2]}
            lines_s = {ch: ax3.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in [1, 2]}
            lines_d = {ch: ax4.plot([], [], 'limegreen', linewidth=2, label=f'CH{ch}')[0] for ch in [1, 2]}
            ax4.axhline(y=capacity1, color='green', linestyle='--', alpha=0.5, label='CH1 Capacity')
            ax4.axhline(y=capacity2, color='limegreen', linestyle='--', alpha=0.5, label='CH2 Capacity')
            ax1.legend()
            ax2.legend()
            ax3.legend()
            ax4.legend()
            plt.tight_layout()

            def update_plot(data_frame):
                if data_frame is None:
                    return list(lines_v.values()) + list(lines_c.values()) + list(lines_s.values()) + list(
                        lines_d.values())
                t = data_frame[0]
                times.append(t)
                for ch in [1, 2]:
                    lines_v[ch].set_data(times, data[ch]['voltages'])
                    lines_c[ch].set_data(times, data[ch]['currents'])
                    lines_s[ch].set_data(times, data[ch]['soc'])
                    lines_d[ch].set_data(times, data[ch]['discharged'])
                ax1.relim()
                ax1.autoscale_view()
                ax2.relim()
                ax2.autoscale_view()
                ax3.relim()
                ax3.autoscale_view()
                ax4.relim()
                ax4.autoscale_view()
                return list(lines_v.values()) + list(lines_c.values()) + list(lines_s.values()) + list(lines_d.values())

            def data_gen():
                for _ in range(int(duration / 0.01) + 1):
                    yield [times[-1] if times else 0] + [data[ch]['voltages'][-1] if data[ch]['voltages'] else 0 for ch
                                                         in [1, 2]]
                yield None

            ani = animation.FuncAnimation(
                fig,
                update_plot,
                frames=data_gen,
                interval=10,  # 10ms update
                blit=True,
                cache_frame_data=False
            )
            try:
                plt.show(block=False)
            except Exception as e:
                print(RED + f"Plotting error: {e}")
                plot_data = False

        # Initialize battery state
        channels = [1, 2]
        discharged_capacity = {1: 0.0, 2: 0.0}  # mAh
        soc = {1: 1.0, 2: 1.0}  # 100% SoC initially
        nominal_voltages = {1: nominal_voltage1, 2: nominal_voltage2}
        internal_resistances = {1: internal_resistance1, 2: internal_resistance2}
        capacities = {1: capacity1, 2: capacity2}
        min_voltages = {1: min_voltage1, 2: min_voltage2}

        # Configure channels
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        for ch in channels:
            if not configure_channel(ch, "VOLT", nominal_voltages[ch], "CURR", 0.1, is_voltage=True):
                smu.write(f":OUTP{ch} OFF")
                return
        for ch in channels:
            smu.write(f":OUTP{ch} ON")
            error = smu.query(":SYST:ERR?")
            if "+0" not in error:
                print(RED + f"Error enabling output on channel {ch}: {error}")
                smu.write(f":OUTP{ch} OFF")
                return

        # Battery emulation loop
        print(GREEN + "Time (s) | Voltage CH1 (V) | Current CH1 (A) | SoC CH1 (%) | Discharged CH1 (mAh) | "
                      "Voltage CH2 (V) | Current CH2 (A) | SoC CH2 (%) | Discharged CH2 (mAh)")
        t = 0
        interval = 0.01  # Fixed 10ms update for responsiveness
        while t <= duration:
            row = [f"{t:.2f}"]
            stop = False
            for ch in channels:
                v, c = measure_channel(ch)
                if v is None or c is None:
                    stop = True
                    break
                # Update discharged capacity (Q = ∫I dt, approximated as I * Δt)
                discharged_capacity[ch] += abs(c) * interval * 1000 / 3600  # Convert to mAh
                soc[ch] = max(0, (capacities[ch] - discharged_capacity[ch]) / capacities[ch])  # SoC in [0, 1]
                # Linear OCV model: OCV = nominal_voltage at SoC=1, min_voltage at SoC=0
                ocv = nominal_voltages[ch] * soc[ch] + min_voltages[ch] * (1 - soc[ch])
                # Adjust voltage for internal resistance
                v_out = ocv - c * internal_resistances[ch]
                smu.write(f":SOUR{ch}:VOLT {max(min_voltages[ch], min(v_out, nominal_voltages[ch]))}")
                row.extend([f"{v_out:.6f}", f"{c:.6f}", f"{soc[ch] * 100:.2f}", f"{discharged_capacity[ch]:.2f}"])
                data[ch]['voltages'].append(v_out)
                data[ch]['currents'].append(c)
                data[ch]['soc'].append(soc[ch] * 100)
                data[ch]['discharged'].append(discharged_capacity[ch])
                if v_out <= min_voltages[ch] or soc[ch] <= 0:
                    stop = True
            print(GREEN + "       ".join(row))
            if save_to_csv and csv_file:
                try:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(row)
                except IOError as e:
                    print(RED + f"Error writing to CSV: {e}")
                    save_to_csv = False
            times.append(t)
            if stop:
                break
            time.sleep(interval)
            t += interval
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")

        if save_to_csv and csv_file:
            try:
                csv_file.close()
                print(GREEN + f"Measurements saved to {filename}")
            except Exception as e:
                print(RED + f"Error closing CSV file: {e}")
        if plot_data and input(GREEN + "Save plot as PNG? [y/n]: ").strip().lower() == 'y':
            plt.savefig(f"battery_emulation_plot_{timestamp}.png", facecolor='black', edgecolor='none')
            print(GREEN + f"Plot saved to battery_emulation_plot_{timestamp}.png")
        if plot_data:
            try:
                plt.close(fig)
            except Exception as e:
                print(RED + f"Error closing plot: {e}")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except KeyboardInterrupt:
        print(RED + "Battery emulation interrupted by user.")
        for ch in channels:
            smu.write(f":OUTP{ch} OFF")
        if save_to_csv and csv_file:
            try:
                csv_file.close()
            except Exception:
                pass
        if plot_data:
            try:
                plt.close(fig)
            except Exception:
                pass
    except ValueError as e:
        print(RED + f"Invalid measurement data: {e}")
    input(GREEN + "[Press Enter to continue]")


def turn_off_output():
    clear_screen()
    print_header()
    try:
        smu.write(":OUTP1 OFF")
        smu.write(":OUTP2 OFF")
        error = smu.query(":SYST:ERR?")
        if "+0" not in error:
            print(RED + f"Error turning off outputs: {error}")
            return
        print(GREEN + "Outputs 1 and 2 turned off.")
    except pyvisa.VisaIOError as e:
        print(RED + f"Communication error with SMU: {e}")
    input(GREEN + "[Press Enter to continue]")


def main():
    try:
        while True:
            clear_screen()
            print_header()
            print_menu()
            option = input(GREEN + "Select an option: ").strip()
            if option == '0':
                turn_off_output()
                break
            elif option == '1':
                inject_voltage()
            elif option == '2':
                inject_current()
            elif option == '3':
                measure_log()
            elif option == '4':
                generate_pwm()
            elif option == '5':
                generate_waveform()
            elif option == '6':
                act_as_load()
            elif option == '7':
                characterize_battery()
            elif option == '8':
                continuous_set_points()
            elif option == '9':
                act_as_battery()
            elif option == '10':
                turn_off_output()
            else:
                print(RED + "Invalid option.")
                input(GREEN + "[Press Enter to continue]")
    finally:
        if smu is not None:
            try:
                smu.write(":OUTP1 OFF")
                smu.write(":OUTP2 OFF")
                smu.close()
                print(GREEN + "VISA resource closed.")
            except pyvisa.VisaIOError as e:
                print(RED + f"Error closing resource: {e}")
        if rm is not None:
            rm.close()

if __name__ == "__main__":
    main()