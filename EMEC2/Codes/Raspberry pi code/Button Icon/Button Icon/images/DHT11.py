
import time
import board
import adafruit_dht

# Define the sensor type and the GPIO pin
sensor = adafruit_dht.DHT11(board.D4)

try:
        # Read the humidity and temperature from the sensor
        while True:
            temperature = sensor.temperature
            humidity = sensor.humidity
            print(f"Temp= {temperature:.1f}°C, Humidity= {humidity:.1f}%")
            time.sleep(2)
except KeyboardInterrupt:
       pass
finally:
       sensor.exit()