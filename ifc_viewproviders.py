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
        if self.Object.ShapeMode == "Shape":
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
        if vobj.Object.ShapeMode == "Shape":
            t = "Remove shape"
        else:
            t = "Load shape"
        action_shape = QtWidgets.QAction(icon, t, menu)
        action_shape.triggered.connect(self.switchShape)
        menu.addAction(action_shape)
        if vobj.Object.ShapeMode == "None":
            action_coin = QtWidgets.QAction(icon, "Load representation", menu)
            action_coin.triggered.connect(self.switchCoin)
            menu.addAction(action_coin)


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


    def switchShape(self):

        """Switch this object between shape and coin"""

        if self.Object.ShapeMode == "Shape":
            self.Object.ShapeMode = "Coin"
            import Part # lazy loading
            self.Object.Shape = Part.Shape()
        elif self.Object.ShapeMode == "Coin":
            self.Object.ShapeMode = "Shape"
        self.Object.Document.recompute()
        self.Object.ViewObject.DiffuseColor = self.Object.ViewObject.DiffuseColor
        self.Object.ViewObject.signalChangeIcon()


    def switchCoin(self):

        """Switch this object between coin and no representation"""

        changed = []
        if self.Object.ShapeMode == "None":
            self.Object.ShapeMode = "Coin"
            changed.append(self.Object.ViewObject)
        # reveal children
        for child in self.Object.OutListRecursive:
            if getattr(child,"ShapeMode",0) == 2:
                child.ShapeMode = 1
                changed.append(child.ViewObject)
        self.Object.Document.recompute()
        for vobj in changed:
            vobj.DiffuseColor = vobj.DiffuseColor



class ifc_vp_document(ifc_vp_object):

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

        path = os.path.dirname(os.path.dirname(__file__))
        icon = QtGui.QIcon(os.path.join(path ,"icons", "IFC.svg"))
        if vobj.Object.Modified:
            if vobj.Object.FilePath:
                action_save = QtWidgets.QAction(icon,"Save IFC file", menu)
                action_save.triggered.connect(self.save)
                menu.addAction(action_save)
        action_saveas = QtWidgets.QAction(icon,"Save IFC file as...", menu)
        action_saveas.triggered.connect(self.saveas)
        menu.addAction(action_saveas)


    def save(self):

        """Saves the associated IFC file"""

        import ifc_tools # lazy import

        ifc_tools.save_ifc(self.Object)
        self.Object.Modified = False


    def saveas(self):

        """Saves the associated IFC file to another file"""

        import ifc_tools # lazy import
        from PySide2 import QtCore, QtGui, QtWidgets # lazy import

        sf = QtWidgets.QFileDialog.getSaveFileName(None,
                                               "Save an IFC file",
                                               self.Object.FilePath,
                                               "Industry Foundation Classes (*.ifc)",)
        if sf and sf[0]:
            ifc_tools.save_ifc(self.Object, sf[0])
            msg = "Replace the stored IFC file path in object "
            msg += self.Object.Label + " with the one you just saved?"
            dlg = QtWidgets.QMessageBox.question(None,
                                               "Replace IFC file path?",
                                               msg,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
            if dlg == QtWidgets.QMessageBox.Yes:
                self.Object.FilePath = sf[0]
                self.Object.Modified = False

