import json
from cv2 import aruco


class Configuration:
    def __init__(self, filepath):
        with open(filepath) as config_file:
            data = json.load(config_file)
            self.has_projector = False
            if "projector" in data:
                self.has_projector = True
                projector = data["projector"]
                self.projector_resolution = (projector["width"], projector["height"])
                self.projector_markers = projector["marker"]
                self.projector_id = projector["screen"]
            table = data["table"]
            self.table_size = (table["width"], table["height"])
            self.table_markers = table["marker"]
            self.marker_dict = int(aruco.__dict__[table["marker_dict"]])
            self.camera_id = data["camera"]["index"]
            self.camera_resolution = (data["camera"]["width"], data["camera"]["height"])
