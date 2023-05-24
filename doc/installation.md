# Installation of the NativeIFC addon

These instructions are temporary. The NativeIFC add-on is meant to be integrated later on with the BIM workbench

### Prerequisites

The NativeIFC add-on will install and work with any version of FreeCAD and will allow to open and inspect IFC files. However, to create new IFC objects, you will need a FreeCAD version above or equal to 0.20.3. The NativeIFC add-on also requires [IfcOpenShell](http://ifcopenshell.org/) installed. IfcOpenShell might [already be installed](https://wiki.freecad.org/Arch_IFC) with your version of FreeCAD.

### Auto install

The advantage of this approach is the ability to update FreeCAD-BlenderBIM workbench via the add-on manager.

* Open the [Addon Manager preferences](https://wiki.freecad.org/Preferences_Editor#Addon_Manager) via `Edit` → `Preferences` → `Addon Manager` → `Custom Repositories`
* Add `https://github.com/yorikvanhavre/FreeCAD-NativeIFC` to `Custom Repositories` list. In the `Branch` section indicate the `main` branch. Press `OK`.
* Start the `Tools` → `Addon Manager` which will automatically find FreeCAD-NativeIFC add-on in the workbench list.
* Install FreeCAD-NativeIFC add-on
* Restart FreeCAD

### Manual install

* Navigate to your FreeCAD Mods folder (`~/.local/share/FreeCAD/Mods`)
* Clone this repo there: `git clone https://github.com/yorikvanhavre/FreeCAD-NativeIFC.git`
* Restart FreeCAD

### Check if installation was successful

* FreeCAD-NativeIFC importer should be available in open/insert file dialogs
* The Project tool in the [BIM Workbench](https://github.com/yorikvanhavre/BIM_Workbench) shows an IFC icon
