import urllib.request
import time
import os
import sys
import json
import threading
import logging

from PIL import Image
from io import BytesIO

PUSH_URL = "YOUR_URL"
GET_URL = "YOUR_URL"
USER_AGENT = "Python/ePaper-"

IMAGE_WORKDIR = "/tmp/"
CLIENTS_JSON = "clients.json"

INTERVAL = 45  #default
#UPD_FROM = 600 #6:00
#UPD_TO = 2200  #22:00

#UPD_INTERVAL = (INTERVAL - 2) * 60 #2 minutes before Checkin

logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

dsn = 0

def print(*args):
  msg = ""
  for arg in args:
    msg += str(arg) + " "
  logger.warning(msg)


def IoTprepareImage(localFileName):
  pf = open(localFileName,mode='rb')
  imgData = pf.read()
  pf.close()
  imgVer = str(int(time.time()))
  file_conv = IMAGE_WORKDIR + imgVer + ".bmp"
  if not os.path.isfile(file_conv):
    pngdata = BytesIO(imgData)
    im = Image.open(pngdata)
    im_L = im.convert("1")
    im_L.save(file_conv)
  imgLen = os.path.getsize(file_conv)

  return (imgVer, imgLen)


def IoTpushInfo(ci, pi, client):
  try:
    client_str = str(bytes(client).hex())
    url = PUSH_URL + "?t=" + str(ci.temperature) + "&ub=" + str(ci.batteryMv / 1000)
    print("Push info ", url)
    headers = {}
    headers['User-Agent']  = USER_AGENT + client_str
    headers['Connection']  = "close"
    headers['Device-Info'] = "Device:Samsung/SoluM4.2" +  \
                             ";MAC:" + client_str + \
                             ";FW:" + str(ci.swVer) + \
                             ";SW:station.py@" + os.uname().nodename + "[" + str(os.getpid()) + "]" + \
                             ";Accept:json" + \
                             ";Interval:" + str(int(pi.nextCheckinDelay/60000)) + \
                             ";Conn:WiFi" + \
                             ";imgUpdateVer:" + str(pi.imgUpdateVer) + \
                             ";RSSI:" + str(ci.lastPacketRSSI)
    req = urllib.request.Request(url, headers = headers)
    resp = urllib.request.urlopen(req)
#    print(headers['User-Agent'])
#    print(headers['Device-Info'])
    respData = json.loads(resp.read())
    print(respData)
    if 'CMD' in respData:
      if respData['CMD'] == 'SET-INTERVAL':
        print("Set nextCheckinDelay to " + str(respData['PARAM']) + " minutes")
        IoTupdateClientsImageInfo(client_str, CLIENTS_JSON, 'imgInt', respData['PARAM'])
    try:
      print("Thread Sleep for ", str(int(pi.nextCheckinDelay/60000)), "minutes")
      tim_thr = threading.Timer((int(pi.nextCheckinDelay/1000)-120), IoTgetImage, args=(client_str, CLIENTS_JSON, )) #2 min before next Checkin packet
      tim_thr.start()
    except Exception as e:
      print("Unable to Get Image", client)
      print(str(e))

  except Exception as e:
    print("Unable to push Info for client", client)
    print(str(e))


def IoTgetClientsImageInfo(jsonFile, client_str):
  try:
    f = open(jsonFile, "r")
    clImgInfo = json.load(f)
    f.close();
  except Exception as e:
    data = '{"clients":{"' + client_str + '":{"imgVer":0,"imgLen":0,"imgInt":' + INTERVAL + '}}}'
    clImgInfo = json.loads(data)
  return clImgInfo

def IoTupdateClientsImageInfo(client_str, jsonFile, elem, value):
  clImgInfo = IoTgetClientsImageInfo(jsonFile, client_str)
  clImgInfo['clients'][client_str][elem] = value
  IoTstoreClientsImageInfo(clImgInfo, jsonFile)


def IoTstoreClientsImageInfo(clImgInfo, jsonFile):
  json_object = json.dumps(clImgInfo)
  f = open(jsonFile, "w")
  f.write(json_object)
  f.close()


def IoTgetImage(client_str, jsonFile, showInfo = False):
  localFileName = client_str + ".png"
  url = GET_URL + "?nocache=true&mac=" + client_str + "&ts=" + str(int(time.time())) + "&ua=station.py"
  try:
    print("HTTP GET image data ", url)
    urllib.request.urlretrieve(url, localFileName)
    imgVer, imgLen = IoTprepareImage(localFileName)
    clImgInfo = IoTgetClientsImageInfo(jsonFile, client_str)
    clImgInfo['clients'][client_str]['imgVer'] = imgVer
    clImgInfo['clients'][client_str]['imgLen'] = imgLen
    IoTstoreClientsImageInfo(clImgInfo, jsonFile)
    if showInfo:
      print("clImgInfo", clImgInfo)
  except Exception as e:
    print("Unable to HTTP GET image data for client", client_str)
    print(str(e))
  return (imgVer, imgLen)
