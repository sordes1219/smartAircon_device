#!/usr/bin/python3

# Import SDK packages
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
from AWSIoTPythonSDK.exception import AWSIoTExceptions
import time
import datetime
import json
from logs import Applogger
import subprocess
import RPi.GPIO as GPIO
import dht11

# Init Logger
applogger = Applogger(__name__)
logger = applogger.logger

# Init GPIO
LED = 17
GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED,GPIO.OUT)

# read data using pin 14
instance = dht11.DHT11(pin=14)

# Init variable
action_mode = ["heating","cooler","blast","dry"]
timer_mode = ["on","off"]
timer_value = ["ontime","offtime"]
timer_setting = {"on":{"active":0,"ontime":"09:00"},"off":{"active":0,"offtime":"10:00"}}
temperature = 20
humidity = 50

# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTShadowClient = None
myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient("smartRemocon")
myAWSIoTMQTTShadowClient.configureEndpoint("a1xfsi89ntz6zn-ats.iot.us-east-1.amazonaws.com", 8883)
myAWSIoTMQTTShadowClient.configureCredentials(r"/opt/smartAircon_device/cert/rootCA.pem", r"/opt/smartAircon_device/cert/private.pem.key", r"/opt/smartAircon_device/cert/certificate.pem.crt")

# AWSIoTMQTTShadowClient connection configuration
myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(10) # 10 sec
myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5) # 5 sec

# Function called when a shadow is deleted
def customShadowCallback_Delete(payload, responseStatus, token):
    # Display status and data from Update request
    if responseStatus == "timeout":
        logger.error("Delete request " + token + " time out!")

    if responseStatus == "accepted":
        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~")
        logger.debug("Delete request with token: " + token + " accepted!")
        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    if responseStatus == "rejected":
        logger.error("Delete request " + token + " rejected!")

# Function called when a shadow is updated
def customShadowCallback_Update(payload, responseStatus, token):
    # Display status and data from Update request
    if responseStatus == "timeout":
        logger.error("Update request " + token + " time out!")

    if responseStatus == "accepted":
        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~")
        logger.debug("Update request with token: " + token + " accepted!")
        logger.debug("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    if responseStatus == "rejected":
        logger.error("Update request " + token + " rejected!")

# Function called when a shadow-delta is updated
def customShadowCallback_DeltaUpdate(payload, responseStatus, token):

    # tempolary dictionary for making payload
    d1 = {}
    d2 = {}
    d3 = {}

    # Display status and data from Update request
    logger.debug("~~~~~~~~~~~~~~~~~~~~~~~")
    logger.debug("DeltaUpdate payload: " + payload)
    logger.debug("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    delta = json.loads(payload)["state"]

    if delta:
        # 動作モード、停止の確認
        for value in action_mode:
            # 初期値(0)をセット
            d1[value] = 0
            if delta.get(value) == 1:
                cmd = "python3 irrp.py -p -g17 -f codes aircon:{}".format(value)
                subprocess.check_call(cmd.split())
                d1[value] = 1
                logger.info("turn on {}".format(value))

        # all0なら停止
        if sum(d1.values()) == 0:
            cmd = "python3 irrp.py -p -g17 -f codes aircon:stop"
            subprocess.check_call(cmd.split())
            logger.info("turn off aircon")

        # タイマーモードの確認、動作設定
        for value in timer_mode:
            if delta.get(value) != None:
                d1[value] = delta.get(value)
                timer_setting[value]["active"] = delta.get(value)
                logger.info("set {}timer {}".format(value,delta.get(value)))

        # タイマー時刻の確認、動作設定
        for value in timer_value:
            if delta.get(value) != None:
                d1[value] = delta.get(value)
                if "on" in value:
                    timer_setting["on"][value] = delta.get(value)
                elif "off" in value:
                    timer_setting["off"][value] = delta.get(value)
                logger.info("set {} at {}".format(value,delta.get(value)))

    # Create message payload
    d2["reported"] = d1
    d3["state"] = d2
    payload = d3

    # Update a Shadow
    deviceShadowHandler.shadowUpdate(json.dumps(payload),customShadowCallback_Update, 5)

# Connect to AWS IoT
myAWSIoTMQTTShadowClient.connect()
logger.debug('connect to shadow')

# Create a device shadow handler, use this to update and Delete shadow document
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName('smartRemocon', True)

# Create message payload
payload = {"state":{"reported":{"heating":0,"cooler":0,"blast":0,"dry":0,"on":0,"off":0,"ontime":"09:00","offtime":"10:00"}}}

# Delete old Shadow
deviceShadowHandler.shadowDelete(customShadowCallback_Delete, 5)

# Create New Shadow
deviceShadowHandler.shadowUpdate(json.dumps(payload),customShadowCallback_Update, 5)

# Update curent shadow JSON doc
deviceShadowHandler.shadowRegisterDeltaCallback(customShadowCallback_DeltaUpdate)

while True:
    # check timer
    for value in timer_mode:
        if timer_setting[value]["active"] == 1:
            nowtime = datetime.datetime.now()
            settime = datetime.datetime.combine(nowtime.date(),datetime.datetime.strptime(timer_setting[value][value + "time"],"%H:%M").time())
            deltatime = nowtime - settime
            if abs(deltatime.total_seconds()) < 60:
                if value == "on":
                    if temperature < 20:
                        cmd = "python3 irrp.py -p -g17 -f codes aircon:heating"
                    else:
                        cmd = "python3 irrp.py -p -g17 -f codes aircon:cooler"
                    subprocess.check_call(cmd.split())
                    logger.info("turn on aircon")
                elif value == "off":
                    cmd = "python3 irrp.py -p -g17 -f codes aircon:stop"
                    subprocess.check_call(cmd.split())
                    logger.info("turn off aircon")

    # Send air condition per 60sec
    time.sleep(10)
    result = instance.read()
    if result.is_valid():
        temperature = result.temperature
        humidity = result.humidity
        logger.info("Temperature: %-3.1f C" % temperature)
        logger.info("Humidity: %-3.1f %%" % humidity)

        payload = {"state":{"reported":{"temp":temperature,"humid":humidity}}}
        deviceShadowHandler.shadowUpdate(json.dumps(payload),customShadowCallback_Update, 5)
