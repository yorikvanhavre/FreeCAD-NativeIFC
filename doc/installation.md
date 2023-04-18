# Installation of the NativeIFC addon

These instructions are temporary. The NativeIFC addon is meant to be integrated later on with the BIM workbench

### Auto install

The advantage of this approach is the ability to update FreeCAD-BlenderBIM workbench via the addon manager.

* Open the [Addon Manager preferences](https://wiki.freecad.org/Preferences_Editor#Addon_Manager) via `Edit` → `Preferences` → `Addon Manager` → `Custom Repositories`
* Add `https://github.com/yorikvanhavre/FreeCAD-NativeIFC` to `Custom Repositories` list. In the `Branch` section indicate the `main` branch. Press `OK`.
* Start the `Tools` → `Addon Manager` which will automatically find FreeCAD-NativeIFC addon in the workbench list.
* Install FreeCAD-NativeIFC addon
* Restart FreeCAD

**Result:** FreeCAD-NativeIFC importer should be available in open/insert file dialogs

### Manual install

* Navigate to your FreeCAD Mods folder (`~/.local/share/FreeCAD/Mods`)
* Clone this repo there: `git clone https://github.com/yorikvanhavre/FreeCAD-NativeIFC.git`
* Restart FreeCAD

**Result:** FreeCAD-NativeIFC importer should be available in open/insert file dialogs


