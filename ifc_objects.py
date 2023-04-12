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
        self.virgin_placement = True # this allows to set the initial placement without triggering any placement change

    def onBeforeChange(self, obj, prop):

        if prop == "Schema":
            self.old_schema = obj.Schema


    def onChanged(self, obj, prop):

        # link Type property to its hidder IfcType counterpart
        if prop == "IfcType" and hasattr(obj,"Type") and obj.Type != obj.IfcType:
            obj.Type = obj.IfcType
            self.rebuild_classlist(obj, setprops=True)
        elif prop == "Type" and hasattr(obj,"IfcType") and obj.Type != obj.IfcType:
            obj.IfcType = obj.Type
            self.rebuild_classlist(obj, setprops=True)

        # edit an IFC attribute
        if prop == "Schema":
            self.set_schema(obj, obj.Schema)
        elif obj.getGroupOfProperty(prop) == "IFC":
            if prop in ["StepId"]:
                pass
            else:
                self.edit_attribute(obj, prop, obj.getPropertyByName(prop))
        elif prop == "Label":
            self.edit_attribute(obj, "Name", obj.Label)

        # change placement
        if prop == "Placement":
            if getattr(self,"virgin_placement",False):
                self.virgin_placement = False
            else:
                # print("placement changed for",obj.Label,"to",obj.Placement)
                self.edit_placement(obj)


    def onDocumentRestored(self, obj):

        self.rebuild_classlist(obj)
        if hasattr(obj,"FilePath"):
            # once we have loaded the project, recalculate child coin nodes
            for child in obj.OutListRecursive:
                if child.ShapeMode == "Coin":
                    child.Proxy.cached = True
                    child.touch()


    def rebuild_classlist(self, obj, setprops=False):

        """rebuilds the list of Type property according to current class"""

        import ifc_tools # lazy import

        obj.Type = ifc_tools.get_ifc_classes(obj, obj.IfcType)
        obj.Type = obj.IfcType
        if setprops:
            ifc_tools.remove_unused_properties(obj)
            ifc_tools.add_properties(obj)


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


    def set_schema(self, obj, schema):

        """Changes the schema of an IFC document"""

        import ifc_tools # lazy import

        ifcfile = ifc_tools.get_ifcfile(obj)
        if not ifcfile:
            return
        if not getattr(self,"old_schema",None):
            return
        if schema != ifcfile.wrapped_data.schema_name():
            # set obj.Proxy.silent = True to disable the schema change warning
            if obj.ViewObject and not getattr(self,"silent",False):
                if not obj.ViewObject.Proxy.schema_warning():
                    return
            ifcfile, migration_table = ifc_tools.migrate_schema(ifcfile, schema)
            self.ifcfile = ifcfile
            obj.Modified = True
            for old_id,new_id in migration_table.items():
                child = [o for o in obj.OutListRecursive if getattr(o,"StepId",None) == old_id]
                if len(child) == 1:
                    child[0].StepId = new_id


    def edit_placement(self, obj):

        """Syncs the internal IFC placement"""

        import ifc_tools # lazy import

        result = ifc_tools.set_placement(obj)
        if result:
            proj = ifc_tools.get_project(obj)
            proj.Modified = True
