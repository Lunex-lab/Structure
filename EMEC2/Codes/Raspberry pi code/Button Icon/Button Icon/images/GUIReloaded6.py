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
import numpy as np
from picamera2.encoders import H264Encoder

# ---------- Configuration ----------
SAVE_PATH = "/home/ulrich/Desktop/New code/Button Icon"
IMAGE_PATH = os.path.join(SAVE_PATH, "images")
VIDEO_PATH = os.path.join(SAVE_PATH, "videos")

os.makedirs(IMAGE_PATH, exist_ok=True)
os.makedirs(VIDEO_PATH, exist_ok=True)

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())

#Initialize serial communication with Arduino
#ser = serial.Serial('/dev/ttyACM0', 9600)

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
    'padx': 5,
    'pady': 5,
    'font': ('Arial', 10, 'bold')
}

# Variable to store the dark spectrum and baseline correction
dark_spectrum = None
baseline_corrected_spectrum = None
smoothed_spectrum = None

# Spectrometer variables
spec = None
wavelengths_spec = None
intensities_spec = None

# Global variable to control logging
logging = False
log_interval = 1000  # Default log interval in milliseconds

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
        config = picam2.create_preview_configuration(main={"size":(400,400)}, buffer_count=3)
        picam2.configure(config)
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

# Function to capture an image and plot RGB intensity vs. wavelength
def capture_image():
    try:
        # Capture an image using the Pi Camera
        picam2.start()
        frame = picam2.capture_array()
        picam2.stop()

        # Convert the captured frame to an RGB image
        img = Image.fromarray(frame)
        img = img.resize((400, 400))

        # Ensure the image is in RGB format before saving
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Save the captured image
        timestamp = get_timestamp()
        filename = os.path.join(IMAGE_PATH, f"img_{timestamp}.jpg")
        img.save(filename)
        print(f"Image saved to {filename}")

        # Extract the RGB channels
        img_array = np.array(img)
        red_channel = img_array[:, :, 0].flatten()
        green_channel = img_array[:, :, 1].flatten()
        blue_channel = img_array[:, :, 2].flatten()

        # Calculate the average intensity for each channel
        avg_red_intensity = np.mean(red_channel)
        avg_green_intensity = np.mean(green_channel)
        avg_blue_intensity = np.mean(blue_channel)

        # Clear the previous plot
        rgb_ax.clear()

        # Plot the average intensities as lines
        wavelengths = [470, 530, 635]  # Updated wavelengths for RGB
        intensities = [avg_blue_intensity, avg_green_intensity, avg_red_intensity]
        rgb_ax.plot([470, 470], [0, avg_blue_intensity], color='blue', label='Blue')
        rgb_ax.plot([530, 530], [0, avg_green_intensity], color='green', label='Green')
        rgb_ax.plot([635, 635], [0, avg_red_intensity], color='red', label='Red')

        # Add markers at the average intensity points
        rgb_ax.scatter([470], [avg_blue_intensity], color='blue')
        rgb_ax.scatter([530], [avg_green_intensity], color='green')
        rgb_ax.scatter([635], [avg_red_intensity], color='red')

        # Add labels and title
        rgb_ax.set_title('Average RGB Intensity vs. Wavelength')
        rgb_ax.set_xlabel('Wavelength (nm)')
        rgb_ax.set_ylabel('Average Intensity')
        rgb_ax.set_xlim([150, 925])  # Adjusted x-axis range to accommodate new wavelengths
        rgb_ax.set_ylim([0, max(intensities) * 1.1])

        # Draw the plot on the canvas
        rgb_canvas.draw()
        print("RGB plot updated successfully.")
    except Exception as e:
        print(f"Error capturing image and plotting RGB: {e}")


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
            spectrometer_status_label.config(text="Spectrometer Detected: " + spec.model, fg='green')
        else:
            spectrometer_status_label.config(text="No spectrometer found", fg='red')
    except Exception as e:
        spectrometer_status_label.config(text="Failed to detect spectrometer: " + str(e), fg='red')

def disconnect_spectrometer():
    global spec
    try:
        if spec is not None:
            spec.close()
            spec = None
            spectrometer_status_label.config(text="Spectrometer Disconnected", fg='red')
    except Exception as e:
        spectrometer_status_label.config(text="Failed to disconnect spectrometer: " + str(e), fg='red')

# Function to update the spectrometer plot
def update_spectrometer_plot():
    try:
        if spec is not None:
            wavelengths = spec.wavelengths()
            intensities = spec.intensities()

            # Clear the previous plot
            ax.clear()

            # Plot the spectral data
            ax.plot(wavelengths, intensities, label='Spectrum')

            # Dynamically set y-axis limits based on the measured intensities
            min_intensity = np.min(intensities) * 0.9  # 10% below the minimum intensity
            max_intensity = np.max(intensities) * 1.1  # 10% above the maximum intensity
            ax.set_ylim([min_intensity, max_intensity])

            # Add labels and title
            ax.set_title('Spectral Intensity vs. Wavelength')
            ax.set_xlabel('Wavelength (nm)')
            ax.set_ylabel('Intensity')
            ax.legend()

            # Draw the plot on the canvas
            canvas.draw()

        # Schedule the next update
        root.after(100, update_spectrometer_plot)  # Update every 1 second
    except Exception as e:
        print(f"Error updating spectrometer plot: {e}")
        
def set_integration_time():
    try:
        value = int(integration_time_entry.get())
        if 1 <= value <= 1000:
            if spec is not None:
                spec.integration_time_micros(value * 1000)  # Convert ms to microseconds
                print(f"Integration time set to {value} ms")
            else:
                print("Spectrometer is not connected.")
        else:
            print("Integration time must be between 1 and 1000 ms")
    except ValueError:
        print("Invalid input for integration time")
        
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
        if spec is not None:
            dark_wavelengths = spec.wavelengths()
            dark_intensities = spec.intensities()
            dark_spectrum = (dark_wavelengths, dark_intensities)
            print("Dark spectrum captured and stored.")
        else:
            print("Spectrometer is not connected.")
    except Exception as e:
        print(f"Error capturing dark spectrum: {e}")

# Define the save function
def save_data():
    try:
        if spec is not None:
            wavelengths = spec.wavelengths()
            intensities = spec.intensities()
            timestamp = get_timestamp()
            save_path = os.path.join(SAVE_PATH, "spectra")
            os.makedirs(save_path, exist_ok=True)
            file_name = f"spectrum_{timestamp}.csv"
            file_path = os.path.join(save_path, file_name)

            with open(file_path, 'w') as file:
                file.write("Wavelength,Intensity\n")
                for wl, intensity in zip(wavelengths, intensities):
                    file.write(f"{wl},{intensity}\n")

            print(f"Data saved to {file_path}")
        else:
            print("Spectrometer is not connected.")
    except Exception as e:
        print(f"Error saving data: {e}")

# Smooth Spectrum Button
def smooth_spectrum():
    global smoothed_spectrum
    try:
        if spec is not None:
            wavelengths = spec.wavelengths()
            intensities = spec.intensities()

            if dark_spectrum is not None:
                dark_wavelengths, dark_intensities = dark_spectrum
                corrected_intensities = intensities - dark_intensities
            else:
                corrected_intensities = intensities

            if baseline_corrected_spectrum is not None:
                wavelengths, corrected_intensities = baseline_corrected_spectrum

            window_size = 5  # Define the window size for the moving average
            smoothed_intensities = np.convolve(corrected_intensities, np.ones(window_size)/window_size, mode='valid')

            smoothed_spectrum = (wavelengths[:len(smoothed_intensities)], smoothed_intensities)
            print("Spectrum smoothed.")
        else:
            print("Spectrometer is not connected.")
    except Exception as e:
        print(f"Error smoothing spectrum: {e}")

# Baseline Correction Button
def baseline_correction():
    global baseline_corrected_spectrum
    try:
        if spec is not None:
            wavelengths = spec.wavelengths()
            intensities = spec.intensities()

            if dark_spectrum is not None:
                dark_wavelengths, dark_intensities = dark_spectrum
                corrected_intensities = intensities - dark_intensities
            else:
                corrected_intensities = intensities

            baseline_points = np.percentile(corrected_intensities, 10)
            baseline_indices = np.where(corrected_intensities <= baseline_points)[0]
            baseline_wavelengths = wavelengths[baseline_indices]
            baseline_intensities = corrected_intensities[baseline_indices]

            coefficients = np.polyfit(baseline_wavelengths, baseline_intensities, 2)  # 2nd order polynomial
            baseline = np.polyval(coefficients, wavelengths)

            baseline_corrected_intensities = corrected_intensities - baseline

            baseline_corrected_spectrum = (wavelengths, baseline_corrected_intensities)
            print("Baseline correction applied.")
        else:
            print("Spectrometer is not connected.")
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

def logging_loop():
    global logging, log_interval
    while logging:
        try:
            if spec is not None:
                wavelengths = spec.wavelengths()
                intensities = spec.intensities()

                # Apply dark subtraction if dark spectrum is available
                if dark_spectrum is not None:
                    dark_wavelengths, dark_intensities = dark_spectrum
                    corrected_intensities = intensities - dark_intensities
                else:
                    corrected_intensities = intensities

                # Apply baseline correction if baseline-corrected spectrum is available
                if baseline_corrected_spectrum is not None:
                    wavelengths, corrected_intensities = baseline_corrected_spectrum

                # Apply smoothing if smoothed spectrum is available
                if smoothed_spectrum is not None:
                    wavelengths, corrected_intensities = smoothed_spectrum

                # Save the data to a CSV file
                timestamp = get_timestamp()
                save_path = os.path.join(SAVE_PATH, "logs")
                os.makedirs(save_path, exist_ok=True)
                file_name = f"log_{timestamp}.csv"
                file_path = os.path.join(save_path, file_name)

                with open(file_path, 'w') as file:
                    file.write("Wavelength,Intensity\n")
                    for wl, intensity in zip(wavelengths, corrected_intensities):
                        file.write(f"{wl},{intensity}\n")

                print(f"Log saved to {file_path}")
            else:
                print("Spectrometer is not connected.")
        except Exception as e:
            print(f"Error during logging: {e}")
        time.sleep(log_interval / 1000)  # Convert milliseconds to seconds

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
control_frame.pack(side='top', padx=(15, 0), pady=(0, 2))

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
preview_frame = tk.Frame(top_container_frame, bg='black', width=404, height=404, borderwidth=2, relief='solid')
preview_frame.pack_propagate(0)
preview_frame.pack(side='right', padx=2,pady=2,fill='none',expand=False)

image_label = tk.Label(preview_frame, bg='black', borderwidth=2, relief='solid')
image_label.pack(fill='both', expand=True)

countdown_label = tk.Label(preview_frame, text="", 
                         font=("Arial", 30, "bold"), 
                         fg="red", bg='black', highlightthickness=0)
countdown_label.place(relx=0.5, rely=0.5, anchor='center')
countdown_label.place_forget()

# Spectrograph Section
spectrograph_frame = tk.Frame(top_container_frame, bg='black', width=400, height=400, borderwidth=2, relief='solid')
spectrograph_frame.pack(side='left', padx=2,pady=2,fill='none',expand=False)

fig, ax = plt.subplots(figsize=(4,4))
canvas = FigureCanvasTkAgg(fig, master=spectrograph_frame)
canvas.get_tk_widget().pack(fill='both', expand=True)

# RGB Container frame
RGB_container_frame=tk.Frame(main_frame, bg='#2d2d2d', width=430, height=200)
RGB_container_frame.pack(side='top', fill='x', padx=2)
# RGB Graph Frame
rgb_graph_frame = tk.Frame(RGB_container_frame, bg='#2d2d2d', width=404, height=200, borderwidth=2, relief='solid')
rgb_graph_frame.pack(side='left', padx=2)
rgb_graph_frame.pack_propagate(0)  # Prevent the frame from resizing

# Create a Matplotlib figure and canvas for the RGB graph
rgb_fig, rgb_ax = plt.subplots(figsize=(4, 1))
rgb_canvas = FigureCanvasTkAgg(rgb_fig, master=rgb_graph_frame)
rgb_canvas.get_tk_widget().pack(fill='both', expand=True)

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
spectrometer_control_frame = tk.Frame(main_frame, bg='#2d2d2d', width=410, height=200, borderwidth=2, relief='solid')
spectrometer_control_frame.pack(side='left', padx=2, pady=2)
spectrometer_control_frame.pack_propagate(0)  # Prevent the frame from resizing

tk.Label(spectrometer_control_frame, text="Spectrometer Control", bg='#3d3d3d', fg='white', font=('Arial', 12, 'bold')).pack(pady=(5, 10))

# Integration Time Section
integration_time_section = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
integration_time_section.pack(side='top', fill='x', pady=2, padx=2)

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
trigger_mode_section.pack(side='top', fill='x', pady=2, padx=2)

# Trigger Mode Label
trigger_mode_label = tk.Label(trigger_mode_section, text="Trigger Mode:", bg='#2d2d2d', fg='white', font=('Arial', 12, 'bold'))
trigger_mode_label.pack(side='left', padx=1, pady=1)

# Trigger Mode Dropdown
trigger_mode_var = tk.StringVar(trigger_mode_section)
trigger_mode_var.set("1")  # Default value
trigger_mode_options = ["1", "2", "3"]
trigger_mode_dropdown = tk.OptionMenu(trigger_mode_section, trigger_mode_var, *trigger_mode_options)
trigger_mode_dropdown.config(bg='#3d3d3d', fg='white', font=('Arial', 10, 'bold'), highlightbackground='#4CAF50', highlightcolor='#4CAF50', highlightthickness=1, width= 14)
trigger_mode_dropdown.pack(side='left', padx=2, pady=2)
set_trigger_mode_button = tk.Button(trigger_mode_section, text="Set Trigger", command=set_trigger_mode, **BUTTON_STYLE)
set_trigger_mode_button.pack(side='left', padx=6, pady=2)

# Buttons Section for Dark Subtraction and Baseline Correction and save data
buttons_section = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
buttons_section.pack(side='top', fill='x', pady=2)

dark_subtraction_button = tk.Button(buttons_section, text="Dark Subtraction", command=dark_subtraction, **BUTTON_STYLE)
dark_subtraction_button.pack(side='left', padx=2, pady=2)

baseline_correction_button = tk.Button(buttons_section, text="Baseline Correction", command=baseline_correction, **BUTTON_STYLE)
baseline_correction_button.pack(side='left', padx=2, pady=2)

smooth_spectrum_button = tk.Button(buttons_section, text="Smooth Spectrum", command=smooth_spectrum, **BUTTON_STYLE)
smooth_spectrum_button.pack(side='left', padx=2, pady=2)

# Buttons Section for Log
buttons_section2 = tk.Frame(spectrometer_control_frame, bg='#2d2d2d')
buttons_section2.pack(side='top', fill='x', pady=2)

start_logging_button = tk.Button(buttons_section2, text="Start Logging", command=start_logging, **BUTTON_STYLE)
start_logging_button.pack(side='left', padx=2, pady=2)

stop_logging_button = tk.Button(buttons_section2, text="Stop Logging", command=stop_logging, **BUTTON_STYLE)
stop_logging_button.pack(side='left', padx=2, pady=2)

save_data_button = tk.Button(buttons_section2, text="Save Data", command=save_data, **BUTTON_STYLE)
save_data_button.pack(side='left', padx=2, pady=2)

# Spectrometer Status Section
spectrometer_status_section = tk.Frame(status_frame, bg='#2d2d2d',borderwidth=2, relief='solid')
spectrometer_status_section.pack(side='top', fill='x', pady=5, padx=2)

# Spectrometer Status Label
spectrometer_status_label = tk.Label(spectrometer_status_section, text="No spectrometer found", bg='#2d2d2d', fg='white', font=('Arial', 12, 'bold'))
spectrometer_status_label.pack(side='left', padx=2)


# Start the dynamic plot update
update_spectrometer_plot()
# Start system monitoring
update_system_info()

root.mainloop()

