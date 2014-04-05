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
import copy
import Queue
import gobject

class Command:
    def __init__(self, function, params=None, requires_timestamp=False, callback=None):
        self.function = function
        self.params = params if params is not None else []
        self.requires_timestamp = requires_timestamp
        self.callback = callback

class CommandManager:
    def __init__(self, new_events_callback, api):
        self.queue = Queue.Queue()
        self.callback = new_events_callback
        self.api = api
        self.running = True
    
    def run(self, last_timestamp):
        self.last_timestamp = last_timestamp
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.start()
    
    def add(self, cmd):
        self.queue.put(cmd)
    
    def stop(self):
        self.running = False
        self.add(None)
        self.thread.join()
    
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
                    result = apply(cmd.function, params)
                    if cmd.callback:
                        gobject.idle_add(cmd.callback, result)
                self.queue.task_done()
            except Queue.Empty as ex:
                if not self.running:
                    return
                else:
                    self.get_new_events()
