import json


class PlaceProvider:

    def __init__(self, filename="resources/places.json"):
        self.filename = filename
        self.places = []
        self.reload()

    def list_all_containing(self, substring):
        names = []
        for place in self.places:
            if substring.lower() in place['name'].lower():
                names.append(place["name"])
        return names

    def get(self, name):
        for place in self.places:
            if name == place['name']:
                return place

    def reload(self):
        self.places = json.load(open(self.filename))