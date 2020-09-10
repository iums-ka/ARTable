import json
import time
from threading import Thread

import numpy as np

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
from energy_app.dynamic_ui import UI
from energy_app.dynamic_ui import find_bounds_for_name as find
from queue import LifoQueue


class MapListener(ArucoAreaListener):
    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui

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
        insolation = self.ui.get_insolation(pos)
        if insolation is not None:
            additional_energy = (insolation - 1100) / 100
            queue.put(None)  # call for update


class PlaceListener(ArucoAreaListener):
    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        config = json.load(open("resources/shortcut_places.json", mode="r", encoding="utf-8"))
        self.keyboard_id = config["keyboard"]
        self.places = config["places"]

    def on_enter(self, marker_id, position):
        if marker_id != self.keyboard_id:
            self.set_place(marker_id)

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass

    def set_place(self, marker_id):
        global place_name, place_population, place_energy
        for place in self.places:
            if place["marker"] == marker_id:
                ui.set_position(place["bounds"], zoom_in=0)
                place_name, place_population, place_energy =place["name"],place["population"],place["energy"]
        queue.put(None)  # call for update


def update_table():
    # print("Coverage: {:3f}".format(.5 + additional_energy))
    image = ui.render(place_name, place_population, place_energy, .5 + additional_energy, .5, .5, .7, .7, .7)
    table.display(image)


ui = UI()
place_name = "Baden-Württemberg"
place_population = 1
place_energy = 1
bounds = find(place_name)
ui.set_position(bounds)
additional_energy = 0
table = ARTable(Configuration("config.json"))
aruco = Aruco()
table.add_plugin(aruco)
update_table()
aruco.add_listener(MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), (4,), table, ui))
aruco.add_listener(PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), (4, 10,), table, ui))
table.start()
queue = LifoQueue()
while True:
    queue.get(block=True)
    update_table()
