import asyncio
import time

import numpy as np
import cv2
from cv2 import aruco
import screeninfo
from threading import Thread

from artable.configuration import Configuration
from PIL.Image import Image as PILImage
from PIL import Image  # TODO: switch to cv2 only

from artable.plugins.Plugin import Plugin


class ARTable:
    def __init__(self, config: Configuration):
        self.config = config
        self.vc = self.__get_camera()
        (self.table_camera_t, self.camera_table_t), (
            self.projector_camera_t, self.camera_projector_t) = self.__calibrate()
        cv2.destroyWindow('Marker (Calibration)')
        self.plugins = set()
        self.stopped = False
        self.image_corners = ((0, 0), self.config.table_size)
        self.image_size = self.config.table_size

        self.__start_update_loop()

    def table_to_image_coords(self, points):
        points = np.array(points)
        keep_dim = True
        if np.array(points).ndim == 1:
            keep_dim = False
            points = [points]
        image_width_after = self.image_corners[1][0] - self.image_corners[0][0]
        image_height_after = self.image_corners[1][1] - self.image_corners[0][1]
        for point in points:
            point[0] = (point[0] - self.image_corners[0][0]) * self.image_size[0] / image_width_after
            point[1] = (point[1] - self.image_corners[0][1]) * self.image_size[1] / image_height_after
        return points if keep_dim else points[0]

    def image_to_table_coords(self, points):
        points = np.array(points)
        keep_dim = True
        if points.ndim == 1:
            keep_dim = False
            points = [points]
        image_width_after = self.image_corners[1][0] - self.image_corners[0][0]
        image_height_after = self.image_corners[1][1] - self.image_corners[0][1]
        for point in points:
            point[0] = (point[0] * image_width_after / self.image_size[0]) + self.image_corners[0][0]
            point[1] = (point[1] * image_height_after / self.image_size[1]) + self.image_corners[0][1]
        return points if keep_dim else points[0]

    def display(self, image: PILImage, xy: (float, float) = None):
        """
        Shows an image at a specified coordinate.

        If no coordinates are given, the image is instead stretched to fit the table.
        This will overwrite all currently displayed content.

        :param image: PIL-Image to display.
        :param xy: top left corner in mm.
        """
        self.image_size = image.size
        image = np.array(image)
        if xy is None:
            # stretch
            self.image_corners = ((0, 0), self.config.table_size)
            screen = cv2.resize(image,self.config.table_size)
        else:
            # move
            self.image_corners = (xy, (xy[0] + self.image_size[0], xy[1] + self.image_size[1]))
            screen = np.zeros((*self.config.table_size, 3), np.uint8)
            screen[xy[0], xy[1]] = image
        # transform & show
        table_image = cv2.warpPerspective(screen, np.dot(self.camera_projector_t, self.table_camera_t),
                                          self.config.projector_resolution, flags=1)
        table_image = cv2.cvtColor(table_image, cv2.COLOR_RGB2BGR)
        cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        # cv2.moveWindow("window", screen.x - 1, screen.y - 1)
        cv2.imshow("window", table_image)
        cv2.waitKey(1)

    def add_plugin(self, plugin: Plugin):
        plugin.set_transforms(self.table_camera_t, self.camera_table_t, self.camera_projector_t,
                              self.projector_camera_t)
        self.plugins.add(plugin)

    def remove_plugin(self, plugin: Plugin):
        plugin.removed()
        self.plugins.remove(plugin)

    def get_size(self, unit: str):
        dimensions = {
            "mm": self.config.table_size,
            "cm": tuple([x / 10 for x in self.config.table_size]),
            "m": tuple([x / 1000 for x in self.config.table_size]),
            "px": self.config.projector_resolution,
        }
        return dimensions.get(unit)

    def __get_color_image(self):
        res, frame = self.vc.read()
        return np.asanyarray(frame)

    # find transformation for the markers with the given ids
    def __calculate_transformation(self, marker_ids, src, aruco_dict, parameters):
        mat = None
        inv_mat = None
        src = np.array(src, dtype="float32")
        mat_found = False
        while not mat_found:
            image = self.__get_color_image()
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            corners, ids, rejected_img_points = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
            frame_markers = aruco.drawDetectedMarkers(image, corners, ids, (0, 0, 255))
            cv2.namedWindow('Marker (Calibration)', cv2.WINDOW_AUTOSIZE)
            cv2.imshow('Marker (Calibration)', frame_markers)
            cv2.waitKey(1)
            if ids is not None:
                np_shape = np.array(corners)
                c = np_shape[:, 0, 0, :]
                points = c.reshape(c.shape[0], 2)
                points = list(zip(ids, points))
                points = sorted(filter(lambda x: (x[0] in marker_ids), points))
                points = np.array(points)

                if len(points) > 3:
                    points = points[:, 1]
                    dst = np.array([points[0], points[1], points[2], points[3]], dtype="float32")
                    mat = cv2.getPerspectiveTransform(src, dst)
                    inv_mat = cv2.getPerspectiveTransform(dst, src)
                    mat_found = True

        return mat, inv_mat

    def __calibrate(self):
        proj_marker_ids = self.config.projector_markers["marker"]
        proj_marker_size = self.config.projector_markers["size"]
        proj_marker_pos = self.config.projector_markers["position"]
        proj_w = self.config.projector_resolution[0]
        proj_h = self.config.projector_resolution[1]
        proj_abs_marker_pos = [
            [proj_marker_pos[0][0], proj_marker_pos[0][1]],
            [proj_w - proj_marker_pos[1][0] - proj_marker_size, proj_marker_pos[1][1]],
            [proj_marker_pos[2][0], proj_h - proj_marker_pos[2][1] - proj_marker_size],
            [proj_w - proj_marker_pos[3][0] - proj_marker_size, proj_h - proj_marker_pos[3][1] - proj_marker_size]
        ]

        table_marker_ids = self.config.table_markers["marker"]
        table_marker_pos = self.config.table_markers["position"]
        table_marker_size = self.config.table_markers["size"]
        table_w = self.config.table_size[0]
        table_h = self.config.table_size[1]
        table_abs_marker_pos = [
            [table_marker_pos[0][0], table_marker_pos[0][1]],
            [table_w - table_marker_size - table_marker_pos[1][0], table_marker_pos[1][1]],
            [table_marker_pos[2][0], table_h - table_marker_size - table_marker_pos[2][1]],
            [table_w - table_marker_size - table_marker_pos[3][0], table_h - table_marker_size - table_marker_pos[3][1]]
        ]

        aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
        parameters = aruco.DetectorParameters_create()

        # Calibrate camera to projector
        img = np.zeros((proj_h, proj_w), np.uint8)
        img[:, :] = 255
        for i in range(0, 4):
            marker = aruco.drawMarker(aruco_dict, proj_marker_ids[i], proj_marker_size)
            img[proj_abs_marker_pos[i][1]:proj_abs_marker_pos[i][1] + proj_marker_size,
            proj_abs_marker_pos[i][0]:proj_abs_marker_pos[i][0] + proj_marker_size] = marker

        # get the size of the screen
        screen = screeninfo.get_monitors()[self.config.projector_id]
        cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.moveWindow("window", screen.x - 1, screen.y - 1)
        cv2.imshow("window", img)
        cv2.waitKey(1)

        return self.__calculate_transformation(table_marker_ids, table_abs_marker_pos, aruco_dict, parameters), \
               self.__calculate_transformation(proj_marker_ids, proj_abs_marker_pos, aruco_dict, parameters)

    def __get_camera(self):
        vc = cv2.VideoCapture(self.config.camera_id)
        if vc.isOpened():
            successful, frame = vc.read()  # try to get the first frame
            if not successful:
                print("Error reading video stream")
                exit(1)
        else:
            print("Error opening video stream")
            exit(1)
        return vc

    def __start_update_loop(self):
        t = Thread(target=self.__update, args=(asyncio.new_event_loop(),))
        t.daemon = False
        t.start()
        pass

    def stop(self):
        """Freezes all plugins."""
        self.stopped = True

    def __update(self, loop):
        asyncio.set_event_loop(loop)
        while not self.stopped:
            frame = self.__get_color_image()
            for plugin in self.plugins:
                plugin.update(frame)
