import json
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
from energy_app.dynamic_ui import UI
from energy_app.dynamic_ui import find_bounds_for_name as find
from queue import LifoQueue

import paho.mqtt.client as mqtt


class MapListener(ArucoAreaListener):
    def reload(self):
        self.energy = {}
        self.cost = {}
        self.emission = {}
        config = json.load(open("resources/plant_types.json", mode="r", encoding="utf-8"))
        self.plants = {}
        for plant in config["types"]:
            self.plants[plant["marker"]] = plant

    def __init__(self, area, ids, ar, dynamic_ui, mqtt_client):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.client = mqtt_client
        self.energy = {}
        self.cost = {}
        self.emission = {}
        self.plants = {}
        self.reload()

    def on_enter(self, marker_id, position):
        coords = self.table_pos_to_geocode(position)
        self.client.publish("MARKER", "enter:" + self.plants[marker_id]["name"] + ":"
                            + str(coords[0]) + ":" + str(coords[1]))
        self.update_energy(marker_id, position)

    def on_move(self, marker_id, last_position, position):
        coords = self.table_pos_to_geocode(position)
        self.client.publish("MARKER", "move:" + self.plants[marker_id]["name"] + ":"
                            + str(coords[0]) + ":" + str(coords[1]))
        self.update_energy(marker_id, position)

    def on_leave(self, marker_id, last_position):
        coords = self.table_pos_to_geocode(last_position)
        self.client.publish("MARKER", "leave:" + self.plants[marker_id]["name"] + ":"
                            + str(coords[0]) + ":" + str(coords[1]))
        for a_dict in (self.energy, self.cost, self.emission):
            if marker_id in a_dict:
                a_dict.pop(marker_id)
        self.sum_and_update()

    def table_pos_to_geocode(self, position):
        return self.ui.image_coordinates_to_geocode(self.table.table_to_image_coords(position))

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
    def reload(self):
        config = json.load(open("resources/shortcut_places.json", mode="r", encoding="utf-8"))
        self.keyboard_id = config["keyboard"]
        self.places = {}
        for place in config["places"]:
            self.places[place["marker"]] = place

    def __init__(self, area, ids, ar, dynamic_ui, mqtt_client):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.client = mqtt_client
        self.keyboard_id = -1
        self.places = {}
        self.reload()

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
        self.client.publish("PLACE", place_name + ":" + str(place_population) + ":" + str(place_energy))
        queue.put(None)  # call for update


def update_table():
    # print("Coverage: {:3f}".format(.5 + additional_energy))
    base_energy = place_energy / 2
    base_emission = 0.5
    base_cost = 0.5
    image = ui.render(place_name, place_population, place_energy, (base_energy + additional_energy) / place_energy,
                      (base_emission + additional_emission), (base_cost + additional_cost), .7, .2, .4)
    table.display(image)


def reload_configs():
    map_listener.reload()
    place_listener.reload()
    print("Reloaded.")


def for_canonical(f):
    return lambda k: f(keyboard_listener.canonical(k))


if __name__ == '__main__':
    client = mqtt.Client("KATZE_Tisch")
    client.connect("localhost")
    client.loop_start()
    client.publish("SYSTEM","startup")

    reload_hotkey = HotKey(HotKey.parse("<ctrl>+r"), reload_configs)
    keyboard_listener = Listener(
        on_press=for_canonical(reload_hotkey.press),
        on_release=for_canonical(reload_hotkey.release))
    keyboard_listener.start()
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
    map_listener = MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), (4, 10,), table, ui, client)
    aruco.add_listener(map_listener)
    place_listener = PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), (4, 10,), table, ui,
                                   client)
    aruco.add_listener(place_listener)
    table.start()
    client.publish("SYSTEM","running")
    queue = LifoQueue()
    while True:
        queue.get(block=True)
        update_table()
