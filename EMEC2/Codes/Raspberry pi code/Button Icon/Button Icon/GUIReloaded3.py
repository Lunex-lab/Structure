import os
import time
import threading
import tkinter as tk
from datetime import datetime
from picamera2 import Picamera2
from PIL import Image, ImageTk
import psutil
import serial
import adafruit_dht
import subprocess
import pynmea2
import seabreeze.spectrometers as sb
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------- Configuration ----------
SAVE_PATH = "/home/ulrich/Desktop/New code/Button Icon"
IMAGE_PATH = os.path.join(SAVE_PATH, "images")
VIDEO_PATH = os.path.join(SAVE_PATH, "videos")

os.makedirs(IMAGE_PATH, exist_ok=True)
os.makedirs(VIDEO_PATH, exist_ok=True)

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())

# Initialize serial communication with Arduino
# ser = serial.Serial('/dev/ttyACM0', 9600)

# Global variables for recording
recording = False
encoder = None
video_filename = ""

# Global variables for GPS
gps_latitude = "N/A"
gps_longitude = "N/A"

# Function to get the current timestamp
def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

# ---------- Tkinter GUI ----------
root = tk.Tk()
root.title("EMEC PROTOTYPE GUI")
root.resizable(False, False)
root.geometry("1200x900")  # Increased height to accommodate the graph
root.configure(bg='#2d2d2d')  # Dark theme background

# Style configuration
BUTTON_STYLE = {
    'activebackground': '#404040',
    'activeforeground': 'white',
    'bg': '#3d3d3d',
    'fg': 'white',
    'bd': 0,
    'padx': 10,
    'pady': 5,
    'font': ('Arial', 10, 'bold')
}
# Variable to store the dark spectrum and baseline correction
dark_spectrum = None
baseline_corrected_spectrum = None

# Spectrometer variables
spec = None
wavelengths_spec = None
intensities_spec = None

# ---------- System Monitoring Functions ----------
def get_cpu_temp():
    try:
        temp = os.popen('vcgencmd measure_temp').readline()
        return temp.replace("temp=", "").replace("'C\n", "°C")
    except:
        return "N/A"

def get_system_info():
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    mem_percent = memory.percent
    mem_used = round(memory.used / 1024 / 1024, 1)
    mem_total = round(memory.total / 1024 / 1024, 1)
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    disk_free = round(disk.free / 1024 / 1024 / 1024, 1)
    return {
        'cpu_temp': get_cpu_temp(),
        'cpu_usage': f"{cpu_percent}%",
        'memory': f"{mem_used}MB / {mem_total}MB ({mem_percent}%)",
        'disk': f"{disk_free}GB free ({disk_percent}% used)"
    }

def read_gps_data():
    global gps_latitude, gps_longitude
    try:
        ser = serial.Serial('/dev/ttyS0', 9600, timeout=0)
        while True:
            new_data = ser.readline().decode('utf-8')
            if new_data.startswith('$GPGGA'):
                newmsg = pynmea2.parse(new_data)
                gps_latitude = newmsg.latitude
                gps_longitude = newmsg.longitude
            time.sleep(0.1)
    except Exception as e:
        print(f"Error reading GPS data: {e}")

gps_thread = threading.Thread(target=read_gps_data, daemon=True)
gps_thread.start()

def read_dht11_data():
    try:
        sensor = adafruit_dht.DHT11
        pin = 4
        humidity, temperature = adafruit_dht.read_retry(sensor, pin)
        if humidity is not None and temperature is not None:
            return f"{temperature}°C", f"{humidity}%"
        else:
            return "N/A", "N/A"
    except Exception as e:
        print(f"Error reading DHT11 data: {e}")
        return "N/A", "N/A"

def update_system_info():
    system_info = get_system_info()
    dht11_data = read_dht11_data()

    system_info_values['cpu_temp'].config(text=system_info['cpu_temp'])
    system_info_values['cpu_usage'].config(text=system_info['cpu_usage'])
    system_info_values['memory'].config(text=system_info['memory'])
    system_info_values['disk'].config(text=system_info['disk'])

    environment_info_values['latitude'].config(text=str(gps_latitude))
    environment_info_values['longitude'].config(text=str(gps_longitude))
    environment_info_values['temperature'].config(text=dht11_data[0])
    environment_info_values['humidity'].config(text=dht11_data[1])

    root.after(1000, update_system_info)

def update_preview():
    if not picam2.started:
        return

    try:
        frame = picam2.capture_array()
        img = Image.fromarray(frame).resize((400, 400))
        tk_img = ImageTk.PhotoImage(img)
        image_label.config(image=tk_img)
        image_label.image = tk_img
    except Exception as e:
        print(f"Preview error: {e}")

    root.after(50, update_preview)

def start_preview():
    try:
        picam2.start()
        update_preview()
    except Exception as e:
        print(f"Error starting preview: {e}")

def stop_preview():
    try:
        picam2.stop()
        image_label.config(image='')
    except Exception as e:
        print(f"Error stopping preview: {e}")

def capture_image():
    def _capture():
        try:
            filename = os.path.join(IMAGE_PATH, f"img_{get_timestamp()}.jpg")
            img = picam2.capture_image()
            img = img.convert("RGB")
            img.save(filename)
        except Exception as e:
            print(f"Error capturing image: {e}")

    threading.Thread(target=_capture, daemon=True).start()

def start_recording():
    show_countdown_timer(3)

def show_countdown_timer(count):
    countdown_label.config(text=str(count))
    if count > 0:
        root.after(1000, show_countdown_timer, count - 1)
    else:
        countdown_label.config(text="")
        start_recording_after_countdown()

def start_recording_after_countdown():
    global recording, encoder, video_filename
    if recording:
        return

    try:
        video_filename = os.path.join(VIDEO_PATH, f"video_{get_timestamp()}.h264")
        encoder = H264Encoder()
        recording = True
        picam2.stop()
        picam2.configure(picam2.create_video_configuration())
        picam2.start()
        picam2.start_recording(encoder, video_filename)
    except Exception as e:
        print(f"Error starting recording: {e}")

def stop_recording():
    global recording, encoder, video_filename
    if not recording:
        return

    def _stop():
        global recording, encoder, video_filename
        try:
            picam2.stop_recording()
            picam2.stop()
            picam2.configure(picam2.create_still_configuration())
            picam2.start()
            recording = False
            encoder = None

            if video_filename:
                mp4_filename = video_filename.replace(".h264", ".mp4")
                def convert_to_mp4():
                    subprocess.run(["ffmpeg", "-i", video_filename, "-c:v", "copy", "-movflags", "+faststart", mp4_filename], check=True)
                    os.remove(video_filename)
                threading.Thread(target=convert_to_mp4, daemon=True).start()
        except Exception as e:
            print(f"Error stopping recording: {e}")

    threading.Thread(target=_stop, daemon=True).start()

# D-pad controller
def send_command(command):
    ser.write((command + '\n').encode())

def forward():
    send_command('forward')

def backward():
    send_command('backward')

def left():
    send_command('left')

def right():
    send_command('right')

def stop():
    send_command('stop')

def send_speed():
    speed = speed_slider.get()
    ser.write(f"speed {speed}\n".encode())

# Load and resize icons
def load_icon(path, size):
    try:
        return ImageTk.PhotoImage(Image.open(path).resize(size, Image.ANTIALIAS))
    except IOError:
        print(f"Error loading icon: {path}")
        return None

# Connect Button
def connect_spectrometer():
    global spec, wavelengths_spec
    try:
        devices = sb.list_devices()
        if devices:
            spec = sb.Spectrometer(devices[0])
            spec.integration_time_micros(50000)  # Set integration time in microseconds
            wavelengths_spec = spec.wavelengths()
            spectrometer_status.config(text="Spectrometer Detected: " + spec.model)
        else:
            spectrometer_status.config(text="No spectrometer found")
    except Exception as e:
        spectrometer_status.config(text="Failed to detect spectrometer: " + str(e))

def update_spectrograph():
    try:
        wavelengths = spectrometer.wavelengths()
        intensities = spectrometer.intensities()
        ax.clear()
        ax.plot(wavelengths, intensities)
        canvas.draw()
        root.after(100, update_spectrograph)
    except Exception as e:
        print(f"Error updating spectrograph: {e}")

# Set Trigger Mode Button
def set_trigger_mode():
    try:
        selected_mode = int(trigger_mode_var.get())
        # Placeholder for setting the trigger mode on the spectrometer
        print(f"Trigger mode set to {selected_mode}")
        # Example: spectrometer.set_trigger_mode(selected_mode)
    except Exception as e:
        print(f"Error setting trigger mode: {e}")
        
# Define Dark substraction function        
def dark_subtraction():
    global dark_spectrum
    try:
        # Capture the dark spectrum (with no light source)
        dark_wavelengths = spectrometer.wavelengths()
        dark_intensities = spectrometer.intensities()
        dark_spectrum = (dark_wavelengths, dark_intensities)
        print("Dark spectrum captured and stored.")
    except Exception as e:
        print(f"Error capturing dark spectrum: {e}")

# Define the save function
def save_data():
    try:
        # Get the current timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Define the file path
        save_path = os.path.join(SAVE_PATH, "spectra")
        os.makedirs(save_path, exist_ok=True)
        file_name = f"spectrum_{timestamp}.csv"
        file_path = os.path.join(save_path, file_name)

        # Get the spectrum data
        wavelengths = spectrometer.wavelengths()
        intensities = spectrometer.intensities()

        # Save the data to a CSV file
        with open(file_path, 'w') as file:
            file.write("Wavelength,Intensity\n")
            for wl, intensity in zip(wavelengths, intensities):
                file.write(f"{wl},{intensity}\n")

        print(f"Data saved to {file_path}")
    except Exception as e:
        print(f"Error saving data: {e}")

# Smooth Spectrum Button
def smooth_spectrum():
    global smoothed_spectrum
    try:
        # Capture the current spectrum
        wavelengths = spectrometer.wavelengths()
        intensities = spectrometer.intensities()

        if dark_spectrum is not None:
            # Apply dark subtraction if dark spectrum is available
            dark_wavelengths, dark_intensities = dark_spectrum
            corrected_intensities = intensities - dark_intensities
        else:
            corrected_intensities = intensities

        if baseline_corrected_spectrum is not None:
            # Use baseline-corrected spectrum if available
            wavelengths, corrected_intensities = baseline_corrected_spectrum

        # Apply a simple moving average for smoothing
        window_size = 5  # Define the window size for the moving average
        smoothed_intensities = np.convolve(corrected_intensities, np.ones(window_size)/window_size, mode='valid')

        # Store the smoothed spectrum
        smoothed_spectrum = (wavelengths[:len(smoothed_intensities)], smoothed_intensities)
        print("Spectrum smoothed.")
    except Exception as e:
        print(f"Error smoothing spectrum: {e}")

# Baseline Correction Button
def baseline_correction():
    global baseline_corrected_spectrum
    try:
        # Capture the current spectrum
        wavelengths = spectrometer.wavelengths()
        intensities = spectrometer.intensities()

        if dark_spectrum is not None:
            # Apply dark subtraction if dark spectrum is available
            dark_wavelengths, dark_intensities = dark_spectrum
            corrected_intensities = intensities - dark_intensities
        else:
            corrected_intensities = intensities

        # Fit a polynomial to the baseline (using the lowest 10% of intensities)
        baseline_points = np.percentile(corrected_intensities, 10)
        baseline_indices = np.where(corrected_intensities <= baseline_points)[0]
        baseline_wavelengths = wavelengths[baseline_indices]
        baseline_intensities = corrected_intensities[baseline_indices]

        # Fit a polynomial to the baseline points
        coefficients = np.polyfit(baseline_wavelengths, baseline_intensities, 2)  # 2nd order polynomial
        baseline = np.polyval(coefficients, wavelengths)

        # Subtract the baseline from the corrected intensities
        baseline_corrected_intensities = corrected_intensities - baseline

        # Store the baseline-corrected spectrum
        baseline_corrected_spectrum = (wavelengths, baseline_corrected_intensities)
        print("Baseline correction applied.")
    except Exception as e:
        print(f"Error applying baseline correction: {e}")

# Start Logging Button
def start_logging():
    global logging
    if not logging:
        logging = True
        logging_thread = threading.Thread(target=logging_loop)
        logging_thread.start()
        print("Logging started.")
    else:
        print("Logging is already running.")

# Stop Logging Button
def stop_logging():
    global logging
    logging = False
    print("Logging stopped.")


def set_integration_time():
    try:
        value = int(integration_time_entry.get())
        if 1 <= value <= 1000:
            # Placeholder for setting the integration time
            print(f"Integration time set to {value} ms")
        else:
            print("Integration time must be between 1 and 1000 ms")
    except ValueError:
        print("Invalid input for integration time")

# Function to update the spectrometer status
def update_spectrometer_status():
    try:
        # Check if the spectrometer is connected
        if spectrometer is not None:
            spectrometer_status_label.config(text="Spectrometer Status: Connected", fg='green')
        else:
            spectrometer_status_label.config(text="Spectrometer Status: Disconnected", fg='red')
    except Exception as e:
        print(f"Error updating spectrometer status: {e}")
        spectrometer_status_label.config(text="Spectrometer Status: Disconnected", fg='red')
        
# Define icon paths and sizes
icon_paths = {
    "start_preview": "start_preview.png",
    "stop_preview": "stop_preview.png",
    "capture_image": "take_picture.png",
    "start_recording": "start_recording.png",
    "stop_recording": "stop_recording.png",
    "connect": "Spectrometer.png"
}

icon_size = (50, 50)  # Adjust the size as needed

icons = {key: load_icon(path, icon_size) for key, path in icon_paths.items()}

# ---------- GUI Layout Enhancements ----------
main_frame = tk.Frame(root, bg='#2d2d2d')
main_frame.pack(fill='both', expand=True, padx=10, pady=10)

status_frame = tk.Frame(main_frame, bg='#2d2d2d', width=350)
status_frame.pack(side='left', fill='y', padx=(0, 10))

# System Status Panel
system_info_frame = tk.Frame(status_frame, bg='#3d3d3d', width=350, height=200, borderwidth=2, relief='solid')
system_info_frame.pack_propagate(0)
system_info_frame.pack(fill='x', pady=(0, 10))

tk.Label(system_info_frame, text="SYSTEM STATUS", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(10, 15))

system_info_labels = {
    'cpu_temp': "CPU Temperature:",
    'cpu_usage': "CPU Usage:",
    'memory': "Memory Usage:",
    'disk': "Disk Space:"
}

system_info_values = {}
for key, text in system_info_labels.items():
    frame = tk.Frame(system_info_frame, bg='#3d3d3d')
    frame.pack(fill='x', padx=10, pady=5)
    
    tk.Label(frame, text=text, bg='#3d3d3d', fg='#a0a0a0', width=15, anchor='w').pack(side='left')
    system_info_values[key] = tk.Label(frame, text="", bg='#3d3d3d', fg='white')
    system_info_values[key].pack(side='left')

# Environment Status Panel
environment_info_frame = tk.Frame(status_frame, bg='#3d3d3d', width=350, height=200, borderwidth=2, relief='solid')
environment_info_frame.pack_propagate(0)
environment_info_frame.pack(fill='x', pady=(0, 10))

tk.Label(environment_info_frame, text="ENVIRONMENT STATUS", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(10, 15))

environment_info_labels = {
    'latitude': "Latitude:",
    'longitude': "Longitude:",
    'temperature': "Ambient Temperature:",
    'humidity': "Ambient Humidity:"
}

environment_info_values = {}
for key, text in environment_info_labels.items():
    frame = tk.Frame(environment_info_frame, bg='#3d3d3d')
    frame.pack(fill='x', padx=10, pady=5)
    
    tk.Label(frame, text=text, bg='#3d3d3d', fg='#a0a0a0', width=15, anchor='w').pack(side='left')
    environment_info_values[key] = tk.Label(frame, text="", bg='#3d3d3d', fg='white')
    environment_info_values[key].pack(side='left')

# Control Section (Moved to the top of the preview window)
control_frame = tk.Frame(main_frame, bg='#2d2d2d')
control_frame.pack(side='top', padx=(15, 0), pady=(0, 10))

# Button configuration with icons
button_config = [
    (icons["start_preview"], start_preview),  # Start Preview
    (icons["stop_preview"], stop_preview),   # Stop Preview
    (icons["capture_image"], capture_image), # Take Picture
    (icons["start_recording"], start_recording), # Start Record
    (icons["stop_recording"], stop_recording),  # Stop Record
]

for icon, command in button_config:
    btn = tk.Button(control_frame, image=icon, command=command, **BUTTON_STYLE, highlightbackground='#4CAF50', highlightcolor='#4CAF50', highlightthickness=2)
    btn.image = icon  # Keep a reference to avoid garbage collection
    btn.pack(side='left', padx=5, pady=5)

connect_button = tk.Button(control_frame, image=icons["connect"], command=connect_spectrometer, **BUTTON_STYLE)
connect_button.image = icons["connect"]
connect_button.pack(side='left', padx=5, pady=5)

# Container frame
top_container_frame=tk.Frame(main_frame, bg='#2d2d2d', width=820, height=400, borderwidth=2, relief='solid')
top_container_frame.pack(side='top', fill='x')

# Preview Section
preview_frame = tk.Frame(top_container_frame, bg='black', width=400, height=400, borderwidth=2, relief='solid')
preview_frame.pack_propagate(0)
preview_frame.pack(side='right', padx=2,pady=2,fill='none',expand=False)

image_label = tk.Label(preview_frame, bg='black', borderwidth=2, relief='solid')
image_label.pack(fill='both', expand=True)

# Spectrograph Section
spectrograph_frame = tk.Frame(top_container_frame, bg='black', width=400, height=400, borderwidth=2, relief='solid')
spectrograph_frame.pack(side='left', padx=2,pady=2,fill='none',expand=False)

fig, ax = plt.subplots(figsize=(4,4))
canvas = FigureCanvasTkAgg(fig, master=spectrograph_frame)
canvas.get_tk_widget().pack(fill='both', expand=True)

# Rover Controller Frame
rover_controller_frame = tk.Frame(status_frame, bg='#3d3d3d', width=350, height=200, borderwidth=2, relief='solid')
rover_controller_frame.pack(fill='x', pady=(0, 5))

tk.Label(rover_controller_frame, text="ROVER CONTROLLER", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(0, 5))

# D-pad frame
d_pad_frame = tk.Frame(rover_controller_frame, bg='#3d3d3d')
d_pad_frame.pack(pady=(0, 5))

# Create D-pad buttons
button_up = tk.Button(d_pad_frame, text="↑", width=2, height=2, font=('Helvetica', 20), command=forward, borderwidth=1, relief='solid')
button_up.grid(row=0, column=1, padx=1, pady=1)

button_left = tk.Button(d_pad_frame, text="←", width=2, height=2, font=('Helvetica', 20), command=left, borderwidth=1, relief='solid')
button_left.grid(row=1, column=0, padx=1, pady=1)

button_center = tk.Button(d_pad_frame, text="•", width=2, height=2, font=('Helvetica', 20), command=stop, borderwidth=1, relief='solid')
button_center.grid(row=1, column=1, padx=1, pady=1)

button_right = tk.Button(d_pad_frame, text="→", width=2, height=2, font=('Helvetica', 20), command=right, borderwidth=1, relief='solid')
button_right.grid(row=1, column=2, padx=1, pady=1)

button_down = tk.Button(d_pad_frame, text="↓", width=2, height=2, font=('Helvetica', 20), command=backward, borderwidth=1, relief='solid')
button_down.grid(row=2, column=1, padx=1, pady=1)

# Motor Speed Frame
speed_control_frame = tk.Frame(status_frame, bg='#3d3d3d', width=350, height=100, borderwidth=2, relief='solid')
speed_control_frame.pack(fill='x', pady=(5, 10))

tk.Label(speed_control_frame, text="MOTOR SPEED", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(10, 15))

# Speed slider
speed_slider = tk.Scale(speed_control_frame, from_=0, to=255, orient='horizontal', label="Speed", length=300, bg='#3d3d3d', fg='white')
speed_slider.set(128)  # Default speed
speed_slider.pack()

# Button to send speed value to Arduino
send_speed_button = tk.Button(speed_control_frame, text="Set Speed", command=send_speed, **BUTTON_STYLE)
send_speed_button.pack(pady=5)

# Spectrometer Control Frame
spectrometer_control_frame = tk.Frame(main_frame, bg='#2d2d2d', width=430, height=400, borderwidth=2, relief='solid')
spectrometer_control_frame.pack(side='left', padx=5, pady=10)
spectrometer_control_frame.pack_propagate(0)  # Prevent the frame from resizing

tk.Label(spectrometer_control_frame, text="Spectrometer Control", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(10, 15))

# Integration Time Section
integration_time_section = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
integration_time_section.pack(side='top', fill='x', pady=5, padx=2)

# Integration Time Label
integration_time_label = tk.Label(integration_time_section, text="Integration Time (ms):", bg='#2d2d2d', fg='white', font=('Arial', 12, 'bold'))
integration_time_label.pack(side='left', padx=2)

# Integration Time Entry
integration_time_entry = tk.Entry(integration_time_section, width=10)
integration_time_entry.pack(side='left', padx=2)
set_integration_time_button = tk.Button(integration_time_section, text="Set Integration Time", command=set_integration_time, **BUTTON_STYLE)
set_integration_time_button.pack(side='left', padx=2)

# Trigger Mode Section
trigger_mode_section = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
trigger_mode_section.pack(side='top', fill='x', pady=5, padx=2)

# Trigger Mode Label
trigger_mode_label = tk.Label(trigger_mode_section, text="Trigger Mode:", bg='#2d2d2d', fg='white', font=('Arial', 12, 'bold'))
trigger_mode_label.pack(side='left', padx=2)

# Trigger Mode Dropdown
trigger_mode_var = tk.StringVar(trigger_mode_section)
trigger_mode_var.set("1")  # Default value
trigger_mode_options = ["1", "2", "3"]
trigger_mode_dropdown = tk.OptionMenu(trigger_mode_section, trigger_mode_var, *trigger_mode_options)
trigger_mode_dropdown.config(bg='#3d3d3d', fg='white', font=('Arial', 10, 'bold'), highlightbackground='#4CAF50', highlightcolor='#4CAF50', highlightthickness=1, width= 14)
trigger_mode_dropdown.pack(side='left', padx=2)
set_trigger_mode_button = tk.Button(trigger_mode_section, text="Set Trigger", command=set_trigger_mode, **BUTTON_STYLE)
set_trigger_mode_button.pack(side='left', padx=6)

# Buttons Section for Dark Subtraction and Baseline Correction and save data
buttons_section = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
buttons_section.pack(side='top', fill='x', pady=5, padx=2)

dark_subtraction_button = tk.Button(buttons_section, text="Dark Subtraction", command=dark_subtraction, **BUTTON_STYLE)
dark_subtraction_button.pack(side='left', padx=5, pady=5)

baseline_correction_button = tk.Button(buttons_section, text="Baseline Correction", command=baseline_correction, **BUTTON_STYLE)
baseline_correction_button.pack(side='left', padx=5, pady=5)

smooth_spectrum_button = tk.Button(buttons_section, text="Smooth Spectrum", command=smooth_spectrum, **BUTTON_STYLE)
smooth_spectrum_button.pack(side='left', padx=5, pady=5)


# Buttons Section for Log
buttons_section2 = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
buttons_section2.pack(side='top', fill='x', pady=5, padx=2)

start_logging_button = tk.Button(buttons_section2, text="Start Logging", command=start_logging, **BUTTON_STYLE)
start_logging_button.pack(side='left', padx=5, pady=5)

stop_logging_button = tk.Button(buttons_section2, text="Stop Logging", command=stop_logging, **BUTTON_STYLE)
stop_logging_button.pack(side='left', padx=5, pady=5)

save_data_button = tk.Button(buttons_section2, text="Save Data", command=save_data, **BUTTON_STYLE)
save_data_button.pack(side='left', padx=5, pady=5)

# Spectrometer Status Section
spectrometer_status_section = tk.Frame(status_frame, bg='#2d2d2d')
spectrometer_status_section.pack(side='top', fill='x', pady=5, padx=2)

# Spectrometer Status Label
spectrometer_status_label = tk.Label(spectrometer_status_section, text="No spectrometer found", bg='#2d2d2d', fg='white', font=('Arial', 12, 'bold'))
spectrometer_status_label.pack(side='left', padx=2)


# Start system monitoring
update_system_info()

# Call the function to update the status initially
update_spectrometer_status()

root.mainloop()
