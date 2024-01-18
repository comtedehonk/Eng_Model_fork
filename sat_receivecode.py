import time
import wifi
from secrets import secrets
import socketpool
import adafruit_requests
import rtc
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import ssl
import sys
import json
from send import send_image


def attempt_wifi():
    # TODO: Move wifi pass and id to config
    # try connecting to wifi
    print("Connecting to WiFi...")
    try:
        wifi.radio.connect(ssid=secrets["wifi"]["ssid"], password=secrets["wifi"]["password"])
        # wifi.radio.connect(ssid="Stanford") # open network
        print("Signal: {}".format(wifi.radio.ap_info.rssi))
        # Create a socket pool
        pool = socketpool.SocketPool(wifi.radio)
        # sync out RTC from the web
        synctime(pool)
    except Exception as e:
        print("Unable to connect to WiFi: {}".format(e))
        return None
    else:
        return pool
    
def synctime(pool):
    try:
        requests = adafruit_requests.Session(pool)
        TIME_API = "http://worldtimeapi.org/api/ip"
        the_rtc = rtc.RTC()
        response = None
        while True:
            try:
                print("Fetching time")
                # print("Fetching json from", TIME_API)
                response = requests.get(TIME_API)
                break
            except (ValueError, RuntimeError) as e:
                print("Failed to get data, retrying\n", e)
                continue

        json1 = response.json()
        print(json1)
        current_time = json1['datetime']
        the_date, the_time = current_time.split('T')
        year, month, mday = [int(x) for x in the_date.split('-')]
        the_time = the_time.split('.')[0]
        hours, minutes, seconds = [int(x) for x in the_time.split(':')]

        # We can also fill in these extra nice things
        year_day = json1['day_of_year']
        week_day = json1['day_of_week']
        is_dst = json1['dst']

        now = time.struct_time(
            (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst))
        the_rtc.datetime = now
    except Exception as e:
        print('[WARNING]', e)

def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print("Connected to MQTT broker!")
    client.subscribe(secrets['mqtt']['codetopic'])

def mqtt_message(client, topic, payload):
    #print("[{}] {}".format(topic, payload))
    payload = json.loads(payload)
    filename = payload['filepath'].split('/')[-1]
    with open(f'images_to_send/{filename}', mode ='wb') as stream:
        stream.write(payload["data"])
        print('done')
    client.disconnect()
    print('disconnected')
    send_image(payload['filepath'])
    print('sent image')
    
        
    

def subscribe(mqtt_client, userdata, topic, granted_qos):
    # This method is called when the mqtt_client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def set_up_mqtt(pool):
    mqtt_client = MQTT.MQTT(
        broker=secrets["mqtt"]["broker"],
        port=secrets['mqtt']["port"],
        username=secrets["mqtt"]["username"],
        password=secrets['mqtt']["password"],
        socket_pool=pool,
        is_ssl = True,
        ssl_context=ssl.create_default_context()
    )

    mqtt_client.on_connect = connected
    mqtt_client.on_message = mqtt_message
    mqtt_client.on_subscribe = subscribe

    mqtt_client.connect()
    print("connected")
    
    return mqtt_client

def receive_image():
    pool = attempt_wifi()
    mqtt_client = set_up_mqtt(pool)
    while True:
        mqtt_client.loop()
        if(not mqtt_client.is_connected()):
            break
        time.sleep(3)
