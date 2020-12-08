import json

import pynput
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
from energy_app.dynamic_ui import UI
from queue import LifoQueue

import asyncio
import websockets

from energy_app.place_provider import PlaceProvider


async def _send(text):
    try:
        uri = "ws://localhost:5500"
        async with websockets.connect(uri) as websocket:
            await websocket.send(text)
            print("> " + text)
    except Exception:
        print("Failed to send: " + text)
        pass


def send(text):
    asyncio.new_event_loop().run_until_complete(_send(text))


class MapListener(ArucoAreaListener):
    def reload(self):
        self.energy = {}
        self.cost = {}
        self.emission = {}
        config = json.load(open("plant_types.json", mode="r", encoding="utf-8"))
        self.plants = {}
        for plant in config["types"]:
            self.plants[plant["marker"]] = plant

    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.energy = {}
        self.cost = {}
        self.emission = {}
        self.plants = {}
        self.reload()

    def on_enter(self, marker_id, position):
        coords = self.table_pos_to_geocode(position)
        send("MARKER:enter:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        self.update_energy(marker_id, position)

    def on_move(self, marker_id, last_position, position):
        coords = self.table_pos_to_geocode(position)
        send("MARKER:move:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        self.update_energy(marker_id, position)

    def on_leave(self, marker_id, last_position):
        coords = self.table_pos_to_geocode(last_position)
        send("MARKER:leave:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
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
            global place_energy, place_population
            self.energy[marker_id] = eval(plant["energy_formula"], {
                'datapoint': energy,
                'needed': place_energy,
                'population': place_population
            })
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
        config = json.load(open("shortcut_places.json", mode="r", encoding="utf-8"))
        self.keyboard_id = config["keyboard"]
        self.places = {}
        for place in config["places"]:
            self.places[place["marker"]] = place

    def __init__(self, area, ids, ar, dynamic_ui):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.keyboard_id = -1
        self.places = {}
        self.reload()

    def on_enter(self, marker_id, position):
        if marker_id != self.keyboard_id:
            self.set_place(marker_id)
        else:
            global typing
            typing = True

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        if marker_id == self.keyboard_id:
            global typing
            typing = False

    def set_place(self, marker_id):
        global place_name, place_population, place_energy
        place = self.places[marker_id]
        ui.set_position(place["bounds"], zoom_in=0)
        place_name, place_population, place_energy = place["name"], place["population"], place["energy"]
        send("PLACE:" + place_name + ":" + str(place_population) + ":" + str(place_energy))
        queue.put(None)  # call for update


def key_input(key):
    global search, selected, results
    if typing:
        if str(key).replace("'", "") in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-äöüÄÖÜß":
            search += str(key).replace("'", "")
            queue.put(None)
        if key == pynput.keyboard.Key.space:
            search += " "
            queue.put(None)
        if key == pynput.keyboard.Key.backspace:
            search = search[:-1]
            if len(search) == 0:
                results = []
                selected = -1
            queue.put(None)
        if len(search) > 0:
            results = place_provider.list_all_containing(search)
            selected = min(len(results) - 1, selected)
            if key == pynput.keyboard.Key.enter:
                if selected != -1:
                    place = place_provider.get(results[selected])
                    ui.set_position(place["bounds"], zoom_in=1)
                    global place_name, place_population, place_energy
                    place_name, place_population, place_energy = place["name"], place["population"], place["energy"]
                    send("PLACE:" + place_name + ":" + str(place_population) + ":" + str(place_energy))
                    results = []
                    search = ""
                    selected = -1
                    queue.put(None)
            if key == pynput.keyboard.Key.up:
                selected = (selected + 1) % len(results)
                queue.put(None)
            if key == pynput.keyboard.Key.down:
                selected = (selected + len(results) - 1) % len(results)
                queue.put(None)



class YearListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("years.json", mode="r", encoding="utf-8"))
        all_goals = config[str(self.year)]
        self.goals = (all_goals["coverage_goal"], all_goals["emission_goal"], all_goals["cost_goal"])

    def __init__(self, area, ids, ar, dynamic_ui, year):
        super().__init__(area, ids)
        self.table = ar
        self.ui = dynamic_ui
        self.year = year
        self.goals = (0, 0, 0)
        self.reload()

    def on_enter(self, marker_id, position):
        global coverage_goal, emission_goal, cost_goal
        coverage_goal, emission_goal, cost_goal = self.goals
        queue.put(None)  # call for update

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass


def update_table():
    # print("Coverage: {:3f}".format(.5 + additional_energy))
    base_energy = place_energy / 2
    base_emission = 0.5
    base_cost = 0.5
    search_data = (search, selected, results) if typing else None
    image = ui.render(place_name, place_population, place_energy, (base_energy + additional_energy) / place_energy,
                      (base_emission + additional_emission), (base_cost + additional_cost),
                      coverage_goal, emission_goal, cost_goal, search_data)
    table.display(image)


def reload_configs():
    map_listener.reload()
    place_listener.reload()
    year_2020_listener.reload()
    year_2030_listener.reload()
    year_2050_listener.reload()
    place_provider.reload()
    print("Reloaded.")


def for_canonical(f):
    return lambda k: f(keyboard_listener.canonical(k))


if __name__ == '__main__':
    send("SYSTEM:startup")
    typing = False
    search = ""
    selected = -1
    results = []
    reload_hotkey = HotKey(HotKey.parse("<ctrl>+r"), reload_configs)
    reload_listener = Listener(
        on_press=for_canonical(reload_hotkey.press),
        on_release=for_canonical(reload_hotkey.release))
    keyboard_listener = Listener(on_press=key_input)
    reload_listener.start()
    keyboard_listener.start()
    table = ARTable(Configuration("table.json"))
    ui = UI()
    place_name = "Stadtkreis Karlsruhe"
    place_provider = PlaceProvider()
    place_data = place_provider.get(place_name)
    place_population = place_data["population"]
    place_energy = place_data["energy"]
    bounds = place_data["bounds"]
    ui.set_position(bounds)
    additional_energy = 0
    additional_emission = 0
    additional_cost = 0
    coverage_goal, emission_goal, cost_goal = .7, .2, .4
    aruco = Aruco()
    table.add_plugin(aruco)
    update_table()
    # todo read ids from config
    map_listener = MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), (4, 10,), table, ui)
    aruco.add_listener(map_listener)
    # todo read ids from config
    place_listener = PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), (4, 10,), table, ui)
    aruco.add_listener(place_listener)
    # todo read ids from config
    year_2020_listener = YearListener(table.image_to_table_coords(ui.get_2020_area()), (4,), table, ui, 2020)
    year_2030_listener = YearListener(table.image_to_table_coords(ui.get_2030_area()), (4,), table, ui, 2030)
    year_2050_listener = YearListener(table.image_to_table_coords(ui.get_2050_area()), (4,), table, ui, 2050)
    aruco.add_listener(year_2020_listener)
    aruco.add_listener(year_2030_listener)
    aruco.add_listener(year_2050_listener)
    table.start()
    queue = LifoQueue()
    send("SYSTEM:running")
    while True:
        queue.get(block=True)
        update_table()
