import json


class Configuration:
    def __init__(self, filepath):
        with open(filepath) as config_file:
            data = json.load(config_file)
            projector = data["projector"]
            table = data["table"]
            self.projector_resolution = (projector["width"], projector["height"])
            self.projector_markers = projector["marker"]
            self.table_size = (table["width"], table["height"])
            self.table_markers = table["marker"]
            self.projector_id = projector["screen"]
            self.camera_id = data["camera"]["index"]
            self.camera_resolution = (data["camera"]["width"], data["camera"]["height"])
