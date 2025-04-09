from flask import Blueprint, render_template, request, flash, redirect, url_for
import os # Import the os module
import subprocess # For running shell commands
import shutil # For checking executables like 'screen'
import re # For validating server_name
from . import db # Import db instance from __init__
from .models import ServerInstance # Import the ServerInstance model

bp = Blueprint('main', __name__)

# --- Helper Functions for Config Generation ---

def generate_server_cfg_content(port, query_port):
    """Generates the content for Server.cfg"""
    # Basic Server.cfg content. More options can be added later.
    # Make sure NUMPLAYERS is set if needed, or use defaults.
    return f"""\
Port={port}
QueryPort={query_port}
"""
    # Consider adding: ServerName=\"{server_name}\" - needs server_name passed in

def generate_rcon_cfg_content(password):
    """Generates the content for Rcon.cfg"""
    return f"Password={password}\n"

def run_shell_command(command, cwd=None, capture_output=True, text=True, check=False, shell=True):
    """Helper to run shell commands."""
    try:
        # Use shell=True carefully, ensure commands are safe
        result = subprocess.run(command, cwd=cwd, capture_output=capture_output, text=text, check=check, shell=shell)
        if result.returncode != 0 and check:
             flash(f"Command failed: {command}\nError: {result.stderr}", "error")
        # Log output for debugging if needed
        # print(f"CMD: {command}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        return result
    except FileNotFoundError:
        flash(f"Error: Command not found in '{command}'. Is it in PATH?", "error")
        return None
    except Exception as e:
        flash(f"An unexpected error occurred running command '{command}': {e}", "error")
        return None

def is_safe_servername(name):
    """Check if server name contains only safe characters for paths/scripts."""
    return bool(re.match(r'^[a-zA-Z0-9_]+$', name))

# --- Routes ---

@bp.route('/')
def index():
    # Query servers from DB to display on homepage (implementation later)
    servers = ServerInstance.query.order_by(ServerInstance.created_at.desc()).all()
    return render_template('index.html', title='Home', servers=servers)

@bp.route('/deploy', methods=['GET', 'POST'])
def deploy_server():
    if request.method == 'POST':
        server_name = request.form.get('server_name')
        base_path = request.form.get('base_path') # Changed from server_path
        server_port_str = request.form.get('server_port', '7787')
        query_port_str = request.form.get('query_port', '27165')
        max_players_str = request.form.get('max_players', '80') # New field
        rcon_password = request.form.get('rcon_password')

        errors = []
        server_port = None
        query_port = None
        max_players = None

        # --- Input Validation ---
        if not server_name: errors.append("Server Name is required.")
        elif not is_safe_servername(server_name): errors.append("Server Name can only contain letters, numbers, and underscores.")

        if not base_path: errors.append("Base Installation Path is required.")
        elif not os.path.isabs(base_path): errors.append("Base Installation Path must be an absolute path (e.g., /home/user/...).")
        # We'll create the base path later if it doesn't exist, but maybe check writability?

        if not rcon_password: errors.append("RCON Password is required.")

        try: # Port validation
            server_port = int(server_port_str)
            if not 1 <= server_port <= 65535: errors.append("Game Port must be between 1 and 65535.")
        except (ValueError, TypeError): errors.append("Game Port must be a valid number.")

        try: # Query Port validation
            query_port = int(query_port_str)
            if not 1 <= query_port <= 65535: errors.append("Query Port must be between 1 and 65535.")
        except (ValueError, TypeError): errors.append("Query Port must be a valid number.")

        try: # Max Players validation
            max_players = int(max_players_str)
            if max_players <= 0: errors.append("Max Players must be a positive number.")
        except (ValueError, TypeError): errors.append("Max Players must be a valid number.")

        # --- Dependency Checks ---
        missing_deps = []
        has_downloader = False
        downloader_to_use = None # Store which one we found

        if shutil.which('wget'):
            has_downloader = True
            downloader_to_use = 'wget'
        elif shutil.which('curl'): # Check curl only if wget not found
            has_downloader = True
            downloader_to_use = 'curl'

        if not has_downloader:
            missing_deps.append("wget or curl")
        if not shutil.which('tar'):
            missing_deps.append("tar")
        if not shutil.which('screen'):
            missing_deps.append("screen")

        if missing_deps:
            # Construct a helpful installation suggestion
            # This is just a guess, might need adjustment based on common distros
            install_suggestion = ""
            if missing_deps:
                 install_suggestion = f"(e.g., 'sudo apt update && sudo apt install {' '.join(missing_deps)}' or 'sudo yum install {' '.join(missing_deps)}') "

            dep_list = ", ".join(missing_deps)
            errors.append(f"Missing required system dependencies: {dep_list}. Please install them using your system's package manager {install_suggestion.strip()}.")

        # --- Handling ---
        if errors:
            for error in errors: flash(error, 'error')
            return render_template('deploy.html', title='Deploy Server',
                                   server_name=server_name, base_path=base_path,
                                   server_port=server_port_str, query_port=query_port_str,
                                   max_players=max_players_str, rcon_password=rcon_password)
        else:
            # --- Deployment Steps ---
            steamcmd_dir = os.path.join(base_path, 'steamcmd')
            server_instance_dir = os.path.join(base_path, server_name) # e.g., /home/user/sqp_servers/server1
            steamcmd_script_path = os.path.join(steamcmd_dir, f'update_{server_name}.txt')
            start_script_path = os.path.join(base_path, f'start_{server_name}.sh') # Place start script in base_path for clarity
            config_dir = os.path.join(server_instance_dir, 'SquadGame', 'ServerConfig')
            rcon_cfg_path = os.path.join(config_dir, 'Rcon.cfg')
            steamcmd_exe = os.path.join(steamcmd_dir, 'steamcmd.sh')
            server_exe = os.path.join(server_instance_dir, 'SquadGameServer.sh') # Linux executable name

            deployment_ok = True

            try:
                # --- Check if server name already exists in DB ---
                existing_server = ServerInstance.query.filter_by(name=server_name).first()
                if existing_server:
                    # If found, prevent deployment
                    raise Exception(f"Server instance with name '{server_name}' already exists in the database.")

                # 1. Ensure base_path exists
                os.makedirs(base_path, exist_ok=True)

                # 2. Ensure SteamCMD exists
                if not os.path.isfile(steamcmd_exe):
                    flash("SteamCMD not found, attempting to download...", "info")
                    os.makedirs(steamcmd_dir, exist_ok=True)

                    # Use the downloader identified during dependency check
                    downloader_cmd = None
                    if downloader_to_use == 'wget':
                        downloader_cmd = f"wget -q -O - https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar xzvf -"
                    elif downloader_to_use == 'curl':
                        downloader_cmd = f"curl -sqL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar xzvf -"
                    else: # Should not happen if dependency check passed
                         raise Exception("Internal error: No downloader (wget or curl) available, despite passing checks.")

                    flash(f"Using {downloader_to_use} to download SteamCMD...", "info")
                    result = run_shell_command(downloader_cmd, cwd=steamcmd_dir, check=True)
                    if result is None or result.returncode != 0:
                        raise Exception(f"Failed to download and extract SteamCMD using {downloader_to_use}.")
                    flash("SteamCMD downloaded and extracted.", "success")
                else:
                     flash("SteamCMD found.", "info")

                # 3. Create update script (update_{server_name}.txt)
                update_script_content = f"""\
@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
force_install_dir ../{server_name}
login anonymous
app_update 403240 validate
quit
"""
                with open(steamcmd_script_path, 'w') as f:
                    f.write(update_script_content)
                flash(f"Created SteamCMD update script: {steamcmd_script_path}", "info")

                # 4. Create start script (start_{server_name}.sh)
                # Note: Using absolute paths in the script for robustness
                start_script_content = f"""\
#!/bin/bash
echo "Running SteamCMD update..."
cd "{steamcmd_dir}" || exit 1
./steamcmd.sh +runscript "{os.path.basename(steamcmd_script_path)}" || exit 1
echo "SteamCMD update finished. Starting server..."
cd "{server_instance_dir}" || exit 1
# Make sure server executable exists and is executable before running
if [ -f "{server_exe}" ]; then
    chmod +x "{server_exe}"
    echo "Starting Squad Server..."
    # Execute the server directly in the foreground for screen
    exec ./{os.path.basename(server_exe)} Port={server_port} QueryPort={query_port} FIXEDMAXPLAYERS={max_players} RANDOM=NONE -log
else
    echo "Error: Server executable not found after update: {server_exe}"
    exit 1
fi
"""
                with open(start_script_path, 'w') as f:
                    f.write(start_script_content)
                run_shell_command(f"chmod +x '{start_script_path}'", check=True) # Make executable
                flash(f"Created start script: {start_script_path}", "info")

                # 5. Create Rcon.cfg (Server must be installed first by start script, but create dir now)
                os.makedirs(config_dir, exist_ok=True)
                rcon_content = generate_rcon_cfg_content(rcon_password)
                with open(rcon_cfg_path, 'w') as f:
                    f.write(rcon_content)
                flash(f"Created RCON config: {rcon_cfg_path}", "info")

                # 6. Run the start script in a detached screen session to install/update and start server
                # This command first runs the update, then starts the server within the script.
                flash(f"Attempting to start server '{server_name}' in screen session...", "info")
                screen_cmd = f"screen -dmS {server_name} bash '{start_script_path}'"
                result = run_shell_command(screen_cmd, check=True)
                if result is None or result.returncode != 0:
                     raise Exception(f"Failed to start screen session for {server_name}")

                flash(f"Deployment initiated for '{server_name}'. SteamCMD update and server start running in screen session '{server_name}'.", "success")

                # --- 7. Store server info in DB (only if all previous steps were ok) ---
                if deployment_ok:
                    new_server = ServerInstance(
                        name=server_name,
                        base_path=base_path,
                        instance_path=server_instance_dir,
                        game_port=server_port,
                        query_port=query_port,
                        max_players=max_players,
                        screen_session_name=server_name,
                        # Store plain RCON password for now - **SECURITY RISK**
                        # TODO: Implement password hashing (e.g., using Werkzeug)
                        rcon_password_hash=rcon_password
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    flash(f"Server instance '{server_name}' saved to database.", "success")
                else:
                    # This else block might be redundant if exceptions are raised on failure
                    # but ensures DB is not touched if deployment_ok is explicitly False
                    flash("Deployment steps completed with errors, server not saved to DB.", "warning")

            except Exception as e:
                db.session.rollback() # Rollback any potential partial DB changes
                flash(f"Deployment failed: {e}", "error")
                deployment_ok = False # Ensure flag is false on any exception
                # Consider cleanup steps here if needed (e.g., remove partial files/scripts)

            # Redirect back to index page after attempt
            return redirect(url_for('main.index'))

    # GET Request
    return render_template('deploy.html', title='Deploy Server',
                           server_name='', base_path='', server_port='7787',
                           query_port='27165', max_players='80', rcon_password='')

# Add other routes here later 