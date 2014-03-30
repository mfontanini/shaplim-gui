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

class ImageManager:
    def __init__(self):
        self.icons = {
            "shuffle" : self.make_image("images/shuffle.png"),
            "play" : self.make_image("images/play.png"),
            "previous" : self.make_image("images/previous.png"),
            "next" : self.make_image("images/next.png"),
            "pause" : self.make_image("images/pause.png"),
            "no_logo" : self.make_image_from_pixbuf("images/no-logo.png", (120, 120))
        }
    
    def make_image(self, path):
        image = gtk.Image()
        image.set_from_file(path)
        return image

    def make_image_from_pixbuf(self, path, scale=None):
        pixbuf = gtk.gdk.pixbuf_new_from_file("images/no-logo.png")
        if scale:
            pixbuf = pixbuf.scale_simple(scale[0], scale[1], gtk.gdk.INTERP_BILINEAR)
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        return image
