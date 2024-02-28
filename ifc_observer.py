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

"""Document observer to act on documents containing NativeIFC objects"""


import os
import FreeCAD

params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/NativeIFC")


def add_observer():
    """Adds an observer to the running FreeCAD instance"""

    observer = ifc_observer()
    FreeCAD.addDocumentObserver(observer)


class ifc_observer:
    """A general document observer that handles IFC objects"""

    # slots

    def slotStartSaveDocument(self, doc, value):
        """Save all IFC documents in this doc"""

        from PySide2 import QtCore  # lazy loading

        self.docname = doc.Name
        # delay execution to not get caught under the wait sursor
        # that occurs when the saveAs file dialog is shown
        # TODO find a more solid way
        QtCore.QTimer.singleShot(100, self.save)

    def slotDeletedObject(self, obj):
        """Deletes the corresponding object in the IFC document"""

        import ifc_tools  # lazy loading

        proj = ifc_tools.get_project(obj)
        if not proj:
            return
        if not hasattr(obj, "Proxy"):
            return
        if getattr(obj.Proxy, "nodelete", False):
            return
        ifc_tools.remove_ifc_element(obj)

    def slotChangedDocument(self, doc, prop):
        """Watch document IFC properties"""

        if prop == "Schema" and "IfcFilePath" in doc.PropertiesList:
            import ifc_tools  # lazy import

            schema = doc.Schema
            ifcfile = ifc_tools.get_ifcfile(doc)
            if ifcfile:
                if schema != ifcfile.wrapped_data.schema_name():
                    # TODO display warming
                    ifcfile, migration_table = ifc_tools.migrate_schema(ifcfile, schema)
                    doc.Proxy.ifcfile = ifcfile
                    # migrate children
                    for old_id, new_id in migration_table.items():
                        child = [
                            o
                            for o in doc.Objects
                            if getattr(o, "StepId", None) == old_id
                        ]
                        if len(child) == 1:
                            child[0].StepId = new_id

    def slotCreatedObject(self, obj):
        """If this is an IFC document, turn the object into IFC"""

        doc = getattr(obj, "Document", None)
        if doc:
            if hasattr(doc, "IfcFilePath"):
                from PySide2 import QtCore  # lazy loading

                self.objname = obj.Name
                self.docname = obj.Document.Name
                # delaying to make sure all other properties are set
                QtCore.QTimer.singleShot(100, self.convert)

    def slotActivateDocument(self, doc):
        """Check if we need to display a ghost"""

        from PySide2 import QtCore  # lazy loading

        if hasattr(doc, "Proxy"):
            if hasattr(doc.Proxy, "ifcfile"):
                # this runs when loading a file
                if getattr(doc, "Objects", ""):
                    for obj in doc.Objects:
                        if getattr(obj, "ShapeMode", None) == "Coin":
                            obj.Proxy.cached = True
                            QtCore.QTimer.singleShot(100, obj.touch)
                    QtCore.QTimer.singleShot(100, doc.recompute)
                    QtCore.QTimer.singleShot(100, self.fit_all)
                else:
                    if not hasattr(doc.Proxy, "ghost"):
                        import ifc_generator

                        ifc_generator.create_ghost(doc)
        else:
            # this is a new file, wait a bit to make sure all components are populated
            QtCore.QTimer.singleShot(1000, self.propose_conversion)

    # implementation methods

    def fit_all(self):
        """Fits the view"""

        if FreeCAD.GuiUp:
            import FreeCADGui

            FreeCADGui.SendMsgToActiveView("ViewFit")

    def save(self):
        """Saves all IFC documents contained in self.docname Document"""

        if not hasattr(self, "docname"):
            return
        if self.docname not in FreeCAD.listDocuments():
            return
        doc = FreeCAD.getDocument(self.docname)
        del self.docname
        objs = []
        if hasattr(doc, "IfcFilePath") and hasattr(doc, "Modified"):
            if doc.Modified:
                objs.append(doc)
        else:
            for obj in doc.findObjects(Type="Part::FeaturePython"):
                if hasattr(obj, "IfcFilePath") and hasattr(obj, "Modified"):
                    if obj.Modified:
                        objs.append(obj)
        if objs:
            import ifc_tools  # lazy loading

            ask = params.GetBool("AskBeforeSaving", True)
            if ask and FreeCAD.GuiUp:
                import FreeCADGui

                moddir = os.path.dirname(__file__)
                uifile = os.path.join(moddir, "ui", "dialogExport.ui")
                dlg = FreeCADGui.PySideUic.loadUi(uifile)
                result = dlg.exec_()
                if not result:
                    return
                ask = dlg.checkAskBeforeSaving.isChecked()
                params.SetBool("AskBeforeSaving", ask)

            for obj in objs:
                if obj.IfcFilePath and getattr(obj.Proxy, "ifcfile", None):
                    obj.ViewObject.Proxy.save()
                else:
                    obj.ViewObject.Proxy.save_as()

    def convert(self):
        """Converts an object to IFC"""

        if not hasattr(self, "objname") or not hasattr(self, "docname"):
            return
        if self.docname not in FreeCAD.listDocuments():
            return
        doc = FreeCAD.getDocument(self.docname)
        if not doc:
            return
        obj = doc.getObject(self.objname)
        if not obj:
            return
        if "StepId" in obj.PropertiesList:
            return
        del self.docname
        del self.objname
        if obj.isDerivedFrom("Part::Feature"):
            if "IfcType" in obj.PropertiesList:
                print("Converting", obj.Label, "to IFC")
                import ifc_tools  # lazy loading
                import ifc_geometry  # lazy loading

                newobj = ifc_tools.aggregate(obj, doc)
                ifc_geometry.add_geom_properties(newobj)
                doc.recompute()

    def propose_conversion(self):
        """Propose a conversion of the current document"""

        doc = FreeCAD.ActiveDocument
        if not getattr(FreeCAD, "IsOpeningIFC", False):
            if not hasattr(doc, "Proxy"):
                if not getattr(doc, "Objects", True):
                    if not doc.FileName:
                        if not hasattr(doc, "IfcFilePath"):
                            # this is really a new, empty document
                            import FreeCADGui
                            from PySide import QtCore, QtGui  # lazy loading

                            if FreeCADGui.activeWorkbench().name() != "BIMWorkbench":
                                return
                            if not params.GetBool("SingleDocAskAgain", True):
                                if params.GetBool("SingleDoc", True):
                                    self.full = params.GetBool("ProjectFull", False)
                                    QtCore.QTimer.singleShot(
                                        1000, self.convert_document
                                    )
                                    return
                                else:
                                    return
                            d = os.path.dirname(__file__)
                            dlg = FreeCADGui.PySideUic.loadUi(
                                os.path.join(d, "ui", "dialogConvertDocument.ui")
                            )
                            dlg.checkStructure.setChecked(
                                params.GetBool("ProjectFull", False)
                            )
                            result = dlg.exec_()
                            self.full = dlg.checkStructure.isChecked()
                            params.SetBool(
                                "SingleDocAskAgain", not dlg.checkAskAgain.isChecked()
                            )
                            if result:
                                params.SetBool("SingleDoc", True)
                                params.SetBool("ProjectFull", self.full)
                                QtCore.QTimer.singleShot(1000, self.convert_document)
                            else:
                                params.SetBool("SingleDoc", False)

    def convert_document(self):
        """Converts the active document"""

        import ifc_tools  # lazy loading

        doc = FreeCAD.ActiveDocument
        ifc_tools.convert_document(doc, strategy=2, silent=True)
        if self.full:
            import Arch

            site = ifc_tools.aggregate(Arch.makeSite(), doc)
            building = ifc_tools.aggregate(Arch.makeBuilding(), site)
            storey = ifc_tools.aggregate(Arch.makeFloor(), building)
            doc.recompute()
