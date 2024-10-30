from flask import Flask, render_template, redirect, url_for, request, abort
import secrets
from dataclasses import dataclass
from flask_socketio import SocketIO, emit, join_room, leave_room
from urllib.parse import urljoin

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store room data in memory (you might want to use a database in production)
@dataclass
class Room:
    id: str
    admin_token: str
    video_url: str = None
    current_time: float = 0
    is_playing: bool = False

rooms = {}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/create-room')
def create_room():
    room_id = secrets.token_urlsafe(8)
    admin_token = secrets.token_urlsafe(16)
    rooms[room_id] = Room(id=room_id, admin_token=admin_token)
    return redirect(url_for('room', room_id=room_id, admintoken=admin_token))

@app.route('/room/<room_id>')
def room(room_id):
    if room_id not in rooms:
        return redirect(url_for('home'))
    
    admin_token = request.args.get('admintoken')
    is_admin = admin_token and admin_token == rooms[room_id].admin_token
    
    # Generate different share URL without admin token
    share_url = urljoin(request.host_url, url_for('room', room_id=room_id))
    
    return render_template('room.html', 
                         room_id=room_id, 
                         is_admin=is_admin,
                         share_url=share_url,
                         admin_warning=is_admin)

@socketio.on('join')
def on_join(data):
    room_id = data['room_id']
    if room_id not in rooms:
        return
    
    join_room(room_id)
    admin_token = data.get('admin_token')
    is_admin = admin_token and admin_token == rooms[room_id].admin_token
    
    if is_admin:
        emit('admin_status', {'is_admin': True})
    
    # Send current video state to new participant
    if rooms[room_id].video_url:
        emit('video_update', {
            'url': rooms[room_id].video_url,
            'currentTime': rooms[room_id].current_time,
            'isPlaying': rooms[room_id].is_playing
        })

@socketio.on('update_video')
def on_video_update(data):
    room_id = data['room_id']
    admin_token = data.get('admin_token')
    
    if (room_id not in rooms or 
        not admin_token or 
        admin_token != rooms[room_id].admin_token):
        return
    
    room = rooms[room_id]
    room.video_url = data.get('url', room.video_url)
    room.current_time = data.get('currentTime', room.current_time)
    room.is_playing = data.get('isPlaying', room.is_playing)
    
    emit('video_update', {
        'url': room.video_url,
        'currentTime': room.current_time,
        'isPlaying': room.is_playing
    }, room=room_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)