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
import copy
import Queue
import gobject

def stock_toolbar_image(stock):
    icon = gtk.Image()
    icon.set_from_stock(stock, gtk.ICON_SIZE_DIALOG)
    return icon

class Command:
    def __init__(self, function, params=None, requires_timestamp=False):
        self.function = function
        self.params = params if params is not None else []
        self.requires_timestamp = requires_timestamp

class CommandManager:
    def __init__(self, new_events_callback, last_timestamp, api):
        self.queue = Queue.Queue()
        self.callback = new_events_callback
        self.last_timestamp = last_timestamp
        self.api = api
        self.running = True
        threading.Thread(target=self.run_loop).start()
        
    def add(self, cmd):
        self.queue.put(cmd)
    
    def stop(self):
        self.running = False
        self.add(None)
    
    def reload_state(self):
        self.queue.put(None)
    
    def get_new_events(self):
        events_data = self.api.new_events(self.last_timestamp)
        self.last_timestamp = events_data["timestamp"]
        gobject.idle_add(self.callback, events_data["events"])

    def run_loop(self):
        while True:
            try:
                cmd = self.queue.get(timeout=0.2)
                if cmd is None:
                    self.get_new_events()
                else:
                    params = cmd.params
                    if cmd.requires_timestamp:
                        params.append(self.last_timestamp)
                    apply(cmd.function, params)
                self.queue.task_done()
            except Queue.Empty as ex:
                if not self.running:
                    return
                else:
                    self.get_new_events()
            


class ShaplimGTK:
    def __init__(self):
        self.running = True
        self.api = api.API('127.0.0.1', 1337)
        window = gtk.Window()
        window.set_default_size(800, 600)
        self.last_selected_index = None
        
        top_box = self.make_top_box()
        
        self.load_playlist()
        
        self.show_shared_content(self.api.list_shared_directories()["directories"], [])
        window.connect("destroy", self.destroy)
        window.add(top_box)
        window.show_all()
        self.cmd_manager = CommandManager(self.handle_new_events, self.last_timestamp, self.api)
    
    def remove_songs(self, indexes):
        self.cmd_manager.add(Command(self.api.delete_songs, [indexes], requires_timestamp=True))
        self.reload_state()
    
    def destroy(self, x):
        gtk.main_quit()
        self.cmd_manager.stop()
    
    def load_playlist(self):
        playlist_data = self.api.show_playlist()
        self.last_timestamp = playlist_data["timestamp"]
        for song in playlist_data["songs"]:
            self.playlist.append([None, song])
        if playlist_data["current"] != -1:
            self.set_current_song(playlist_data["current"])
    
    def reload_state(self):
        self.cmd_manager.reload_state()
    
    def set_current_song(self, index):
        if self.last_selected_index is not None:
            iterator = self.playlist.get_iter(self.last_selected_index)
            self.playlist.set_value(iterator, 0, None)
        if index == -1:
            self.last_selected_index = None
            return
        self.last_selected_index = index
        iterator = self.playlist.get_iter(index)
        pixbuf = self.playlist_view.render_icon(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
        self.playlist.set_value(iterator, 0, pixbuf)
    
    def handle_new_events(self, events):
        for event in events:
            if event["type"] == "add_songs":
                for song in event["songs"]:
                    self.playlist.append([None, song])
            elif event["type"] == "play_song":
                self.set_current_song(event["index"])
            elif event["type"] == "delete_songs":
                indexes = event["indexes"]
                indexes.sort(reverse=True)
                for index in indexes:
                    self.playlist.remove(self.playlist[index].iter)
                if self.last_selected_index in indexes:
                    self.last_selected_index = None
    
    def prev_button_clicked(self, widget, event=None):
        self.cmd_manager.add(Command(self.api.previous_song))
        self.reload_state()
    
    def play_button_clicked(self, widget, event=None):
        self.cmd_manager.add(Command(self.api.play))
        self.reload_state()
    
    def pause_button_clicked(self, widget, event=None):
        self.cmd_manager.add(Command(self.api.pause))
        self.reload_state()
    
    def next_button_clicked(self, widget, event=None):
        self.cmd_manager.add(Command(self.api.next_song))
        self.reload_state()
    
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
        self.shared_content_view.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.shared_content_view.set_text_column(0)
        self.shared_content_view.set_pixbuf_column(1)
        self.shared_content_view.set_item_width(120)
        self.shared_content_view.connect('key-press-event', self.shared_content_key_press)
        
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
    
    def make_playlist(self):
        self.playlist = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.playlist_view = gtk.TreeView(self.playlist)
        self.playlist_view.set_headers_visible(False)
        self.playlist_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.playlist_view.connect('key-press-event', self.playlist_key_press)
        
        renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn('', renderer, pixbuf=0)
        self.playlist_view.append_column(column)
        
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("", renderer, text=1)
        column.set_property("min-width", 230)
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_cell_data_func(renderer, retrieve_filename)
        self.playlist_view.append_column(column)
        self.playlist_view.connect("row-activated", self.on_playlist_element_activated)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.playlist_view)
        
        label = gtk.Label("<b>Playlist</b>") 
        label.set_use_markup(True)
        
        vbox = gtk.VBox()
        vbox.pack_start(label, False)
        vbox.pack_start(gtk.HSeparator(), False)
        vbox.pack_start(scroll, True)
        return vbox
    
    def make_top_box(self):
        box = gtk.HBox(False)
        box.pack_start(gtk.VSeparator(), False)
        box.pack_start(self.make_playlist(), True)
        
        paned = gtk.HPaned()
        paned.pack1(self.make_controls_and_folders_box(), True)
        paned.pack2(box, False)
        return paned
    
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
    
    def get_file_name(self, path):
        return path.split('/')[-1]
    
    def get_dir_name(self, path):
        return '/'.join(path.split('/')[:-1])
    
    # Events
    
    def playlist_key_press(self, view, event):
        if event.keyval == gtk.gdk.keyval_from_name("Delete"):
            (model, pathlist) = self.playlist_view.get_selection().get_selected_rows()
            pathlist = map(lambda i: i[0], pathlist)
            self.remove_songs(pathlist)
        
    def shared_content_key_press(self, view, event):
        # This is Enter, fix me plx
        if event.keyval == 65293:
            self.add_selected_songs()
            return True
        return False
    
    def on_shared_content_clicked(self, widget, item):
        model = widget.get_model()
        # Is it a directory?
        if model[item][2]:
            # Check for ..
            directory = model[item][0]
            if directory.split('/')[-1] == '..':
                directory = '/'.join(directory.split('/')[:-2])
            if directory == '':
                data = self.api.list_shared_directories()
                data["files"] = ''
                directory = None
            else:
                data = self.api.list_directory(directory)
            self.show_shared_content(data["directories"], data["files"], directory)
        else:
            self.add_selected_songs()

    def add_selected_songs(self):
        selected = self.shared_content_view.get_selected_items()
        selected = filter(lambda i: not self.shared_content[i][2], selected)
        selected = map(lambda i: self.shared_content[i[0]][0], selected)
        dir_name = set(map(self.get_dir_name, selected))
        if len(dir_name) > 1:
            return False
        dir_name = dir_name.pop()
        file_names = map(self.get_file_name, selected)
        file_names.sort()
        self.shared_content_view.unselect_all()
        self.cmd_manager.add(Command(self.api.add_shared_songs, [ dir_name, file_names ]))
        self.reload_state()
    
    def on_playlist_element_activated(self, treeview, path, view_column):
        return False


def retrieve_shared_name(column, cell, model, iter):
    pyobj = model.get_value(iter, 0)
    name = str(pyobj).split('/')[-1]
    if name.endswith('.mp3'):
        name = name[:-4]
    if len(name) > 60:
        name = name[:58] + '...'
    cell.set_property('text', name)
    return


def retrieve_filename(treeviewcolumn, cell, model, iter):
    pyobj = model.get_value(iter, 1)
    name = str(pyobj).split('/')[-1]
    name = '.'.join(name.split('.')[:-1])
    cell.set_property('text', name)
    return

if __name__ == "__main__":
    app = ShaplimGTK()
    gobject.threads_init()
    gtk.main()
