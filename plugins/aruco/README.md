# ArUco Plugin ARTable
The ArUco Plugin is made use of through listeners. Those listeners are classes following a certain scheme, 
which get notified whenever there is an update to the markers on the table.

## Usage
To enable the Plugin, use the following lines:
```python
from artable import ARTable, Configuration
from artable.plugins import Aruco

table = ARTable(Configuration("table.json"))
aruco = Aruco()
table.add_plugin(aruco)
table.start()
```

Here is an example for adding a simple listener, that will listen for markers 1 and 2 and print out
their positions if within the top left corner of the table:
```python
from artable.plugins import Aruco, ArucoAreaListener
class SimpleAreaListener(ArucoAreaListener):
    def __init__(self):
        super().__init__([0,0,100,100], [1,2])

    def on_enter(self, marker_id, position):
        print("marker", marker_id ,"entered top left corner at", position)

    def on_move(self, marker_id, last_position, position):
        print("marker", marker_id ,"moved to", position)

    def on_leave(self, marker_id, last_position):
        print("marker", marker_id ,"left top left corner. Last seen at", last_position)


aruco = Aruco()
example_listener = SimpleAreaListener()
aruco.add_listener(example_listener)
```

# Reference

## Aruco
The main plugin, responsible for detecting markers.
### `Aruco([marker_dict])`
The Constructor.
* `marker_dict` : The type of markers to detect. Can be set either as string (e.g. `"DICT_6X6_250"`) or directly as 
  a constant of `cv2.aruco` (e.g. `aruco.DICT_5X5_100`). Default: `DICT_4X4_250`
### `add_listener(listener)`
### `remove_listener(listener)`
## ArucoListenerBase
The base class of all ArUco listeners. 
### `update(marker_ids, positions):`
Abstract method called by the plugin to be reimplemented.
* `marker_ids` : List of all detected markers
* `positions` : List of the corresponding positions on the table
## ArucoAreaListener
A listener detecting markers in an area.
### `ArucoAreaListener(area, [ids, delta=5, time_threshold=2])`
The Constructor.
* `area` : The area to observe in table coordinates [x1,y1,x2,y2]
* `ids` : Marker IDs to observe. Default value: empty list.
* `delta` : How much a marker has to move, in order to be classified as moving.
  Default value: 5.
* `time_threshold` : How many seconds a marker has to not be detected, in order to be classified as left.
  Default value: 2.
### `set_ids(ids)`
Updates the marker ids to be observed.
* `ids` : Marker ids to observe.
### `on_enter(marker_id, position)`
Abstract method called when a marker was newly detected inside the observed area.
* `marker_id` : ID of the detected marker.
* `position` : Table coordinates of the marker.
### `on_leave(marker_id, last_position)`
Abstract method called when a marker that had entered before,
was not detected inside the observed area for `time_threshold` seconds.
* `marker_id` : ID of the marker that has left.
* `last_position` : Table coordinates of the marker before it left.
### `on_move(marker_id, last_position, position)`
Abstract method called when a marker was detected in the observed area
at least `delta` away from the last position it was detected at.
* `marker_id` : ID of the marker that has been moved.
* `last_position` : Old table coordinates of the marker.
* `position` : New table coordinates of the marker.
