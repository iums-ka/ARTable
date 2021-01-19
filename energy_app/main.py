import json
import random

import pynput
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration
from energy_app.dynamic_ui import UI
from queue import LifoQueue

import asyncio
import websockets

from energy_app.place_provider import PlaceProvider

sending_enabled = False


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
    if sending_enabled:
        asyncio.new_event_loop().run_until_complete(_send(text))
    else:
        print(text)


class MapListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("resources/plant_types.json", mode="r", encoding="utf-8"))
        self.statements = json.load(open("resources/statements.json", mode="r", encoding="utf-8"))
        self.plants = {}
        ids = []
        for plant in config["types"]:
            ids.append(plant["marker"])
            self.plants[plant["marker"]] = plant
        self.set_ids(ids)

    def __init__(self, area, ar, dynamic_ui):
        super().__init__(area)
        self.table = ar
        self.ui = dynamic_ui
        self.plants = {}
        self.statements = {}
        self.active_plants = {}
        self.reload()

    def on_enter(self, marker_id, position):
        coords = self.table_pos_to_geocode(position)
        send("MARKER:enter:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        self.active_plants[marker_id] = self.table.table_to_image_coords(position)
        self.update_statements(marker_id)
        self.sum_and_update()

    def on_move(self, marker_id, last_position, position):
        coords = self.table_pos_to_geocode(position)
        send("MARKER:move:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        self.active_plants[marker_id] = self.table.table_to_image_coords(position)
        self.sum_and_update()

    def on_leave(self, marker_id, last_position):
        coords = self.table_pos_to_geocode(last_position)
        send("MARKER:leave:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        self.active_plants.pop(marker_id)
        self.update_statements()
        self.sum_and_update()

    def table_pos_to_geocode(self, position):
        return self.ui.image_coordinates_to_geocode(self.table.table_to_image_coords(position))

    def sum_and_update(self):
        global created_energy, created_emission, created_cost, place_energy, place_population
        created_energy = 0
        created_emission = 0
        created_cost = 0
        for current_plant_type in ("water", "wind", "solar", "bio", "coal", "atom"):  # prioritization
            for marker_id in self.active_plants.keys():
                plant = self.plants[marker_id]
                if plant["type"] != current_plant_type:
                    continue
                potential = self.get_potential(plant["type"], self.active_plants[marker_id])
                plant_possible_energy = eval(plant["energy_formula"], {
                    'potential': potential,
                    'needed': place_energy,
                    'population': place_population
                })
                plant_energy = plant_possible_energy + min(place_energy - (created_energy + plant_possible_energy), 0)
                plant_emission = eval(plant["emission_formula"], {
                    'potential': potential,
                    'needed': place_energy,
                    'population': place_population,
                    'power': plant_energy
                })
                plant_cost = eval(plant["cost_formula"], {
                    'potential': potential,
                    'needed': place_energy,
                    'population': place_population,
                    'power': plant_energy
                })
                created_energy += plant_energy
                created_emission += plant_emission
                created_cost += plant_cost
        queue.put(None)  # call for update

    def get_potential(self, plant_type, position):
        energy = 0
        if plant_type == "solar":
            energy = self.ui.get_insolation(position)
        elif plant_type == "wind":
            energy = self.ui.get_wind(position)
        elif plant_type == "water":
            energy = self.ui.get_water(position)
        return energy

    def update_statements(self, new_marker=-1):
        global visible_statments
        visible_statments = []
        if len(self.active_plants.keys()) == 0: return
        visible_statments.append(self.get_statement(new_marker))
        visible_statments.append(self.get_statement(-1))
        visible_statments = [dict(t) for t in {tuple(d.items()) for d in visible_statments}]

    def get_statement(self, marker_id):
        if marker_id == -1:
            marker_id = random.sample(self.active_plants.keys(), 1)[0]
        plant_type = self.plants[marker_id]["type"]
        stakeholder = random.sample(["economist", "scientist", "conservationist"], 1)[0]
        statement = random.sample(self.statements[plant_type][stakeholder], 1)[0]
        statement["from"] = stakeholder
        return statement


class PlaceListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("resources/shortcut_places.json", mode="r", encoding="utf-8"))
        self.keyboard_id = config["keyboard"]
        self.places = {}
        ids = [self.keyboard_id]
        for place in config["places"]:
            ids.append(place["marker"])
            self.places[place["marker"]] = place
        self.set_ids(ids)

    def __init__(self, area, ar, dynamic_ui):
        super().__init__(area)
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
        place = self.places[marker_id]
        ui.set_position(place["bounds"], zoom_in=0)
        set_place(place)
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
                    set_place(place)
                    results = []
                    search = ""
                    selected = -1
                    queue.put(None)
            if key == pynput.keyboard.Key.up:
                selected = (selected + 1) % len(results) if len(results) > 0 else -1
                queue.put(None)
            if key == pynput.keyboard.Key.down:
                selected = (selected + len(results) - 1) % len(results) if len(results) > 0 else -1
                queue.put(None)


def set_place(place):
    global place_name, place_population, place_energy, place_emission
    place_name, place_population, place_energy, place_emission = \
        place["name"], place["population"], place["energy"], place["emissions"]
    send("PLACE:" + place_name + ":" + str(place_population) + ":" + str(place_energy) + ":" + str(place_emission))


class YearListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("resources/years.json", mode="r", encoding="utf-8"))
        all_goals = config[str(self.year)]
        self.goals = (all_goals["coverage_goal"], all_goals["emission_goal"], all_goals["cost_goal"])
        self.set_ids([config["marker"]])

    def __init__(self, area, ar, dynamic_ui, year):
        super().__init__(area)
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
    search_data = (search, selected, results) if typing else None
    image = ui.render(place_name, place_population, place_energy, created_energy / place_energy,
                      created_emission / place_emission, created_cost / (place_population*1000),
                      coverage_goal, emission_goal, cost_goal, search_data, visible_statments)
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
    visible_statments = []
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
    place_emission = place_data["emissions"]
    place_energy = place_data["energy"]
    bounds = place_data["bounds"]
    ui.set_position(bounds)
    created_energy = 0
    created_emission = 0
    created_cost = 0
    coverage_goal, emission_goal, cost_goal = -1, .95, -1
    aruco = Aruco()
    table.add_plugin(aruco)
    update_table()
    map_listener = MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), table, ui)
    aruco.add_listener(map_listener)
    place_listener = PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), table, ui)
    aruco.add_listener(place_listener)
    year_2020_listener = YearListener(table.image_to_table_coords(ui.get_2020_area()), table, ui, 2020)
    year_2030_listener = YearListener(table.image_to_table_coords(ui.get_2030_area()), table, ui, 2030)
    year_2050_listener = YearListener(table.image_to_table_coords(ui.get_2050_area()), table, ui, 2050)
    aruco.add_listener(year_2020_listener)
    aruco.add_listener(year_2030_listener)
    aruco.add_listener(year_2050_listener)
    table.start()
    queue = LifoQueue()
    send("SYSTEM:running")
    while True:
        queue.get(block=True)
        update_table()
