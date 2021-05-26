# ARTable
Interactive Projection Framework based on Katze.

## Concept
The ARTable Class handles all the calibrating and displaying. It can 
communicate with plugins that in turn may provide an interface to attach
listeners to.

## Usage
To use the ARTable, you need to create a configuration file containing
data about the table, camera and projector. Then you load the file into
a Configuration class and create an ARTable using it. 

Now you can add Plugins, respecting their individual setup instructions
and display Images on the table using the display command.


### Config
The root object must contain the following entries:
* `table` : An object containing the table configuration:
  * `width` : The width of the table in mm.
  * `height` : The height of the table in mm.
  * `marker` : An object containing information about the markers on the table:
    * `size` : The size of the markers in mm.
    * `marker` : A list of the ids of the markers on the table. Clockwise starting from the top left corner.
    * `position` : A list of the four corner-markers positions on the table:
      * `[x,y]` , where `x` is the horizontal (and `y` the vertical) distance from the corresponding border in mm.
* `projector` : An object containing the projector's configuration:
  * `width` : The width of the projector in pixels.
  * `height` : The height of the projector in pixels.
  * `screen` : The index of the screen used for the projector.
  * `marker` : An object containing information about the markers on the table:  
    * `size` : The size of the markers in pixels
    * `marker` : A list of the ids of the markers to use for calibration. Should not overlap with physical markers.
    * `position` : A list of the marker's positions on the table:
      * `[x,y]` , where `x` is the horizontal (and `y` the vertical) distance from the corresponding border in mm.
* `camera` : An object containing the camera's configuration:
  * `index` : The index of the camera to be used. `0` is a good guess.

# Plugins
You can find more information about Plugins in their directories.
A plugin can access camera data and table transforms. 
It is activated through calling `add_plugin()` on the table object before calling `start()`.