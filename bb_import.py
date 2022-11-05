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
import time

import FreeCAD
import Part

import ifcopenshell
from ifcopenshell import geom
from bb_objects import bb_object
from bb_viewproviders import bb_vp_document
from bb_viewproviders import bb_vp_object

SCALE = 1000.0 # IfcOpenShell works in meters, FreeCAD works in mm

def open(filename):

    """Opens an IFC file"""

    name = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument()
    doc.Label = name
    FreeCAD.setActiveDocument(doc.Name)
    insert(filename,doc.Name)


def insert(filename, docname):

    """Inserts an IFC document in a FreeCAD document"""

    stime = time.time()
    document = FreeCAD.getDocument(docname)
    create_document(filename, document)
    document.recompute()
    endtime = "%02d:%02d" % (divmod(round(time.time() - stime, 1), 60))
    fsize = round(os.path.getsize(filename)/1048576, 2)
    print ("Imported", fsize, "Mb in", endtime)


def create_document(filename, document):

    """Creates a FreeCAD IFC document object"""
    obj = document.addObject('Part::FeaturePython', 'IfcDocument', bb_object.bb_object(), 
            bb_vp_document.bb_vp_document(), True)

    obj.addProperty("App::PropertyString","FilePath","Base","The path to the linked IFC file")
    obj.FilePath = filename
    ifcfile = ifcopenshell.open(filename)
    obj.Proxy.ifcfile = ifcfile
    project = ifcfile.by_type("IfcProject")[0]
    add_properties(project, obj)
    # Perform initial import
    # Default to all IfcElement (in the future, user can configure this as a custom filter
    geoms = ifcfile.by_type("IfcElement")
    # Never load feature elements, they can be lazy loaded
    geoms = [e for e in geoms if not e.is_a("IfcFeatureElement")]
    # Add site geometry
    geoms.extend(ifcfile.by_type("IfcSite"))
    obj.Shape = get_shape(geoms, ifcfile)
    #create_hierarchy(obj, ifcfile, recursive=True)
    return obj


def create_children(obj, ifcfile, recursive=False):

    """Creates a hierarchy of objects under an object"""

    def create_child(parent, element):
        # do not create if a child with same stepid already exists
        if not element.id() in [getattr(c,"StepId",0) for c in getattr(parent,"Group",[])]:
            child = create_object(element, parent.Document, ifcfile)
            parent.addObject(child)
            if recursive:
                create_children(child, ifcfile, recursive)

    for child in get_children(obj, ifcfile):
        create_child(obj, child)
    obj.Document.recompute()


def get_children(obj, ifcfile):

    """Returns the direct descendants of an object"""

    ifcentity = ifcfile[obj.StepId]
    children = []
    for rel in getattr(ifcentity, "IsDecomposedBy", []):
        children.extend(rel.RelatedObjects)
    for rel in getattr(ifcentity, "ContainsElements", []):
        children.extend(rel.RelatedElements)
    return children


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

    if getattr(obj, "Type") == "IfcProject":
        return obj

    for parent in obj.InListRecursive:
        if getattr(parent, "Type") == "IfcProject":
            return parent
    return None


def create_object(ifcentity, document, ifcfile):

    """Creates a FreeCAD object from an IFC entity"""
    obj = document.addObject('Part::FeaturePython', 'IfcObject', bb_object.bb_object(), 
            bb_vp_object.bb_vp_object(), True)
    add_properties(ifcentity, obj)
    geoms = ifcopenshell.util.element.get_decomposition(ifcentity)
    geoms = [e for e in geoms if not e.is_a("IfcFeatureElement")]
    if not geoms:
        # no children to decompose
        geoms = [ifcentity]
    obj.Shape = get_shape(geoms, ifcfile)
    if ifcentity.is_a("IfcSite"):
        shape = get_shape([ifcentity], ifcfile)
        if shape:
            obj.SiteShape = get_shape([ifcentity], ifcfile)
    return obj


def add_properties(ifcentity, obj):

    """Adds the properties of the given IFC object to a FreeCAD object"""

    if getattr(ifcentity, "Name", None):
        obj.Label = ifcentity.Name
    else:
        obj.Label = ifcentity.is_a()
    if ifcentity.is_a("IfcSite"):
        obj.addProperty("Part::PropertyPartShape", "SiteShape", "Base")
    for attr, value in ifcentity.get_info().items():
        if attr == "id":
            attr = "StepId"
        elif attr == "type":
            attr = "Type"
        elif attr == "Name":
            continue
        if attr not in obj.PropertiesList:
            if isinstance(value, int):
                obj.addProperty("App::PropertyInteger", attr, "IFC")
                setattr(obj, attr, value)
            elif isinstance(value, float):
                obj.addProperty("App::PropertyFloat", attr, "IFC")
                setattr(obj, attr, value)
            elif isinstance(value, ifcopenshell.entity_instance):
                #value = create_object(value, obj.Document)
                obj.addProperty("App::PropertyLink", attr, "IFC")
                #setattr(obj, attr, value)
            elif isinstance(value, (list, tuple)) and value:
                if isinstance(value[0], ifcopenshell.entity_instance):
                    #nvalue = []
                    #for elt in value:
                    #    nvalue.append(create_object(elt, obj.Document))
                    obj.addProperty("App::PropertyLinkList", attr, "IFC")
                    #setattr(obj, attr, nvalue)
            else:
                obj.addProperty("App::PropertyString", attr, "IFC")
                if value is not None:
                    setattr(obj, attr, str(value))


def get_shape(geoms, ifcfile):

    """Returns a Part shape from a list of IFC entities"""

    settings = ifcopenshell.geom.settings()
    settings.set(settings.DISABLE_TRIANGULATION, True)
    settings.set(settings.USE_BREP_DATA,True)
    settings.set(settings.SEW_SHELLS,True)
    body_contexts = get_body_context_ids(ifcfile)
    if body_contexts:
        settings.set_context_ids(body_contexts)
    shapes = []
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=geoms)
    is_valid = iterator.initialize()
    if not is_valid:
        return
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
        if not iterator.next():
            break
    return Part.makeCompound(shapes)


def get_mesh(geoms, ifcfile):

    # Unused for now

    """Returns a Mesh from a list of IFC entities"""

    settings = ifcopenshell.geom.settings()
    body_contexts = get_body_context_ids(ifcfile)
    if body_contexts:
        settings.set_context_ids(body_contexts)
    meshes = Mesh.Mesh()
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=geoms)
    is_valid = iterator.initialize()
    if not is_valid:
        return
    while True:
        item = iterator.get()
        if item:
            verts = item.geometry.verts
            faces = item.geometry.faces
            verts = [FreeCAD.Vector(verts[i:i+3]) for i in range(0,len(verts),3)]
            faces = [tuple(faces[i:i+3]) for i in range(0,len(faces),3)]
            mesh = Mesh.Mesh((verts,faces))
            mat = get_matrix(item.transformation.matrix.data)
            mesh.transform(mat)
            scale = FreeCAD.Matrix()
            scale.scale(SCALE)
            mesh.transform(scale)
            meshes.addMesh(mesh)
        if not iterator.next():
            break
    return meshe


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
