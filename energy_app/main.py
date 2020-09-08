import time
from threading import Thread

import numpy as np

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
from energy_app.dynamic_ui import UI
import energy_app.dynamic_ui as dyn
from energy_app.dynamic_ui import find_bounds_for_name as find
from queue import LifoQueue

class MapListener(ArucoAreaListener):
    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.runner = None

    def on_enter(self, marker_id, position):
        self.set_insolation(position)

    def on_move(self, marker_id, last_position, position):
        self.set_insolation(position)

    def on_leave(self, marker_id, last_position):
        global additional_energy
        additional_energy = 0

    def set_insolation(self, position):
        global additional_energy
        pos = self.table.table_to_image_coords(position)
        additional_energy = (self.ui.get_insolation(pos) - 1100)/100
        queue.put(None)  # call for update

def update_table():
    # print("Coverage: {:3f}".format(.5 + additional_energy))
    image = ui.render("Baden-Württemberg", 1, 1, .5 + additional_energy, .5, .5, .7, .7, .7)
    table.display(image)

ui = UI()
bounds = find("Baden-Württemberg")
ui.set_position(bounds)
additional_energy = 0
table = ARTable(Configuration("config.json"))
aruco = Aruco()
table.add_plugin(aruco)
update_table()
aruco.add_listener(MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), (4,), table, ui))
queue = LifoQueue()
while True:
    queue.get(block=True)
    update_table()
