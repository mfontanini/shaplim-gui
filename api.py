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

import socket
import json
import os
import threading

class API:
    def __init__(self, host, port):
        self.__lock = threading.Lock()
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((host, port))    

    def __send_command(self, command_type, params=None):
        data = { 'type' : command_type }
        if params:
            data['params'] = params
        data = json.dumps(data)
        #print data
        with self.__lock:
            self.__socket.sendall(data + '\n')
            fd = self.__socket.makefile()
            line = fd.readline()
        #print line
        return json.loads(line)
    
    def pause(self):
        return self.__send_command('pause')
    
    def play(self):
        return self.__send_command('play')
    
    def next_song(self):
        return self.__send_command('next_song')
    
    def previous_song(self):
        return self.__send_command('previous_song')
    
    def playlist_mode(self):
        return self.__send_command('playlist_mode')
    
    def set_playlist_mode(self, mode):
        if len(mode) != 1 or mode[0] not in ['shuffle', 'default']:
            raise Exception('Invalid mode')
        return self.__send_command('set_playlist_mode', mode[0])

    def clear_playlist(self):
        return self.__send_command('clear_playlist')

    def show_playlist(self):
        return self.__send_command('show_playlist')
    
    def list_shared_directories(self):
        return self.__send_command('list_shared_dirs')
    
    def list_directory(self, directory):
        return self.__send_command('list_directory', directory)
    
    def new_events(self, timestamp):
        return self.__send_command('new_events', int(timestamp))
    
    def player_status(self):
        return self.__send_command('player_status')
    
    def delete_songs(self, indexes, timestamp):
        json_params = { 'timestamp' : int(timestamp), 'indexes' : indexes }
        return self.__send_command('delete_songs', json_params)
    
    def set_current_song(self, index, timestamp):
        json_params = { 'timestamp' : int(timestamp), 'index' : int(index) }
        return self.__send_command('set_current_song', json_params)
    
    def song_info(self, path):
        return self.__send_command('song_info', path)
    
    def add_shared_songs(self, base_path, songs):
        json_params = { 'base_path' : base_path, 'songs' : songs }
        return self.__send_command('add_shared_songs', json_params)
