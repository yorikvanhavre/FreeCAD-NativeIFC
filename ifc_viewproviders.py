# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2022 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License (GPL)            *
# *   as published by the Free Software Foundation; either version 3 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import os


class ifc_vp_object:

    """Base class for all blenderbim view providers"""

    def attach(self, vobj):
        self.Object = vobj.Object

    def getDisplayModes(self, obj):
        return []

    def getDefaultDisplayMode(self):
        return "FlatLines"

    def setDisplayMode(self, mode):
        return mode

    def onChanged(self, vobj, prop):
        if prop == "Visibility":
            for child in vobj.Object.Group:
                child.ViewObject.Visibility = vobj.Visibility
            return True

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def updateData(self, obj, prop):
        if prop == "Shape" and getattr(obj, "Group", None):
            colors = []
            for child in obj.Group:
                if hasattr(child.ViewObject, "DiffuseColor"):
                    colors.extend(child.ViewObject.DiffuseColor)
            if colors:
                obj.ViewObject.DiffuseColor = colors

    def getIcon(self):
        path = os.path.dirname(os.path.dirname(__file__))
        if self.Object.ShapeMode == "Shape":
            i = "IFC_object.svg"
        else:
            i = "IFC_mesh.svg"
        return os.path.join(path, "icons", i)

    def claimChildren(self):
        if hasattr(self.Object, "Group"):
            return self.Object.Group
        return []

    def setupContextMenu(self, vobj, menu):
        import ifc_tools  # lazy import
        from PySide2 import QtCore, QtGui, QtWidgets  # lazy import

        path = os.path.dirname(os.path.dirname(__file__))
        icon = QtGui.QIcon(os.path.join(path, "icons", "IFC.svg"))
        if self.hasChildren(vobj.Object):
            action_expand = QtWidgets.QAction(icon, "Expand children", menu)
            action_expand.triggered.connect(self.expandChildren)
            menu.addAction(action_expand)
        if vobj.Object.Group:
            action_shrink = QtWidgets.QAction(icon, "Collapse children", menu)
            action_shrink.triggered.connect(self.collapseChildren)
            menu.addAction(action_shrink)
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
        element = ifc_tools.get_ifc_element(vobj.Object)
        if element and ifc_tools.has_representation(element):
            action_geom = QtWidgets.QAction(icon, "Add geometry properties", menu)
            action_geom.triggered.connect(self.addGeometryProperties)
            menu.addAction(action_geom)
        action_tree = QtWidgets.QAction(icon, "Show geometry tree", menu)
        action_tree.triggered.connect(self.showTree)
        menu.addAction(action_tree)
        if ifc_tools.has_psets(self.Object):
            action_props = QtWidgets.QAction(icon, "Expand property sets", menu)
            action_props.triggered.connect(self.showProps)
            menu.addAction(action_props)

    def hasChildren(self, obj):
        """Returns True if this IFC object can be decomposed"""

        import ifc_tools  # lazy import

        ifcfile = ifc_tools.get_ifcfile(obj)
        if ifcfile:
            return ifc_tools.can_expand(obj, ifcfile)
        return False

    def expandChildren(self, obj=None):
        """Creates children of this object"""

        import ifc_tools  # lazy import

        if not obj:
            obj = self.Object
        ifcfile = ifc_tools.get_ifcfile(obj)
        if ifcfile:
            ifc_tools.create_children(obj, ifcfile, recursive=False, assemblies=True)
        obj.Document.recompute()

    def collapseChildren(self):
        """Collapses the children of this object"""

        objs = self.Object.Group
        for o in objs:
            objs.extend(self.getOwnChildren(o))
        for o in objs:
            if hasattr(o, "Proxy"):
                # this prevents to trigger the deletion inside the IFC file
                o.Proxy.nodelete = True
        names = [o.Name for o in objs]
        for name in names:
            self.Object.Document.removeObject(name)
        self.Object.Document.recompute()

    def getOwnChildren(self, obj):
        """Recursively gets the children only used by this object"""
        children = []
        for child in obj.OutList:
            if len(child.InList) == 1 and child.InList[1] == obj:
                children.append(child)
                children.extend(self.getOwnChildren(child))
        return children

    def switchShape(self):
        """Switch this object between shape and coin"""

        if self.Object.ShapeMode == "Shape":
            self.Object.ShapeMode = "Coin"
            import Part  # lazy loading

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
            if getattr(child, "ShapeMode", 0) == 2:
                child.ShapeMode = 1
                changed.append(child.ViewObject)
        self.Object.Document.recompute()
        for vobj in changed:
            vobj.DiffuseColor = vobj.DiffuseColor

    def addGeometryProperties(self):
        """Adds geometry properties to this object"""

        import ifc_geometry  # lazy loading

        ifc_geometry.add_geom_properties(self.Object)

    def showTree(self):
        """Shows a dialog with a geometry tree for the object"""

        import ifc_tools  # lazy loading
        import ifc_tree  # lazy loading

        element = ifc_tools.get_ifc_element(self.Object)
        if element:
            ifc_tree.show_geometry_tree(element)

    def showProps(self):
        """Expands property sets"""

        import ifc_tools  # lazy loading

        ifc_tools.show_psets(self.Object)
        self.Object.Document.recompute()

    def canDragObjects(self):
        """Whether children can be removed by d&d"""

        return True

    def canDropObjects(self):
        """Whether objects can be added here by d&d or drop only"""

        return True

    def canDragObject(self, dragged_object):
        """Whether the given object can be removed by d&d"""

        return True

    def canDropObject(self, incoming_object):
        """Whether the object can be dropped here by d&d or drop only"""

        return True  # in principle, any object can be dropped and become IFC

    def dragObject(self, vobj, dragged_object):
        """Remove a child from the view provider by d&d"""

        import ifc_tools  # lazy import

        parent = vobj.Object
        ifc_tools.deaggregate(dragged_object, parent)

    def dropObject(self, vobj, incoming_object):
        """Add an object to the view provider by d&d"""

        import ifc_tools  # lazy import

        parent = vobj.Object
        ifc_tools.aggregate(incoming_object, parent)
        if self.hasChildren(parent):
            self.expandChildren(parent)
        proj = ifc_tools.get_project(parent)
        proj.Modified = True


class ifc_vp_document(ifc_vp_object):

    """View provider for the IFC document object"""

    def getIcon(self):
        basepath = os.path.dirname(os.path.dirname(__file__))
        iconpath = os.path.join(basepath, "icons", "IFC_document.svg")
        if self.Object.Modified:
            if not hasattr(self, "modicon"):
                from PySide import QtCore, QtGui  # lazy load

                # build an overlay "warning" icon
                baseicon = QtGui.QImage(iconpath)
                overlay = QtGui.QImage(":/icons/media-record.svg")
                width = baseicon.width() / 2
                overlay = overlay.scaled(width, width)
                painter = QtGui.QPainter()
                painter.begin(baseicon)
                painter.drawImage(0, 0, overlay)
                painter.end()
                ba = QtCore.QByteArray()
                b = QtCore.QBuffer(ba)
                b.open(QtCore.QIODevice.WriteOnly)
                baseicon.save(b, "XPM")
                self.modicon = ba.data().decode("latin1")
            return self.modicon
        else:
            return iconpath

    def setupContextMenu(self, vobj, menu):
        super().setupContextMenu(vobj, menu)

        from PySide2 import QtCore, QtGui, QtWidgets  # lazy import

        path = os.path.dirname(os.path.dirname(__file__))
        icon = QtGui.QIcon(os.path.join(path, "icons", "IFC.svg"))
        if vobj.Object.Modified:
            if vobj.Object.FilePath:
                action_diff = QtWidgets.QAction(icon, "View diff...", menu)
                action_diff.triggered.connect(self.diff)
                menu.addAction(action_diff)
                action_save = QtWidgets.QAction(icon, "Save IFC file", menu)
                action_save.triggered.connect(self.save)
                menu.addAction(action_save)
        action_saveas = QtWidgets.QAction(icon, "Save IFC file as...", menu)
        action_saveas.triggered.connect(self.saveas)
        menu.addAction(action_saveas)

    def save(self):
        """Saves the associated IFC file"""

        import ifc_tools  # lazy import

        ifc_tools.save_ifc(self.Object)
        self.Object.Modified = False

    def saveas(self):
        """Saves the associated IFC file to another file"""

        import ifc_tools  # lazy import
        from PySide2 import QtCore, QtGui, QtWidgets  # lazy import

        sf = QtWidgets.QFileDialog.getSaveFileName(
            None,
            "Save an IFC file",
            self.Object.FilePath,
            "Industry Foundation Classes (*.ifc)",
        )
        if sf and sf[0]:
            sf = sf[0]
            if not sf.lower().endswith(".ifc"):
                sf += ".ifc"
            ifc_tools.save_ifc(self.Object, sf)
            self.replace_file(self.Object, sf)

    def replace_file(self, obj, newfile):
        """Asks the user if the attached file path needs to be replaced"""

        from PySide2 import QtCore, QtGui, QtWidgets  # lazy import

        msg = "Replace the stored IFC file path in object "
        msg += self.Object.Label + " with the new one: "
        msg += newfile
        msg += " ?"
        dlg = QtWidgets.QMessageBox.question(
            None,
            "Replace IFC file path?",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if dlg == QtWidgets.QMessageBox.Yes:
            self.Object.FilePath = newfile
            self.Object.Modified = False
            return True
        else:
            return False

    def schema_warning(self):
        from PySide2 import QtCore, QtGui, QtWidgets  # lazy import

        msg = "Warning: This operation will change the whole IFC file contents "
        msg += "and will not give versionable results. It is best to not do "
        msg += "this while you are in the middle of a project. "
        msg += "Do you wish to continue anyway?"
        dlg = QtWidgets.QMessageBox.question(
            None,
            "Replace IFC file schema?",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if dlg == QtWidgets.QMessageBox.Yes:
            return True
        else:
            return False

    def diff(self):
        import ifc_diff

        diff = ifc_diff.get_diff(self.Object)
        ifc_diff.show_diff(diff)


class ifc_vp_group:

    """View provider for the IFC group object"""

    def getIcon(self):
        path = os.path.dirname(os.path.dirname(__file__))
        icom = "IFC_group.svg"
        return os.path.join(path, "icons", icom)
