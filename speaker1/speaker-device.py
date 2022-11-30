# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import urllib3
import json
import boto3
import argparse

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient


########### from polly #############

from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import os
import sys
import subprocess
from tempfile import gettempdir
import time
import playsound

###########

# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("--region", action="store", required=True, dest="region", help="AWS Region")
parser.add_argument("-n", "--thingname", action="store", required=True, dest="thingname", help="Same thing name registered on IoT Core")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", required=True, dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", required=True, dest="privateKeyPath", help="Private key file path")
parser.add_argument("-u", "--credentials_url", action="store", required=True, dest="credentials_url", help="Role Alias URL")
parser.add_argument("-t", "--topic", action="store", dest="topic", default="speaker/message", help="Topic to subscribe")
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-p", "--port", action="store", dest="port", type=int, help="Port number override")
parser.add_argument("-w", "--websocket", action="store_true", dest="useWebsocket", default=False, help="Use MQTT over WebSocket")


args = parser.parse_args()
region = args.region
thing_name = args.thingname
cert_file = args.certificatePath
key_file = args.privateKeyPath
credentials_url = args.credentials_url
topic = args.topic
host = args.host
rootCAPath = args.rootCAPath
port = args.port
useWebsocket = args.useWebsocket

def sayText(msg,pauseafter):
    
    ########### Polly begin #################

    try:
        # Request speech synthesis
        response = polly.synthesize_speech(Text=msg, OutputFormat="mp3", VoiceId="Joanna")
    except (BotoCoreError, ClientError) as error:
        # The service returned an error, exit gracefully
        print(error)
        sys.exit(-1)

    # Access the audio stream from the response
    if "AudioStream" in response:
        # Note: Closing the stream is important because the service throttles on the
        # number of parallel connections. Here we are using contextlib.closing to
        # ensure the close method of the stream object will be called automatically
        # at the end of the with statement's scope.
        with closing(response["AudioStream"]) as stream:
                output = os.path.join(gettempdir(), "iniIoTmessage.mp3")
                
                try:
                    # Open a file for writing the output as a binary stream
                    with open(output, "wb") as file:
                        file.write(stream.read())
                        
                except IOError as error:
                    # Could not write to file, exit gracefully
                    print(error)
                    sys.exit(-1)
                playsound.playsound(output)
        

    else:
        # The response didn't contain audio data, exit gracefully
        print("Could not stream audio")
        sys.exit(-1)

    # Play the audio using the platform's default player

    # playsound.playsound(output)
  
    time.sleep(pauseafter)

    ########### Polly end ###################



retries = urllib3.Retry(connect=5, read=2, redirect=5)
http = urllib3.PoolManager(
    cert_file=cert_file,
    key_file=key_file,
    cert_reqs="CERT_REQUIRED",
    headers={
        'x-amzn-iot-thingname': thing_name
    },
    retries=retries
)

def get_boto_session():
    resp = http.request("GET", credentials_url)
    if resp.status != 200:
        raise Exception("Failed to retrieve STS token: {}".format(resp.reason))
    global creds 
    creds = json.loads(resp.data)['credentials']
    # return boto3.session.Session(aws_access_key_id=creds['accessKeyId'], aws_secret_access_key=creds['secretAccessKey'], aws_session_token=creds['sessionToken'], region_name=region)
    return boto3.Session(
        aws_access_key_id=creds['accessKeyId'],
        aws_secret_access_key=creds['secretAccessKey'],
        aws_session_token=creds['sessionToken']
        )
        
if __name__ == '__main__':
    sess = get_boto_session()
    polly = sess.client('polly', region_name=region)
    print("I got here")
    # client.do_things()

    ########### Initial message ############

    sayText("Hi, My name is Joanna Polly. I will let you know if a robot get stuck",1)

########### MQTT CALL BACK ############ Custom MQTT message callback
def customCallback(client, userdata, message):
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")

    messageonly = message.payload.decode()
    jmessage = json.loads(messageonly)
    msg = (jmessage["message"])
    sayText(msg,10)


######### END OF MQTT CALL BACK ########

if args.useWebsocket and args.certificatePath and args.privateKeyPath:
    parser.error("X.509 cert authentication and WebSocket are mutual exclusive. Please pick one.")
    exit(2)

if not args.useWebsocket and (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

# Port defaults
if args.useWebsocket and not args.port:  # When no port override for WebSocket, default to 443
    port = 443
if not args.useWebsocket and not args.port:  # When no port override for non-WebSocket, default to 8883
    port = 8883

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(thing_name, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(thing_name)
    myAWSIoTMQTTClient.configureEndpoint(host, port)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, key_file, cert_file)

    
# myAWSIoTMQTTClient.configureIAMCredentials(session)
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect and subscribe to AWS IoT

myAWSIoTMQTTClient.connect()
print("connected")
myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
time.sleep(2)

# Publish to the same topic in a loop forever
loopCount = 0
# print("Waiting for message")
while True:
    # myAWSIoTMQTTClient.publish(topic, "New Message " + str(loopCount), 1)
    loopCount += 1
    # print("Waiting for Message: " + str(loopCount))
    time.sleep(1)