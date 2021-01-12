import json
from functools import partial

import geotiler
from geotiler.tile.io import fetch_tiles
from PIL import Image, ImageDraw, ImageFont  # todo: switch to cv2 for performance
from geotiler.cache import caching_downloader
import matplotlib.pyplot as plt
from shapely.geometry import Point
# install GDAL and Fiona first. Their wheels must be downloaded manually for Windows.
# rtree, which must be downloaded manually is also needed.
# https://www.lfd.uci.edu/~gohlke/pythonlibs/ is a good source for Windows binaries
import geopandas
from energy_app.geotiler_shelvecache import Cache

import shelve

default_name = "Karlsruhe"
default_bounds = [8.277349, 48.94036, 8.541143, 49.091529]
default_population = 313092
default_energy_consumption = 9100
default_coverage = 1
default_emission = .4
default_cost = .75
default_coverage_goal = .97
default_emission_goal = .45
default_cost_goal = .55


class UI:

    def __init__(self):
        self.map_data = None
        self.map_data_shading = None
        self.map_area = ((362, 173), (2784, 2606))
        self.place_selection_area = ((2615, 2446), (2743, 2574))
        print("Loading datasets...")
        self.data_cache = shelve.open("data_cache", writeback=True)
        if "sun" in self.data_cache.keys() and "wind" in self.data_cache.keys():
            self.insolation = self.data_cache["sun"]
            self.wind_potential = self.data_cache["wind"]
            self.data_cache.close()
        else:
            print("No cache found!")
            self.insolation = geopandas.read_file(
                "resources/Globalstrahlung/Globalstrahlung (kWh_m²)_polygon.shp", encoding='utf-8'
            ).to_crs(epsg=4326)
            self.wind_potential = geopandas.read_file(
                "resources/windatlas_flaechen_2019.json", encoding='utf-8'
            ).to_crs(epsg=4326)
            self.wind_potential = self.wind_potential.replace(
                {"<= 75": 75, "> 75 - 105": 105, "> 105 - 145": 145, "> 145 - 190": 190, "> 190 - 250": 250,
                 "> 250 - 310": 310, "> 310 - 375": 375, "> 375 - 515": 515, "> 515 - 660": 660, "> 660 - 1.600": 1000}
            )
            # does not help with the windows-sometimes-crash
            # self.get_closest_row((0,0),self.insolation)
            # self.get_closest_row((0,0),self.wind_potential)
            self.data_cache["sun"] = self.insolation
            self.data_cache["wind"] = self.wind_potential
            self.data_cache.close()
        print("Done.")
        self.static_layer = Image.open('resources/static-layer.png')
        self.map_image = None
        self.map_requires_rerender = True

    def set_position(self, target_bounds, zoom_in=2):
        # hint: lon, lat instead of lat, lon
        self.map_data = geotiler.Map(extent=target_bounds, size=self.get_map_size())
        self.map_data.zoom += zoom_in
        self.map_data_shading = geotiler.Map(extent=target_bounds, size=self.get_map_size())
        self.map_data_shading.zoom += zoom_in
        self.map_data_shading.provider = geotiler.provider.MapProvider(json.load(open("resources/hillshade.json", encoding='utf8', mode="r")))
        self.map_requires_rerender = True

    def render(self, place,
               population, energy_consumption,
               coverage, emission, cost,
               coverage_goal, emission_goal, cost_goal, search_data=None):
        # black background
        screen = Image.new('RGBA', (4902, 2756), color='black')
        # map (2423 x 2435 at 362, 172)
        if self.map_requires_rerender:
            cache = Cache("tiles_cache")
            downloader = partial(caching_downloader, cache.get, cache.set, fetch_tiles)
            self.map_image = geotiler.render_map(self.map_data, downloader=downloader)
            map_shading = geotiler.render_map(self.map_data_shading, downloader=downloader)
            cache.close()
            self.map_image.alpha_composite(map_shading)
            self.map_requires_rerender = False
        screen.paste(self.map_image, self.get_map_area()[0])
        # bars (1735 x 92 at 2887,814; 2887,1123; 2887,1429) rgb(248, 215, 61)
        bar_w = 1735
        bar_h = 92
        bar_x = 2887
        bar_1 = 814
        bar_2 = 1123
        bar_3 = 1429
        bar_c = (248, 215, 61)
        draw_screen = ImageDraw.Draw(screen)
        draw_screen.rectangle((bar_x, bar_1, bar_x + bar_w * coverage, bar_1 + bar_h), bar_c)
        draw_screen.rectangle((bar_x, bar_2, bar_x + bar_w * emission, bar_2 + bar_h), bar_c)
        draw_screen.rectangle((bar_x, bar_3, bar_x + bar_w * cost, bar_3 + bar_h), bar_c)
        # static layer (4902 x 2756)
        screen.alpha_composite(self.static_layer)
        # text (87 at 3467,195;3467,320;3467,445)
        text_s = 87
        text_1 = 195
        text_2 = 320
        text_3 = 445
        text_x = 3467
        font = ImageFont.truetype('MyriadPro-Regular.otf', text_s)
        draw_screen.text((text_x, text_1), place, 'white', font)
        import locale
        locale.setlocale(locale.LC_ALL, '')
        draw_screen.text((text_x, text_2), "{:n} Menschen".format(int(population)), 'white', font)
        draw_screen.text((text_x, text_3), "{:n} MWh".format(int(energy_consumption)), 'white', font)
        # lines (12 x 178) rgb(153,153,153)
        line_w = 12
        line_h = 178
        if coverage_goal >= 0:
            line_1_y = bar_1 - (line_h - bar_h) / 2
            line_1_x = bar_x + bar_w * coverage_goal
            draw_screen.rectangle((line_1_x - line_w / 2, line_1_y, line_1_x + line_w / 2, line_1_y + line_h),
                                  (153, 153, 153))
        if emission_goal >= 0:
            line_2_y = bar_2 - (line_h - bar_h) / 2
            line_2_x = bar_x + bar_w * emission_goal
            draw_screen.rectangle((line_2_x - line_w / 2, line_2_y, line_2_x + line_w / 2, line_2_y + line_h),
                              (153, 153, 153))
        if cost_goal >= 0:
            line_3_y = bar_3 - (line_h - bar_h) / 2
            line_3_x = bar_x + bar_w * cost_goal
            draw_screen.rectangle((line_3_x - line_w / 2, line_3_y, line_3_x + line_w / 2, line_3_y + line_h),
                                  (153, 153, 153))
        if search_data is not None:
            print(search_data)
            font = ImageFont.truetype('MyriadPro-Regular.otf', 42)
            draw_screen.text((2192, 2480), search_data[0], 'black', font)
            draw_screen.rectangle((2174, 2450, 2174 + 564, 2450 - len(search_data[2]) * 54), (255, 255, 255))
            if search_data[1] != -1:
                draw_screen.rectangle((2174, 2450 - search_data[1] * 54, 2174 + 564, 2450 - search_data[1] * 54 - 54),
                                      (100, 100, 255))
            for i in range(len(search_data[2])):
                draw_screen.text((2192, 2410 - i * 54), search_data[2][i], 'black', font)

        return screen

    def render_default(self):
        self.set_position(default_bounds)
        return self.render(default_name,
                           default_population, default_energy_consumption,
                           default_coverage, default_emission, default_cost,
                           default_coverage_goal, default_emission_goal, default_cost_goal)

    def get_insolation(self, image_coordinates):
        return self.closest_tile(image_coordinates, self.insolation, "CODE")

    def get_wind(self, image_coordinates):
        return self.closest_tile(image_coordinates, self.wind_potential, "klasse")

    def image_coordinates_to_geocode(self, image_coordinates):
        relative_coordinates = ((image_coordinates[0] - self.get_map_area()[0][0]),
                                (image_coordinates[1] - self.get_map_area()[0][1]))
        return self.map_data.geocode(relative_coordinates)

    def closest_tile(self, image_coordinates, dataframe, key):
        map_coordinates = self.image_coordinates_to_geocode(image_coordinates)
        # points, values = data_provider.sample(
        #    (self.map_data.geocode((0, 0)), self.map_data.geocode(self.get_map_size())))
        # return griddata(points, values, map_coordinates, method='cubic')
        result = self.get_closest_row(map_coordinates, dataframe)
        return result[key] if result is not None else None

    def get_closest_row(self, point, dataframe):
        epsilon = 0.1
        x, y = point
        spatial_index = dataframe.sindex
        filtered = dataframe.iloc[
            list(spatial_index.intersection((x - epsilon, y - epsilon, x + epsilon, y + epsilon)))
        ]
        if not len(filtered) == 0:
            closest = filtered.distance(Point(point)).idxmin()
            return dataframe.iloc[closest]
        return None

    def get_map_area(self):
        return self.map_area

    def get_map_size(self):
        return (self.map_area[1][0] - self.map_area[0][0]), (self.map_area[1][1] - self.map_area[0][1])

    def get_map_interaction_area(self):
        return self.map_area[0], (self.map_area[1][0], self.map_area[1][1] - 196)

    def get_place_selection_area(self):
        return self.place_selection_area

    def get_2020_area(self):
        return (2883, 2461), (2883 + 129, 2461 + 129)

    def get_2030_area(self):
        return (3723, 2461), (3723 + 129, 2461 + 129)

    def get_2050_area(self):
        return (4532, 2461), (4532 + 129, 2461 + 129)


if __name__ == '__main__':
    ui = UI().render_default()
    print("Done. Showing result...")
    fig = plt.figure(figsize=(4902, 2756), dpi=1)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(ui)
    plt.show()
