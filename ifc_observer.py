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

"""Document observer for documents containing NativeIFC objects"""

import os
import FreeCAD
import FreeCADGui


def add_observer():

    """Adds an observer to the running FreeCAD instance"""

    observer = ifc_observer()
    FreeCAD.addDocumentObserver(observer)


class ifc_observer:

    """A general document observer that handles IFC objects"""


    def slotStartSaveDocument(self, doc, value):

        """Save all IFC documents in this doc"""

        from PySide2 import QtCore # lazy loading
        self.docname = doc.Name
        # delay execution to not get caught under the wait sursor
        # that occurs when the saveAs file dialog is shown
        # TODO find a more solid way
        QtCore.QTimer.singleShot(100, self.save)


    def save(self):

        if not hasattr(self, "docname"):
            return
        if not self.docname in FreeCAD.listDocuments():
            return
        doc = FreeCAD.getDocument(self.docname)
        objs = []
        for obj in doc.findObjects(Type="Part::FeaturePython"):
            if hasattr(obj,"FilePath") and hasattr(obj,"Modified"):
                if obj.Modified:
                    objs.append(obj)
        if objs:

            import ifc_tools # lazy loading

            ppath = "User parameter:BaseApp/Preferences/Mod/NativeIFC"
            params = FreeCAD.ParamGet(ppath)
            ask = params.GetBool("AskBeforeSaving",True)
            if ask:
                moddir = os.path.dirname(__file__)
                uifile = os.path.join(moddir,"ui","dialogExport.ui")
                dlg = FreeCADGui.PySideUic.loadUi(uifile)
                result = dlg.exec_()
                if not result:
                    return
                ask = dlg.checkAskBeforeSaving.isChecked()
                params.SetBool("AskBeforeSaving",ask)

            for obj in objs:
                if obj.FilePath and getattr(obj.Proxy,"ifcfile",None):
                    obj.ViewObject.Proxy.save()
                else:
                    obj.ViewObject.Proxy.save_as()
