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
import multiprocessing

import FreeCAD
from FreeCAD import Base
import Part
import Mesh
from pivy import coin

import ifcopenshell
from ifcopenshell import geom
from ifcopenshell import api
from ifcopenshell.util import attribute
from ifcopenshell.util import schema
from objects import ifc_object
from viewproviders import ifc_vp_document
from viewproviders import ifc_vp_object

SCALE = 1000.0 # IfcOpenShell works in meters, FreeCAD works in mm

def create_document(filename, document, shapemode=0, strategy=0):

    """Creates a FreeCAD IFC document object"""

    obj = add_object(document, shapemode, fctype='document')
    obj.addProperty("App::PropertyFile","FilePath","Base","The path to the linked IFC file")
    obj.addProperty("App::PropertyBool","Modified","Base")
    obj.setPropertyStatus("Modified","Hidden")
    obj.FilePath = filename
    ifcfile = ifcopenshell.open(filename)
    obj.Proxy.ifcfile = ifcfile
    project = ifcfile.by_type("IfcProject")[0]
    add_properties(project, obj, ifcfile)
    obj.HoldShape = False # do not hold shapes by default
    # Perform initial import
    # Default to all IfcElement (in the future, user can configure this as a custom filter
    elements = ifcfile.by_type("IfcElement")
    # Add site geometry
    elements.extend(ifcfile.by_type("IfcSite"))
    # populate according to strategy
    if strategy == 0:
        set_geometry(obj, elements, ifcfile, init=True)
    elif strategy == 1:
        create_children(obj, ifcfile, recursive=True, shapemode=shapemode, only_structure=True)
    elif strategy == 2:
        create_children(obj, ifcfile, recursive=True, shapemode=shapemode, assemblies=False)
    return obj


def create_object(ifcentity, document, ifcfile, shapemode=0):

    """Creates a FreeCAD object from an IFC entity"""

    obj = add_object(document, shapemode)
    add_properties(ifcentity, obj, ifcfile)
    elements = [ifcentity]
    set_geometry(obj, elements, ifcfile, init=True)
    return obj


def create_children(obj, ifcfile, recursive=False, shapemode=0, only_structure=False, assemblies=True):

    """Creates a hierarchy of objects under an object"""

    def create_child(parent, element):
        subresult = []
        # do not create if a child with same stepid already exists
        if not element.id() in [getattr(c,"StepId",0) for c in getattr(parent,"Group",[])]:
            child = create_object(element, parent.Document, ifcfile, shapemode)
            subresult.append(child)
            parent.addObject(child)
            if element.is_a("IfcSite"):
                # force-create a building too if we just created a site
                building = [o for o in get_children(child, ifcfile) if o.is_a("IfcBuilding")][0]
                subresult.extend(create_child(child, building))
            if recursive:
                subresult.extend(create_children(child, ifcfile, recursive, shapemode, only_structure, assemblies))
        return subresult

    result = []
    for child in get_children(obj, ifcfile, only_structure, assemblies):
        result.extend(create_child(obj, child))
    return result


def get_children(obj, ifcfile, only_structure=False, assemblies=True):

    """Returns the direct descendants of an object"""

    ifcentity = ifcfile[obj.StepId]
    children = []
    if assemblies or not ifcentity.is_a("IfcElement"):
        for rel in getattr(ifcentity, "IsDecomposedBy", []):
            children.extend(rel.RelatedObjects)
    if not only_structure:
        for rel in getattr(ifcentity, "ContainsElements", []):
            children.extend(rel.RelatedElements)
        for rel in getattr(ifcentity, "HasOpenings", []):
            children.extend([rel.RelatedOpeningElement])
        for rel in getattr(ifcentity, "HasFillings", []):
            children.extend([rel.RelatedBuildingElement])
    return filter_elements(children)


def get_ifcfile(obj):

    """Returns the ifcfile that handles this object"""

    project = get_project(obj)
    if hasattr(project,"Proxy"):
        if hasattr(project.Proxy,"ifcfile"):
            return project.Proxy.ifcfile
        else:
            if project.FilePath:
                ifcfile = ifcopenshell.open(project.FilePath)
                project.Proxy.ifcfile = ifcfile
                return ifcfile
    return None


def get_project(obj):

    """Returns the ifcdocument this object belongs to"""

    proj_types = ("IfcProject","IfcProjectLibrary")
    if getattr(obj, "Type", None) in proj_types:
        return obj
    for parent in obj.InListRecursive:
        if getattr(parent, "Type", None) in proj_types:
            return parent
    return None


def can_expand(obj, ifcfile):

    """Returns True if this object can have any more child extracted"""

    children = get_children(obj, ifcfile)
    group = [o.StepId for o in obj.Group]
    for child in children:
        if child.id() not in group:
            return True
    return False


def add_object(document, shapemode=0, fctype="object"):

    """adds a new object to a FreeCAD document"""

    if shapemode == 2:
        otype = 'App::FeaturePython'
    elif shapemode == 1:
        otype = 'Mesh::FeaturePython'
    else:
        otype = 'Part::FeaturePython'
    ot = ifc_object.ifc_object()
    if fctype == "document":
        vp = ifc_vp_document.ifc_vp_document()
    else:
        vp = ifc_vp_object.ifc_vp_object()
    obj = document.addObject(otype, 'IfcObject', ot, vp, False)
    return obj


def add_properties(ifcentity, obj, ifcfile, links=False):

    """Adds the properties of the given IFC object to a FreeCAD object"""

    schema = ifcfile.wrapped_data.schema_name()
    if getattr(ifcentity, "Name", None):
        obj.Label = ifcentity.Name
    else:
        obj.Label = ifcentity.is_a()
    obj.addExtension('App::GroupExtensionPython')
    if FreeCAD.GuiUp:
        obj.ViewObject.addExtension("Gui::ViewProviderGroupExtensionPython")
    obj.addProperty("App::PropertyBool", "HoldShape", "Base")
    attr_defs = ifcentity.wrapped_data.declaration().as_entity().all_attributes()
    for attr, value in ifcentity.get_info().items():
        if attr == "type":
            attr = "Type"
        elif attr == "id":
            attr = "StepId"
        elif attr == "Name":
            continue
        attr_def = next((a for a in attr_defs if a.name() == attr), None)
        data_type = ifcopenshell.util.attribute.get_primitive_type(attr_def) if attr_def else None
        if attr not in obj.PropertiesList:
            if attr == "Type":
                # main enum property, not saved to file
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
                obj.setPropertyStatus(attr,"Transient")
                setattr(obj, attr, get_ifc_classes(value, schema))
                setattr(obj, attr, value)
                # companion hidden propertym that gets saved to file
                obj.addProperty("App::PropertyString", "IfcType", "IFC")
                obj.setPropertyStatus("IfcType","Hidden")
                setattr(obj, "IfcType", value)
            elif isinstance(value, int):
                obj.addProperty("App::PropertyInteger", attr, "IFC")
                setattr(obj, attr, value)
                if attr == "StepId":
                    obj.setPropertyStatus(attr,"ReadOnly")
            elif isinstance(value, float):
                obj.addProperty("App::PropertyFloat", attr, "IFC")
                setattr(obj, attr, value)
            elif data_type == "boolean":
                obj.addProperty("App::PropertyBool", attr, "IFC")
                setattr(obj, attr, value) #will trigger error. TODO: Fix this
            elif isinstance(value, ifcopenshell.entity_instance):
                if links:
                    #value = create_object(value, obj.Document)
                    obj.addProperty("App::PropertyLink", attr, "IFC")
                    #setattr(obj, attr, value)
            elif isinstance(value, (list, tuple)) and value:
                if isinstance(value[0], ifcopenshell.entity_instance):
                    if links:
                        #nvalue = []
                        #for elt in value:
                        #    nvalue.append(create_object(elt, obj.Document))
                        obj.addProperty("App::PropertyLinkList", attr, "IFC")
                        #setattr(obj, attr, nvalue)
            elif data_type == "enum":
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
                items = ifcopenshell.util.attribute.get_enum_items(attr_def)
                setattr(obj, attr, items)
                if not value in items:
                    for v in ("UNDEFINED","NOTDEFINED","USERDEFINED"):
                        if v in items:
                            value = v
                            break
                if value in items:
                    setattr(obj, attr, value)
            else:
                obj.addProperty("App::PropertyString", attr, "IFC")
                if value is not None:
                    setattr(obj, attr, str(value))


def get_ifc_classes(ifcclass, schema="IFC4"):

    """Returns a list of sibling classes from a given IFC class"""

    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(schema)
    declaration = schema.declaration_by_name(ifcclass)
    if "StandardCase" in ifcclass:
        declaration = declaration.supertype()
    classes = [sub.name() for sub in declaration.supertype().subtypes()]
    # also include subtypes of the current class (ex, StandardCases)
    classes.extend([sub.name() for sub in declaration.subtypes()])
    return classes


def get_ifc_element(obj):

    """Returns the corresponding IFC element of an object"""

    ifc_file = get_ifcfile(obj)
    if ifc_file and hasattr(obj, "StepId"):
        return ifc_file.by_id(obj.StepId)
    return None


def filter_elements(elements):

    """Filter elements list of unwanted types"""

    # make sure we have a clean list
    if not isinstance(elements,(list,tuple)):
        elements = [elements]
    # Never load feature elements, they can be lazy loaded
    elements = [e for e in elements if not e.is_a("IfcFeatureElement")]
    # do not load spaces for now (TODO handle them correctly)
    elements = [e for e in elements if not e.is_a("IfcSpace")]
    # skip projects
    elements = [e for e in elements if not e.is_a("IfcProject")]
    # skip furniture for now, they can be lazy loaded probably
    elements = [e for e in elements if not e.is_a("IfcFurnishingElement")]
    # skip annotations for now
    elements = [e for e in elements if not e.is_a("IfcAnnotation")]
    return elements


def get_shape(elements, ifcfile):

    """Returns a Part shape from a list of IFC entities"""

    elements = filter_elements(elements)
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating "+str(total)+" shapes...",total)
    settings = get_settings(ifcfile, brep=True)
    shapes, elements = get_cache(elements)
    colors = []
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=elements)
    is_valid = iterator.initialize()
    if not is_valid:
        return None,None
    while True:
        item = iterator.get()
        if item:
            brep = item.geometry.brep_data
            shape = Part.Shape()
            shape.importBrepFromString(brep, False)
            mat = get_matrix(item.transformation.matrix.data)
            shape.scale(SCALE)
            shape.transformShape(mat)
            shapes.append(shape)
            color = item.geometry.surface_styles
            #color = (color[0], color[1], color[2], 1.0 - color[3])
            # TODO temp workaround for tranparency bug
            color = (color[0], color[1], color[2], 0.0)
            for i in range(len(shape.Faces)):
                colors.append(color)
            progressbar.next(True)
        if not iterator.next():
            break
    progressbar.stop()
    if len(shapes) == 1:
        shape = shapes[0]
    else:
        shape = Part.makeCompound(shapes)
    return shape, colors


def get_mesh(elements, ifcfile):

    """Returns a Mesh from a list of IFC entities"""

    elements = filter_elements(elements)
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating "+str(total)+" shapes...",total)
    settings = get_settings(ifcfile)
    meshes, elements = get_cache(elements, mesh=True)
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=elements)
    is_valid = iterator.initialize()
    colors = []
    if not is_valid:
        return None,None
    while True:
        item = iterator.get()
        if item:
            verts = item.geometry.verts
            faces = item.geometry.faces
            verts = [FreeCAD.Vector(verts[i:i+3]) for i in range(0,len(verts),3)]
            faces = [tuple(faces[i:i+3]) for i in range(0,len(faces),3)]
            mat = get_matrix(item.transformation.matrix.data)
            verts = [mat.multVec(v.multiply(SCALE)) for v  in verts]
            mesh = Mesh.Mesh((verts,faces))
            meshes.addMesh(mesh)
            # TODO buggy
            #color = item.geometry.surface_styles
            #color = (color[0], color[1], color[2], 0.0)
            #for i in range(len(faces)):
            #    colors.append(color)
            progressbar.next(True)
        if not iterator.next():
            break
    progressbar.stop()
    return meshes, colors


def get_coin(mesh):

    """Returns a coin node from a mesh"""

    buf = coin.SoInput()
    buf.setBuffer(mesh.writeInventor())
    node = coin.SoDB.readAll(buf)
    return node


def get_cache(elements, mesh=False):

    """Retrieves elements from a shape cache"""

    if mesh:
        geom = Mesh.Mesh()
    else:
        geom = []
    return geom, elements


def get_settings(ifcfile, brep=False):

    """Returns ifcopenshell settings"""

    settings = ifcopenshell.geom.settings()
    if brep:
        settings.set(settings.DISABLE_TRIANGULATION, True)
        settings.set(settings.USE_BREP_DATA,True)
        settings.set(settings.SEW_SHELLS,True)
    body_contexts = get_body_context_ids(ifcfile)
    if body_contexts:
        settings.set_context_ids(body_contexts)
    return settings


def set_geometry(obj, elements, ifcfile, init=False):

    """Sets the geometry of the given object"""

    shape = None
    mesh = None
    colors = None

    # check if this element has its own shape
    if obj.isDerivedFrom("Part::Feature"):
        shape, colors = get_shape(elements, ifcfile)
    else:
        mesh, colors = get_mesh(elements, ifcfile)
    if not shape and not mesh:
        # we don't have an own shape
        if obj.isDerivedFrom("Part::Feature"):
            if init:
                # gather decomposition
                elements = ifcopenshell.util.element.get_decomposition(elements[0])
                shape, colors = get_shape(elements, ifcfile)
            else:
                # gather child shapes (faster)
                shapes = [child.Shape for child in obj.Group if child.isDerivedFrom("Part::Feature")]
                if shapes:
                    if obj.HoldShape:
                        shape = Part.makeCompound(shapes)
                    else:
                        # workaround for group extension bug: add a dummy placeholder shape)
                        shape = Part.makeBox(1,1,1)
        else:
            if init:
                # gather decomposition
                elements = ifcopenshell.util.element.get_decomposition(elements[0])
                mesh, colors = get_mesh(elements, ifcfile)
            else:
                # gather child meshes (faster)
                meshes = [child.Mesh for child in obj.Group if child.isDerivedFrom("Mesh::Feature")]
                if meshes:
                    mesh = Mesh.Mesh()
                    if obj.HoldShape:
                        for m in meshes:
                            mesh.addMesh(m)
    if shape and shape.Vertexes:
        obj.Shape = shape
    elif mesh:
        if obj.isDerivedFrom("Mesh::Feature"):
            obj.Mesh = mesh
        elif FreeCAD.GuiUp:
            node = get_coin(mesh)
            obj.ViewObject.RootNode.addChild(node)
    set_colors(obj, colors)


def set_attribute(ifcfile, element, attribute, value):

    """Sets the value of an attribute of an IFC element"""

    if attribute == "Type":
        if value != element.is_a():
            if value and value.startswith("Ifc"):
                cmd = 'root.reassign_class'
                FreeCAD.Console.PrintLog("Changing IFC class value: "+element.is_a()+" to "+str(value)+"\n")
                product = ifcopenshell.api.run(cmd, ifcfile, product=element, ifc_class=value)
                # TODO fix attributes
                return product
    cmd = 'attribute.edit_attributes'
    attribs = {attribute: value}
    if hasattr(element, attribute):
        if getattr(element, attribute) != value:
            FreeCAD.Console.PrintLog("Changing IFC attribute value of "+str(attribute)+": "+str(value)+"\n")
            ifcopenshell.api.run(cmd, ifcfile, product=element, attributes=attribs)
            return True
    return False


def set_colors(obj, colors):

    """Sets the given colors to an object"""

    if FreeCAD.GuiUp and colors:
        if hasattr(obj.ViewObject,"ShapeColor"):
            obj.ViewObject.ShapeColor = colors[0][:3]
        if hasattr(obj.ViewObject,"DiffuseColor"):
            obj.ViewObject.DiffuseColor = colors


def get_body_context_ids(ifcfile):

    # Facetation is to accommodate broken Revit files
    # See https://forums.buildingsmart.org/t/suggestions-on-how-to-improve-clarity-of-representation-context-usage-in-documentation/3663/6?u=moult
    body_contexts = [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationSubContext")
        if c.ContextIdentifier in ["Body", "Facetation"]
    ]
    # Ideally, all representations should be in a subcontext, but some BIM programs don't do this correctly
    body_contexts.extend(
        [
            c.id()
            for c in ifcfile.by_type("IfcGeometricRepresentationContext", include_subtypes=False)
            if c.ContextType == "Model"
        ]
    )
    return body_contexts


def get_plan_contexts_ids(ifcfile):

    # Annotation is to accommodate broken Revit files
    # See https://github.com/Autodesk/revit-ifc/issues/187
    return [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationContext")
        if c.ContextType in ["Plan", "Annotation"]
    ]


def get_matrix(ios_matrix):

    """Converts an IfcOpenShell matrix tuple into a FreeCAD matrix"""

    # https://github.com/IfcOpenShell/IfcOpenShell/issues/1440
    # https://pythoncvc.net/?cat=203
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)


def save_ifc(obj):

    """Saves the linked IFC file of an object"""

    if hasattr(obj,"FilePath") and obj.FilePath:
        ifcfile = ifc_tools.get_ifcfile(obj)
        ifcfile.write(obj.FilePath)
        obj.Modified = False
        FreeCAD.Console.PrintMessage("Saved " + obj.FilePath + "\n")

