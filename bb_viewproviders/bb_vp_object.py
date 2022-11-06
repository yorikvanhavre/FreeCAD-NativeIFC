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

class bb_vp_object:

    """Base class for all blenderbim view providers"""

    def attach(self, vobj):
        self.Object = vobj.Object

    def getDisplayModes(self, obj):
        return []

    def getDefaultDisplayMode(self):
        return "FlatLines"

    def setDisplayMode(self,mode):
        return mode

    def onChanged(self, vobj, prop):
        return

    def updateData(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def getIcon(self):
        return os.path.join(os.path.dirname(os.path.dirname(__file__)),"icons","IFC_object.svg")

    def claimChildren(self):

        #TODO refactor / use group extension

        children = []
        relprops = ["Item","ForLayerSet"] # properties that actually store parents
        for prop in self.Object.PropertiesList:
            if prop.startswith("Relating") or (prop in relprops):
                continue
            else:
                value = getattr(self.Object, prop)
                if hasattr(value, "ViewObject"):
                    children.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if hasattr(item, "ViewObject"):
                            children.append(item)
        for parent in self.Object.InList:
            for prop in parent.PropertiesList:
                if prop.startswith("Relating") or (prop in relprops):
                    value = getattr(parent, prop)
                    if value == self.Object:
                        children.append(parent)
        return children


    def setupContextMenu(self, vobj, menu):

        from PySide2 import QtCore, QtGui, QtWidgets # lazy import

        if self.hasChildren(vobj.Object):
            path = os.path.dirname(os.path.dirname(__file__))
            icon = QtGui.QIcon(os.path.join(path ,"icons", "IFC.svg"))
            action1 = QtWidgets.QAction(icon,"Reveal children", menu)
            action1.triggered.connect(self.revealChildren)
            menu.addAction(action1)


    def hasChildren(self, obj):
        
        """Returns True if this IFC object can be decomposed"""
        
        import bb_import # lazy import

        ifcfile = bb_import.get_ifcfile(obj)
        if ifcfile:
            return bool(bb_import.get_children(obj, ifcfile))
        return False


    def revealChildren(self):

        """Creates children of this object"""

        import bb_import # lazy import

        ifcfile = bb_import.get_ifcfile(self.Object)
        if ifcfile:
            bb_import.create_children(self.Object, ifcfile)

