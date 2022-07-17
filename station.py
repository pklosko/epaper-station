#!/usr/bin/env python3

import timaccop
from Cryptodome.Cipher import AES
from collections import namedtuple
import struct
import os
import logging
import logging.handlers
from PIL import Image
import binascii
import time
from io import BytesIO
import IoTrequests
import threading
import signal
import json
import sys

masterkey = bytearray.fromhex("D306D9348E29E5E358BF2934812002C1")

PORT = "/dev/ttyACM0"
EXTENDED_ADDRESS = [ 0x00, 0x12, 0x4B, 0x00, 0x14, 0xD9, 0x49, 0x35 ]
PANID = [ 0x47, 0x44 ]
CHANNEL = 11
IMAGE_WORKDIR = "/tmp/"
BASE_DIR = "/etc/scripts/epaper-station"
LOG_FILENAME = "/var/log/station.log"     # File name 
LOG_LEVEL    = logging.INFO               # Could be e.g. "INFO", DEBUG" or "WARNING"
CLIENTS_JSON = "clients.json"
INTERVAL = 45                             # minutes
UPD_INTERVAL_MS = INTERVAL * 60000        # mseconds
SLEEP_TIME = 2100                         # last update at 21:00 h / everything above 2400 disable this feature
SLEEP_INTERVAL = 9                        # 9 hours after SLEEP_TIME 
SLEEP_DELAY_MS = SLEEP_INTERVAL * 3600000 # mseconds

PKT_ASSOC_REQ			= (0xF0)
PKT_ASSOC_RESP			= (0xF1)
PKT_CHECKIN			= (0xF2)
PKT_CHECKOUT			= (0xF3)
PKT_CHUNK_REQ			= (0xF4)
PKT_CHUNK_RESP			= (0xF5)

imgVer = 0
imgLen = 0
imgInt = 0
client_str = ""

TagInfo = namedtuple('TagInfo', """
protoVer,
swVer,
hwType,
batteryMv,
rfu1,
screenPixWidth,
screenPixHeight,
screenMmWidth,
screenMmHeight,
compressionsSupported,
maxWaitMsec,
screenType,
rfu
""")

AssocInfo = namedtuple('AssocInfo', """
checkinDelay,
retryDelay,
failedCheckinsTillBlank,
failedCheckinsTillDissoc,
newKey,
rfu
""")

CheckinInfo = namedtuple('CheckinInfo', """
swVer,
hwType,
batteryMv,
lastPacketLQI,
lastPacketRSSI,
temperature,
rfu,
""")

PendingInfo = namedtuple('PendingInfo', """
imgUpdateVer,
imgUpdateSize,
osUpdateVer,
osUpdateSize,
nextCheckinDelay,
rfu
""")

ChunkReqInfo = namedtuple('ChunkReqInfo', """
versionRequested,
offset,
len,
osUpdatePlz,
rfu,
""")

ChunkInfo = namedtuple('ChunkInfo', """
offset,
osUpdatePlz,
rfu,
""")

logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
handler   = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=3)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


dsn = 0

def print(*args):
    msg = ""
    for arg in args:
        msg += str(arg) + " "
    logger.warning(msg)

def decrypt(hdr, enc, tag, nonce):
    cipher = AES.new(masterkey, AES.MODE_CCM, nonce, mac_len=4)
    cipher.update(hdr)
    plaintext = cipher.decrypt(enc)
    #print("rcvd_packet:", plaintext.hex())
    #print("rcvhdr:", hdr.hex())
    try:
        cipher.verify(tag)
        return plaintext
    except:
        return None

def send_data(dst, data):
    global dsn
    dsn += 1
    if dsn > 255:
        dsn = 0
    hdr = bytearray.fromhex("41cc")
    hdr.append(dsn)
    hdr.extend(PANID)
    hdr.extend(reversed(dst))
    hdr.extend(EXTENDED_ADDRESS)
    #print("hdr:", hdr.hex())

    cntr = int(time.time())
    cntrb = struct.pack('<L', cntr)

    nonce = bytearray(cntrb)
    nonce.extend(EXTENDED_ADDRESS)
    nonce.append(0)
    #print("nonce:", nonce.hex())

    cipher = AES.new(masterkey, AES.MODE_CCM, nonce, mac_len=4)
    cipher.update(hdr)
    ciphertext, tag = cipher.encrypt_and_digest(data)

    out = ciphertext+tag+cntrb
    timaccop.mac_data_req(dst, PANID, 12, dsn, out)

def process_assoc(pkt, data):
    ti = TagInfo._make(struct.unpack('<BQHHBHHHHHHB11s',data))
    print(ti)

    ai = AssocInfo(
	    checkinDelay=UPD_INTERVAL_MS, #check each 40minutes 
	    retryDelay=1000, #retry delay 1000ms
	    failedCheckinsTillBlank=2,
	    failedCheckinsTillDissoc=0,
	    newKey=masterkey,
	    rfu=bytearray(8*[0])
    )
    print(ai)
    ai_pkt = bytearray([ PKT_ASSOC_RESP ]) + bytearray(struct.pack('<LLHH16s8s', *ai))

    send_data(pkt['src_add'], ai_pkt)

def prepare_image(client):
    try:
      client_str = str(bytes(client).hex())
      clImgInfo = IoTrequests.IoTgetClientsImageInfo(CLIENTS_JSON, client_str)
      imgVer = int(clImgInfo['clients'][client_str]['imgVer'])
      imgLen = int(clImgInfo['clients'][client_str]['imgLen'])
      imgInt = int(clImgInfo['clients'][client_str]['imgInt'])
    except Exception as e :
      print("Unable to get Image info for client", client)
      imgVer = 0
      imgLen = 0
      imgInt = INTERVAL

    return (imgVer, imgLen, imgInt)

def get_image_data(imgVer, offset, length):
    filename = IMAGE_WORKDIR + str(imgVer) + ".bmp"
    if notDaemon() or offset == 0:
      print("Reading image file:", filename)

    f = open(filename,mode='rb')
    f.seek(offset)
    image_data = f.read(length)
    f.close()

    return image_data

def process_checkin(pkt, data):
    currHM = int(time.strftime("%H%I"))
    updIntervalMS = 900000               # default 15 minutes

    ci = CheckinInfo._make(struct.unpack('<QHHBBB6s',data))
    print(ci)

    try:
        global imgVer, imgLen, imgInt
        imgVer, imgLen, imgInt = prepare_image(pkt['src_add'])
    except Exception as e :
        print("Unable to prepare image data for client", pkt['src_add'])
        print(e)
        return

    if (imgInt > 0):
      updIntervalMS = imgInt * 60000

    if (currHM > SLEEP_TIME):
      updIntervalMS = SLEEP_DELAY_MS

    pi = PendingInfo(
        imgUpdateVer = imgVer,
        imgUpdateSize = imgLen,
        osUpdateVer = ci.swVer,
        osUpdateSize = 0,
        nextCheckinDelay = updIntervalMS,
        rfu=bytearray(4*[0])
    )
    print(pi)

    pi_pkt = bytearray([ PKT_CHECKOUT ]) + bytearray(struct.pack('<QLQLL4s', *pi))

    send_data(pkt['src_add'], pi_pkt)

    thr = threading.Thread(target=IoTrequests.IoTpushInfo, args=(ci, pi, pkt['src_add'],), daemon=True)
    thr.start()

def process_download(pkt, data):
    cri = ChunkReqInfo._make(struct.unpack('<QLBB6s',data))
    if notDaemon():
      print(cri)

    ci = ChunkInfo(
        offset = cri.offset,
        osUpdatePlz = 0,
        rfu = 0,
    )
    if notDaemon():
      print(ci)

    try:
        fdata = get_image_data(cri.versionRequested, cri.offset, cri.len)
    except Exception as e :
        print("Unable to get image data for version", cri.versionRequested)
        print(e)
        return

    outpkt = bytearray([ PKT_CHUNK_RESP ]) + bytearray(struct.pack('<LBB', *ci)) + bytearray(fdata)

    if notDaemon():
      print("sending chunk", len(outpkt), outpkt[:10].hex() ,"...")

    send_data(pkt['src_add'], outpkt)

def generate_pkt_header(pkt): #hacky- timaccop cannot provide header data
    bcast = True
    if pkt['dst_add'] == b'\xff\xff': #broadcast assoc
        hdr = bytearray.fromhex("01c8")
    else:
        hdr = bytearray.fromhex("41cc")
        bcast = False
    hdr.append(pkt['dsn'])
    hdr.extend(pkt['dst_pan_id'])
    hdr.extend(pkt['dst_add'])
    if bcast:
        hdr.extend(pkt['src_pan_id'])
    hdr.extend(reversed(pkt['src_add']))

    return hdr


def process_pkt(pkt):
    hdr = generate_pkt_header(pkt)

    if len(pkt['data']) < 10:
        print("Received a too short paket")
        print("data", pkt['data'].hex())
        return

    nonce = bytearray(pkt['data'][-4:])
    nonce.extend(reversed(pkt['src_add']))
    nonce.extend(b'\x00')

    tag = pkt['data'][-8:-4]

    ciphertext = pkt['data'][:-8]

    plaintext = decrypt(hdr, ciphertext, tag, nonce)
    if not plaintext:
        print("data", pkt['data'].hex())
        print("hdr", hdr.hex())
        print("ciph", ciphertext.hex())
        print("nonce", nonce.hex())
        print("tag", tag.hex())
        print("packet is NOT authentic")
        return

    typ = plaintext[0]

    if typ == PKT_ASSOC_REQ:
        print("Got assoc request")
        process_assoc(pkt, plaintext[1:])
    elif typ == PKT_CHECKIN:
        print("Got checkin request")
        process_checkin(pkt, plaintext[1:])
    elif typ == PKT_CHUNK_REQ:
        if notDaemon():
          print("Got chunk request")
        process_download(pkt, plaintext[1:])
    else:
        print("Unknown request", typ)

def notDaemon():
  try:
    notD = (os.getpgrp() == os.tcgetpgrp(sys.stdout.fileno()))
  except Exception as e :
    notD = True
  return notD


def sigusr1_handler(signum, frame):
  print("SIGUSR1(", signum, ") at ", time.time())
  if os.path.isfile(CLIENTS_JSON):
    clImgInfo = IoTrequests.IoTgetClientsImageInfo(CLIENTS_JSON, "")
    print("clImgInfo", clImgInfo)
    for clStr in clImgInfo['clients']:
      imgFile = IMAGE_WORKDIR + str(clImgInfo['clients'][clStr]['imgVer']) + ".bmp"
      if not os.path.isfile(imgFile):
        print("Error : File not found", imgFile)
      else:
        print("OK :", imgFile, " found")

def sigusr2_handler(signum, frame):
  print("SIGUSR2(", signum, ") at ", time.time())
  if os.path.isfile(CLIENTS_JSON):
    clImgInfo = IoTrequests.IoTgetClientsImageInfo(CLIENTS_JSON, "")
    print("clImgInfo", clImgInfo)
    for i in clImgInfo['clients']:
      IoTrequests.IoTgetImage(i, CLIENTS_JSON, True)
  else:
    cwd = os.getcwd()
    print("CLIENTS_JSON not exits", cwd, CLIENTS_JSON)

def create_daemon():
  try:
    pid = os.fork()
    print("Fork : " + str(pid))
    if pid > 0:
      sys.exit(0)

  except OSError as e:
    print("Unable to fork")
    sys.exit(1)

signal.signal(signal.SIGUSR1, sigusr1_handler)
signal.signal(signal.SIGUSR2, sigusr2_handler)

os.chdir(BASE_DIR)
create_daemon()
timaccop.init(PORT, PANID, CHANNEL, EXTENDED_ADDRESS, process_pkt)
PID=os.getpid()
print("Station started :", PID )
timaccop.run()
