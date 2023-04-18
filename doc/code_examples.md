# IfcOpenShell Code examples

### Initial import + getting the main file structure

```python
import ifcopenshell
ifcfile = ifcopenshell.open("IfcOpenHouse.ifc")
project = ifcfile.by_type("IfcProject")[0]
# get descendants (site, building, and everything inside)
entitieslist = ifcopenshell.util.element.get_decomposition(project)
```

### Using the geometry iterator

```python
from ifcopenshell import geom
import multiprocessing
settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_TRIANGULATION, True)
settings.set(settings.USE_BREP_DATA,True)
settings.set(settings.SEW_SHELLS,True)
settings.set(settings.USE_WORLD_COORDS,True)
settings.set(settings.APPLY_LAYERSETS,True)
shapes = []
colors = []
cores = multiprocessing.cpu_count()-2
iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=entitieslist)
iterator.initialize()
while True:
    item = iterator.get()
    if item:
        ifcproduct = ifcfile.by_id(item.guid)
        brep = item.geometry.brep_data
        shape = Part.Shape()
        shape.importBrepFromString(brep, False)
        shape.scale(1000.0) # IfcOpenShell outputs in meters
        shapes.append(shape)
        colors.append(item.geometry.surface_styles)
    if not iterator.next():
        break
compound = Part.makeCompound(shapes)
```

### Change a parameter of an object

```python
cmd = 'attribute.edit_attributes'
prod = ifcfile.by_type("IfcWall")[0]
attribs = {"Name": "Foo"}
ifcopenshell.api.run(cmd, ifcfile, product=prod, attributes=attribs)
```

### Working with classes and types

```python
# getting supertypes for types
>>> ifcopenshell.util.type.get_applicable_types("IfcWall")
['IfcWallType']
>>> ifcopenshell.util.type.get_applicable_entities("IfcWallType")
['IfcWall', 'IfcWallElementedCase', 'IfcWallStandardCase']
```

### Working with schema classes

```python
schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name('IFC4')
declaration = schema.declaration_by_name('IfcWall')
print(declaration.supertype())
for subtype in declaration.supertype().subtypes():
    print(subtype.name())
```

### Working with documentation

```python
entdoc = ifcopenshell.util.doc.get_entity_doc("IFC4","IfcWall")
entdoc.keys() # 'description', 'predefined_types', 'spec_url', 'attributes'
entdoc['attributes']['IsDefinedBy']
# gives the same result as
ifcopenshell.util.doc.get_attribute_doc("IFC4","IfcWall","IsDefinedBy")
# 'Set of relationships to the object type that provides the type definitions
# for this object occurrence. The then associated _IfcTypeObject_, or its subtypes,
# contains the specific information (or type, or style), that is common to all
# instances of _IfcObject_, or its subtypes, referring to the same type.'
```

### Change class

```python
>>> f=ifcopenshell.open("IfcOpenHouse.ifc")
>>> w=f.by_type("IfcWall")[0]
>>> w
#40=IfcWallStandardCase('1TGeFqjqb3$xFeUl92Fwvi',#5,'South wall',$,$,#61,#43,$)
>>> ifcopenshell.util.schema.reassign_class(f,w,"IfcBeam")
#2746=IfcBeam('1TGeFqjqb3$xFeUl92Fwvi',#5,'South wall',$,$,#61,#43,$)
>>> f.write("IfcOpenHouse2.ifc")
```
