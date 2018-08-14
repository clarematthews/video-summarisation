## Based on GoPro Instant Streaming v1.0
##
## By @Sonof8Bits and @KonradIT
##

import sys
import socket
from urllib.request import urlopen
import subprocess
from time import sleep
import signal
import json
import http
import summarise
from multiprocessing.pool import ThreadPool

BASE = 'http://10.5.5.9'
URL = '{}:8080/live/amba.m3u8'.format(BASE)
UDP_IP = '10.5.5.9'
UDP_PORT = 8554
KEEP_ALIVE_PERIOD = 2500
KEEP_ALIVE_CMD = 2
FRAMES = './frames/'


def get_command_msg(id):
    return '_GPHD_:0:0:{:d}:0.000000\n'.format(id)


def gopro_live():
    message = get_command_msg(KEEP_ALIVE_CMD)
    try:
        response_raw = urlopen('{}/gp/gpControl'.format(BASE)).read().decode('utf-8')
        jsondata = json.loads(response_raw)
        response = jsondata['info']['firmware_version']
    except http.client.BadStatusLine:
        response = urlopen('{}/camera/cv'.format(BASE)).read().decode('utf-8')
    print(response)
    print(jsondata['info']['model_name']+'\n'+jsondata['info']['firmware_version'])
    ##
	## HTTP GETs the URL that tells the GoPro to start streaming.
	##
    urlopen('{}/gp/gpControl/execute?p1=gpStream&a1=proto_v2&c1=restart'.format(BASE)).read()
    print('UDP target IP:', UDP_IP)
    print('UDP target port:', UDP_PORT)
    print('message:', message)

    print('Recording stored in: ' + FRAMES)
    template = '{}img{{:06d}}.png'.format(FRAMES)
    fname = '{}img%06d.png'.format(FRAMES)
    ffmpegstr = 'ffmpeg -loglevel panic -y -i "udp://10.5.5.100:8554?fifo_size=1000000&overrun_nonfatal=1&buffer_size=128000" -vf fps=10 {}'.format(fname)
    subprocess.Popen(ffmpegstr, shell=True)
    if sys.version_info.major >= 3:
        message = bytes(message, 'utf-8')
    print('Press ctrl+C to quit this application.\n')
    pool = ThreadPool(processes=1)
    keyframes = pool.apply_async(summarise.run, (FRAMES, template))
    try:
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(message, (UDP_IP, UDP_PORT))
            sleep(KEEP_ALIVE_PERIOD/1000)
    except KeyboardInterrupt:
        quit_gopro()
    print('Waiting for kfs')
    return keyframes.get()


def quit_gopro():
    urlopen('{}/gp/gpControl/execute?p1=gpStream&a1=proto_v2&c1=stop'.format(BASE)).read()


if __name__ == '__main__':
    subprocess.Popen('rm {}img*.jpg'.format(FRAMES), shell=True)
    subprocess.Popen('rm {}img*.png'.format(FRAMES), shell=True)
    keyframes = gopro_live()
    print(keyframes)
