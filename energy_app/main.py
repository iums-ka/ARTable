import json
import locale
import random
import threading
import time

import cv2
import pynput
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTableGL, Configuration
from energy_app.dynamic_ui import UI
from queue import LifoQueue

import asyncio
import websockets

from energy_app.place_provider import PlaceProvider

sending_enabled = False
statements_only_latest = True
force_two_statements = True
statement_update_interval = 30
tutorial_timeout = 180
info_marker = 10


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


def cmp(a, b):
    return bool(a > b) - bool(a < b)


class TutorialListener(ArucoAreaListener):
    def reload(self):
        ids = []
        for i in range(100):
            ids.append(i)
        self.set_ids(ids)

    def __init__(self, area, action_id):
        super().__init__(area, delta=10, time_threshold=2)
        self.update_timer = None
        self.action_id = action_id
        self.reload()

    def on_enter(self, marker_id, position):
        global tutorial_visible, tutorial_page
        if tutorial_page == self.action_id:
            return
        if self.action_id == -1:
            tutorial_visible = False
            switch_to_main()
            return
        print("show tutorial page", self.action_id)
        tutorial_visible = True
        tutorial_page = self.action_id
        if 1 <= self.action_id <= 4:
            start_tutorial_video_player("resources/tutorial-page-" + str(self.action_id) + "-video.mp4")
        else:
            disable_tutorial_video_player()
        queue.put(None)

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass


class TutorialVideoPlayer(threading.Thread):
    def __init__(self, filename):
        super().__init__()
        self._filename = filename
        self._stopped = False
        self.video_capture = cv2.VideoCapture()
        self.current_video_frame = None

    def _get_video_frame(self):
        success, frame = self.video_capture.read()
        if success:
            return frame
        if not self.video_capture.isOpened():
            self.video_capture.open(self._filename)
        else:
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return self.video_capture.read()[1]

    def run(self):
        last_frame_time = time.time_ns()
        self._get_video_frame()
        ns_per_frame = 1000000000/self.video_capture.get(cv2.CAP_PROP_FPS)
        while not self._stopped:
            while time.time_ns() - last_frame_time < ns_per_frame:
                time.sleep(max(ns_per_frame - time.time_ns() + last_frame_time, 1)/1000000000)
            last_frame_time = time.time_ns()
            self.current_video_frame = self._get_video_frame()
            queue.put(None)
        self.current_video_frame = None

    def get_current_frame(self):
        return self.current_video_frame

    def stop_and_wait(self):
        self._stopped = True
        self.join()


class InfoListener(ArucoAreaListener):
    def reload(self):
        marker_id = info_marker
        self.set_ids([marker_id])

    def __init__(self, area):
        super().__init__(area, delta=10, time_threshold=4)
        self.reload()

    def on_enter(self, marker_id, position):
        print("show info screen")
        self.set_visible(True)

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        print("hide info screen")
        self.set_visible(False)

    def set_visible(self, visible):
        global info_visible
        info_visible = visible
        queue.put(None)


class MapListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("resources/plant_types.json", mode="r", encoding="utf-8"))
        self.plant_type_names = json.load(open("resources/plant_type_names.json", mode="r", encoding="utf-8"))
        self.statements = json.load(open("resources/statements.json", mode="r", encoding="utf-8"))
        self.coverage_texts = json.load(open("resources/coverage_text.json", mode="r", encoding="utf-8"))
        self.plants = {}
        ids = []
        for plant in config["types"]:
            ids.append(plant["marker"])
            self.plants[plant["marker"]] = plant
        self.set_ids(ids)

    def __init__(self, area, ar, dynamic_ui):
        super().__init__(area, delta=10, time_threshold=3)  # reaction tangibles
        self.table = ar
        self.ui = dynamic_ui
        self.plants = {}
        self.statements = {}
        self.active_plants = {}
        self.plant_type_names = {}
        self.coverage_texts = []
        self.update_timer = None
        self.popup_shown_for = -1
        self.reload()

    def on_enter(self, marker_id, position):
        self.do_marker_update(marker_id, position, "enter")
        self.update_statements(marker_id)
        self.sum_and_update()

    def on_move(self, marker_id, last_position, position):
        self.do_marker_update(marker_id, position, "move")
        self.sum_and_update()

    def on_leave(self, marker_id, last_position):
        global show_popup
        coords = self.table_pos_to_geocode(last_position)
        send("MARKER:leave:" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        if self.popup_shown_for == marker_id:
            show_popup = False
            self.popup_shown_for = -1
        self.active_plants.pop(marker_id)
        self.update_statements()
        self.sum_and_update()

    def table_pos_to_geocode(self, position):
        return self.ui.image_coordinates_to_geocode(self.table.table_to_image_coords(position))

    def sum_and_update(self):
        global created_energy, created_emission, created_cost, place_energy, place_population, \
               coverage_sign, emission_sign, cost_sign
        new_created_energy, new_created_emission, new_created_cost = 0, 0, 0
        for current_plant_type in (
        "water", "wind", "solar", "bio", "gas", "atom", "coal"):  # prioritization #gas hinzugefügt
            for marker_id in self.active_plants.keys():
                plant = self.plants[marker_id]
                if plant["type"] != current_plant_type:
                    continue
                potential = self.get_potential(plant["type"], self.active_plants[marker_id])
                if potential is None:
                    continue
                plant_possible_energy = eval(plant["energy_formula"], {
                    'potential': potential,
                    'needed': place_energy,
                    'population': place_population
                })
                plant_energy = plant_possible_energy + min(place_energy - (new_created_energy + plant_possible_energy), 0)
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
                new_created_energy += plant_energy
                new_created_emission += plant_emission
                new_created_cost += plant_cost
        coverage_sign, emission_sign, cost_sign = cmp(new_created_energy, created_energy), \
                                                  cmp(new_created_emission, created_emission), \
                                                  cmp(new_created_cost, created_cost)
        created_energy, created_emission, created_cost = new_created_energy, new_created_emission, new_created_cost
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
        if statements_only_latest:
            visible_statments.append(self.get_statement(new_marker))
        else:
            visible_statments.append(self.get_statement(-1))
        visible_statments = [dict(t) for t in {tuple(d.items()) for d in visible_statments}]  # remove duplicates
        if force_two_statements and len(visible_statments) < 2:
            self.update_statements(new_marker)
        # reset update timer
        if self.update_timer is not None:
            self.update_timer.cancel()
        self.update_timer = threading.Timer(statement_update_interval, lambda: self.auto_update_statements(new_marker))
        self.update_timer.start()

    def auto_update_statements(self, new_marker=-1):
        self.update_statements(new_marker)
        queue.put(None)  # call for update

    def get_statement(self, marker_id):
        if marker_id == -1:
            marker_id = random.sample(self.active_plants.keys(), 1)[0]
        plant_type = self.plants[marker_id]["type"]
        stakeholder = random.sample(["economist", "scientist", "conservationist"], 1)[0]
        if stakeholder not in self.statements[plant_type]:
            return self.get_statement(marker_id)
        statement = random.sample(self.statements[plant_type][stakeholder], 1)[0]
        statement["from"] = stakeholder
        if plant_type in self.plant_type_names:
            statement["type"] = self.plant_type_names[plant_type]
        else:
            statement["type"] = plant_type
        return statement

    def get_coverage_text(self, marker_id):
        plant_possible_energy = self.get_plant_raw_data(marker_id)[0]
        if plant_possible_energy is None:
            return None
        best_match = 0
        best_coverage_text = ""
        for coverage_text in self.coverage_texts:
            from_mwh = coverage_text['from_megawatthours']
            if best_match < from_mwh < plant_possible_energy:
                best_match = from_mwh
                best_coverage_text = coverage_text['text']
        return best_coverage_text

    def get_data_line(self, marker_id):
        plant_possible_energy, plant_emission, plant_cost = self.get_plant_raw_data(marker_id)
        if plant_possible_energy is None:
            return None
        locale.setlocale(locale.LC_ALL, '')
        return "{0:.5n} MW\n{1:.3n} ct/kWh\n{2:.4n} t(CO2)/kWh".format(plant_possible_energy/(365*24),
                                                           plant_cost/plant_possible_energy/10,
                                                           plant_emission/plant_possible_energy)

    def do_marker_update(self, marker_id, position, update_type):
        global show_popup, popup_position, popup_dataline, popup_text
        coords = self.table_pos_to_geocode(position)
        send("MARKER:" + update_type + ":" + self.plants[marker_id]["name"] + ":" + str(coords[0]) + ":" + str(coords[1]))
        img_pos = self.table.table_to_image_coords(position)
        self.active_plants[marker_id] = img_pos
        popup_dataline, popup_text = self.get_data_line(marker_id), self.get_coverage_text(marker_id)
        show_popup, popup_position = popup_dataline is not None, (img_pos[0], img_pos[1])
        if show_popup:
            self.popup_shown_for = marker_id
        # optional ausblenden nach 20 sekunden?

    def get_plant_raw_data(self, marker_id):

        plant = self.plants[marker_id]
        potential = self.get_potential(plant["type"], self.active_plants[marker_id])
        if potential is None:
            return None, None, None
        plant_possible_energy = eval(plant["energy_formula"], {
            'potential': potential,
            'needed': place_energy,
            'population': place_population
        })
        plant_emission = eval(plant["emission_formula"], {
            'potential': potential,
            'needed': place_energy,
            'population': place_population,
            'power': plant_possible_energy
        })
        plant_cost = eval(plant["cost_formula"], {
            'potential': potential,
            'needed': place_energy,
            'population': place_population,
            'power': plant_possible_energy
        })
        return plant_possible_energy, plant_emission, plant_cost


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
            print("Search active")
            typing = True

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        if marker_id == self.keyboard_id:
            global typing
            print("Search disabled")
            typing = False

    def set_place(self, marker_id):
        place = self.places[marker_id]
        ui.set_position(place["bounds"])
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
                    ui.set_position(place["bounds"])
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
        self.set_goals()

    def set_goals(self):
        global coverage_goal, emission_goal, cost_goal
        global active_year
        print("Set goals to", self.year)
        coverage_goal, emission_goal, cost_goal = self.goals
        active_year = self.year
        queue.put(None)  # call for update

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass


def update_table():
    tutorial_video_frame = tutorial_video_player.get_current_frame() if tutorial_video_player is not None else None
    search_data = (search, selected, results) if typing else None
    ui.rendergl(place_name, place_population, place_energy,
                show_popup, popup_position, popup_dataline, popup_text,
                created_energy / place_energy, # % of needed
                created_emission / place_emission, # % of 2018
                min(created_cost / (place_population * 1000), 1), # [0,1]
                coverage_goal, emission_goal, cost_goal, # [0,1] u {-1}
                coverage_sign, emission_sign, cost_sign, # {-1, 0, 1}
                search_data, visible_statments, active_year,
                tutorial_visible, tutorial_page, tutorial_video_frame,
                info_visible
                )


def reload_configs():
    map_listener.reload()
    info_listener.reload()
    place_listener.reload()
    year_2020_listener.reload()
    year_2030_listener.reload()
    year_2050_listener.reload()
    place_provider.reload()
    print("Reloaded.")


def switch_to_tutorial():
    global tutorial_page, tutorial_visible
    print("start tutorial")

    aruco.remove_listener(map_listener)
    aruco.remove_listener(place_listener)
    aruco.remove_listener(year_2020_listener)
    aruco.remove_listener(year_2030_listener)
    aruco.remove_listener(year_2050_listener)
    aruco.remove_listener(info_listener)

    aruco.add_listener(tutorial_listener_0)
    aruco.add_listener(tutorial_listener_1)
    aruco.add_listener(tutorial_listener_2)
    aruco.add_listener(tutorial_listener_3)
    aruco.add_listener(tutorial_listener_4)
    aruco.add_listener(tutorial_listener_s)

    tutorial_page = 0
    tutorial_visible = True

    queue.put(None)


def disable_tutorial_video_player():
    global tutorial_video_player
    if tutorial_video_player is not None:
        tutorial_video_player.stop_and_wait()
        tutorial_video_player = None


def start_tutorial_video_player(filename):
    global tutorial_video_player
    disable_tutorial_video_player()
    tutorial_video_player = TutorialVideoPlayer(filename)
    tutorial_video_player.start()


def switch_to_main():
    print("end tutorial")

    disable_tutorial_video_player()

    aruco.remove_listener(tutorial_listener_0)
    aruco.remove_listener(tutorial_listener_1)
    aruco.remove_listener(tutorial_listener_2)
    aruco.remove_listener(tutorial_listener_3)
    aruco.remove_listener(tutorial_listener_4)
    aruco.remove_listener(tutorial_listener_s)

    aruco.add_listener(map_listener)
    aruco.add_listener(place_listener)
    aruco.add_listener(year_2020_listener)
    aruco.add_listener(year_2030_listener)
    aruco.add_listener(year_2050_listener)
    aruco.add_listener(info_listener)

    queue.put(None)

    threading.Timer(10, switch_to_tutorial).start()  # todo when to reset?


def for_canonical(f):
    return lambda k: f(keyboard_listener.canonical(k))


if __name__ == '__main__':
    send("SYSTEM:startup")
    typing = False
    tutorial_visible = True
    info_visible = False
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
    table = ARTableGL(Configuration("table.json"))
    ui = UI(table)
    tutorial_video_player = None
    place_name = "Baden-W\u00fcrttemberg"  # Vorher "Stadtkreis Karlsruhe
    # place_name = "Baden-Wuerttemberg"
    place_provider = PlaceProvider()
    place_data = place_provider.get(place_name)
    place_population = place_data["population"]
    place_emission = place_data["emissions"]
    place_energy = place_data["energy"]
    bounds = place_data["bounds"]
    ui.set_position(bounds)
    tutorial_page = 0
    created_energy = 0
    created_emission = 0
    created_cost = 0
    coverage_goal, emission_goal, cost_goal = -1, -1, -1
    coverage_sign, emission_sign, cost_sign = 0, 0, 0
    show_popup, popup_position, popup_dataline, popup_text = False, (0, 0), "", ""
    active_year = 2020
    update_table()
    aruco = Aruco(marker_dict="DICT_4X4_250")
    table.add_plugin(aruco)
    map_listener = MapListener(table.image_to_table_coords(ui.get_map_interaction_area()), table, ui)
    aruco.add_listener(map_listener)
    tutorial_listener_0 = TutorialListener(table.image_to_table_coords(((3483, 1615), (3483 + 200, 1615 + 200))), 0)
    tutorial_listener_1 = TutorialListener(table.image_to_table_coords(((3483, 434), (3483 + 200, 434 + 200))), 1)
    tutorial_listener_2 = TutorialListener(table.image_to_table_coords(((3483, 729), (3483 + 200, 729 + 200))), 2)
    tutorial_listener_3 = TutorialListener(table.image_to_table_coords(((3483, 1024), (3483 + 200, 1024 + 200))), 3)
    tutorial_listener_4 = TutorialListener(table.image_to_table_coords(((3483, 1320), (3483 + 200, 1320 + 200))), 4)
    tutorial_listener_s = TutorialListener(table.image_to_table_coords(((3483, 2306), (3483 + 200, 2306 + 200))), -1)
    place_listener = PlaceListener(table.image_to_table_coords(ui.get_place_selection_area()), table, ui)
    aruco.add_listener(place_listener)
    year_2020_listener = YearListener(table.image_to_table_coords(ui.get_2020_area()), table, ui, 2020)
    year_2030_listener = YearListener(table.image_to_table_coords(ui.get_2030_area()), table, ui, 2030)
    year_2050_listener = YearListener(table.image_to_table_coords(ui.get_2050_area()), table, ui, 2050)
    aruco.add_listener(year_2020_listener)
    aruco.add_listener(year_2030_listener)
    aruco.add_listener(year_2050_listener)
    info_listener = InfoListener(table.image_to_table_coords([(0, 0), ui.screen_size]))
    aruco.add_listener(info_listener)
    queue = LifoQueue()
    year_2020_listener.set_goals()
    table.start()
    send("SYSTEM:running")
    switch_to_tutorial()
    while True:
        queue.get(block=True)
        update_table()
