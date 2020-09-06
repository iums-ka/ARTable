import time

import numpy as np

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
import energy_app.dynamic_ui as ui


class TestAreaListener(ArucoAreaListener):
    def __init__(self, area, ids, ar):
        super().__init__(area, ids)
        self.table = ar

    def on_enter(self, marker_id, position):
        print("Marker {} entered at {}".format(marker_id, self.table.table_to_image_coords(position)))

    def on_leave(self, marker_id, last_position):
        print("Marker {} left at {}".format(marker_id, self.table.table_to_image_coords(last_position)))

    def on_move(self, marker_id, last_position, position):
        print("Marker {} moved from {} to {}".format(marker_id, self.table.table_to_image_coords(last_position),
                                                     self.table.table_to_image_coords(position)))

print("start",time.time())
table = ARTable(Configuration("config.json"))
print("render",time.time())
image = ui.render_default()
print("show",time.time())
table.display(image)
print("done",time.time())
aruco = Aruco()
table.add_plugin(aruco)
aruco.add_listener(TestAreaListener(table.image_to_table_coords(((362, 173), (2783, 2410))), (4,), table))
