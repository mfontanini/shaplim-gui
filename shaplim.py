#!/usr/bin/python
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


import sys
import api
import gtk
import time
import threading

def stock_toolbar_image(stock):
    icon = gtk.Image() # icon widget
    icon.set_from_stock(stock, gtk.ICON_SIZE_DIALOG)
    return icon

class ShaplimGTK:
    def __init__(self):
        self.running = True
        self.api = api.API('127.0.0.1', 1337)
        self.cond_variable = threading.Condition()
        window = gtk.Window()
        window.set_default_size(800, 600)
        
        top_box = self.make_top_box()
        
        self.load_playlist()
        
        self.show_shared_content(self.api.list_shared_directories()["directories"], [])
        window.connect("destroy", self.destroy)
        window.add(top_box)
        window.show_all()
        threading.Thread(target=self.poll_events_loop).start()
    
    def destroy(self, x):
        gtk.main_quit()
        with self.cond_variable:
            self.running = False
            self.cond_variable.notify()
    
    def load_playlist(self):
        playlist_data = self.api.show_playlist()
        self.last_timestamp = playlist_data["timestamp"]
        for song in playlist_data["songs"]:
            self.playlist.append([song])
        if playlist_data["current"] != -1:
            self.playlist_view.set_cursor(playlist_data["current"])
    
    def reload_state(self):
        with self.cond_variable:
            self.cond_variable.notify()
    
    def poll_events_loop(self):
        while True:
            with self.cond_variable:
                if self.running == False:
                    return
                self.cond_variable.wait(0.5)
                if self.running == False:
                    return
            self.poll_events()
    
    def poll_events(self):
        events_data = self.api.new_events(self.last_timestamp)
        self.last_timestamp = events_data["timestamp"]
        for event in events_data["events"]:
            if event["type"] == "add_songs":
                for song in event["songs"]:
                    self.playlist.append([song])
            elif event["type"] == "play_song":
                self.playlist_view.set_cursor(event["index"])
            
    
    def prev_button_clicked(self, widget, event=None):
        self.reload_state()
        self.api.previous_song()
    
    def play_button_clicked(self, widget, event=None):
        self.reload_state()
        self.api.play()
    
    def pause_button_clicked(self, widget, event=None):
        self.reload_state()
        self.api.pause()
    
    def next_button_clicked(self, widget, event=None):
        self.reload_state()
        self.api.next_song()
    
    def make_controls_box(self):
        toolbar = gtk.Toolbar()
        toolbar.append_item("", "Previous song","",stock_toolbar_image(gtk.STOCK_MEDIA_PREVIOUS), self.prev_button_clicked)
        toolbar.append_item("", "Play","",stock_toolbar_image(gtk.STOCK_MEDIA_PLAY), self.play_button_clicked)
        toolbar.append_item("", "Pause","",stock_toolbar_image(gtk.STOCK_MEDIA_PAUSE), self.pause_button_clicked)
        toolbar.append_item("", "Next song","",stock_toolbar_image(gtk.STOCK_MEDIA_NEXT), self.next_button_clicked)
        toolbar.set_icon_size(gtk.ICON_SIZE_DIALOG)
        
        alignment = gtk.Alignment(xalign=0.5)
        alignment.add(toolbar)
        return alignment
    
    def make_shared_folders_view_control(self):
        self.shared_content = gtk.ListStore(str, gtk.gdk.Pixbuf, bool)
        self.shared_content_view = gtk.IconView(self.shared_content)
        self.shared_content_view.set_text_column(0)
        self.shared_content_view.set_pixbuf_column(1)
        self.shared_content_view.set_item_width(100)
        
        cell = self.shared_content_view.get_cells()[0]
        self.shared_content_view.set_cell_data_func(cell, retrieve_shared_name)
        
        self.shared_content_view.connect("item-activated", self.on_shared_content_clicked)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.shared_content_view)
        return scroll
    
    def make_controls_and_folders_box(self):
        box = gtk.VBox(False)
        box.pack_start(self.make_shared_folders_view_control(), True)
        box.pack_start(self.make_controls_box(), False)
        return box
    
    def make_top_box(self):
        self.playlist = gtk.ListStore(str)
        self.playlist_view = gtk.TreeView(self.playlist)
        
        box = gtk.HBox(False)
        box.pack_start(self.make_controls_and_folders_box(), True)
        box.pack_start(self.playlist_view, False)
        
        column = gtk.TreeViewColumn("Playlist")
        column.set_property("min-width", 230)
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        self.playlist_view.append_column(column)
        
        cell = gtk.CellRendererText()
        column.pack_start(cell, False)
        column.add_attribute(cell, "text", 0)
        column.set_cell_data_func(cell, retrieve_filename)
        return box
    
    def show_shared_content(self, dirs, files, parent=None):
        self.shared_content.clear()
        if parent is not None:
            pixbuf = self.shared_content_view.render_icon(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_DIALOG)
            self.shared_content.append([parent + "/..", pixbuf, True])
            parent = parent + '/'
        else:
            parent = ''
        for directory in dirs:
            pixbuf = self.shared_content_view.render_icon(gtk.STOCK_DIRECTORY, gtk.ICON_SIZE_DIALOG)
            self.shared_content.append([parent + directory, pixbuf, True])
        for f in files:
            pixbuf = self.shared_content_view.render_icon(gtk.STOCK_FILE, gtk.ICON_SIZE_DIALOG)
            self.shared_content.append([parent + f, pixbuf, False])
    
    def on_shared_content_clicked(self, widget, item):
        model = widget.get_model()
        # Is it a directory?
        if model[item][2]:
            # Check for ..
            directory = model[item][0]
            if directory.split('/')[-1] == '..':
                directory = '/'.join(directory.split('/')[:-2])
            if directory == '':
                data = self.show_shared_content(self.api.list_shared_directories()["directories"], [])
                data["files"] = ''
                directory = None
            else:
                data = self.api.list_directory(directory)
            self.show_shared_content(data["directories"], data["files"], directory)
        else:
            dir_name = self.get_dir_name(model[item][0])
            file_name = self.get_file_name(model[item][0])
            self.api.add_shared_songs(dir_name, [file_name])
            self.reload_state()
    
    def get_file_name(self, path):
        return path.split('/')[-1]
    
    def get_dir_name(self, path):
        return '/'.join(path.split('/')[:-1])

def retrieve_shared_name(column, cell, model, iter):
    pyobj = model.get_value(iter, 0)
    name = str(pyobj).split('/')[-1]
    if name.endswith('.mp3'):
        name = name[:-4]
    cell.set_property('text', name)
    return


def retrieve_filename(treeviewcolumn, cell, model, iter):
    pyobj = model.get_value(iter, 0)
    name = str(pyobj).split('/')[-1]
    name = '.'.join(name.split('.')[:-1])
    cell.set_property('text', name)
    return

if __name__ == "__main__":
    app = ShaplimGTK()
    gtk.gdk.threads_init()
    gtk.main()
