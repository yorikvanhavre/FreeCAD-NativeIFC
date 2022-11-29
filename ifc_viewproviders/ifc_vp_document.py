#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2022 Yorik van Havre <yorik@uncreated.net>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU General Public License (GPL)            *
#*   as published by the Free Software Foundation; either version 3 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU General Public License for more details.                          *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

import os
from ifc_viewproviders import ifc_vp_object

class ifc_vp_document(ifc_vp_object.ifc_vp_object):

    """View provider for the IFC document object"""

    def getIcon(self):

        basepath = os.path.dirname(os.path.dirname(__file__))
        iconpath = os.path.join(basepath,"icons","IFC_document.svg")
        if self.Object.Modified:
            if not hasattr(self, "modicon"):

                from PySide import QtCore, QtGui # lazy load

                # build an overlay "warning" icon
                baseicon = QtGui.QImage(iconpath)
                overlay = QtGui.QImage(":/icons/media-record.svg")
                width = baseicon.width()/2
                overlay = overlay.scaled(width, width)
                painter = QtGui.QPainter()
                painter.begin(baseicon)
                painter.drawImage(0, 0, overlay)
                painter.end()
                ba = QtCore.QByteArray()
                b = QtCore.QBuffer(ba)
                b.open(QtCore.QIODevice.WriteOnly)
                baseicon.save(b,"XPM")
                self.modicon = ba.data().decode("latin1")
            return self.modicon
        else:
            return iconpath

    def setupContextMenu(self, vobj, menu):

        super().setupContextMenu(vobj, menu)

        from PySide2 import QtCore, QtGui, QtWidgets # lazy import

        if vobj.Object.Modified:
            path = os.path.dirname(os.path.dirname(__file__))
            icon = QtGui.QIcon(os.path.join(path ,"icons", "IFC.svg"))
            action1 = QtWidgets.QAction(icon,"Save IFC file", menu)
            action1.triggered.connect(self.save)
            menu.addAction(action1)

    def save(self):

        """Saves the associated IFC file"""

        import ifc_tools

        ifcfile = ifc_tools.get_ifcfile(self.Object)
        ifcfile.write(self.Object.FilePath)
        self.Object.Modified = False

