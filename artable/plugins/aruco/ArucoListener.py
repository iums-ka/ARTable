from abc import ABC, abstractmethod

import numpy as np


class ListenerBase(ABC):
    @abstractmethod
    def update(self, marker_id, position):
        pass


def distance_sqr(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


class AreaListener(ListenerBase, ABC):
    def __init__(self, area, ids, delta=5):
        self.area = np.array(area).flatten() # x1, y1, x2, y2
        self.ids = ids
        self.delta_sqr = delta ** 2
        self.last_positions = {}

    def __inbounds(self, position):
        return (self.area[0] <= position[0] <= self.area[2]) and \
               (self.area[1] <= position[1] <= self.area[3])

    def update(self, marker_id, position):
        if marker_id in self.ids:
            if self.__inbounds(position):
                if marker_id in self.last_positions:
                    if distance_sqr(self.last_positions[marker_id], position) >= self.delta_sqr:
                        # move
                        self.on_move(marker_id, self.last_positions[marker_id].copy(), position.copy())
                        self.last_positions[marker_id] = position
                else:
                    # enter
                    self.on_enter(marker_id, position.copy())
                    self.last_positions[marker_id] = position
            elif marker_id in self.last_positions:
                # leave
                self.on_leave(marker_id, self.last_positions[marker_id].copy())
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
