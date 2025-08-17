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
        img = Image.fromarray(frame).resize((800, 300))
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
    return ImageTk.PhotoImage(Image.open(path).resize(size, Image.ANTIALIAS))

# Define icon paths and sizes
icon_paths = {
    "start_preview": "start_preview.png",
    "stop_preview": "stop_preview.png",
    "capture_image": "take_picture.png",
    "start_recording": "start_recording.png",
    "stop_recording": "stop_recording.png"
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
system_info_frame.pack( fill='x', pady=(0, 10))

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
    (icons["stop_recording"], stop_recording)  # Stop Record
]

for icon, command in button_config:
    btn = tk.Button(control_frame, image=icon, command=command, **BUTTON_STYLE, highlightbackground='#4CAF50', highlightcolor='#4CAF50', highlightthickness=2)
    btn.image = icon  # Keep a reference to avoid garbage collection
    btn.pack(side='left', padx=5, pady=5)

# Preview Section
preview_frame = tk.Frame(main_frame, bg='black', width=800, height=400, borderwidth=2, relief='solid')
preview_frame.pack_propagate(0)
preview_frame.pack(side='top', pady=(0,10))

# Video preview elements
image_label = tk.Label(preview_frame, bg='black', borderwidth=2, relief='solid')
image_label.pack(fill='both', expand=True)

countdown_label = tk.Label(preview_frame, text="", font=("Arial", 30, "bold"), fg="red", bg='black', highlightthickness=0)
countdown_label.place(relx=0.5, rely=0.5, anchor='center')
countdown_label.place_forget()

# Create a frame for the D-pad
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

# Create a frame for the speed control
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



# Start system monitoring
update_system_info()

root.mainloop()
