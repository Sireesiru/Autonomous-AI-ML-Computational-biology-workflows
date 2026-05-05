import socket
import pickle   # serialize/deserialize Python dicts
import subprocess
import ssl
from copy_ibw_watcher_v2a import start_watcher

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(certfile="server.crt", keyfile="server.key")  # Generate these first
context.verify_mode = ssl.CERT_NONE

HOST = "127.0.0.1"   # Localhost (replace with server IP if needed)
PORT = 8015         # Must match the port in gui.py verify_nomad()

"""
def forward_to_ibw_watcher(folder, file_type):
    #Forward folder + file_type details to ibw_watcher.py (simulated).
    print(f"[server] Forwarding to ibw_watcher: folder={folder}, file_type={file_type}")
    try:
        # This assumes ibw_watcher.py accepts folder and file_type as CLI args
        subprocess.Popen(["python", "ibw_watcher.py", folder, file_type])
    except Exception as e:
        print(f"[server] Error launching ibw_watcher: {e}")

def forward_to_nomad(credentials, metadata):
    #Forward credentials + metadata to NOMAD (simulated).
    print(f"[server] Forwarding to NOMAD: {credentials}")
    print(f"[server] Metadata: {metadata}")
    # TODO: replace with real NOMAD API call
    print("[server] (simulated) NOMAD upload success")"""

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        s.bind((HOST, PORT))
        s.listen()
        print(f"[server] Listening on {HOST}:{PORT}")
        with context.wrap_socket(s, server_side=True) as ssock:
            while True:
                conn, addr = ssock.accept()
                with conn:
                    print(f"[server] Connected by {addr}")
                    data = conn.recv(4096)
                    if not data:
                        break

                    print(f"[server] Starting watcher")

                   
                    conn.sendall(b"Watcher started successfully!")

                    # Unpack dict sent from client
                    info = pickle.loads(data)
                    
                    # Extract details
                    credentials = info.get("nomad", {})
                    metadata    = info.get("metadata", {})
                    folder      = info.get("folder", "")
                    file_type   = info.get("file_type", "")

                    print("[server] Received Metadata:", metadata)
                    print("[server] Received Folder:", folder)

                    # Start the watcher
                    start_watcher(folder, metadata, credentials)

                    """# Forward to ibw_watcher
                    if folder and file_type:
                        modified_folder = r'/brave_mnt/' + folder[3:] 
                        forward_to_ibw_watcher(modified_folder, file_type)

                    # Forward to NOMAD if credentials exist
                    if credentials.get("Server") and credentials.get("Username"):
                        forward_to_nomad(credentials, metadata)"""
                    

                    # Acknowledge to client
                    ack = f"Credentials for {credentials.get('Username','?')} received and forwarded."
                    conn.sendall(ack.encode())

if __name__ == "__main__":
    run_server()
