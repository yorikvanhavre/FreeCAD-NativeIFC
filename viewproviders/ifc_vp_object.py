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

class ifc_vp_object:

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

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


    def updateData(self, obj, prop):

        if prop == "Shape" and getattr(obj, "Group", None):
            colors = []
            for child in obj.Group:
                colors.extend(child.ViewObject.DiffuseColor)
            if colors:
                obj.ViewObject.DiffuseColor = colors


    def getIcon(self):

        path = os.path.dirname(os.path.dirname(__file__))
        if self.Object.HoldShape:
            i = "IFC_object.svg"
        else:
            i = "IFC_mesh.svg"
        return os.path.join(path,"icons",i)


    def setupContextMenu(self, vobj, menu):

        from PySide2 import QtCore, QtGui, QtWidgets # lazy import

        path = os.path.dirname(os.path.dirname(__file__))
        icon = QtGui.QIcon(os.path.join(path ,"icons", "IFC.svg"))
        if self.hasChildren(vobj.Object):
            action_expand = QtWidgets.QAction(icon,"Expand children", menu)
            action_expand.triggered.connect(self.expandChildren)
            menu.addAction(action_expand)
        if vobj.Object.HoldShape:
            t = "Remove shape"
        else:
            t = "Load shape"
        action_shape = QtWidgets.QAction(icon, t, menu)
        action_shape.triggered.connect(self.switchObject)
        menu.addAction(action_shape)


    def hasChildren(self, obj):

        """Returns True if this IFC object can be decomposed"""

        import ifc_tools # lazy import

        ifcfile = ifc_tools.get_ifcfile(obj)
        if ifcfile:
            return ifc_tools.can_expand(obj, ifcfile)
        return False


    def expandChildren(self):

        """Creates children of this object"""

        import ifc_tools # lazy import

        ifcfile = ifc_tools.get_ifcfile(self.Object)
        if ifcfile:
            ifc_tools.create_children(self.Object, ifcfile)
        self.Object.Document.recompute()


    def switchObject(self):

        """Switch this object between shape and coin"""

        self.Object.HoldShape = not self.Object.HoldShape
        self.Object.Document.recompute()
        self.Object.ViewObject.DiffuseColor = self.Object.ViewObject.DiffuseColor 
        self.Object.ViewObject.signalChangeIcon()



