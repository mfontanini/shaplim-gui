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
import time
from command_manager import Command
from youtube_widget import YoutubeWidget

class SharedMediaPanelWidget(gtk.IconView):
    def __init__(self, core, parent):
        self.core = core
        self.tabs = parent
        self.shared_content = gtk.ListStore(str, gtk.gdk.Pixbuf, bool)
        gtk.IconView.__init__(self, self.shared_content)
        self.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.set_text_column(0)
        self.set_pixbuf_column(1)
        self.set_item_width(120)
        self.connect('key-press-event', self.shared_content_key_press)
        self.set_size_request(550, self.get_size_request()[1])
        
        cell = self.get_cells()[0]
        self.set_cell_data_func(cell, retrieve_shared_name)
        
        self.connect("item-activated", self.shared_content_activated)
        self.connect("button-release-event", self.button_released)
        
        self.current_strings = []
        self.press_timestamp = 0
        self.current_string = ''
        self.current_items = []
        self.current_directory = ''
        self.control_held = False
    
    def select_cell(self, path):
        self.select_path((path, ))
        self.set_cursor((path, ))
    
    def save_press_timestamp(self):
        self.press_timestamp = time.time()
    
    def press_timestamp_valid(self):
        return time.time() - self.press_timestamp < 2
    
    def button_released(self, widget, event):
        self.control_held = (event.get_state() &  gtk.gdk.CONTROL_MASK)
    
    def show_shared_content(self, dirs, files, parent=''):
        self.current_directory = parent
        self.current_items = []
        self.shared_content.clear()
        if parent != '':
            pixbuf = self.core.image_manager.icons["folder"].get_pixbuf()
            self.shared_content.append([parent + "/..", pixbuf, True])
            parent = parent + '/'
        else:
            parent = ''
        for directory in dirs:
            pixbuf = self.core.image_manager.icons["folder"].get_pixbuf()
            self.shared_content.append([parent + directory, pixbuf, True])
            self.current_items.append(directory.lower())
        for f in files:
            pixbuf = self.core.image_manager.icons["song"].get_pixbuf()
            self.shared_content.append([parent + f, pixbuf, False])
            self.current_items.append(f.lower())
    
    def shared_content_key_press(self, view, event):
        trigger_keys = [ 
            gtk.gdk.keyval_from_name("Return"),
            gtk.gdk.keyval_from_name("KP_Enter")
        ]
        self.control_held = event.get_state() &  gtk.gdk.CONTROL_MASK
        if event.keyval in trigger_keys:
            selected = self.get_selected_items()
            if any(selected):
                directory = self.current_directory
                self.shared_content_activated(self, selected[0])
                self.current_string = ''
                if not self.control_held and directory != self.current_directory:
                    self.select_cell(0)
            return True
        elif event.keyval == gtk.gdk.keyval_from_name("w") and self.control_held:
            self.tabs.destroy_current_tab()
            return True
        elif event.keyval == gtk.gdk.keyval_from_name("Page_Up") and self.control_held:
            self.tabs.prev_page()
            return True
        elif event.keyval == gtk.gdk.keyval_from_name("Page_Down") and self.control_held:
            self.tabs.next_page()
            return True
        elif event.keyval == gtk.gdk.keyval_from_name("c") and self.control_held:
            self.current_string = ''
            return True
        elif event.string == 'a' and self.control_held:
            self.select_all()
            return True
        if event.string != '':
            if not self.press_timestamp_valid():
                self.current_string = ''
            self.save_press_timestamp()
            self.current_string += event.string.lower()
            best_result = self.find_largest_item_match(self.current_string)
            if best_result is not None:
                # If we're not in the root, there's a '..'
                if self.current_directory != '':
                    best_result += 1
                self.unselect_all()
                self.select_cell(best_result)
                self.scroll_to_path((best_result, ), True, 0.5, 0.5)
            return True
        elif event.keyval == gtk.gdk.keyval_from_name("BackSpace"):
            if self.current_directory != '':
                self.load_directory(get_dir_name(self.current_directory))
                self.select_cell(0)
                return True
        return False
    
    def shared_content_activated(self, widget, item):
        model = widget.get_model()
        # Is it a directory?
        if model[item][2]:
            # Check for ..
            directory = model[item][0]
            if directory.split('/')[-1] == '..':
                directory = '/'.join(directory.split('/')[:-2])
                
            if self.control_held:
                self.tabs.add_tab(directory, True)
            else:
                self.load_directory(directory)
        else:
            self.add_selected_songs()

    def add_selected_songs(self):
        selected = self.get_selected_items()
        selected = filter(lambda i: not self.shared_content[i][2], selected)
        selected = map(lambda i: self.shared_content[i[0]][0], selected)
        dir_name = set(map(get_dir_name, selected))
        if len(dir_name) > 1:
            return False
        dir_name = dir_name.pop() if len(dir_name) == 1 else ''
        file_names = map(get_file_name, selected)
        file_names.sort()
        self.unselect_all()
        self.core.cmd_manager.add(Command(self.core.api.add_shared_songs, [ dir_name, file_names ]))
        self.core.cmd_manager.reload_state()

    def load_directory(self, directory):
        data = self.core.api.list_directory(directory)
        self.current_string = ''
        self.show_shared_content(data["directories"], data["files"], directory)
        self.tabs.directory_changed(self, directory)

    def find_largest_item_match(self, searched):
        for i in range(len(self.current_items)):
            if self.current_items[i].startswith(searched):
                return i
        return None
                
                

class SharedMediaWidget(gtk.Notebook):
    def __init__(self, core):
        gtk.Notebook.__init__(self)
        self.set_tab_pos(gtk.POS_TOP)
        self.youtube_widget = YoutubeWidget(core)
        self.append_page(self.youtube_widget, gtk.Label("Youtube"))
        self.core = core
    
    def make_shared_content_view(self):
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        widget = SharedMediaPanelWidget(self.core, self)
        scroll.add(widget)
        return scroll
    
    def make_label(self, widget, contents=''):
        tab = gtk.HBox()
        label = gtk.Label(contents)
        self.labels[widget.get_child()] = label
        
        button = gtk.Button()
        close_image = gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        image_w, image_h = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
        button.set_relief(gtk.RELIEF_NONE)
        button.set_focus_on_click(False)
        button.set_image(close_image)
        style = gtk.RcStyle()
        style.xthickness = 0
        style.ythickness = 0
        button.modify_style(style)
        button.connect('clicked', self.destroy_tab, widget)
        
        tab.pack_start(label, True)
        tab.pack_start(button, False, False)
        tab.show_all()
        return tab
    
    def reset(self):
        self.labels = {}
        widget = self.add_tab('')
        self.labels[widget.get_child()].set_text('Home')
    
    def add_tab(self, directory, select_first=False):
        widget = self.make_shared_content_view()
        tab_label = self.make_label(widget, get_file_name(directory) or 'Home')
        
        widget.show()
        if len(self.get_children()) == 1:
            self.insert_page(widget, tab_label, 0)
            self.set_current_page(0)
        else:
            self.append_page(widget, tab_label)
            self.set_current_page(-1)
        widget.get_child().load_directory(directory)
        self.set_show_tabs(True)
        self.show_all()
        self.set_tab_reorderable(widget, True)
        widget.get_child().grab_focus()
        if select_first:
            widget.get_child().select_cell(0)
        return widget
    
    def directory_changed(self, widget, directory):
        if directory == '':
            directory = 'Home'
        self.labels[widget].set_text(get_file_name(directory))
    
    def destroy_tab(self, sender, widget):
        if len(self.get_children()) > 1:
            page = self.page_num(widget)
            self.remove_page(page)
            del self.labels[widget.get_child()]
            if len(self.get_children()) == 1:
                self.set_show_tabs(False)

    def destroy_current_tab(self):
        page = self.get_current_page()
        self.destroy_tab(None, self.get_nth_page(page))

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
