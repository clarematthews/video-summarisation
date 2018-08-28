#!/bin/sh

# Activate virtual environment
source ./cc/bin/activate

# Kill off UDP connection hanging around
pid=$(lsof -i udp:8554 | awk '{for(i=1;i<=NF;i++) if ($i=="ffmpeg") print $(i+1)}')
if ! [ -z "$pid" ]
then
	kill -9 $pid
fi

# Start redis and worker
redis-server &
python cc_app/worker.py &

# Start client
cd client
npm start &
cd ..

# Start app
export FLASK_APP=./cc_app/index.py
flask run -h 0.0.0.0
