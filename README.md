# epaper-station
ORIGINAL code by @danielkucera. See https://github.com/danielkucera/epaper-station for more details

Modifiation:
- <DISPLAY_MAC>.png, is now GET on client request between 6:00 and 22:00 (can be changed in IoTrequests.py)
- imgVer is timestamp of GET/generation of bitmap instead of CRC of PNG 
- Bitmap data for client is generated "before" client Checkin request
- Client/ePaper send info to the server (http GET, on Checkin request) 
- All *.bmp stored in /tmp dir
- SIGUSR signals, see below

## Install
```
apt install python3-serial python3-pycryptodome python3-pil
```

## Config
```
edit url & CONSTS in IoTrequests.py
```

## Run
```
cd /home/pi/epaper-station/; /usr/bin/python3 ./station.py&
```

## Usage
- to pair a display, it has to be really really close (touching the adapter with left edge) - when the display "checks in", it will check the presence of <DISPLAY_MAC>.png in current dir, convert it to bmp and send to display - 
  if the image doesn't change, the display will stay as is and checks back again in defined interval (`checkinDelay`)

- <DISPLAY_MAC>.png is now HTTP GETed on Checkin request sent by client (ePaper)

## SIGUSR Signals - Info & Action
If running as a daemon
- show image version [name of /tmp/*.bmp] and image size that will be sent to the client on Checkin request
```
kill -SIGUSR1 <PID>
```

- HTTP GET images for all known clients (stored in clients.json)
```
kill -SIGUSR2 <PID>
```

## cc2531, RPi, Flash HowTo
[https://www.klosko.net/tools/ePaper/howto.txt]
