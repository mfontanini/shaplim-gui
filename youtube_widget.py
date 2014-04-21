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
import Queue
import threading
import urllib2
import gobject
import re
import datetime
import httplib2
import errno
import os
from os.path import expanduser
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from apiclient.discovery import build
from command_manager import Command
from image_manager import ImageManager

class AsyncProcessor:
    def __init__(self):
        self.queue = Queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.start()
    
    def load_image(self, url, callback):
        self.queue.put(('load_image', url, callback))
    
    def api_call(self, search_args, callback):
        self.queue.put(('api_call', search_args, callback))
    
    def clear(self):
        with self.queue.mutex:
            self.queue.queue.clear()
    
    def call_function(self, function, callback):
        self.queue.put(('call_function', function, callback))
    
    def _do_load_image(self, data):
        loader = gtk.gdk.PixbufLoader("jpeg")
        loader.write(data)
        loader.close()
        return loader.get_pixbuf().scale_simple(120, 67, gtk.gdk.INTERP_BILINEAR)
    
    def stop(self):
        self.running = False
    
    def run_loop(self):
        while True:
            try:
                (job, args, callback) = self.queue.get(timeout=0.5)
                if job == 'load_image':
                    data = urllib2.urlopen(args).read()
                    gobject.idle_add(callback, self._do_load_image(data))
                elif job == 'api_call':
                    result = args.execute()
                    gobject.idle_add(callback, result)
                elif job == 'call_function':
                    result = args()
                    gobject.idle_add(callback, result)
                self.queue.task_done()
            except Queue.Empty as ex:
                if not self.running:
                    return

class YoutubeVideoWidget(gtk.VBox):
    def __init__(self, youtube_api_builder, core):
        gtk.VBox.__init__(self)
        self.core = core
        self.youtube_api_builder = youtube_api_builder
        self.async_processor = AsyncProcessor()
        
        self.content = gtk.ListStore(str, gtk.gdk.Pixbuf, str)
        self.content_view = gtk.IconView(self.content)
        self.content_view.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.content_view.set_text_column(0)
        self.content_view.set_pixbuf_column(1)
        self.content_view.set_item_width(160)
        self.content_view.set_size_request(550, 400)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.content_view)

        self.pack_start(self.make_search_box(), False, False)
        self.pack_start(self.scroll, True)
        self.pack_start(self.make_pages_box(), False, False)
        
        self.content_view.connect("item-activated", self.video_activated)
        self.api = None
        self.next_page_token = self.prev_page_token = None
        self.async_processor.call_function(self.youtube_api_builder, self.set_api)
    
    def set_api(self, api):
        self.api = api
    
    def make_search_input_box(self):
        box = gtk.HBox()
        self.search_input = gtk.Entry()
        self.search_button = gtk.Button("Search")
        self.search_button.connect('clicked', self.search)
        self.search_button.set_property("height-request", 45)
        
        box.pack_start(self.search_input, True)
        box.pack_start(self.search_button, False, False)
        box.set_size_request(0, 28)
        return box
    
    def make_upload_date_box(self):
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label("Upload Date"))
        self.upload_date = gtk.ListStore(str, gobject.TYPE_PYOBJECT)
        self.upload_date.append(['Today', time_today])
        self.upload_date.append(['This week', time_this_week])
        self.upload_date.append(['This month', time_this_month])
        self.upload_date.append(['All time', time_all_time])
        self.upload_date_combo = gtk.ComboBox(self.upload_date)
        cell = gtk.CellRendererText()
        self.upload_date_combo.pack_start(cell, True)
        self.upload_date_combo.add_attribute(cell, 'text', 0)
        self.upload_date_combo.set_active(3)
        vbox.pack_start(self.upload_date_combo)
        return vbox
    
    def make_duration_box(self):
        vbox = gtk.VBox()
        self.duration = gtk.ListStore(str, str)
        self.duration.append(['Any', 'any'])
        self.duration.append(['Long', 'long'])
        self.duration.append(['Medium', 'medium'])
        self.duration.append(['Short', 'short'])
        self.duration_combo = gtk.ComboBox(self.duration)
        cell = gtk.CellRendererText()
        self.duration_combo.pack_start(cell, True)
        self.duration_combo.add_attribute(cell, 'text', 0)
        self.duration_combo.set_active(0)
        vbox.pack_start(gtk.Label("Duration"))
        vbox.pack_start(self.duration_combo)
        return vbox
    
    def make_sort_by_box(self):
        vbox = gtk.VBox()
        self.sort_by = gtk.ListStore(str, str)
        self.sort_by.append(['Relevance', 'relevance'])
        self.sort_by.append(['Upload date', 'date'])
        self.sort_by.append(['View count', 'viewCount'])
        self.sort_by.append(['Rating', 'rating'])
        self.sort_by_combo = gtk.ComboBox(self.sort_by)
        cell = gtk.CellRendererText()
        self.sort_by_combo.pack_start(cell, True)
        self.sort_by_combo.add_attribute(cell, 'text', 0)
        self.sort_by_combo.set_active(0)
        vbox.pack_start(gtk.Label("Duration"))
        vbox.pack_start(self.sort_by_combo)
        return vbox
    
    def make_filters_box(self):
        expander = gtk.Expander("Filters")
        box = gtk.HBox()
        box.set_spacing(15)
        
        box.pack_start(self.make_upload_date_box(), False)
        box.pack_start(self.make_duration_box(), False)
        box.pack_start(self.make_sort_by_box(), False)
        
        align = gtk.Alignment(0.5)
        align.add(box)
        
        expander.add(align)
        return expander
    
    def make_pages_box1(self):
        box = gtk.HBox()
        box.set_spacing(40)
        prev_page = gtk.Button()
        next_page = gtk.Button()
        prev_page.set_image(self.core.image_manager.icons["back"])
        next_page.set_image(self.core.image_manager.icons["forward"])
        box.pack_start(prev_page, False, False)
        box.pack_start(next_page, False, False)
        for i in [prev_page, next_page]:
            i.set_property("height-request", 30)
        
        align = gtk.Alignment(0.5)
        align.add(box)
        return align
    
    def make_pages_box(self):
        toolbar = gtk.Toolbar()
        toolbar.append_item("", "Previous page","", self.core.image_manager.icons["back"], self.prev_page_button_clicked)
        toolbar.append_item("", "Next page","", self.core.image_manager.icons["forward"], self.next_page_button_clicked)
        
        align = gtk.Alignment(0.5)
        align.add(toolbar)
        return align
    
    def make_search_box(self):
        box = gtk.VBox()
        box.pack_start(self.make_search_input_box(), False)
        box.pack_start(self.make_filters_box())
        return box
    
    def process_image(self, treeiter, pixbuf):
        self.content.set(treeiter, 1, pixbuf)
    
    def process_video_info(self, data, id_to_iter):
        for i in data.get("items", []):
            duration = i['contentDetails']['duration']
            duration = parse_duration(duration)
            new_title = '[{0}] '.format(duration) + self.content.get(id_to_iter[i['id']], 0)[0]
            self.content.set(id_to_iter[i['id']], 0, new_title)
    
    def process_search(self, search_response):
        self.content_view.scroll_to_path((0, ), True, 0.5, 0.5)
        self.content.clear()
        
        # keep the first element, or just None
        self.next_page_token = search_response.get("nextPageToken", [])[0:] or None
        self.prev_page_token = search_response.get("prevPageToken", [])[0:] or None
        
        id_to_iter = {}
        id_to_url = []
        for search_result in search_response.get("items", []):
            treeiter = self.content.append([
                search_result["snippet"]["title"], 
                self.core.image_manager.icons["song"].get_pixbuf(),
                search_result["id"]["videoId"]
            ])
            id_to_iter[search_result["id"]["videoId"]] = treeiter
            id_to_url.append((search_result["id"]["videoId"], search_result["snippet"]["thumbnails"]["medium"]["url"]))
        video_list = self.api.videos().list(
            part='contentDetails',
            id=','.join(id_to_iter.keys())
        )
        self.async_processor.api_call(
            video_list,
            lambda i, id_to_iter=id_to_iter: self.process_video_info(i, id_to_iter)
        )
        for key in id_to_url:
            self.async_processor.load_image(
                key[1],
                lambda i, treeiter=id_to_iter[key[0]]: self.process_image(treeiter, i)
            )
        self.search_button.set_sensitive(True)
        self.search_input.set_sensitive(True)
    
    def build_query_params(self, page_token=None):
        sort_by = self.sort_by.get(self.sort_by.get_iter(self.sort_by_combo.get_active()), 1)
        upload_date = self.upload_date.get(self.upload_date.get_iter(self.upload_date_combo.get_active()), 1)
        # this one's a function
        upload_date = upload_date[0]()
        duration = self.duration.get(self.duration.get_iter(self.duration_combo.get_active()), 1)
        params = {
            'q' : self.search_input.get_text(),
            'order' : sort_by[0],
            'videoDuration' : duration[0],
            'publishedAfter' : upload_date
        }
        if page_token is not None:
            params['pageToken'] = page_token
        return params
    
    def do_search(self, page_token = None):
        self.query_params = self.build_query_params(page_token)
        video_search = self.api.search().list(
            part='id,snippet',
            type='video',
            maxResults=20,
            **self.query_params
        )
        self.async_processor.clear()
        self.async_processor.api_call(video_search, self.process_search)
    
    def prev_page_button_clicked(self, widget, event=None):
        if self.prev_page_token is not None:
            self.load_api_and_call(lambda: self.do_search(self.prev_page_token))
    
    def next_page_button_clicked(self, widget, event=None):
        if self.next_page_token is not None:
            self.load_api_and_call(lambda: self.do_search(self.next_page_token))
    
    def load_api_and_call(self, callback):
        if self.api is None:
            self.async_processor.call_function(
                self.youtube_api_builder, 
                lambda i: self.set_api(i), callback()
            )
        else:
            callback()
    
    def search(self, widget):
        self.search_button.set_sensitive(False)
        self.search_input.set_sensitive(False)
        self.load_api_and_call(self.do_search)
    
    def video_activated(self, widget, item):
        model = widget.get_model()
        identifier = model[item][2]
        params = [ identifier ]
        self.core.cmd_manager.add(Command(self.core.api.add_youtube_songs, [ params ]))
            

class YoutubeAuthenticationWidget(gtk.VBox):
    def __init__(self, callback):
        gtk.VBox.__init__(self)
        self.callback = callback
        self.async_processor = AsyncProcessor()
        align = gtk.Alignment(0.5, 0.5)
        box = gtk.VBox()
        self.flow = OAuth2WebServerFlow(
            client_id='948655016507-g452c5iqpriiinjm3vgnivd1l1l8ufqo.apps.googleusercontent.com',
            client_secret='_3LYacqjNE1SU962bfqO9j5s',
            scope='https://www.googleapis.com/auth/youtube.readonly',
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        text = 'Click <a href="{0}">this link</a> to connect <i>shaplim</i> with your <i>Google</i> account.'
        text = text.format(self.flow.step1_get_authorize_url().replace('&', '&amp;'))
        label = gtk.Label(text)
        label.set_use_markup(True)
        self.error_label = gtk.Label()
        self.code_text = gtk.Entry()
        self.connect_button = gtk.Button('Connect')
        self.connect_button.connect('clicked', self.connect)
        
        box.pack_start(label)
        box.pack_start(gtk.Label('Then paste the provided code below:'))
        
        hbox = gtk.HBox()
        hbox.pack_start(self.code_text)
        hbox.pack_start(self.connect_button, False, False)
        box.pack_start(hbox)
        box.pack_start(self.error_label)
        
        align.add(box)
        self.pack_start(align)
        self.code_text.grab_focus()
    
    def step2_exchange_proxy(self, code):
        try:
            return self.flow.step2_exchange(code)
        except:
            return None
    
    def connect_callback(self, data):
        if data:
            self.callback(data)
        else:
            self.connect_button.set_sensitive(True)
            self.error_label.set_text('<span color="red">Error authenticating. Please try again.</span>')
            self.error_label.set_use_markup(True)
            pass
    
    def connect(self, widget):
        code = self.code_text.get_text()
        self.connect_button.set_sensitive(False)
        self.error_label.set_text('')
        self.async_processor.call_function(
            lambda: self.step2_exchange_proxy(code),
            self.connect_callback
        )
    

class YoutubeWidget(gtk.VBox):
    def __init__(self, core):
        gtk.VBox.__init__(self)
        self.storage = self.create_oauth_storage()
        self.core = core
        credentials = self.storage.get()
        # we already have some credentials
        if credentials:
            self.add_youtube_video_widget(credentials)
        else:
            self.add_youtube_auth_widget()
        self.connect("destroy", self.destroy)
    
    def create_oauth_storage(self):
        dir_path = expanduser("~/.shaplim/")
        try:
            os.makedirs(dir_path)
        except OSError as ex: 
            if ex.errno != errno.EEXIST or not os.path.isdir(dir_path):
                raise
        return Storage(dir_path + 'youtube-oauth2.json')
    
    def add_youtube_auth_widget(self):
        self.youtube_widget = YoutubeAuthenticationWidget(self.oauth_complete)
        self.pack_start(self.youtube_widget)
        self.youtube_widget.show()
    
    
    def add_youtube_video_widget(self, credentials):
        youtube_api_builder = lambda: build(
            "youtube", 
            "v3",
            http=credentials.authorize(httplib2.Http())
        )
        self.youtube_widget = YoutubeVideoWidget(
            youtube_api_builder, 
            self.core
        )
        self.pack_start(self.youtube_widget)
        self.show_all()
    
    def oauth_complete(self, credentials):
        self.storage.put(credentials)
        self.youtube_widget.async_processor.stop()
        self.remove(self.youtube_widget)
        self.add_youtube_video_widget(credentials)
    
    def destroy(self, x):
        self.youtube_widget.async_processor.stop()

def time_today():
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat("T").split('.')[0] + 'Z'

def time_this_week():
    return (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat("T").split('.')[0] + 'Z'

def time_this_month():
    return (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat("T").split('.')[0] + 'Z'

def time_all_time():
    return '1970-01-01T00:00:00Z'

def parse_duration(duration):
    duration = duration.split('T')
    left = re.findall('(([\d]+)([WD]{1}))', duration[0])
    right = re.findall('(([\d]+)([HMS]{1}))', duration[1])
    multipliers = { 'W' : 24 * 7, 'D' : 24 }
    hours = 0
    minutes = 0
    seconds = 0
    for i in left:
        hours += multipliers[i[2]] * int(i[1])
    for i in right:
        if i[2] == 'H':
            hours += int(i[1])
        elif i[2] == 'M':
            minutes += int(i[1])
        elif i[2] == 'S':
            seconds += int(i[1])
    minutes += seconds / 60
    seconds = seconds % 60
    hours += minutes / 60
    minutes = minutes % 60
    if hours > 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)

class TestWindow(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.set_default_size(800, 600)
        self.connect("destroy", self.destroy)
        image_manager = ImageManager()
        self.youtube_widget = YoutubeWidget('shaplim-oauth2.json', image_manager)
        self.add(self.youtube_widget)
        self.show_all()
        
    def destroy(self, x):
        gtk.main_quit()

#gobject.threads_init()
#q = TestWindow()
#gtk.main()
