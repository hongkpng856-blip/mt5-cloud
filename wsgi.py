# Render WSGI entry point
# 用 gunicorn + eventlet worker 行 Flask-SocketIO
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from app import app, socketio

# Gunicorn will use this
application = app

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
