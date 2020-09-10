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
        self.energy = {}
        self.cost = {}
        self.emission = {}
        self.plants = {}
        config = json.load(open("resources/plant_types.json", mode="r", encoding="utf-8"))
        for plant in config["types"]:
            self.plants[plant["marker"]] = plant

    def on_enter(self, marker_id, position):
        self.update_energy(marker_id, position)

    def on_move(self, marker_id, last_position, position):
        self.update_energy(marker_id, position)

    def on_leave(self, marker_id, last_position):
        self.energy.pop(marker_id)
        self.cost.pop(marker_id)
        self.emission.pop(marker_id)
        self.sum_and_update()

    def update_energy(self, marker_id, position):
        plant = self.plants[marker_id]
        pos = self.table.table_to_image_coords(position)
        energy = 0
        if plant["type"] == "solar":
            energy = self.ui.get_insolation(pos)
        if plant["type"] == "wind":
            energy = self.ui.get_wind(pos)
        if energy is not None:
            self.energy[marker_id] = eval(plant["energy_formula"], {'datapoint': energy})
            self.emission[marker_id] = plant["emission"]
            self.cost[marker_id] = plant["cost"]
            self.sum_and_update()

    def sum_and_update(self):
        global additional_energy, additional_emission, additional_cost
        additional_energy = 0
        additional_emission = 0
        additional_cost = 0
        for energy, emission, cost in zip(self.energy.values(), self.emission.values(), self.cost.values()):
            additional_energy = additional_energy + energy
            additional_emission = additional_emission + emission
            additional_cost = additional_cost + cost
        queue.put(None)  # call for update


class PlaceListener(ArucoAreaListener):
    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        config = json.load(open("resources/shortcut_places.json", mode="r", encoding="utf-8"))
        self.keyboard_id = config["keyboard"]
        self.places = {}
        for place in config["places"]:
            self.places[place["marker"]] = place

    def on_enter(self, marker_id, position):
        if marker_id != self.keyboard_id:
            self.set_place(marker_id)

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass

    def set_place(self, marker_id):
        global place_name, place_population, place_energy
        place = self.places[marker_id]
        ui.set_position(place["bounds"], zoom_in=0)
        place_name, place_population, place_energy = place["name"], place["population"], place["energy"]
        queue.put(None)  # call for update


def update_table():
    # print("Coverage: {:3f}".format(.5 + additional_energy))
    base_energy = place_energy / 2
    base_emission = 0.5
    base_cost = 0.5
    image = ui.render(place_name, place_population, place_energy, (base_energy + additional_energy) / place_energy,
                      (base_emission + additional_emission), (base_cost + additional_cost), .7, .2, .4)
    table.display(image)


ui = UI()
place_name = "Karlsruhe"
place_population = 313092
place_energy = 9100
bounds = find(place_name)
ui.set_position(bounds)
additional_energy = 0
additional_emission = 0
additional_cost = 0
table = ARTable(Configuration("config.json"))
aruco = Aruco()
table.add_plugin(aruco)
update_table()
aruco.add_listener(MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), (4, 10,), table, ui))
aruco.add_listener(PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), (4, 10,), table, ui))
table.start()
queue = LifoQueue()
while True:
    queue.get(block=True)
    update_table()
