import asyncio

import numpy as np
import cv2
from PIL import Image
from cv2 import aruco
import screeninfo
from threading import Thread

from ctypes import c_uint

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GL.ARB.framebuffer_object import *
from OpenGL.GL.EXT.framebuffer_object import *

from artable.configuration import Configuration

from artable.plugins.Plugin import Plugin


class ARTableGL:
    def __init__(self, config: Configuration):
        self.config = config
        self.vc = self.__get_camera()
        print("Calibrating table...")
        if self.config.has_projector:
            (self.table_camera_t, self.camera_table_t), (
                self.projector_camera_t, self.camera_projector_t) = self.__calibrate()
        else:
            (self.table_camera_t, self.camera_table_t) = self.__calibrate()
        print("Done.")
        cv2.destroyWindow('Marker (Calibration)')
        self.plugins = set()
        self.stopped = False
        self.image_corners = ((0, 0), self.config.table_size)
        self.image_size = self.config.table_size
        self.tex, self.fbo, self.draw_context, self.display_context = self.initGraphics()

    def initGraphics(self):
        glutInit(sys.argv)
        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
        glutInitWindowSize(0, 0)
        glutCreateWindow("OpenGL Offscreen")
        glutHideWindow()
        glutDisplayFunc(lambda: ())
        glutMainLoopEvent()
        fbo = c_uint(1)
        glGenFramebuffers(1, fbo)
        glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.config.projector_resolution[0], self.config.projector_resolution[1], 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glFramebufferTexture(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, tex, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glViewport(0, 0, self.config.projector_resolution[0], self.config.projector_resolution[1])
        draw_context = glutGetWindow()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glutSetOption(GLUT_RENDERING_CONTEXT, GLUT_USE_CURRENT_CONTEXT)
        glutCreateWindow("OpenGL Display")
        glutDisplayFunc(self.display)
        display_context = glutGetWindow()
        return tex, fbo, draw_context, display_context

    def table_to_image_coords(self, points):
        if not self.config.has_projector:
            raise AssertionError("No projector configured.")
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
        if not self.config.has_projector:
            raise AssertionError("No projector configured.")
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

    def update_display(self):
        w = glutGetWindow()
        glutSetWindow(self.display_context)
        glutMainLoopEvent()
        glutSetWindow(w)

    def display_py_image(self, image):
        w = glutGetWindow()
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image = image.resize((self.config.projector_resolution[0], self.config.projector_resolution[1]))
        img_data = image.convert("RGB").tobytes()
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
        glutSetWindow(w)

    def display(self):
        glClearColor(0, 0, 0, 1)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.config.projector_resolution[0], 0, self.config.projector_resolution[1], -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadMatrixd(self.table_camera_t)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # clear the screen to the color of glClearColor
        glColor(1, 1, 1, 1)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glEnable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glTexCoord2f(0., 0.)
        glVertex2f(100., 100.)
        glTexCoord2f(0., 1.)
        glVertex2f(100., self.config.projector_resolution[1] - 100.)
        glTexCoord2f(1., 1.)
        glVertex2f(self.config.projector_resolution[0] - 100., self.config.projector_resolution[1] - 100.)
        glTexCoord2f(1., 0.)
        glVertex2f(self.config.projector_resolution[0] - 100., 100.)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, 0)
        glFlush()
        glutSwapBuffers()

    def add_plugin(self, plugin: Plugin):
        if self.config.has_projector:
            plugin.set_transforms(self.table_camera_t, self.camera_table_t, self.camera_projector_t,
                                  self.projector_camera_t)
        else:
            plugin.set_transforms(self.table_camera_t, self.camera_table_t)
        self.plugins.add(plugin)

    def remove_plugin(self, plugin: Plugin):
        plugin.removed()
        self.plugins.remove(plugin)

    def get_size(self, unit: str = "mm"):
        dimensions = {
            "mm": self.config.table_size,
            "cm": tuple([x / 10 for x in self.config.table_size]),
            "m": tuple([x / 1000 for x in self.config.table_size])
        }
        if self.config.has_projector:
            dimensions["px"] = self.config.projector_resolution
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
                points = np.array(points, dtype=object)

                if len(points) > 3:
                    points = points[:, 1]
                    dst = np.array([points[0], points[1], points[2], points[3]], dtype="float32")
                    mat = cv2.getPerspectiveTransform(src, dst)
                    inv_mat = cv2.getPerspectiveTransform(dst, src)
                    mat_found = True

        return mat, inv_mat

    def __calibrate(self):
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

        aruco_dict = aruco.Dictionary_get(self.config.marker_dict)
        parameters = aruco.DetectorParameters_create()

        table_tf = self.__calculate_transformation(table_marker_ids, table_abs_marker_pos, aruco_dict, parameters)

        if self.config.has_projector:
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

            proj_tf = self.__calculate_transformation(proj_marker_ids, proj_abs_marker_pos, aruco_dict, parameters)
            return table_tf, proj_tf

        return table_tf

    def __get_camera(self):
        vc = cv2.VideoCapture(self.config.camera_id)
        vc.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_resolution[0])
        vc.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_resolution[1])
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

    def start(self):
        self.__start_update_loop()
