# epaper-station
ORIGINAL code by @danielkucera. See https://github.com/danielkucera/epaper-station for more details & fresh updates / bigfixes

Modifiation:
- <DISPLAY_MAC>.png, is now GET on client request between 6:00 and 22:00 (can be changed in IoTrequests.py)
- imgVer is timestamp of GET/generation of bitmap instead of CRC of PNG 
- Bitmap data for client is generated "before" client Checkin request
- Client/ePaper send info to the server (http GET, on Checkin request) 
- All *.bmp stored in /tmp dir
- SIGUSR signals, see below
- Daemonize after start
- Set epaper "nextCheckinDelay" via remote server - IoTpushInfo()
- Do not refresh after 22:00 for 8 hours to save power/display
- add python interpreter directry to tohe script


## Install
```
apt install python3-serial python3-pycryptodome python3-pil
```
on Turris Omnia
```
Login > LuCi > System > Software 
Download and install package: kmod-usb-acm
```
## Config
```
edit url & CONSTS in IoTrequests.py
```

## Run
```
cd /home/pi/epaper-station/; ./station.py
```
or from rc.local as a pi user 
```
sudo vi /etc/rc.local

su - pi -c '/home/pi/epaper-station/station.py'
```
On Turris Omnia
```
nano /etc/rc.local

/pathTo/epaper-station/station.py
```

All messages are logged to /var/log/daemon.log & /var/log/syslog when running from rc.local


## Usage
- to pair a display, it has to be really really close (touching the adapter with left edge) - when the display "checks in", it will check the presence of <DISPLAY_MAC>.png in current dir, convert it to bmp and send to display - 
  if the image doesn't change, the display will stay as is and checks back again in defined interval (`checkinDelay`)

- <DISPLAY_MAC>.png is now HTTP GETed on Checkin request sent by client (ePaper)

## SIGUSR Signals - Info & Action
*SIGUSR1
- show/log image version [name of /tmp/*.bmp] and image size that will be sent to the client on Checkin request
- check if bmp image exists 

```
kill -10 <PID>
```
or
```
kill -10 <PID> ; cat /var/log/syslog | tail -4
```
if running from rc.local

*SIGUSR2
- HTTP GET images for all known clients (stored in clients.json) and show image version/size
```
kill -12 <PID>
```
or
```
kill -12 <PID> ; cat /var/log/syslog | tail -3
```
if running from rc.local


## cc2531, RPi, Flash HowTo
[https://www.klosko.net/tools/ePaper/howto.txt]

## Possible improvements
- Add update schedule scheme


