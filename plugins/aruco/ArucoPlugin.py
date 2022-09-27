% Copyright (c) 2022, Jonas Hansert
% All rights reserved.
% 
% This source code is licensed under the BSD-style license found in the
% LICENSE file in the root directory of this source tree. 

import cv2
import numpy as np
from cv2 import aruco

from artable.plugins.Plugin import Plugin
from artable.plugins.aruco.ArucoListener import ListenerBase


class ArucoPlugin(Plugin):
    def __init__(self, marker_dict=aruco.DICT_4X4_250):
        super().__init__()
        self.listeners = set()
        if type(marker_dict) == str:
            marker_dict = int(aruco.__dict__[marker_dict])
        self.aruco_dict = aruco.Dictionary_get(marker_dict)
        self.parameters = aruco.DetectorParameters_create()

    def update(self, image: np.array):
        markers = self.__get_tangible_coordinates(image)
        marker_ids = []
        positions = []
        for marker in markers:
            marker_ids.append(marker[0][0])
            positions.append(marker[1])
        for listener in self.listeners:
            listener.update(marker_ids, positions)

    def add_listener(self, listener: ListenerBase):
        self.listeners.add(listener)
        pass

    def remove_listener(self, listener: ListenerBase):
        self.listeners.remove(listener)
        pass

    def __get_tangible_coordinates(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected_img_points = aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)
        # frame_markers = aruco.drawDetectedMarkers(image, corners, ids, (0,0,255))
        # cv2.namedWindow('Marker', cv2.WINDOW_AUTOSIZE)
        # cv2.imshow('Marker', frame_markers)
        # cv2.waitKey(1)
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
