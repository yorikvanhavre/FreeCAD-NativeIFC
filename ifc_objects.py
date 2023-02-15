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

class ifc_object:

    """Base class for all IFC-based objects"""

    def __init__(self):

        self.cached = True # this marks that the object is freshly created and its shape should be taken from cache

    def onChanged(self, obj, prop):

        # link Type property to its hidder IfcType counterpart
        if prop == "IfcType" and hasattr(obj,"Type") and obj.Type != obj.IfcType:
            obj.Type = obj.IfcType
            self.rebuild_classlist(obj)
        elif prop == "Type" and hasattr(obj,"IfcType") and obj.Type != obj.IfcType:
            obj.IfcType = obj.Type
            self.rebuild_classlist(obj)

        # edit an IFC attribute
        if obj.getGroupOfProperty(prop) == "IFC":
            if prop in ["StepId"]:
                pass
            else:
                self.edit_attribute(obj, prop, obj.getPropertyByName(prop))
        elif prop == "Label":
            self.edit_attribute(obj, "Name", obj.Label)


    def onDocumentRestored(self, obj):

        self.rebuild_classlist(obj)
        if hasattr(obj,"FilePath"):
            # once we have loaded the project, recalculate child coin nodes
            for child in obj.OutListRecursive:
                if not getattr(child,"HoldShape",True):
                    child.Proxy.cached = True
                    child.touch()
            obj.Document.recompute()


    def rebuild_classlist(self, obj):

        """rebuilds the list of Type property according to current class"""

        import ifc_tools # lazy import

        obj.Type = ifc_tools.get_ifc_classes(obj, obj.IfcType)
        obj.Type = obj.IfcType


    def __getstate__(self):

        return None


    def __setstate__(self, state):

        return None


    def execute (self, obj):

        import ifc_tools # lazy import

        cached = getattr(self,"cached",False)
        ifcfile = ifc_tools.get_ifcfile(obj)
        element = ifc_tools.get_ifc_element(obj)
        ifc_tools.set_geometry(obj, element, ifcfile, cached=cached)
        self.cached = False
        self.rebuild_classlist(obj)


    def edit_attribute(self, obj, attribute, value):

        """Edits an attribute of an underlying IFC object"""

        import ifc_tools # lazy import

        ifcfile = ifc_tools.get_ifcfile(obj)
        elt = ifc_tools.get_ifc_element(obj)
        if elt:
            result = ifc_tools.set_attribute(ifcfile, elt, attribute, value)
            if result:
                proj = ifc_tools.get_project(obj)
                proj.Modified = True
                if hasattr(result,"id") and (result.id() != obj.StepId):
                    obj.StepId = result.id()

