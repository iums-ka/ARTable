import cv2
import numpy as np
from cv2 import aruco

from artable.plugins.Plugin import Plugin
from artable.plugins.aruco.ArucoListener import ListenerBase


class ArucoPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.listeners = set()
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
        self.parameters = aruco.DetectorParameters_create()

    def update(self, image: np.array):
        markers = self.__get_tangible_coordinates(image)
        for marker in markers:
            marker_id = marker[0][0]
            position = marker[1]
            for listener in self.listeners:
                listener.update(marker_id, position)  # TODO: update vanishing markers

    def add_listener(self, listener: ListenerBase):
        self.listeners.add(listener)
        pass

    def remove_listener(self, listener: ListenerBase):
        self.listeners.remove(listener)
        pass

    def __get_tangible_coordinates(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected_img_points = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)
        frame_markers = aruco.drawDetectedMarkers(image, corners, ids, (0,0,255))
        cv2.namedWindow('Marker', cv2.WINDOW_AUTOSIZE)
        cv2.imshow('Marker', frame_markers)
        cv2.waitKey(1)
        points = np.array([])
        if ids is not None:
            np_shape = np.array(corners)
            c = np_shape[:, 0, :, :]
            points = c.reshape(c.shape[0], c.shape[1], 2)
            points = np.array(points)
            points = np.mean(points, axis=1)
            points = cv2.perspectiveTransform(points.reshape((-1, 1, 2)), self.camera_table_t)
            points = points.reshape((-1,2))
            points = list(zip(ids, points))
        return points
