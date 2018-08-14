import socket
import cv2
import numpy as np
import argparse


BUFFER = 1024

def stream(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (host, port)

    counter = 0
    while(True):

        #sock.bind(server_address)
        sock.connect(server_address)

        data, server = sock.recvfrom(BUFFER)
        print('Fragment size : {}'.format(len(data)))
        array = np.frombuffer(data, dtype=np.dtype('uint8'))
        img = cv2.imdecode(array, 1)
        filename = 'files/img_{}.jpg'.format(counter)
        status = cv2.imwrite(filename, img)
        print('File {} saved: {}'.format(filename, status)) 
        counter += 1
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Read UDP stream')
    parser.add_argument('--host', default='10.5.5.100')
    parser.add_argument('--port', default=8554)
    args = parser.parse_args()

    stream(args.host, args.port)

