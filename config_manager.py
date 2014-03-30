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

import json
import os

class ConfigurationManager:
    def __init__(self, path=None):
        self.server_data = None
        self.loaded_file = None
    
    def default_path(self):
        return os.path.dirname(os.path.abspath(__file__)) + '/shaplim-gui.conf'
    
    def load_default_file(self):
        try:
            self.load_file(self.default_path())
            return True
        except Exception as ex:
            return False
    
    def serialize_configuration(self):
        data = {}
        if self.server_data:
            data["server"] = { 
                "address" : self.server_data[0], 
                "port" : self.server_data[1]
            }
        return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
    
    def save_configuration(self):
        path = self.loaded_file or self.default_path()
        fd = open(path, 'w')
        data = self.serialize_configuration()
        fd.write(data)
        fd.close()
    
    def parse_file(self, path):
        try:
            fd = open(path)
            contents = fd.read()
            fd.close()
            return json.loads(contents)
        except Exception as ex:
            raise Exception("Error loading configuration: " + str(ex))
    
    def load_file(self, path):
        json_data = self.parse_file(path)
        try:
            if 'server' in json_data:
                data = json_data['server']
                self.server_data = (data["address"], data["port"])
        except Exception as ex:
            raise Exception("Failed parsing configuration file")
        self.loaded_file = path
