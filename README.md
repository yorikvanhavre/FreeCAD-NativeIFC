## BlenderBIM addon for FreeCAD

This is a preliminary stub to integrate [BlenderBIM](https://blenderbim.org) 
into FreeCAD. The final goal is to offer in FreeCAD the same level of 
functionality found in BlenderBIM.

### Roadmap

#### Get a working concept up

* [x] Write an importer that allows an initial import of an IFC file into FreeCAD
* [x] Write a custom parametric FreeCAD object that represents an IFC document in the FreeCAD tree
* [x] Do an initial geometry import
* [ ] Write a custom parametric FreeCAD object that represents in IFC product in the FreeCAD tree
* [ ] Allow to expand a document (reveal its children in FreeCAD in the FreeCAD tree)
* [ ] Write a hook system that allows FreeCAD to save the IFC document
* [ ] Test what happens when opening a bb file in vanilla FreeCAD

### Installation & Usage

#### Auto install

*The advantage of this approach is the ability to update FreeCAD-BlenderBIM workbench via the addon manager.* 

* Open the [Addon Manager preferences](https://wiki.freecad.org/Preferences_Editor#Addon_Manager) via `Edit` → `Preferences` → `Addon Manager` → `Custom Repositories`
* Add `https://github.com/yorikvanhavre/FreeCAD-BlenderBIM` to `Custom Repositories` list and press `OK`.
* Start the `Tools` → `Addon Manager` which will automatically find FreeCAD-BlenderBIM addon in the workbench list. 
* Install FreeCAD-BlenderBIM addon  
* Restart FreeCAD  
**Result:** FreeCAD-BlenderBIM IFC importer should be available in open/insert file dialogs


#### Manual install

* Navigate to your FreeCAD Mods folder (`~/.local/share/FreeCAD/Mods`)
* Clone this repo there: `git clone https://github.com/yorikvanhavre/FreeCAD-BlenderBIM.git`
* Restart FreeCAD  
**Result:** FreeCAD-BlenderBIM IFC importer should be available in open/insert file dialogs

#### To test

* Run FreeCAD
* `File` → `Open` or `File` → `Insert`, select an IFC file
* Select the BlenderBIM importer (bb_import)
* A FreeCAD document is created
* An object is created representing the IFC root document + project

### Notes

#### Documentation

* [IfcOpenShell github](https://github.com/IfcOpenShell/IfcOpenShell)
* [IfcOpenShell docs](https://blenderbim.org/docs-python/ifcopenshell.html)
* [BlenderBIM docs](https://blenderbim.org/docs/)

#### Code examples

Initial import + getting the main file structure

```python
import ifcopenshell
f = ifcopenshel.open("IfcOpenHouse.ifc")
p = f.by_type("IfcProject")[0]
# get descendents (site, building, and everything inside)
d = ifcopenshell.util.element.get_decomposition(p)
```

Using the geometry iterator

```python
import multicore
settings = ifcopenshell.geom.settings()
settings.set(settings.DISABLE_TRIANGULATION, True)
settings.set(settings.USE_BREP_DATA,True)
settings.set(settings.SEW_SHELLS,True)
settings.set(settings.USE_WORLD_COORDS,True)
settings.set(settings.APPLY_LAYERSETS,True)
shapes = []
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
    if not iterator.next():
        break
compound = Part.makeCompound(shapes)
```

schependomlaan.ifc of 47Mb imports in 23s
