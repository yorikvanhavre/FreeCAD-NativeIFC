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
import multiprocessing
import re

# heavyweight libraries - ifc_tools should always be lazy loaded

import FreeCAD
from FreeCAD import Base
import Part
import Mesh
from pivy import coin
import exportIFC
import exportIFCHelper

import ifcopenshell
from ifcopenshell import geom
from ifcopenshell import api
from ifcopenshell import template
from ifcopenshell.util import attribute
from ifcopenshell.util import schema
from ifcopenshell.util import placement
from ifcopenshell.util import unit

import ifc_objects
import ifc_viewproviders
import ifc_import

SCALE = 1000.0  # IfcOpenShell works in meters, FreeCAD works in mm
SHORT = False  # If True, only Step ID attribute is created
ROUND = 8  # rounding value for placements
PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/NativeIFC")


def create_document(document, filename=None, shapemode=0, strategy=0, silent=False):
    """Creates a IFC document object in the given FreeCAD document.

    filename:  If not given, a blank IFC document is created
    shapemode: 0 = full shape
               1 = coin only
               2 = no representation
    strategy:  0 = only root object
               1 = only bbuilding structure,
               2 = all children
    """

    obj = add_object(document, otype="project")
    full = False
    d = "The path to the linked IFC file"
    obj.addProperty("App::PropertyFile", "FilePath", "Base", d)
    obj.addProperty("App::PropertyBool", "Modified", "Base")
    obj.setPropertyStatus("Modified", "Hidden")
    if filename:
        obj.FilePath = filename
        ifcfile = ifcopenshell.open(filename)
    else:
        if not silent:
            full = ifc_import.get_project_type()
        ifcfile = create_ifcfile()
    project = ifcfile.by_type("IfcProject")[0]
    obj.Proxy.ifcfile = ifcfile
    add_properties(obj, ifcfile, project, shapemode=shapemode)
    obj.addProperty("App::PropertyEnumeration", "Schema", "Base")
    # add default groups - can be done later when needed
    # get_group(obj, "IfcOrphansGroup")
    # get_group(obj, "IfcMaterialsGroup")
    # get_group(obj, "IfcTypesGroup")
    obj.Schema = ifcopenshell.ifcopenshell_wrapper.schema_names()
    obj.Schema = ifcfile.wrapped_data.schema_name()
    # populate according to strategy
    if strategy == 0:
        pass
    elif strategy == 1:
        create_children(obj, ifcfile, recursive=True, only_structure=True)
    elif strategy == 2:
        create_children(obj, ifcfile, recursive=True, assemblies=False)
    # create default structure
    if full:
        import Arch

        site = aggregate(Arch.makeSite(), obj)
        building = aggregate(Arch.makeBuilding(), site)
        storey = aggregate(Arch.makeFloor(), building)
    return obj


def create_ifcfile():
    """Creates a new, empty IFC document"""

    # TODO do not rely on the template,
    # and create a minimal file instead, with no person, no org, no
    # nothing. These shold be populated later on by the user
    # use api: https://blenderbim.org/docs-python/autoapi/ifcopenshell/api/project/create_file/

    ifcfile = ifcopenshell.template.create()
    param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
    user = param.GetString("prefAuthor", "")
    user = user.split("<")[0].strip()
    if user:
        person = ifcfile.by_type("IfcPerson")[0]
        set_attribute(ifcfile, person, "FamilyName", user)
    org = param.GetString("prefCompany", "")
    if org:
        comp = ifcfile.by_type("IfcOrganization")[0]
        set_attribute(ifcfile, comp, "Name", user)
    application = "FreeCAD"
    version = FreeCAD.Version()
    version = ".".join([str(v) for v in version[0:3]])
    app = ifcfile.by_type("IfcApplication")[0]
    set_attribute(ifcfile, app, "ApplicationFullName", application)
    set_attribute(ifcfile, app, "Version", version)
    return ifcfile


def api_run(*args, **kwargs):
    """Runs an IfcOpenShell API call and flags the ifcfile as modified"""

    ifcopenshell.api.run(*args, **kwargs)
    # *args are command, ifcfile
    ifcfile = args[1]
    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if hasattr(o, "Proxy") and hasattr(o.Proxy, "ifcfile"):
                if o.Proxy.ifcfile == ifcfile:
                    o.Modified = True


def create_object(ifcentity, document, ifcfile, shapemode=0):
    """Creates a FreeCAD object from an IFC entity"""

    exobj = get_object(ifcentity, document)
    if exobj:
        return exobj
    s = "IFC: Created #{}: {}, '{}'\n".format(
        ifcentity.id(), ifcentity.is_a(), ifcentity.Name
    )
    FreeCAD.Console.PrintLog(s)
    obj = add_object(document)
    add_properties(obj, ifcfile, ifcentity, shapemode=shapemode)
    if FreeCAD.GuiUp:
        if ifcentity.is_a("IfcSpace") or ifcentity.is_a("IfcOpeningElement"):
            obj.ViewObject.DisplayMode = "Wireframe"
    elements = [ifcentity]
    return obj


def create_material(element, parent, recursive=False):
    """Creates a material object in the given project or parent material"""

    if not element:
        return
    if isinstance(element, (tuple, list)):
        for e in element:
            create_material(e, parent, recursive)
        return
    exobj = get_object(element, parent.Document)
    if exobj:
        return exobj
    obj = add_object(parent.Document, otype="material")
    ifcfile = get_ifcfile(parent)
    add_properties(obj, ifcfile, element)
    if parent.isDerivedFrom("App::MaterialObject"):
        parent.Proxy.addObject(parent, obj)
    else:
        get_group(parent, "IfcMaterialsGroup").addObject(obj)
    if recursive:
        submat = get_material(obj)
        if isinstance(submat, list):
            for s in submat:
                create_material(s, obj, recursive)
        else:
            create_material(submat, obj, recursive)
    show_psets(obj)
    return obj


def create_children(
    obj,
    ifcfile=None,
    recursive=False,
    only_structure=False,
    assemblies=True,
    expand=False,
):
    """Creates a hierarchy of objects under an object"""

    def create_child(parent, element):
        subresult = []
        # do not create if a child with same stepid already exists
        if not element.id() in [
            getattr(c, "StepId", 0) for c in getattr(parent, "Group", [])
        ]:
            child = create_object(element, parent.Document, ifcfile, parent.ShapeMode)
            subresult.append(child)
            parent.Proxy.addObject(parent, child)
            if element.is_a("IfcSite"):
                # force-create contained buildings too if we just created a site
                buildings = [
                    o for o in get_children(child, ifcfile) if o.is_a("IfcBuilding")
                ]
                for building in buildings:
                    subresult.extend(create_child(child, building))
            elif element.is_a("IfcOpeningElement"):
                # force-create contained windows too if we just created an opening
                windows = [
                    o
                    for o in get_children(child, ifcfile)
                    if o.is_a() in ("IfcWindow", "IfcDoor")
                ]
                for window in windows:
                    subresult.extend(create_child(child, window))
            if recursive:
                subresult.extend(
                    create_children(
                        child, ifcfile, recursive, only_structure, assemblies
                    )
                )
        return subresult

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
    result = []
    for child in get_children(obj, ifcfile, only_structure, assemblies, expand):
        result.extend(create_child(obj, child))
    return result


def get_children(
    obj, ifcfile=None, only_structure=False, assemblies=True, expand=False
):
    """Returns the direct descendants of an object"""

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
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
    return filter_elements(
        children, ifcfile, expand=expand, spaces=True, assemblies=assemblies
    )


def get_object(element, document=None):
    """Returns the object that references this element, if any"""

    if document:
        ldocs = {"document": document}
    else:
        ldocs = FreeCAD.listDocuments()
    for n, d in ldocs.items():
        for obj in d.Objects:
            if hasattr(obj, "StepId"):
                if obj.StepId == element.id():
                    if get_ifc_element(obj) == element:
                        return obj
    return None


def get_ifcfile(obj):
    """Returns the ifcfile that handles this object"""

    project = get_project(obj)
    if project:
        if hasattr(project, "Proxy"):
            if hasattr(project.Proxy, "ifcfile"):
                return project.Proxy.ifcfile
        if project.FilePath:
            ifcfile = ifcopenshell.open(project.FilePath)
            if hasattr(project, "Proxy"):
                project.Proxy.ifcfile = ifcfile
            return ifcfile
    return None


def get_project(obj):
    """Returns the ifcdocument this object belongs to"""

    proj_types = ("IfcProject", "IfcProjectLibrary")
    if getattr(obj, "Class", None) in proj_types:
        return obj
    if hasattr(obj, "InListRecursive"):
        for parent in obj.InListRecursive:
            if getattr(parent, "Class", None) in proj_types:
                return parent
    return None


def can_expand(obj, ifcfile=None):
    """Returns True if this object can have any more child extracted"""

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
    children = get_children(obj, ifcfile, expand=True)
    group = [o.StepId for o in obj.Group if hasattr(o, "StepId")]
    for child in children:
        if child.id() not in group:
            return True
    return False


def get_material(obj):
    """Returns a material attched to this object"""

    element = get_ifc_element(obj)
    if not element:
        return None
    if element.is_a("IfcMaterialConstituentSet"):
        return element.MaterialConstituents
    elif element.is_a() in [
        "IfcMaterialLayer",
        "IfcMaterialConstituent",
        "IfcMaterialProfile",
    ]:
        return element.Material
    elif element.is_a("IfcMaterialLayerSet"):
        return element.MaterialLayers
    elif element.is_a("IfcMaterialProfileSet"):
        return element.MaterialProfiles
    else:
        material = ifcopenshell.util.element.get_material(
            element, should_skip_usage=True
        )
        return material


def show_material(obj):
    """Creates and links materials for the given object, if available"""

    material = get_material(obj)
    if not material:
        return
    if not hasattr(obj, "Material"):
        obj.addProperty("App::PropertyLink", "Material", "IFC")
    project = get_project(obj)
    matobj = create_material(material, project, recursive=True)
    obj.Material = matobj


def add_object(document, otype=None, oname="IfcObject"):
    """adds a new object to a FreeCAD document.
    otype can be 'project', 'group' or None (normal object)"""

    if otype == "group":
        proxy = None
        ftype = "App::DocumentObjectGroupPython"
    elif otype == "material":
        proxy = ifc_objects.ifc_object()
        ftype = "App::MaterialObjectPython"
    else:
        proxy = ifc_objects.ifc_object()
        ftype = "Part::FeaturePython"
    if otype == "project":
        vp = ifc_viewproviders.ifc_vp_document()
    elif otype == "group":
        vp = ifc_viewproviders.ifc_vp_group()
    elif otype == "material":
        vp = ifc_viewproviders.ifc_vp_material()
    else:
        vp = ifc_viewproviders.ifc_vp_object()
    obj = document.addObject(ftype, oname, proxy, vp, False)
    return obj


def add_properties(
    obj, ifcfile=None, ifcentity=None, links=False, shapemode=0, short=SHORT
):
    """Adds the properties of the given IFC object to a FreeCAD object"""

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
    if not ifcentity:
        ifcentity = get_ifc_element(obj)
    if getattr(ifcentity, "Name", None):
        obj.Label = ifcentity.Name
    else:
        obj.Label = ifcentity.is_a()
    if "Group" not in obj.PropertiesList:
        obj.addProperty("App::PropertyLinkList", "Group", "Base")
    if obj.isDerivedFrom("Part::Feature") and "ShapeMode" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "ShapeMode", "Base")
        shapemodes = [
            "Shape",
            "Coin",
            "None",
        ]  # possible shape modes for all IFC objects
        if isinstance(shapemode, int):
            shapemode = shapemodes[shapemode]
        obj.ShapeMode = shapemodes
        obj.ShapeMode = shapemode
    attr_defs = ifcentity.wrapped_data.declaration().as_entity().all_attributes()
    try:
        info_ifcentity = ifcentity.get_info()
    except:
        # slower but no errors
        info_ifcentity = get_elem_attribs(ifcentity)
    for attr, value in info_ifcentity.items():
        if attr == "type":
            attr = "Class"
        elif attr == "id":
            attr = "StepId"
        elif attr == "Name":
            continue
        if short and attr not in ("Class", "StepId"):
            continue
        attr_def = next((a for a in attr_defs if a.name() == attr), None)
        data_type = (
            ifcopenshell.util.attribute.get_primitive_type(attr_def)
            if attr_def
            else None
        )
        if attr == "Class":
            # main enum property, not saved to file
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
                obj.setPropertyStatus(attr, "Transient")
            setattr(obj, attr, get_ifc_classes(obj, value))
            setattr(obj, attr, value)
            # companion hidden propertym that gets saved to file
            obj.addProperty("App::PropertyString", "IfcClass", "IFC")
            obj.setPropertyStatus("IfcClass", "Hidden")
            setattr(obj, "IfcClass", value)
        elif isinstance(value, int):
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyInteger", attr, "IFC")
                if attr == "StepId":
                    obj.setPropertyStatus(attr, "ReadOnly")
            setattr(obj, attr, value)
        elif isinstance(value, float):
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyFloat", attr, "IFC")
            setattr(obj, attr, value)
        elif data_type == "boolean":
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyBool", attr, "IFC")
            if not value:
                value = False
            elif not isinstance(value, bool):
                print("DEBUG: attempting to set boolean value:", attr, value)
            setattr(obj, attr, value)  # will trigger error. TODO: Fix this
        elif isinstance(value, ifcopenshell.entity_instance):
            if links:
                if attr not in obj.PropertiesList:
                    # value = create_object(value, obj.Document)
                    obj.addProperty("App::PropertyLink", attr, "IFC")
                # setattr(obj, attr, value)
        elif isinstance(value, (list, tuple)) and value:
            if isinstance(value[0], ifcopenshell.entity_instance):
                if links:
                    if attr not in obj.PropertiesList:
                        # nvalue = []
                        # for elt in value:
                        #    nvalue.append(create_object(elt, obj.Document))
                        obj.addProperty("App::PropertyLinkList", attr, "IFC")
                    # setattr(obj, attr, nvalue)
        elif data_type == "enum":
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
            items = ifcopenshell.util.attribute.get_enum_items(attr_def)
            setattr(obj, attr, items)
            if value not in items:
                for v in ("UNDEFINED", "NOTDEFINED", "USERDEFINED"):
                    if v in items:
                        value = v
                        break
            if value in items:
                setattr(obj, attr, value)
        else:
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyString", attr, "IFC")
            if value is not None:
                setattr(obj, attr, str(value))
    # link Label2 and Description
    if "Description" in obj.PropertiesList:
        obj.setExpression("Label2", "Description")


def remove_unused_properties(obj):
    """Remove IFC properties if they are not part of the current IFC class"""

    elt = get_ifc_element(obj)
    props = list(elt.get_info().keys())
    props[props.index("id")] = "StepId"
    props[props.index("type")] = "Class"
    for prop in obj.PropertiesList:
        if obj.getGroupOfProperty(prop) == "IFC":
            if prop not in props:
                obj.removeProperty(prop)


def get_ifc_classes(obj, baseclass):
    """Returns a list of sibling classes from a given FreeCAD object"""

    # this function can become pure IFC

    if baseclass in ("IfcProject", "IfcProjectLibrary"):
        return ("IfcProject", "IfcProjectLibrary")
    ifcfile = get_ifcfile(obj)
    if not ifcfile:
        return [baseclass]
    schema = ifcfile.wrapped_data.schema_name()
    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(schema)
    declaration = schema.declaration_by_name(baseclass)
    if "StandardCase" in baseclass:
        declaration = declaration.supertype()
    classes = [sub.name() for sub in declaration.supertype().subtypes()]
    # also include subtypes of the current class (ex, StandardCases)
    classes.extend([sub.name() for sub in declaration.subtypes()])
    if baseclass not in classes:
        classes.append(baseclass)
    return classes


def get_ifc_element(obj):
    """Returns the corresponding IFC element of an object"""

    ifc_file = get_ifcfile(obj)
    if ifc_file and hasattr(obj, "StepId"):
        return ifc_file.by_id(obj.StepId)
    return None


def has_representation(element):
    """Tells if an elements has an own representation"""

    # This function can become pure IFC

    if hasattr(element, "Representation") and element.Representation:
        return True
    return False


def filter_elements(elements, ifcfile, expand=True, spaces=False, assemblies=True):
    """Filter elements list of unwanted classes"""

    # This function can become pure IFC

    # gather decomposition if needed
    openings = False
    if assemblies and any([e.is_a("IfcOpeningElement") for e in elements]):
        openings = True
    if expand and (len(elements) == 1):
        elem = elements[0]
        if elem.is_a("IfcSpace"):
            spaces = True
        if not has_representation(elem):
            if elem.is_a("IfcProject"):
                elements = ifcfile.by_type("IfcElement")
                elements.extend(ifcfile.by_type("IfcSite"))
            else:
                elements = ifcopenshell.util.element.get_decomposition(elem)
        else:
            if elem.Representation.Representations:
                rep = elem.Representation.Representations[0]
                if (
                    rep.Items
                    and rep.Items[0].is_a() == "IfcPolyline"
                    and elem.IsDecomposedBy
                ):
                    # only use the decomposition and not the polyline
                    # happens for multilayered walls exported by VectorWorks
                    # the Polyline is the wall axis
                    # see https://github.com/yorikvanhavre/FreeCAD-NativeIFC/issues/28
                    elements = ifcopenshell.util.element.get_decomposition(elem)
    if not openings:
        # Never load feature elements by default, they can be lazy loaded
        elements = [e for e in elements if not e.is_a("IfcFeatureElement")]
    # do load spaces when required, otherwise skip computing their shapes
    if not spaces:
        elements = [e for e in elements if not e.is_a("IfcSpace")]
    # skip projects
    elements = [e for e in elements if not e.is_a("IfcProject")]
    # skip furniture for now, they can be lazy loaded probably
    elements = [e for e in elements if not e.is_a("IfcFurnishingElement")]
    # skip annotations for now
    elements = [e for e in elements if not e.is_a("IfcAnnotation")]
    return elements


def get_cache(ifcfile):
    """Returns the shape cache dictionary associated with this ifc file"""

    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if hasattr(o, "Proxy") and hasattr(o.Proxy, "ifcfile"):
                if o.Proxy.ifcfile == ifcfile:
                    if hasattr(o.Proxy, "ifccache") and o.Proxy.ifccache:
                        return o.Proxy.ifccache
    return {"Shape": {}, "Color": {}, "Coin": {}, "Placement": {}}


def set_cache(ifcfile, cache):
    """Sets the given dictionary as shape cache for the given ifc file"""

    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if hasattr(o, "Proxy") and hasattr(o.Proxy, "ifcfile"):
                if o.Proxy.ifcfile == ifcfile:
                    o.Proxy.ifccache = cache
                    return


def get_shape(elements, ifcfile, cached=False):
    """Returns a Part shape from a list of IFC entities"""

    elements = filter_elements(elements, ifcfile)
    if len(elements) == 0:
        return None, None  # happens on empty storeys
    shapes = []
    colors = []
    # process cached elements
    cache = get_cache(ifcfile)
    if cached:
        rest = []
        for e in elements:
            if e.id in cache["Shape"]:
                s = cache["Shape"][e.id]
                shapes.append(s.copy())
                if e.id in cache["Color"]:
                    c = cache["Color"][e.id]
                else:
                    c = (0.8, 0.8, 0.8)
                if len(c) <= 4:
                    for f in s.Faces:
                        colors.append(c)
                else:
                    colors = c
            else:
                rest.append(e)
        elements = rest
    if not elements:
        return shapes, colors
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating " + str(total) + " shapes...", total)
    iterator = get_geom_iterator(ifcfile, elements, brep=True)
    if iterator is None:
        return None, None
    while True:
        item = iterator.get()
        if item:
            brep = item.geometry.brep_data
            shape = Part.Shape()
            shape.importBrepFromString(brep, False)
            mat = get_freecad_matrix(item.transformation.matrix.data)
            shape.scale(SCALE)
            shape.transformShape(mat)
            shapes.append(shape)
            sstyle = item.geometry.surface_styles
            # color = (color[0], color[1], color[2], 1.0 - color[3])
            # TODO temp workaround for tranparency bug
            scolors = []
            if (
                (len(sstyle) > 4)
                and len(shape.Solids) > 1
                and len(sstyle) // 4 == len(shape.Solids)
            ):
                # multiple colors
                for i in range(len(shape.Solids)):
                    for j in range(len(shape.Solids[i].Faces)):
                        scolors.append(
                            (sstyle[i * 4], sstyle[i * 4 + 1], sstyle[i * 4 + 2], 0.0)
                        )
                if len(colors) < len(shape.Faces):
                    for i in range(len(shape.Faces) - len(colors)):
                        scolors.append((sstyle[0], sstyle[1], sstyle[2], 0.0))
            else:
                color = (sstyle[0], sstyle[1], sstyle[2], 0.0)
                for f in shape.Faces:
                    scolors.append(color)
            cache["Shape"][item.id] = shape
            cache["Color"][item.id] = scolors
            colors.extend(scolors)
            progressbar.next(True)
        if not iterator.next():
            break
    set_cache(ifcfile, cache)
    if len(shapes) == 1:
        shape = shapes[0]
    else:
        shape = Part.makeCompound(shapes)
    progressbar.stop()
    return shape, colors


def apply_coin_placement(node, placement):
    """Applies the given placement to the given node"""

    coords = node.getChild(1)
    verts = [FreeCAD.Vector(p.getValue()) for p in coords.point.getValues()]
    verts = [tuple(placement.multVec(v)) for v in verts]
    coords.point.setValues(verts)


def get_coin(elements, ifcfile, cached=False):
    """Returns a Coin node from a list of IFC entities"""

    elements = filter_elements(elements, ifcfile)
    grouping = bool(len(elements) > 1)
    nodes = coin.SoSeparator()
    # process cached elements
    placement = None
    cache = get_cache(ifcfile)
    if cached:
        rest = []
        for e in elements:
            if e.id() in cache["Placement"]:
                placement = cache["Placement"][e.id()]
            if e.id() in cache["Coin"]:
                node = cache["Coin"][e.id()].copy()
                if grouping:
                    apply_coin_placement(node, placement)
                nodes.addChild(node)
            else:
                rest.append(e)
        if grouping:
            placement = None
        elements = rest
    elements = [e for e in elements if has_representation(e)]
    if not elements:
        return nodes, None, placement
    # TODO fix below
    if nodes.getNumChildren():
        print(
            "DEBUG: Following elements are excluded because they make coin crash (to investigate):"
        )
        print(
            "DEBUG: If you wish to test, comment out line 488 (return nodes, None) in ifc_tools.py"
        )
        [print("   ", e) for e in elements]
        return nodes, None, None
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating " + str(total) + " shapes...", total)
    iterator = get_geom_iterator(ifcfile, elements, brep=False)
    if iterator is None:
        return None, None, None
    while True:
        item = iterator.get()
        if item:
            node = coin.SoSeparator()
            # colors
            mat = coin.SoMaterial()
            if item.geometry.materials:
                color = item.geometry.materials[0].diffuse
                color = (color[0], color[1], color[2], 0.0)
                mat.diffuseColor.setValue(color[:3])
                # TODO treat transparency
                # mat.transparency.setValue(0.8)
                # TODO treat multiple materials
            else:
                mat.diffuseColor.setValue(0.85, 0.85, 0.85)
            node.addChild(mat)
            # verts
            matrix = get_freecad_matrix(item.transformation.matrix.data)
            placement = FreeCAD.Placement(matrix)
            verts = item.geometry.verts
            verts = [FreeCAD.Vector(verts[i : i + 3]) for i in range(0, len(verts), 3)]
            verts = [tuple(v.multiply(SCALE)) for v in verts]
            coords = coin.SoCoordinate3()
            coords.point.setValues(verts)
            node.addChild(coords)
            # faces
            faces = list(item.geometry.faces)
            faces = [
                f for i in range(0, len(faces), 3) for f in faces[i : i + 3] + [-1]
            ]
            faceset = coin.SoIndexedFaceSet()
            faceset.coordIndex.setValues(faces)
            node.addChild(faceset)
            cache["Coin"][item.id] = node
            if grouping:
                # if we are joining nodes together, their placement
                # must be baked in
                node = node.copy()
                apply_coin_placement(node, placement)
            nodes.addChild(node)
            cache["Placement"][item.id] = placement
            progressbar.next(True)
        if not iterator.next():
            break
    if grouping:
        placement = None
    set_cache(ifcfile, cache)
    progressbar.stop()
    return nodes, None, placement


def get_settings(ifcfile, brep=True):
    """Returns ifcopenshell settings"""

    # This function can become pure IFC

    settings = ifcopenshell.geom.settings()
    if brep:
        settings.set(settings.DISABLE_TRIANGULATION, True)
        settings.set(settings.USE_BREP_DATA, True)
        settings.set(settings.SEW_SHELLS, True)
    body_contexts = get_body_context_ids(ifcfile)
    if body_contexts:
        settings.set_context_ids(body_contexts)
    return settings


def get_geom_iterator(ifcfile, elements, brep):
    # This function can become pure IFC

    settings = get_settings(ifcfile, brep)
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=elements)
    if not iterator.initialize():
        print("  DEBUG: ifc_tools.get_geom_iterator: Invalid iterator")
        return None

    return iterator


def set_geometry(obj, elem, ifcfile, cached=False):
    """Sets the geometry of the given object
    obj: FreeCAD document object
    elem: IfcOpenShell ifc entity instance
    ifcfile: IfcOpenShell ifc file instance
    """

    if not obj or not elem or not ifcfile:
        return
    basenode = None
    colors = None
    if obj.ViewObject:
        # getChild(2) is master on/off switch,
        # getChild(0) is flatlines display mode
        # (1 = shaded, 2 = wireframe, 3 = points)
        basenode = obj.ViewObject.RootNode.getChild(2).getChild(0)
        if basenode.getNumChildren() == 5:
            # Part VP has 4 nodes, we have added 1 more
            basenode.removeChild(4)
    allspaces = all(
        [(not hasattr(ch, "Class") or ch.Class == "IfcSpace") for ch in obj.Group]
    )
    if obj.Group and not (has_representation(get_ifc_element(obj))) and not allspaces:
        # workaround for group extension bug: add a dummy placeholder shape)
        # otherwise a shape is force-created from the child shapes
        # and we don't want that otherwise we can't select children
        obj.Shape = Part.makeBox(1, 1, 1)
        colors = None
    elif obj.ShapeMode == "Shape":
        # set object shape
        shape, colors = get_shape([elem], ifcfile, cached)
        if shape is None:
            if not elem.is_a("IfcContext") and not elem.is_a(
                "IfcSpatialStructureElement"
            ):
                print(
                    "DEBUG: No Shape returned for object {}, {}, {}".format(
                        obj.StepId, obj.IfcClass, obj.Label
                    )
                )
        else:
            placement = shape.Placement
            obj.Shape = shape
            obj.Placement = placement
    elif basenode and obj.ShapeMode == "Coin":
        if obj.Group:
            # this is for objects that have own coin representation,
            # but shapes among their children and not taken by first if
            # case above. TODO do this more elegantly
            obj.Shape = Part.makeBox(1, 1, 1)
        # set coin representation
        node, colors, placement = get_coin([elem], ifcfile, cached)
        if node:
            basenode.addChild(node)
        if placement:
            obj.Placement = placement
    set_colors(obj, colors)


def set_attribute(ifcfile, element, attribute, value):
    """Sets the value of an attribute of an IFC element"""

    # This function can become pure IFC

    if attribute == "Class":
        if value != element.is_a():
            if value and value.startswith("Ifc"):
                cmd = "root.reassign_class"
                FreeCAD.Console.PrintLog(
                    "Changing IFC class value: "
                    + element.is_a()
                    + " to "
                    + str(value)
                    + "\n"
                )
                product = api_run(cmd, ifcfile, product=element, ifc_class=value)
                # TODO fix attributes
                return product
    cmd = "attribute.edit_attributes"
    attribs = {attribute: value}
    if hasattr(element, attribute):
        if getattr(element, attribute) != value:
            FreeCAD.Console.PrintLog(
                "Changing IFC attribute value of "
                + str(attribute)
                + ": "
                + str(value)
                + "\n"
            )
            api_run(cmd, ifcfile, product=element, attributes=attribs)
            return True
    return False


def set_colors(obj, colors):
    """Sets the given colors to an object"""

    if FreeCAD.GuiUp and colors:
        # ifcopenshell issues (-1,-1,-1) colors if not set
        if isinstance(colors[0], (tuple, list)):
            colors = [tuple([abs(d) for d in c]) for c in colors]
        else:
            colors = [abs(c) for c in colors]
        if hasattr(obj.ViewObject, "ShapeColor"):
            if isinstance(colors[0], (tuple, list)):
                obj.ViewObject.ShapeColor = colors[0][:3]
            else:
                obj.ViewObject.ShapeColor = colors[:3]
        if hasattr(obj.ViewObject, "DiffuseColor"):
            obj.ViewObject.DiffuseColor = colors


def get_body_context_ids(ifcfile):
    # This function can become pure IFC

    # Facetation is to accommodate broken Revit files
    # See https://forums.buildingsmart.org/t/suggestions-on-how-to-improve-clarity-of-representation-context-usage-in-documentation/3663/6?u=moult
    body_contexts = [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationSubContext")
        if c.ContextIdentifier in ["Body", "Facetation"]
    ]
    # Ideally, all representations should be in a subcontext, but some BIM apps don't do this
    # correctly
    body_contexts.extend(
        [
            c.id()
            for c in ifcfile.by_type(
                "IfcGeometricRepresentationContext", include_subtypes=False
            )
            if c.ContextType == "Model"
        ]
    )
    return body_contexts


def get_plan_contexts_ids(ifcfile):
    # This function can become pure IFC

    # Annotation is to accommodate broken Revit files
    # See https://github.com/Autodesk/revit-ifc/issues/187
    return [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationContext")
        if c.ContextType in ["Plan", "Annotation"]
    ]


def get_freecad_matrix(ios_matrix):
    """Converts an IfcOpenShell matrix tuple into a FreeCAD matrix"""

    # https://github.com/IfcOpenShell/IfcOpenShell/issues/1440
    # https://pythoncvc.net/?cat=203
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)


def get_ios_matrix(m):
    """Converts a FreeCAD placement or matrix into an IfcOpenShell matrix tuple"""

    if isinstance(m, FreeCAD.Placement):
        m = m.Matrix
    mat = [
        [m.A11, m.A12, m.A13, m.A14],
        [m.A21, m.A22, m.A23, m.A24],
        [m.A31, m.A32, m.A33, m.A34],
        [m.A41, m.A42, m.A42, m.A44],
    ]
    # apply rounding because OCCT often changes 1.0 to 0.99999999999 or something
    rmat = []
    for row in mat:
        rmat.append([round(e, ROUND) for e in row])
    return rmat


def set_placement(obj):
    """Updates the internal IFC placement according to the object placement"""

    # This function can become pure IFC

    ifcfile = get_ifcfile(obj)
    if not ifcfile:
        print("DEBUG: No ifc file for object", obj.Label, "Aborting")
    element = get_ifc_element(obj)
    placement = FreeCAD.Placement(obj.Placement)
    scale = ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    # the above lines yields meter -> file unit scale factor. We need mm
    scale = 0.001 / scale
    placement.Base = FreeCAD.Vector(placement.Base).multiply(scale)
    new_matrix = get_ios_matrix(placement)
    old_matrix = ifcopenshell.util.placement.get_local_placement(
        element.ObjectPlacement
    )
    # conversion from numpy array
    old_matrix = old_matrix.tolist()
    old_matrix = [[round(c, ROUND) for c in r] for r in old_matrix]
    if new_matrix != old_matrix:
        FreeCAD.Console.PrintLog(
            "IFC: placement changed for "
            + obj.Label
            + " old: "
            + str(old_matrix)
            + " new: "
            + str(new_matrix)
            + "\n"
        )
        api = "geometry.edit_object_placement"
        api_run(api, ifcfile, product=element, matrix=new_matrix, is_si=False)
        return True
    return False


def save_ifc(obj, filepath=None):
    """Saves the linked IFC file of a project, but does not mark it as saved"""

    if not filepath:
        if hasattr(obj, "FilePath") and obj.FilePath:
            filepath = obj.FilePath
    if filepath:
        ifcfile = get_ifcfile(obj)
        if not ifcfile:
            ifcfile = create_ifcfile()
        ifcfile.write(filepath)
        FreeCAD.Console.PrintMessage("Saved " + filepath + "\n")


def save(obj, filepath=None):
    """Saves the linked IFC file of a project and set its saved status"""

    save_ifc(obj, filepath)
    obj.Modified = False


def aggregate(obj, parent):
    """Takes any FreeCAD object and aggregates it to an existing IFC object"""

    if get_project(obj):
        FreeCAD.Console.PrintError("This object is already part of an IFC project\n")
        return
    proj = get_project(parent)
    if not proj:
        FreeCAD.Console.PrintError("The parent object is not part of an IFC project\n")
        return
    ifcfile = get_ifcfile(proj)
    product = get_ifc_element(obj)
    if product:
        # this object already has an associated IFC product
        print("DEBUG:", obj.Label, "is already an IFC object")
        newobj = obj
        new = False
    else:
        product = create_product(obj, parent, ifcfile)
        newobj = create_object(product, obj.Document, ifcfile, parent.ShapeMode)
        new = True
    create_relationship(obj, newobj, parent, product, ifcfile)
    base = getattr(obj, "Base", None)
    if base:
        # make sure the base is used only by this object before deleting
        if base.InList != [obj]:
            base = None
    delete = not (PARAMS.GetBool("KeepAggregated", False))
    if new and delete and base:
        obj.Document.removeObject(base.Name)
    label = obj.Label
    if new and delete:
        obj.Document.removeObject(obj.Name)
    newobj.Label = label  # to avoid 001-ing the Label...
    # TODO the line below should be done automatically when using the api to create products
    proj.Modified = True
    return newobj


def deaggregate(obj, parent):
    """Removes a FreeCAD object form its parent"""

    ifcfile = get_ifcfile(obj)
    element = get_ifc_element(obj)
    if not element:
        return
    api_run("aggregate.unassign_object", ifcfile, product=element)
    parent.Proxy.removeObject(parent, obj)


def create_product(obj, parent, ifcfile, ifcclass=None):
    """Creates an IFC product out of a FreeCAD object"""

    uid = ifcopenshell.guid.new()
    history = get_ifc_element(parent).OwnerHistory  # TODO should this be changed?
    name = obj.Label
    description = getattr(obj, "Description", "")

    # TEMPORARY use the Arch exporter
    # TODO this is temporary. We should rely on ifcopenshell for this with:
    # https://blenderbim.org/docs-python/autoapi/ifcopenshell/api/root/create_entity/index.html
    # a new FreeCAD 'engine' should be added to:
    # https://blenderbim.org/docs-python/autoapi/ifcopenshell/api/geometry/index.html
    # that should contain all typical use cases one could have to convert FreeCAD geometry
    # to IFC.

    # setup exporter - TODO do that in the module init
    exportIFC.clones = {}
    exportIFC.profiledefs = {}
    exportIFC.surfstyles = {}
    exportIFC.shapedefs = {}
    exportIFC.ifcopenshell = ifcopenshell
    try:
        exportIFC.ifcbin = exportIFCHelper.recycler(ifcfile, template=False)
    except:
        FreeCAD.Console.PrintError(
            "ERROR: You need a more recent version of FreeCAD >= 0.20.3\n"
        )
        return
    if not ifcclass:
        ifcclass = exportIFC.getIfcTypeFromObj(obj)
    prefs, context = get_export_preferences(ifcfile)
    # TODO migrate this to ifcopenshell api
    representation, placement, shapetype = exportIFC.getRepresentation(
        ifcfile, context, obj, preferences=prefs
    )
    product = exportIFC.createProduct(
        ifcfile,
        obj,
        ifcclass,
        uid,
        history,
        name,
        description,
        placement,
        representation,
        prefs,
    )
    # TODO use api to create a product: ifcopenshell.api.run("root.create_entity", self.file, ifc_class="IfcWall")
    # product = ifcopenshell.api.run("root.create_entity", ifcfile, ifc_class=ifcclass, name=obj.Label)
    # product.ObjectPlacement = placement
    # product.Description = getattr(obj, "Description", "")
    # ifcopenshell.api.run("geometry.assign_representation", ifcfile, product=product, representation=representation)
    return product


def get_export_preferences(ifcfile):
    """returns a preferences dict for exportIFC"""

    prefs = exportIFC.getPreferences()
    prefs["SCHEMA"] = ifcfile.wrapped_data.schema_name()
    s = ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    # the above lines yields meter -> file unit scale factor. We need mm
    prefs["SCALE_FACTOR"] = 0.001 / s
    context = ifcfile[
        get_body_context_ids(ifcfile)[-1]
    ]  # TODO should this be different?
    return prefs, context


def get_subvolume(obj):
    """returns a subface + subvolume from a window object"""

    tempface = None
    tempobj = None
    subvolume = None
    if hasattr(obj, "Proxy") and hasattr(obj.Proxy, "getSubVolume"):
        tempshape = obj.Proxy.getSubVolume(obj)
    elif hasattr(obj, "Subvolume") and obj.Subvolume:
        tempshape = obj.Subvolume
    if subvolume:
        if len(tempshape.Faces) == 6:
            # We assume the standard output of ArchWindows
            faces = sorted(tempshape.Faces, key=lambda f: f.CenterOfMass.z)
            baseface = faces[0]
            ext = faces[-1].CenterOfMass.sub(faces[0].CenterOfMass)
            tempface = obj.Document.addObject("Part::Feature", "BaseFace")
            tempface.Shape = baseface
            tempobj = obj.Document.addObject("Part::Extrusion", "Opening")
            tempobj.Base = tempface
            tempobj.DirMode = "Custom"
            tempobj.Dir = FreeCAD.Vector(ext).normalize()
            tempobj.LengthFwd = ext.Length
        else:
            tempobj = obj.Document.addObject("Part::Feature", "Opening")
            tempobj.Shape = tempshape
    return tempface, tempobj


def create_relationship(old_obj, obj, parent, element, ifcfile):
    """Creates a relationship between an IFC object and a parent IFC object"""

    parent_element = get_ifc_element(parent)
    # case 1: element inside spatiual structure
    if parent_element.is_a("IfcSpatialStructureElement") and element.is_a("IfcElement"):
        api_run("spatial.unassign_container", ifcfile, product=element)
        uprel = api_run(
            "spatial.assign_container",
            ifcfile,
            product=element,
            relating_structure=parent_element,
        )
    # case 2: dooe/window inside element
    # https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/annex/annex-e/wall-with-opening-and-window.htm
    elif parent_element.is_a("IfcElement") and element.is_a() in [
        "IfcDoor",
        "IfcWindow",
    ]:
        tempface, tempobj = get_subvolume(old_obj)
        if tempobj:
            opening = create_product(tempobj, parent, ifcfile, "IfcOpeningElement")
            old_obj.Document.removeObject(tempobj.Name)
            if tempface:
                old_obj.Document.removeObject(tempface.Name)
            api_run(
                "void.add_opening", ifcfile, opening=opening, element=parent_element
            )
            api_run("void.add_filling", ifcfile, opening=opening, element=element)
        # windows must also be part of a spatial container
        api_run("spatial.unassign_container", ifcfile, product=element)
        if parent_element.ContainedInStructure:
            container = parent_element.ContainedInStructure[0].RelatingStructure
            uprel = api_run(
                "spatial.assign_container",
                ifcfile,
                product=element,
                relating_structure=container,
            )
        elif parent_element.Decomposes:
            container = parent_element.Decomposes[0].RelatingObject
            uprel = api_run(
                "aggregate.assign_object",
                ifcfile,
                product=element,
                relating_object=container,
            )
    # case 3: element aggregated inside other element
    else:
        api_run("aggregate.unassign_object", ifcfile, product=element)
        uprel = api_run(
            "aggregate.assign_object",
            ifcfile,
            product=element,
            relating_object=parent_element,
        )
    parent.Proxy.addObject(parent, obj)
    return uprel


def get_elem_attribs(ifcentity):
    # This function can become pure IFC

    # usually info_ifcentity = ifcentity.get_info() would de the trick
    # the above could raise an unhandled excption on corrupted ifc files
    # in IfcOpenShell
    # see https://github.com/IfcOpenShell/IfcOpenShell/issues/2811
    # thus workaround

    info_ifcentity = {"id": ifcentity.id(), "class": ifcentity.is_a()}

    # get attrib keys
    attribs = []
    for anumber in range(20):
        try:
            attr = ifcentity.attribute_name(anumber)
        except Exception:
            break
        # print(attr)
        attribs.append(attr)

    # get attrib values
    for attr in attribs:
        try:
            value = getattr(ifcentity, attr)
        except Exception as e:
            # print(e)
            value = "Error: {}".format(e)
            print(
                "DEBUG: The entity #{} has a problem on attribute {}: {}".format(
                    ifcentity.id(), attr, e
                )
            )
        # print(value)
        info_ifcentity[attr] = value

    return info_ifcentity


def migrate_schema(ifcfile, schema):
    """migrates a file to a new schema"""

    # This function can become pure IFC

    newfile = ifcopenshell.file(schema=schema)
    migrator = ifcopenshell.util.schema.Migrator()
    table = {}
    for entity in ifcfile:
        new_entity = migrator.migrate(entity, newfile)
        table[entity.id()] = new_entity.id()
    return newfile, table


def remove_ifc_element(obj):
    """removes the IFC data associated with an object"""

    # This function can become pure IFC

    ifcfile = get_ifcfile(obj)
    element = get_ifc_element(obj)
    if ifcfile and element:
        api_run("root.remove_product", ifcfile, product=element)
        return True
    return False


def get_orphan_elements(ifcfile):
    """returns a list of orphan products in an ifcfile"""

    products = ifcfile.by_type("IfcElement")
    products = [p for p in products if not p.Decomposes]
    products = [p for p in products if not p.ContainedInStructure]
    products = [
        p for p in products if not hasattr(p, "VoidsElements") or not p.VoidsElements
    ]
    return products


def get_group(project, name):
    """returns a group of the given type under the given IFC project. Creates it if needed"""

    for c in project.Group:
        if c.isDerivedFrom("App::DocumentObjectGroupPython"):
            if c.Name == name:
                return c
    group = add_object(project.Document, otype="group", oname=name)
    group.Label = name.strip("Ifc").strip("Group")
    if FreeCAD.GuiUp:
        group.ViewObject.ShowInTree = PARAMS.GetBool("ShowDataGroups", False)
    project.Proxy.addObject(project, group)
    return group


def load_orphans(obj):
    """loads orphan objects from the given project object"""

    doc = obj.Document
    ifcfile = get_ifcfile(obj)
    shapemode = obj.ShapeMode
    elements = get_orphan_elements(ifcfile)
    if elements:
        group = get_group(obj, "IfcOrphansGroup")
        for element in elements:
            child = create_object(element, doc, ifcfile, shapemode)
            group.addObject(child)


def has_psets(obj):
    """Returns True if an object has attached psets"""

    element = get_ifc_element(obj)
    psets = getattr(element, "IsDefinedBy", [])
    if [p for p in psets if p.is_a("IfcRelDefinesByProperties")]:
        # TODO verify too if these psets are not already there
        return True
    return False


def get_psets(element):
    """Returns a dictionary of dictionaries representing the
    properties of an element in the form:
    { pset_name : { property_name : IfcType(value), ... }, ... }"""

    result = {}
    psets = getattr(element, "IsDefinedBy", [])
    psets = [p for p in psets if p.is_a("IfcRelDefinesByProperties")]
    psets = [p.RelatingPropertyDefinition for p in psets]
    for pset in psets:
        pset_dict = {}
        if pset.is_a("IfcPropertySet"):
            for prop in pset.HasProperties:
                pset_dict[prop.Name] = str(prop.NominalValue)
        elif pset.is_a("IfcElementQuantity"):
            # TODO implement quantities
            pass
        if pset_dict:
            result[pset.Name] = pset_dict
    return result


def get_pset(psetname, element):
    """Returns an IfcPropertySet with the given name"""

    psets = getattr(element, "IsDefinedBy", [])
    psets = [p for p in psets if p.is_a("IfcRelDefinesByProperties")]
    for p in psets:
        pset = p.RelatingPropertyDefinition
        if pset.Name == psetname:
            return pset
    return None


def show_psets(obj):
    """Shows the psets attached to the given object as properties"""

    element = get_ifc_element(obj)
    if not element:
        return
    psets = get_psets(element)
    for gname, pset in psets.items():
        for pname, pvalue in pset.items():
            oname = pname
            ptype, value = pvalue.split("(", 1)
            value = value.strip(")")
            value = value.strip("'")
            pname = re.sub("[^0-9a-zA-Z]+", "", pname)
            if pname[0].isdigit():
                pname = "_" + pname
            ttip = (
                ptype + ":" + oname
            )  # setting IfcType:PropName as a tooltip to desambiguate
            while pname in obj.PropertiesList:
                # print("DEBUG: property", pname, "(", value, ") already exists in", obj.Label)
                pname += "_"
            if ptype in [
                "IfcPositiveLengthMeasure",
                "IfcLengthMeasure",
                "IfcNonNegativeLengthMeasure",
            ]:
                obj.addProperty("App::PropertyDistance", pname, gname, ttip)
            elif ptype in ["IfcVolumeMeasure"]:
                obj.addProperty("App::PropertyVolume", pname, gname, ttip)
            elif ptype in ["IfcPositivePlaneAngleMeasure", "IfcPlaneAngleMeasure"]:
                obj.addProperty("App::PropertyAngle", pname, gname, ttip)
            elif ptype in ["IfcMassMeasure"]:
                obj.addProperty("App::PropertyMass", pname, gname, ttip)
            elif ptype in ["IfcAreaMeasure"]:
                obj.addProperty("App::PropertyArea", pname, gname, ttip)
            elif ptype in ["IfcCountMeasure", "IfcInteger"]:
                obj.addProperty("App::PropertyInteger", pname, gname, ttip)
                value = int(value.strip("."))
            elif ptype in ["IfcReal"]:
                obj.addProperty("App::PropertyFloat", pname, gname, ttip)
                value = float(value)
            elif ptype in ["IfcBoolean", "IfcLogical"]:
                obj.addProperty("App::PropertyBool", pname, gname, ttip)
                if value in [".T."]:
                    value = True
                else:
                    value = False
            elif ptype in [
                "IfcDateTime",
                "IfcDate",
                "IfcTime",
                "IfcDuration",
                "IfcTimeStamp",
            ]:
                obj.addProperty("App::PropertyTime", pname, gname, ttip)
            else:
                obj.addProperty("App::PropertyString", pname, gname, ttip)
            # print("DEBUG: setting",pname, ptype, value)
            setattr(obj, pname, value)


def edit_pset(obj, prop, value=None):
    """Edits the corresponding property"""

    pset = obj.getGroupOfProperty(prop)
    ttip = obj.getDocumentationOfProperty(prop)
    if value is None:
        value = getattr(obj, prop)
    ifcfile = get_ifcfile(obj)
    element = get_ifc_element(obj)
    pset_exist = get_psets(element)
    if ttip.startswith("Ifc") and ":" in ttip:
        target_prop = ttip.split(":", 1)[-1]
    else:
        # no tooltip set - try to build a name
        prop = prop.rstrip("_")
        prop_uncamel = re.sub(r"(\w)([A-Z])", r"\1 \2", prop)
        prop_unslash = re.sub(r"(\w)([A-Z])", r"\1\/\2", prop)
        target_prop = None
    if pset in pset_exist:
        if not target_prop:
            if prop in pset_exist[pset]:
                target_prop = prop
            elif prop_uncamel in pset_exist[pset]:
                target_prop = prop_uncamel
            elif prop_unslash in pset_exist[pset]:
                target_prop = prop_unslash
        if target_prop:
            value_exist = pset_exist[pset][target_prop].split("(", 1)[1][:-1].strip("'")
            if value_exist in [".F.", ".U."]:
                value_exist = False
            elif value_exist in [".T."]:
                value_exist = True
            elif isinstance(value, int):
                value_exist = int(value_exist.strip("."))
            elif isinstance(value, float):
                value_exist = float(value_exist)
            elif isinstance(value, FreeCAD.Units.Quantity):
                value_exist = FreeCAD.Units.Quantity(float(value_exist), value.Unit)
            if value == value_exist:
                return False
            else:
                FreeCAD.Console.PrintLog(
                    "IFC: property changed for "
                    + obj.Label
                    + " ("
                    + str(obj.StepId)
                    + ") : "
                    + target_prop
                    + " : "
                    + str(value)
                    + " ("
                    + type(value)
                    + ") -> "
                    + str(value_exist)
                    + " ("
                    + type(value_exist)
                    + ")\n"
                )
        pset = get_pset(pset, element)
    else:
        pset = api_run("pset.add_pset", ifcfile, product=element, name=pset)
    if not target_prop:
        target_prop = prop
    api_run("pset.edit_pset", ifcfile, pset=pset, properties={target_prop: value})
    # TODO manage quantities
    return True


def load_psets(obj):
    """Recursively loads psets of child objects"""

    show_psets(obj)
    for child in obj.Group:
        load_psets(child)


def load_materials(obj):
    """Recursively loads materials of child objects"""

    show_material(obj)
    for child in obj.Group:
        load_materials(child)
