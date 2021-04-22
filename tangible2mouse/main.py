import json
import threading

import pyautogui
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration

from PIL import ImageDraw

cursor_radius = 5


class TangibleListener(ArucoAreaListener):
    def __init__(self, area, delta=5, time_threshold=2):
        super().__init__(area, [], delta, time_threshold)
        self.timer = None
        self.event = None
        self.delay = None
        self.markers = {}
        self.action = {}

    def reload(self):
        config = json.load(open("config.json"))
        markers = [v for (k, v) in config["tangibles"].items()]
        self.markers = config["tangibles"]
        self.action = {v: k for k, v in config["tangibles"].items()}
        self.delay = config["action_delay"]
        self.set_ids(markers)

    def on_leave(self, marker_id, last_position):
        if self.markers[self.event] == marker_id:
            self.stop_action_timer()
        pass

    def on_move(self, marker_id, last_position, position):
        update_position(position)

    def on_enter(self, marker_id, position):
        update_position(position)
        self.start_action_timer(marker_id)

    def start_action_timer(self, marker_id):
        self.stop_action_timer()
        self.event = self.action[marker_id]
        print("Scheduling " + str(self.event) + " in " + str(self.delay) + " seconds")
        self.timer = threading.Timer(self.delay, self.timer_event)
        self.timer.start()
        pass

    def stop_action_timer(self):
        if self.timer is None: return
        print("Stopping scheduled event")
        if self.event == "drag" and not self.timer.is_alive():
            print("Lifting mouse")
            pyautogui.mouseUp()
        self.timer.cancel()

    def timer_event(self):
        print(str(self.event) + "ing!")
        if self.event == "hover":
            pass
        elif self.event == "leftclick":
            pyautogui.leftClick()
        elif self.event == "doubleclick":
            pyautogui.doubleClick()
        elif self.event == "rightclick":
            pyautogui.rightClick()
        elif self.event == "middleclick":
            pyautogui.middleClick()
        elif self.event == "drag":
            pyautogui.mouseDown()


def reload_configs():
    global hotkeys, screen_area
    hotkeys = []
    config = json.load(open("config.json"))
    screen_area = config["screen_area"]
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["reload"]), reload_configs))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["toggle"]), toggle))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["update"]), update))
    listener.reload()
    print("Reloaded!")


def update():
    pyautogui.moveTo(goal[0], goal[1])


def toggle():
    global live
    live = not live
    print("live: ", live)


def update_position(position):
    global goal
    goal = table.table_to_image_coords(position)
    print("new position: ", goal)
    if live:
        update()


def hotkeys_press(key):
    for hotkey in hotkeys:
        hotkey.press(reload_listener.canonical(key))


def hotkeys_release(key):
    for hotkey in hotkeys:
        hotkey.release(reload_listener.canonical(key))


def update_table():
    screen = pyautogui.screenshot(region=screen_area)
    draw = ImageDraw.Draw(screen)
    draw.ellipse([goal[0] - cursor_radius, goal[1] - cursor_radius, goal[0] + cursor_radius, goal[1] + cursor_radius],
                 fill="red")
    table.display(screen)


if __name__ == '__main__':
    screen_area = [0, 0, 1920, 1080]
    goal = (0, 0)
    live = True
    hotkeys = []
    reload_listener = Listener(
        on_press=hotkeys_press,
        on_release=hotkeys_release
    )
    reload_listener.start()
    table_conf = Configuration("table.json")
    table = ARTable(table_conf)
    aruco = Aruco(marker_dict="DICT_4X4_250")
    table.add_plugin(aruco)
    listener = TangibleListener(((0, 0), table_conf.table_size), delta=1, time_threshold=1)
    aruco.add_listener(listener)
    reload_configs()
    table.start()
    while True:
        update_table()
