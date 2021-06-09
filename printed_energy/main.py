import json

from pynput.keyboard import HotKey, Listener

from artable.plugins import Aruco, ArucoAreaListener
from artable import ARTable, Configuration

import asyncio
import websockets

sending_enabled = False


async def _send(text):
    try:
        uri = "ws://localhost:5500"
        async with websockets.connect(uri) as websocket:
            await websocket.send(text)
            print("> " + text)
    except OSError:
        print("Failed to send: " + text)
        pass


def send(text):
    if sending_enabled:
        asyncio.new_event_loop().run_until_complete(_send(text))
    else:
        print(text)


class ControlsListener(ArucoAreaListener):
    def reload(self):
        config = json.load(open("config.json", mode="r", encoding="utf-8"))
        self.set_ids([config["tangibles"][self.field_type]])
        pos = config["field_positions"][self.field_name]
        size = config["field_size"]
        self.set_area((pos,[p+s for p,s in zip(pos,size)]))

    def __init__(self, field_type, field_name):
        super().__init__([0, 0, 0, 0], delta=10, time_threshold=1)
        self.field_type = field_type
        self.field_name = field_name
        self.reload()

    def on_enter(self, marker_id, position):
        send("CONTROL:" + self.field_type + ":" + self.field_name)

    def on_move(self, marker_id, last_position, position):
        pass

    def on_leave(self, marker_id, last_position):
        pass


def reload_configs():
    global hotkeys
    hotkeys = []
    config = json.load(open("config.json"))
    hotkeys.append(HotKey(HotKey.parse(config["keys"]["reload"]), reload_configs))
    print("Reloaded.")


def hotkeys_press(key):
    for hotkey in hotkeys:
        hotkey.press(reload_listener.canonical(key))


def hotkeys_release(key):
    for hotkey in hotkeys:
        hotkey.release(reload_listener.canonical(key))


def add_listeners():
    for listener in listeners:
        aruco.add_listener(listener)


if __name__ == '__main__':
    send("SYSTEM:startup")
    hotkeys = []
    listeners = []
    reload_listener = Listener(
        on_press=hotkeys_press,
        on_release=hotkeys_release
    )
    reload_listener.start()
    table_config = Configuration("table.json")
    table = ARTable(table_config)
    aruco = Aruco(marker_dict="DICT_4X4_250")
    table.add_plugin(aruco)
    listeners.append(ControlsListener("perspective", "overview"))
    listeners.append(ControlsListener("perspective", "bird"))
    listeners.append(ControlsListener("perspective", "normal"))
    listeners.append(ControlsListener("perspective", "frog"))
    listeners.append(ControlsListener("perspective", "detail"))
    listeners.append(ControlsListener("layer", "areas"))
    listeners.append(ControlsListener("layer", "noise"))
    add_listeners()
    reload_configs()
    table.start()
    send("SYSTEM:running")
