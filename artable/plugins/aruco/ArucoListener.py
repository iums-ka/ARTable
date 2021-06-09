import time
from abc import ABC, abstractmethod

import numpy as np


class ListenerBase(ABC):
    @abstractmethod
    def update(self, marker_ids, positions):
        pass


def distance_sqr(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


class AreaListener(ListenerBase, ABC):
    def __init__(self, area, ids=(), delta=5, time_threshold=2):
        self.area = np.array(area).flatten()  # x1, y1, x2, y2
        self.ids = ids
        self.delta_sqr = delta ** 2
        self.last_positions = {}
        self.time_threshold = time_threshold

    def set_ids(self, ids):
        self.ids = ids

    def set_area(self, area):
        self.area = np.array(area).flatten()

    def __inbounds(self, position):
        return (self.area[0] <= position[0] <= self.area[2]) and \
               (self.area[1] <= position[1] <= self.area[3])

    def update(self, marker_ids, positions):
        for marker_id, position in zip(marker_ids, positions):
            if marker_id in self.ids:
                if self.__inbounds(position):
                    if marker_id in self.last_positions:
                        if distance_sqr(self.last_positions[marker_id][0], position) >= self.delta_sqr:
                            # move
                            self.on_move(marker_id, self.last_positions[marker_id][0].copy(), position.copy())
                            self.last_positions[marker_id] = (position, time.time())
                        else:
                            # update time
                            self.last_positions[marker_id] = (self.last_positions[marker_id][0], time.time())
                    else:
                        # enter
                        self.on_enter(marker_id, position.copy())
                        self.last_positions[marker_id] = (position, time.time())
                elif marker_id in self.last_positions:
                    # leave
                    self.on_leave(marker_id, self.last_positions[marker_id][0].copy())
                    self.last_positions.pop(marker_id)
        # vanish
        remove = []
        for marker_id in self.last_positions:
            if marker_id not in marker_ids and time.time() - self.last_positions[marker_id][1] > self.time_threshold:
                remove.append(marker_id)
        for marker_id in remove:
            self.on_leave(marker_id, self.last_positions[marker_id][0].copy())
            self.last_positions.pop(marker_id)

    @abstractmethod
    def on_enter(self, marker_id, position):
        pass

    @abstractmethod
    def on_leave(self, marker_id, last_position):
        pass

    @abstractmethod
    def on_move(self, marker_id, last_position, position):
        pass
