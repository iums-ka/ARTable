import json

import pyautogui
from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration

from PIL import ImageDraw

cursor_radius = 5

class TangibleListener(ArucoAreaListener):

    def on_leave(self, marker_id, last_position):
        pass

    def on_move(self, marker_id, last_position, position):
        update_position(position)

    def on_enter(self, marker_id, position):
        update_position(position)


def reload_configs():
    global hotkeys
    hotkeys = []
    config = json.load(open("config.json"))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["reload"]), reload_configs))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["toggle"]), toggle))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["update"]), update))
    print(hotkeys)


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
    screen = pyautogui.screenshot()
    draw = ImageDraw.Draw(screen)
    draw.ellipse([goal[0] - cursor_radius, goal[1] - cursor_radius, goal[0] + cursor_radius, goal[1] + cursor_radius], fill="red")
    table.display(screen)


if __name__ == '__main__':
    goal = (0, 0)
    live = False
    hotkeys = []
    reload_listener = Listener(
        on_press=hotkeys_press,
        on_release=hotkeys_release
    )
    reload_listener.start()
    reload_configs()
    table_conf = Configuration("table.json")
    table = ARTable(table_conf)
    aruco = Aruco()
    table.add_plugin(aruco)
    aruco.add_listener(TangibleListener(((0,0),table_conf.table_size),[4],delta=1))
    table.start()
    while True:
        update_table()
