# Tangible2Mouse
This app is used to map a part of the screen 
to the ARTable and provide mouse interactions.

# Configuration

## table.json
Configuration for ARTable. See ARTable documentation.

## config.json
* `keys` : Object defining global shortcuts.
    * `update` : Shortcut to manually move the mouse to the 
      tangible's position.
    * `toggle` : Shortcut to toggle auto updating the mouse.
    * `reload` : Shortcut to reload the config file.
* `tangibles` : Object defining ids for mouse actions.
    * `hover` : ID for no action, only move.
    * `leftclick` : ID for left-clicking.
    * `doubleclick` :  ID for double-clicking (left).
    * `rightclick` : ID for right-clicking.
    * `middleclick` : ID for middle-clicking.
    * `drag` : ID for holding down left mouse button while visible.
* `screen_area` : [x,y,w,h] to select the displayed screen area. 
* `action_delay` : Seconds to wait for potential user-re-decision
  before performing actions. 

Example:
```json
{
  "keys": {
    "update": "g",
    "toggle": "<shift>+g",
    "reload": "<ctrl>+r"
  },
  "tangibles": {
    "hover": 7,
    "leftclick": 10,
    "doubleclick": 11,
    "rightclick": 12,
    "middleclick": 13,
    "drag": 14
  },
  "screen_area": [0,0,1920,1080],
  "action_delay": 2
}
```