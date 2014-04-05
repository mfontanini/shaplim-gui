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
import gobject
import signal
from server_selection_window import ServerSelectionWindow
from command_manager import Command, CommandManager
from config_manager import ConfigurationManager
from image_manager import ImageManager
from shared_media import SharedMediaWidget

gobject.threads_init()

def stock_toolbar_image(stock):
    icon = gtk.Image()
    icon.set_from_stock(stock, gtk.ICON_SIZE_DIALOG)
    return icon

def make_markup_label(text):
    label = gtk.Label(text) 
    label.set_use_markup(True)
    return label

def make_song_control_label(text):
    label = make_markup_label(text)
    label.set_alignment(xalign=0, yalign=0)
    
    return label 

def make_song_info_label(text):
    label = make_markup_label(text)
    label.set_alignment(xalign=0, yalign=0)
    align = gtk.Alignment()
    align.set_padding(0, 0, 20, 5)
    align.add(label)
    return align 

class ShaplimGTK:
    def __init__(self):
        self.running = True
        self.image_manager = ImageManager()
        window = gtk.Window()
        window.set_title("Shaplim")
        window.set_default_size(800, 600)
        self.is_playing = False
        self.api = None
        self.cmd_manager = None
        
        top_box = self.make_top_box()
        
        window.connect("destroy", self.destroy)
        window.add(top_box)
        window.show_all()
        
        self.config_manager = ConfigurationManager()
        if self.config_manager.load_default_file():
            if self.config_manager.server_data:
                data = self.config_manager.server_data
                self.connect_to_server(data[0], data[1])
        if not self.api:
            server_selection_window = ServerSelectionWindow(self.connect_to_server)
    
    def connect_to_server(self, address, port, connect_automatically=False):
        if self.cmd_manager:
            self.cmd_manager.stop()
        if self.api:
            self.api.disconnect()
        self.timer = None
        self.playlist.clear()
        self.last_selected_index = None
        self.current_song_length = 0
        self.api = api.API(address, port)
        self.cmd_manager = CommandManager(self.handle_new_events, self.api)
        timestamp = self.load_playlist()
        self.cmd_manager.run(timestamp)
        self.shared_media.show_shared_content(self.api.list_shared_directories()["directories"], [])
        if connect_automatically:
            self.config_manager.server_data = (address, port)
            self.config_manager.save_configuration()
    
    def song_bar_timeout(self):
        if self.current_song_length != 0 and self.is_playing:
            self.song_bar.set_value(self.song_bar.get_value() + 1)
            self.set_label_song_time(self.current_song_seconds, int(self.song_bar.get_value()))
        return True
    
    def remove_songs(self, indexes):
        self.cmd_manager.add(Command(self.api.delete_songs, [indexes], requires_timestamp=True))
        self.reload_state()
    
    def destroy(self, x):
        gtk.main_quit()
        if self.cmd_manager:
            self.cmd_manager.stop()
        if self.api:
            self.api.disconnect()
    
    def load_playlist(self):
        playlist_data = self.api.show_playlist()
        for song in playlist_data["songs"]:
            self.playlist.append([None, song])
        if playlist_data["current"] != -1:
            self.set_current_song(playlist_data["current"])
        else:
            self.cmd_manager.add(Command(self.api.player_status, callback=self.process_player_status))
        return playlist_data["timestamp"]
    
    def reload_state(self):
        self.cmd_manager.reload_state()
    
    def set_default_song_data(self):
        self.set_current_song_data(
            {
                "title" : "-",
                "artist" : "-",
                "title" : "-",
                "album" : "-",
                "picture_mime" : "",
                "length" : 0
            }
        )
    
    def process_player_status(self, data):
        self.shuffle_button.handler_block(self.shuffle_button_handle_id)
        self.shuffle_button.set_active(data["playlist_mode"] == "shuffle")
        self.shuffle_button.handler_unblock(self.shuffle_button_handle_id)
        self.is_playing = data["status"] == "playing"
        self.song_bar.set_value(int(data["current_song_percent"] * self.current_song_length))
        self.set_label_song_time(self.current_song_seconds, int(self.song_bar.get_value()))
        if self.timer is None:
            self.timer = gobject.timeout_add(1000, self.song_bar_timeout)
    
    def set_label_song_time(self, label, song_time):
        seconds = song_time % 60
        label.set_text("{0}:{1}".format(song_time / 60, seconds if seconds >= 10 else '0' + str(seconds)))
    
    def set_current_song_length(self, length):
        self.current_song_length = length
        self.song_bar.set_upper(length)
        self.set_label_song_time(self.total_song_seconds, length)
        self.cmd_manager.add(Command(self.api.player_status, callback=self.process_player_status))
    
    def set_current_song_data(self, data):
        self.info_controls["title"].set_text(data["title"] or "Unknown")
        self.info_controls["artist"].set_text(data["artist"] or "Unknown")
        self.info_controls["album"].set_text(data["album"] or "Unknown")
        self.set_current_song_length(data["length"])
        if data["picture_mime"] == "image/jpeg":
            loader = gtk.gdk.PixbufLoader("jpeg")
        elif data["picture_mime"] == "image/png":
            loader = gtk.gdk.PixbufLoader("png")
        else:
            self.info_controls["picture"].set_from_pixbuf(
                self.image_manager.icons["no_logo"].get_pixbuf()
            )
            return
        loader.write(data["picture"].decode('base64'))
        loader.close()
        pixbuf = loader.get_pixbuf().scale_simple(120, 120, gtk.gdk.INTERP_BILINEAR)
        self.info_controls["picture"].set_from_pixbuf(pixbuf)

    def set_current_song(self, index):
        if self.last_selected_index is not None:
            iterator = self.playlist.get_iter(self.last_selected_index)
            self.playlist.set_value(iterator, 0, None)
        if index == -1:
            self.last_selected_index = None
            self.is_playing = False
            self.current_song_length = 0
            self.set_default_song_data()
            return
        self.last_selected_index = index
        iterator = self.playlist.get_iter(index)
        pixbuf = self.playlist_view.render_icon(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU)
        self.playlist.set_value(iterator, 0, pixbuf)
        self.cmd_manager.add(
            Command(
                self.api.song_info, 
                [self.playlist[index][1]], 
                requires_timestamp=False, 
                callback=self.set_current_song_data
            )
        )
    
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
                removed_current = self.last_selected_index in indexes
                for index in indexes:
                    # Any index
                    if index < self.last_selected_index:
                        self.last_selected_index -= 1
                    self.playlist.remove(self.playlist[index].iter)
                if removed_current:
                    self.last_selected_index = None
                    self.set_default_song_data()
            elif event["type"] == "play":
                self.is_playing = True
            elif event["type"] == "pause":
                self.is_playing = False
            elif event["type"] == "playlist_mode_changed":
                self.shuffle_button.handler_block(self.shuffle_button_handle_id)
                self.shuffle_button.set_active(event["mode"] == "shuffle")
                self.shuffle_button.handler_unblock(self.shuffle_button_handle_id)
    
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
        toolbar.append_item("", "Previous song","", self.image_manager.icons["previous"], self.prev_button_clicked)
        toolbar.append_item("", "Play","", self.image_manager.icons["play"], self.play_button_clicked)
        toolbar.append_item("", "Pause","", self.image_manager.icons["pause"], self.pause_button_clicked)
        toolbar.append_item("", "Next song","", self.image_manager.icons["next"], self.next_button_clicked)
        toolbar.set_icon_size(gtk.ICON_SIZE_MENU)
        
        self.song_bar = gtk.Adjustment(0.0, 0.0, 100.0, 1.0, 1.0, 0.0)
        scale = gtk.HScale(self.song_bar)
        scale.set_update_policy(gtk.UPDATE_CONTINUOUS)
        scale.set_draw_value(False)
        
        hbox = gtk.HBox()
        self.current_song_seconds = make_markup_label("0:00")
        self.total_song_seconds = make_markup_label("0:00")
        hbox.pack_start(self.current_song_seconds, False)
        hbox.pack_start(scale, True)
        hbox.pack_start(self.total_song_seconds, False)
        
        alignment = gtk.Alignment(xalign=0.5)
        alignment.add(toolbar)
        vbox = gtk.VBox()
        vbox.pack_start(hbox, True, True)
        vbox.pack_start(alignment)
        return vbox
    
    def make_controls_and_folders_box(self):
        box = gtk.VBox(False)
        self.shared_media = SharedMediaWidget(self)
        box.pack_start(self.shared_media, True)
        box.pack_start(gtk.HSeparator(), False)
        box.pack_start(self.make_controls_box(), False)
        return box
    
    def make_song_information_frame(self):
        vbox = gtk.VBox()
        table = gtk.Table(3, 2)
        self.info_controls = {
            "title" : make_song_control_label("-"),
            "artist" : make_song_control_label("-"),
            "album" : make_song_control_label("-"),
            "length" : 0,
            "picture" : gtk.Image()
        }
        table.set_row_spacings(5)
        table.attach(make_song_info_label("<b>Title</b>:"), 0, 1, 0, 1)
        table.attach(self.info_controls["title"], 1, 2, 0, 1)
        table.attach(make_song_info_label("<b>Artist</b>:"), 0, 1, 1, 2)
        table.attach(self.info_controls["artist"], 1, 2, 1, 2)
        table.attach(make_song_info_label("<b>Album</b>:"), 0, 1, 2, 3)
        table.attach(self.info_controls["album"], 1, 2, 2, 3)
        
        self.info_controls["picture"].set_property("ypad", 2)
        self.info_controls["picture"].set_from_pixbuf(
            self.image_manager.icons["no_logo"].get_pixbuf()
        )
        
        vbox.pack_start(make_markup_label("<b>Song information</b>"))
        vbox.pack_start(gtk.HSeparator(), False)
        vbox.pack_start(self.info_controls["picture"], False)
        vbox.pack_start(table, padding=3, fill=False)
        return vbox
    
    def make_playlist_controls(self):
        toolbar = gtk.Toolbar()
        self.shuffle_button = gtk.ToggleToolButton()
        self.shuffle_button.set_icon_widget(self.image_manager.icons["shuffle"])
        self.shuffle_button_handle_id = self.shuffle_button.connect("toggled", self.change_playlist_mode)
        toolbar.insert(self.shuffle_button, 0)
        toolbar.set_icon_size(gtk.ICON_SIZE_BUTTON)
        
        return toolbar
    
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
        self.playlist_view.connect("row-activated", self.playlist_element_activated)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.playlist_view)
        
        vbox = gtk.VBox()
        vbox.pack_start(self.make_song_information_frame(), False)
        vbox.pack_start(gtk.HSeparator(), False)
        vbox.pack_start(make_markup_label("<b>Playlist</b>"), False)
        vbox.pack_start(gtk.HSeparator(), False)
        vbox.pack_start(scroll, True)
        vbox.pack_start(gtk.HSeparator(), False)
        vbox.pack_start(self.make_playlist_controls(), False)
        return vbox
    
    def make_top_box(self):
        box = gtk.HBox(False)
        box.pack_start(gtk.VSeparator(), False)
        box.pack_start(self.make_playlist(), True)
        
        paned = gtk.HPaned()
        paned.pack1(self.make_controls_and_folders_box(), True, True)
        paned.pack2(box, False)
        return paned
    
    # Events
    
    def playlist_key_press(self, view, event):
        if event.keyval == gtk.gdk.keyval_from_name("Delete"):
            (model, pathlist) = self.playlist_view.get_selection().get_selected_rows()
            pathlist = map(lambda i: i[0], pathlist)
            self.remove_songs(pathlist)
    
    def playlist_element_activated(self, treeview, path, view_column):
        self.cmd_manager.add(Command(self.api.set_current_song, [path[0]], requires_timestamp=True))
        self.reload_state()

    def change_playlist_mode(self, x):
        if self.shuffle_button.get_active():
            self.cmd_manager.add(Command(self.api.set_playlist_mode, ["shuffle"]))
        else:
            self.cmd_manager.add(Command(self.api.set_playlist_mode, ["default"]))

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
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    gtk.main()
