# Printed Energy App
This app is the interface between the simulation, and a map on paper.

# Configuration

## table.json
Configuration for ARTable. See ARTable documentation.

## config.json
* `keys` : Object defining global shortcuts.
    * `reload` : Shortcut to reload the config file.
* `tangibles` : Object defining ids for mouse actions.
    * `perspective` : ID for perspective selection tangible.
    * `layer` : ID for layer selection tangible. Can be the same as for perspective.
* `map_bounds` : [lon_min, lat_min, lon_max, lat_max] area of the world visible on the map. 
* `field_size` : [w,h] Size of the control fields in mm.
* `field_positions` : [x,y] Top left corner of the corresponding field.
    * `overview`
    * `bird`
    * `normal`
    * `frog`
    * `detail`
    * `areas`
    * `noise`

Example:
```json
{
  "keys": {
    "reload": "<ctrl>+r"
  },
  "tangibles": {
    "perspective": 10,
    "layer": 11
  },
  "map_bounds": [8.2881, 48.96465, 8.51503, 49.0700],
  "field_size": [280, 280],
  "field_positions": {
    "overview": [536, 2227],
    "bird": [861, 2227],
    "normal": [1189, 2227],
    "frog": [1518, 2227],
    "detail": [1844, 2227],
    "areas": [536, 2810],
    "noise": [1518, 2810]
  }
}
```

## resources/plant_types.json
Same as for Energy App.