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
            if prop in ["IfcType","StepId"]:
                pass
            else:
                self.edit_attribute(obj, prop, obj.getPropertyByName(prop))
        elif prop == "Label":
            self.edit_attribute(obj, "Name", obj.Label)


    def onDocumentRestored(self, obj):

        self.rebuild_classlist(obj)

    def rebuild_classlist(self, obj):

        """rebuilds the list of Type property according to current class"""

        import ifc_tools # lazy import

        ifcclass = obj.IfcType
        ifcfile = ifc_tools.get_ifcfile(obj)
        schema = ifcfile.wrapped_data.schema_name()
        obj.Type = ifc_tools.get_ifc_classes(ifcclass, schema)
        obj.Type = ifcclass

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def execute (self, obj):

        import Part # lazy import

        shapes = [child.Shape for child in obj.Group if child.isDerivedFrom("Part::Feature")]
        siteshape = getattr(obj,"SiteShape",None)
        if shapes:
            if isinstance(siteshape,Part.Shape) and not siteshape.isNull():
                obj.Shape = siteshape
            elif obj.HoldShape:
                obj.Shape = Part.makeCompound(shapes)
            else:
                # workaround for group extension bug: add a dummy placeholder shape)
                obj.Shape = Part.makeBox(1,1,1)
        else:
            import Mesh
            meshes = [child.Mesh for child in obj.Group if child.isDerivedFrom("Mesh::Feature")]
            if meshes:
                if isinstance(siteshape,Mesh.Mesh):
                    obj.Mesh = siteshape
                else:
                    mesh = Mesh.Mesh()
                    for m in meshes:
                        mesh.addMesh(m)
                    obj.Mesh = mesh

    def get_ifc_element(self, obj):

        """Returns the corresponding IFC element of this object"""

        import ifc_tools # lazy import

        ifc_file = ifc_tools.get_ifcfile(obj)
        if ifc_file and hasattr(obj, "StepId"):
            return ifc_file.by_id(obj.StepId)
        return None

    def edit_attribute(self, obj, attribute, value):

        """Edits an attribute of an underlying IFC object"""

        import ifc_tools # lazy import

        ifcfile = ifc_tools.get_ifcfile(obj)
        elt = self.get_ifc_element(obj)
        if elt and ifc_tools.set_attribute(ifcfile, elt, attribute, value):
            proj = ifc_tools.get_project(obj)
            proj.Modified = True
