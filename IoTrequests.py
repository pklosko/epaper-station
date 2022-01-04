import urllib.request
import time
import os
import json
import threading

from PIL import Image
from io import BytesIO

IMAGE_WORKDIR = "/tmp/"
CLIENTS_JSON = "clients.json"
UPD_FROM = -1 #5:45
UPD_TO = 2500  #25:00
UPD_INTERVAL = 1680 #28 minutes

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
    currHM = int(time.strftime("%H%I"))
    client_str = str(bytes(client).hex())
    url = "http://YOUR_URL/?t=" + str(ci.temperature) + "&ub=" + str(ci.batteryMv / 1000)
    print("Push info ", url)
    headers = {}
    headers['User-Agent']  = "IoT.ePap-80-" + client_str
    headers['Device-Info'] = "Device:Samsung/SoluM4.2" +  \
                             ";MAC:" + client_str + \
                             ";FW:" + str(ci.swVer) + \
                             ";SW:station.py@" + os.uname().nodename + "[" + str(os.getpid()) + "]" + \
                             ";Interval:30" + \
                             ";Conn:WiFi" + \
                             ";imgUpdateVer:" + str(pi.imgUpdateVer) + \
                             ";RSSI:" + str(ci.lastPacketRSSI)
    req = urllib.request.Request(url, headers = headers)
    resp = urllib.request.urlopen(req)
    print(headers['User-Agent'])
    print(headers['Device-Info'])
    respData = resp.read()
    print(respData)

    if (currHM > UPD_FROM and currHM < UPD_TO):
      try:
        print("Thread Sleep for ", UPD_INTERVAL)
        tim_thr = threading.Timer(UPD_INTERVAL, IoTgetImage, args=(client_str, CLIENTS_JSON, ))
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
    data = '{"clients":{"' + client_str + '":{"imgVer":0,"imgLen":0}}}'
    clImgInfo = json.loads(data)
  return clImgInfo


def IoTstoreClientsImageInfo(clImgInfo, jsonFile):
  json_object = json.dumps(clImgInfo)
  f = open(jsonFile, "w")
  f.write(json_object)
  f.close()


def IoTgetImage(client_str, jsonFile, showInfo = False):
  currHour = int(time.strftime("%H"))
  localFileName = client_str + ".png"
  url = "https://YOUR_URL/?nocache=true&mac=" + client_str + "&ts=" + str(int(time.time())) + "&ua=station.py"
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
