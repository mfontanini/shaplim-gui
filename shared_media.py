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

import gtk
from command_manager import Command

class SharedMediaWidget(gtk.VBox):
    def __init__(self, core):
        gtk.VBox.__init__(self)
        
        self.core = core
        
        self.shared_content = gtk.ListStore(str, gtk.gdk.Pixbuf, bool)
        self.shared_content_view = gtk.IconView(self.shared_content)
        self.shared_content_view.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.shared_content_view.set_text_column(0)
        self.shared_content_view.set_pixbuf_column(1)
        self.shared_content_view.set_item_width(120)
        self.shared_content_view.connect('key-press-event', self.shared_content_key_press)
        self.shared_content_view.set_size_request(550, self.shared_content_view.get_size_request()[1])
        
        cell = self.shared_content_view.get_cells()[0]
        self.shared_content_view.set_cell_data_func(cell, retrieve_shared_name)
        
        self.shared_content_view.connect("item-activated", self.shared_content_clicked)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scroll.add(self.shared_content_view)
        
        self.pack_start(scroll, True)
    
    def show_shared_content(self, dirs, files, parent=None):
        self.shared_content.clear()
        if parent is not None:
            pixbuf = self.core.image_manager.icons["folder"].get_pixbuf()
            self.shared_content.append([parent + "/..", pixbuf, True])
            parent = parent + '/'
        else:
            parent = ''
        for directory in dirs:
            pixbuf = self.core.image_manager.icons["folder"].get_pixbuf()
            self.shared_content.append([parent + directory, pixbuf, True])
        for f in files:
            pixbuf = self.core.image_manager.icons["song"].get_pixbuf()
            self.shared_content.append([parent + f, pixbuf, False])
    
    def shared_content_key_press(self, view, event):
        # This is Enter, fix me plx
        if event.keyval == 65293:
            self.add_selected_songs()
            return True
        return False
    
    def shared_content_clicked(self, widget, item):
        model = widget.get_model()
        # Is it a directory?
        if model[item][2]:
            # Check for ..
            directory = model[item][0]
            if directory.split('/')[-1] == '..':
                directory = '/'.join(directory.split('/')[:-2])
            if directory == '':
                data = self.core.api.list_shared_directories()
                data["files"] = ''
                directory = None
            else:
                data = self.core.api.list_directory(directory)
            self.show_shared_content(data["directories"], data["files"], directory)
        else:
            self.add_selected_songs()

    def add_selected_songs(self):
        selected = self.shared_content_view.get_selected_items()
        selected = filter(lambda i: not self.shared_content[i][2], selected)
        selected = map(lambda i: self.shared_content[i[0]][0], selected)
        dir_name = set(map(get_dir_name, selected))
        if len(dir_name) > 1:
            return False
        dir_name = dir_name.pop()
        file_names = map(get_file_name, selected)
        file_names.sort()
        self.shared_content_view.unselect_all()
        self.core.cmd_manager.add(Command(self.core.api.add_shared_songs, [ dir_name, file_names ]))
        self.core.cmd_manager.reload_state()


def get_file_name(path):
        return path.split('/')[-1]
    
def get_dir_name(path):
    return '/'.join(path.split('/')[:-1])

def retrieve_shared_name(column, cell, model, iter):
    pyobj = model.get_value(iter, 0)
    name = str(pyobj).split('/')[-1]
    if name.endswith('.mp3'):
        name = name[:-4]
    if len(name) > 60:
        name = name[:58] + '...'
    cell.set_property('text', name)
    return
