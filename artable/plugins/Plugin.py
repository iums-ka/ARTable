from abc import ABC, abstractmethod

import numpy as np


class Plugin(ABC):
    def __init__(self):
        self.table_camera_t = None
        self.camera_table_t = None
        self.camera_projector_t = None
        self.projector_camera_t = None
        self.table_projector_t = None
        self.projector_table_t = None

    def set_transforms(self, table_camera_t, camera_table_t, camera_projector_t, projector_camera_t):
        self.table_camera_t, self.camera_table_t = table_camera_t, camera_table_t
        self.camera_projector_t, self.projector_camera_t = camera_projector_t, projector_camera_t
        self.table_projector_t = np.dot(self.camera_projector_t, self.table_camera_t)
        self.projector_table_t = np.dot(self.camera_table_t, self.projector_camera_t)

    def removed(self):
        self.table_camera_t, self.camera_table_t = None, None
        self.camera_projector_t, self.projector_camera_t = None, None
        self.table_projector_t, self.projector_table_t = None, None

    @abstractmethod
    def update(self, image: np.array):
        pass
