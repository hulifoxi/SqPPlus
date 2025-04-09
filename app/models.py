from . import db # Import the db instance from __init__.py
from datetime import datetime

class ServerInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True, nullable=False) # Unique server name (e.g., server1)
    base_path = db.Column(db.String(256), nullable=False) # Base installation directory
    instance_path = db.Column(db.String(320), nullable=False) # Full path to server instance directory
    game_port = db.Column(db.Integer, nullable=False)
    query_port = db.Column(db.Integer, nullable=False)
    max_players = db.Column(db.Integer, nullable=False)
    screen_session_name = db.Column(db.String(64), nullable=False) # Should match 'name' usually
    rcon_password_hash = db.Column(db.String(128)) # Store hash, not plain text (optional for now)
    # status = db.Column(db.String(20), default='Unknown') # Maybe track status later? (Running, Stopped, Error)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ServerInstance {self.name}>'

    # Optional: Methods to set/check RCON password hash
    # def set_rcon_password(self, password):
    #     self.rcon_password_hash = generate_password_hash(password) # Need Werkzeug for this

    # def check_rcon_password(self, password):
    #     return check_password_hash(self.rcon_password_hash, password) 