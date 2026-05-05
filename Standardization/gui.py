import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket, pickle
import ssl

def toggle_metadata():
    """Show or hide metadata section."""
    if metadata_frame.winfo_ismapped():
        metadata_frame.pack_forget()
    else:
        metadata_frame.pack(fill="x", padx=10, pady=5)

def toggle_nomad():
    """Show or hide NOMAD credentials section."""
    if nomad_frame.winfo_ismapped():
        nomad_frame.pack_forget()
    else:
        nomad_frame.pack(fill="x", padx=10, pady=5)

def browse_folder():
    path = filedialog.askdirectory(title="Select folder to watch")
    if path:
        folder_var.set(path)

def verify_nomad():
    """Send NOMAD credentials + metadata + folder info to server."""

    # Basic validation
    if not folder_var.get():
        messagebox.showerror("NOMAD", "Please choose a folder to watch.")
        return
    if not filetype_var.get():
        messagebox.showerror("NOMAD", "Please choose a file type (.ibw or .h5).")
        return

    # NOMAD creds
    creds = {
        "Server": nomad_server.get(),
        "Username": nomad_user.get(),
        "Password": nomad_pass.get()
    }

    # Metadata (6 sections)
    metadata_info = {f: entry.get("1.0", "end-1c") for f, entry in metadata_entries.items()}

    # Basic sample fields
    sample_info = {
        "Sample Name": sample_name.get(),
        "Data": sample_data.get(),
        "Date": sample_date.get(),
        "Person": person_name.get(),
    }

    # Folder/file info
    folder = folder_var.get()
    file_type = filetype_var.get()

    # Bundle into one dict (matches revised server.py expectation; adds sample_info)
    payload = {
        "nomad": creds,
        "metadata": metadata_info,
        "sample": sample_info,
        "folder": folder,
        "file_type": file_type
    }

    HOST = server_host_var.get().strip() or "localhost"
    try:
        PORT = int(server_port_var.get().strip() or "8104")
    except ValueError:
        messagebox.showerror("NOMAD", "Port must be a number.")
        return

    try:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_verify_locations("server.crt")  # Trust this cert
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            with context.wrap_socket(s, server_hostname=HOST) as ssock:
                ssock.connect((HOST, PORT))
                ssock.sendall(pickle.dumps(payload))
                ack = ssock.recv(1024).decode()
                messagebox.showinfo("NOMAD", f"Server replied: {ack}")
    except Exception as e:
        messagebox.showerror("NOMAD", f"Connection failed: {e}")

# -------------------
# Main Window
# -------------------
root = tk.Tk()
root.title("Data Entry + NOMAD Verification")
root.geometry("760x880")

# -------------------
# Server connection
# -------------------
server_box = ttk.LabelFrame(root, text="Server Connection")
server_box.pack(fill="x", padx=10, pady=8)

ttk.Label(server_box, text="Server Host:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
server_host_var = tk.StringVar(value="localhost")
ttk.Entry(server_box, textvariable=server_host_var, width=24).grid(row=0, column=1, sticky="w", padx=8, pady=4)

ttk.Label(server_box, text="Port:").grid(row=0, column=2, sticky="w", padx=8, pady=4)
server_port_var = tk.StringVar(value="8104")
ttk.Entry(server_box, textvariable=server_port_var, width=10).grid(row=0, column=3, sticky="w", padx=8, pady=4)

# -------------------
# Folder + file type
# -------------------
watch_box = ttk.LabelFrame(root, text="Data Source for Watcher")
watch_box.pack(fill="x", padx=10, pady=8)

ttk.Label(watch_box, text="Folder to Watch:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
folder_var = tk.StringVar(value="")
ttk.Entry(watch_box, textvariable=folder_var, width=54).grid(row=0, column=1, sticky="w", padx=8, pady=4)
ttk.Button(watch_box, text="Browse…", command=browse_folder).grid(row=0, column=2, sticky="w", padx=8, pady=4)

ttk.Label(watch_box, text="File Type:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
filetype_var = tk.StringVar(value=".ibw")
ttk.Combobox(watch_box, textvariable=filetype_var, values=[".ibw", ".h5"], width=10, state="readonly").grid(row=1, column=1, sticky="w", padx=8, pady=4)

# -------------------
# Basic Data Fields
# -------------------
ttk.Label(root, text="Sample Name:").pack(anchor="w", padx=10, pady=2)
sample_name = ttk.Entry(root, width=60)
sample_name.pack(padx=10, pady=2)

ttk.Label(root, text="Data:").pack(anchor="w", padx=10, pady=2)
sample_data = ttk.Entry(root, width=60)
sample_data.pack(padx=10, pady=2)

ttk.Label(root, text="Date:").pack(anchor="w", padx=10, pady=2)
sample_date = ttk.Entry(root, width=60)
sample_date.pack(padx=10, pady=2)

ttk.Label(root, text="Person Entering:").pack(anchor="w", padx=10, pady=2)
person_name = ttk.Entry(root, width=60)
person_name.pack(padx=10, pady=2)

# -------------------
# Metadata Button
# -------------------
metadata_button = ttk.Button(root, text="Show/Hide Metadata", command=toggle_metadata)
metadata_button.pack(pady=10)

# -------------------
# Metadata Fields (6 sections)
# -------------------
metadata_frame = ttk.Frame(root, relief="groove", borderwidth=2)

fields = [
    "Sample Metadata",
    "Experimental Content",
    "Data Acquisition",
    "Annotation & AI/ML Readiness",
    "Additional Notes",
    "Data Integration"
]

metadata_entries = {}
for f in fields:
    ttk.Label(metadata_frame, text=f + ":").pack(anchor="w", padx=10, pady=2)
    entry = tk.Text(metadata_frame, width=80, height=3)
    entry.pack(padx=10, pady=2)
    metadata_entries[f] = entry

# -------------------
# NOMAD Section Button
# -------------------
nomad_button = ttk.Button(root, text="Show/Hide NOMAD", command=toggle_nomad)
nomad_button.pack(pady=10)

# -------------------
# NOMAD Fields
# -------------------
nomad_frame = ttk.Frame(root, relief="groove", borderwidth=2)

ttk.Label(nomad_frame, text="NOMAD Server:").pack(anchor="w", padx=10, pady=2)
nomad_server = ttk.Entry(nomad_frame, width=60)
nomad_server.pack(padx=10, pady=2)

ttk.Label(nomad_frame, text="Username:").pack(anchor="w", padx=10, pady=2)
nomad_user = ttk.Entry(nomad_frame, width=60)
nomad_user.pack(padx=10, pady=2)

ttk.Label(nomad_frame, text="Password:").pack(anchor="w", padx=10, pady=2)
nomad_pass = ttk.Entry(nomad_frame, width=60, show="*")
nomad_pass.pack(padx=10, pady=2)

ttk.Button(nomad_frame, text="Verify NOMAD (send to server)", command=verify_nomad).pack(pady=10)

# -------------------
# Run the App
# -------------------
root.mainloop()
