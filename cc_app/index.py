from flask import Flask, jsonify, request, url_for
import json
from urllib.request import urlopen
from multiprocessing.pool import ThreadPool
import time
from redis import Redis
import os
import socket
import subprocess
import rq
import cc_app.worker


BASE = 'http://10.5.5.9'
URL = '{}/gp/gpControl'.format(BASE)
STREAM_ADDR = 'udp://10.5.5.100'
UDP_IP = '10.5.5.9'
UDP_PORT = 8554
KEEP_ALIVE_PERIOD = 2500
FRAMES = './cc_app/static/'

app = Flask(__name__)
app.config.from_object('cc_app.config.Config')
queue = rq.Queue(connection=cc_app.worker.conn)
status = {'isStreaming': False, 'images': []}


def keep_alive():
    message = bytes('_GPHD_:0:0:2:0.000000\n', 'utf-8')
    while status['isStreaming']:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message, (UDP_IP, UDP_PORT))
        time.sleep(KEEP_ALIVE_PERIOD/1000)


def clean_up():
    subprocess.Popen('rm -f {}img*.jpg'.format(FRAMES), shell=True)
    subprocess.Popen('rm -f {}img*.png'.format(FRAMES), shell=True)


@app.route('/start', methods=['POST'])
def start_stream():
    data = json.loads(request.data)
    budget = int(data['budget'])
    subprocess.Popen('rm -f {}img*.jpg'.format(FRAMES), shell=True).wait()
    subprocess.Popen('rm -f {}img*.png'.format(FRAMES), shell=True).wait()
    subprocess.Popen('rm -f {}.DS_Store'.format(FRAMES), shell=True).wait()
    while os.listdir(FRAMES):
        time.sleep(1)
    
    status['isStreaming'] = True
    print('Start streaming: {}'.format(status['isStreaming']))

    urlopen('{}/execute?p1=gpStream&a1=proto_v2&c1=restart'.format(URL)).read()
    template = '{}img{{:06d}}.png'.format(FRAMES)
    fname = '{}img%06d.png'.format(FRAMES)
    ffmpegstr = 'ffmpeg -loglevel panic -y -i '\
            '"{}:{}?fifo_size=1000000&overrun_nonfatal=1&buffer_size=128000"'\
            ' -vf fps=2 {}'.format(STREAM_ADDR, UDP_PORT, fname)
    subprocess.Popen(ffmpegstr, shell=True)

    job = queue.enqueue('summarise.run', args=[FRAMES, template, budget])
    id = job.get_id()

    alivepool = ThreadPool(processes=1)
    alivepool.apply_async(keep_alive)

    return jsonify({'id': id}), 200


@app.route('/stop', methods=['POST'])
def stop_stream():
    urlopen('{}/execute?p1=gpStream&a1=proto_v2&c1=stop'.format(URL)).read()
    status['isStreaming'] = False
    return '', 200


@app.route('/clear', methods=['POST'])
def clear_images():
    pool = ThreadPool(processes=1)
    pool.apply_async(clean_up)
    status['images'] = []
    return '', 200


@app.route('/status/', defaults={'id': None})
@app.route('/status/<id>')
def get_status(id):
    if not status['isStreaming']:
        return jsonify(status)

    if id is None or id == '0':
        return jsonify(status)

    job = queue.fetch_job(id)
    job.refresh()
    images = job.meta.get('frames')
    if images is None:
        images = []
    status['images'] = images
    return jsonify(status)


@app.after_request
def add_header(response):
    response.cache_control.public = True
    response.cache_control.max_age = 0
    response.cache_control.no_cache = True
    return response
