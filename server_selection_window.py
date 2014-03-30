#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import threading
import gtk
import gobject
import socket
import socket
import json
import time
import select

class ServerSelectionWindow(gtk.Window):
    def __init__(self, connection_callback):
        gtk.Window.__init__(self)
        self.set_title("Server selection")
        self.connection_callback = connection_callback
        self.set_default_size(450, 300)
        self.add(self.make_top_box())
        self.show_all()
        self.found_servers = set()
        self.thread_running = False
        self.thread_running_lock = threading.Lock()
        self.launch_discovery_thread(0)
    
    def load_discovered_server(self, data):
        self.server_list.append([data["server_name"], data["server_address"], str(data["server_port"])])
    
    def launch_discovery_thread(self, x):
        with self.thread_running_lock:
            if self.thread_running:
                return
            self.thread_running = True
            self.discovery_button.set_sensitive(False)
            threading.Thread(target=self.discover_servers).start()
    
    def read_message(self, sock):
        data, addr = sock.recvfrom(1024)
        data = json.loads(data)
        server_tuple = (addr[0], data["server_port"])
        if server_tuple not in self.found_servers:
            self.found_servers.add(server_tuple)
            data["server_address"] = addr[0]
            gobject.idle_add(self.load_discovered_server, data)

    def discover_servers(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto("X", ("<broadcast>", 21283))
        sock.sendto("X", ("<broadcast>", 21284))
        timeout = 2
        try:
            while timeout > 0:
                start_time = time.time()
                read_socks, _, _ = select.select([sock], [], [], timeout)
                if any(read_socks):
                    self.read_message(sock)
                else:
                    break
                timeout = max(timeout - (time.time() - start_time), 0)
        except socket.timeout:
            pass
        except ValueError:
            pass
        with self.thread_running_lock:
            self.thread_running = False
            gobject.idle_add(self.discovery_button.set_sensitive, True)
            
    def server_list_cursor_changed(self, treeview):
        self.connect_button.set_sensitive(True)

    def connect_button_clicked(self, x):
        (model, tree_iter) = self.server_list_view.get_selection().get_selected()
        address = self.server_list.get_value(tree_iter, 1)
        port = int(self.server_list.get_value(tree_iter, 2))
        connect_automatically = self.connect_automatically_checkbox.get_active()
        self.connection_callback(address, port, connect_automatically)
        self.destroy()

    def make_top_box(self):
        box = gtk.VBox(False)
        box.pack_start(self.make_server_list(), True)
        box.pack_start(self.make_bottom_box(), False)
        return box

    def make_server_list(self):
        self.server_list = gtk.ListStore(str, str, str)
        self.server_list_view = gtk.TreeView(self.server_list)
        
        server_name_col = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=0)
        server_address_col = gtk.TreeViewColumn('Address', gtk.CellRendererText(), text=1)
        server_port_col = gtk.TreeViewColumn('Port', gtk.CellRendererText(), text=2)
        server_name_col.set_resizable(True)
        server_address_col.set_resizable(True)
        server_name_col.set_expand(True)
        server_address_col.set_expand(True)
        server_port_col.set_expand(True)
        
        self.server_list_view.append_column(server_name_col)
        self.server_list_view.append_column(server_address_col)
        self.server_list_view.append_column(server_port_col)
        
        self.server_list_view.connect("cursor-changed", self.server_list_cursor_changed)
        return self.server_list_view

    def make_bottom_box(self):
        box = gtk.HBox(False)
        self.connect_button = gtk.Button("Connect")
        self.connect_button.set_sensitive(False)
        self.connect_button.connect("clicked", self.connect_button_clicked)
        
        self.discovery_button = gtk.Button("Search")
        self.discovery_button.connect("clicked", self.launch_discovery_thread)
        
        self.connect_automatically_checkbox = gtk.CheckButton("Connect automatically next time")
        
        box.pack_start(self.connect_automatically_checkbox)
        box.pack_start(self.discovery_button)
        box.pack_start(self.connect_button)
        return box
