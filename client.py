#!/usr/bin/python3
# coding: UTF-8

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
temperature = 20
humidity = 50
device_shadow = {"state":{"reported":{"heating":0,"cooler":0,"blast":0,"dry":0,"on":0,"off":0,"ontime":"09:00","offtime":"10:00"}}}

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

    zero_counter = 0

    # Display status and data from Update request
    logger.debug("~~~~~~~~~~~~~~~~~~~~~~~")
    logger.debug("DeltaUpdate payload: " + payload)
    logger.debug("~~~~~~~~~~~~~~~~~~~~~~~\n\n")

    delta = json.loads(payload)["state"]

    if delta:
        # 動作モード、停止の確認
        for value in action_mode:
            # 初期値(0)をセット
            if delta.get(value) != None:
                if delta.get(value) == 1:
                    cmd = "python3 irrp.py -p -g17 -f codes aircon:{}".format(value)
                    subprocess.check_call(cmd.split())
                    logger.info("turn on {}".format(value))
                    device_shadow["state"]["reported"][value] = delta.get(value)
                    zero_counter -= 1

                elif delta.get(value) == 0:
                    device_shadow["state"]["reported"][value] = delta.get(value)
                    zero_counter += 1

        # zero_counter>0なら停止
        if zero_counter > 0:
            cmd = "python3 irrp.py -p -g17 -f codes aircon:stop"
            subprocess.check_call(cmd.split())
            logger.info("turn off aircon")

        # タイマーモードの確認、動作設定
        for value in timer_mode:
            if delta.get(value) != None:
                device_shadow["state"]["reported"][value] = delta.get(value)
                logger.info("set {}timer {}".format(value,delta.get(value)))

        # タイマー時刻の確認、動作設定
        for value in timer_value:
            if delta.get(value) != None:
                device_shadow["state"]["reported"][value] = delta.get(value)
                logger.info("set {} at {}".format(value,delta.get(value)))

    # Update a Shadow
    deviceShadowHandler.shadowUpdate(json.dumps(device_shadow),customShadowCallback_Update, 5)

# Connect to AWS IoT
myAWSIoTMQTTShadowClient.connect()
logger.debug('connect to shadow')

# Create a device shadow handler, use this to update and Delete shadow document
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName('smartRemocon', True)

# Delete old Shadow
deviceShadowHandler.shadowDelete(customShadowCallback_Delete, 5)

# Create New Shadow
deviceShadowHandler.shadowUpdate(json.dumps(device_shadow),customShadowCallback_Update, 5)

# Update curent shadow JSON doc
deviceShadowHandler.shadowRegisterDeltaCallback(customShadowCallback_DeltaUpdate)

while True:
    # check timer
    for value in timer_mode:
        if device_shadow["state"]["reported"][value] == 1:
            nowtime = datetime.datetime.now()
            settime = datetime.datetime.combine(nowtime.date(),datetime.datetime.strptime(device_shadow["state"]["reported"]["{}time".format(value)],"%H:%M").time())
            deltatime = nowtime - settime
            if (deltatime.total_seconds() < 10) & (deltatime.total_seconds() > 0):
                if value == "on":
                    if temperature < 20 :
                        cmd = "python3 irrp.py -p -g17 -f codes aircon:heating"
                        subprocess.check_call(cmd.split())
                        logger.info("turn on heating")
                        device_shadow["state"]["reported"]["heating"] = 1
                    else:
                        cmd = "python3 irrp.py -p -g17 -f codes aircon:cooler"
                        subprocess.check_call(cmd.split())
                        logger.info("turn on cooler")
                        device_shadow["state"]["reported"]["cooler"] = 1
                elif value == "off":
                    cmd = "python3 irrp.py -p -g17 -f codes aircon:stop"
                    subprocess.check_call(cmd.split())
                    logger.info("turn off aircon")
                    for v in action_mode:
                        device_shadow["state"]["reported"][v] = 0

                # Update a Shadow
                deviceShadowHandler.shadowUpdate(json.dumps(device_shadow),customShadowCallback_Update, 5)

    # Send air condition per 60sec
    time.sleep(10)
    result = instance.read()
    # print(result.is_valid())
    if result.is_valid():
        temperature = result.temperature
        humidity = result.humidity
        logger.info("Temperature: %-3.1f C" % temperature)
        logger.info("Humidity: %-3.1f %%" % humidity)

        device_shadow["state"]["reported"]["temp"] = temperature
        device_shadow["state"]["reported"]["humid"] = humidity

        deviceShadowHandler.shadowUpdate(json.dumps(device_shadow),customShadowCallback_Update, 5)
