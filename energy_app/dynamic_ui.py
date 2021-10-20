import json
import math
import os
from functools import partial

import locale
import geotiler
from geotiler.tile.io import fetch_tiles
from PIL import Image, ImageDraw, ImageFont
from geotiler.cache import caching_downloader
import matplotlib.pyplot as plt
from svgpath2mpl import parse_path
from shapely.geometry import Point
# install GDAL and Fiona first. Their wheels must be downloaded manually for Windows.
# rtree, which must be downloaded manually is also needed.
# https://www.lfd.uci.edu/~gohlke/pythonlibs/ is a good source for Windows binaries
import geopandas
from energy_app.geotiler_shelvecache import Cache

from OpenGL.GL import *
from OpenGL.GLUT import *
from freetype import *
import numpy as np

import shelve

stakeholder_icon_path = "resources/stakeholders/"

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
map_scale = 2


def gen_tex(img):
    img_tex = glGenTextures(1)
    img_data = img.convert("RGBA").tobytes()
    glBindTexture(GL_TEXTURE_2D, img_tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
    glBindTexture(GL_TEXTURE_2D, 0)
    return img_tex


class UI:

    def __init__(self, table):
        self.table = table
        self.map_data = None
        self.map_data_shading = None
        self.map_area = ((362, 173), (2784, 2606))
        self.place_selection_area = ((2615, 2446), (2743, 2574))
        self.screen_size = (4901, 2755)
        print("Loading datasets...")
        self.data_cache = shelve.open("data_cache", writeback=True)
        if "sun" in self.data_cache.keys() and "wind" in self.data_cache.keys() and "water" in self.data_cache.keys():
            self.insolation = self.data_cache["sun"]
            self.wind_potential = self.data_cache["wind"]
            self.water_potential = self.data_cache["water"]
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
            self.water_potential = geopandas.read_file(
                "resources/Wasserkraftpotenzial/ermitteltes_wasserkraftpotenzial__abfrage_.shp", encoding='utf-8'
            ).to_crs(epsg=4326)
            # does not help with the windows-sometimes-crash
            # self.get_closest_row((0,0),self.insolation)
            # self.get_closest_row((0,0),self.wind_potential)
            self.data_cache["sun"] = self.insolation
            self.data_cache["wind"] = self.wind_potential
            self.data_cache["water"] = self.water_potential
            self.data_cache.close()
        print("Loading textures...")
        self.static_layer = Image.open('resources/static-layer3.png')
        self.static_layer_tex = gen_tex(self.static_layer)
        self.tutorial_overlay = Image.open('resources/tutorial-overlay.png')
        self.tutorial_overlay_tex = gen_tex(self.tutorial_overlay)
        self.energieatlas_info = Image.open('resources/energieatlas-info.png')
        self.energieatlas_info_tex = gen_tex(self.energieatlas_info)
        self.map_image = None
        self.map_image_tex = None
        self.map_requires_rerender = True
        self.font_87 = self.makefont('resources/MyriadPro-Regular.otf', 87)
        self.font_72 = self.makefont('resources/MyriadPro-Regular.otf', 72)
        self.font_70 = self.makefont('resources/MyriadPro-Regular.otf', 70)
        self.font_64 = self.makefont('resources/MyriadPro-Regular.otf', 64)
        self.font_42 = self.makefont('resources/MyriadPro-Regular.otf', 42)
        self.stakeholder_icons = {}
        for icon_file in os.listdir(stakeholder_icon_path):
            if icon_file.endswith(".png"):
                icon_parts = icon_file.split(".")[0].split("_")
                img = Image.open(stakeholder_icon_path + icon_file)
                self.stakeholder_icons[(icon_parts[0], icon_parts[1])] = gen_tex(img)
        print("Done.")

    def set_position(self, target_bounds):
        # hint: lon, lat instead of lat, lon
        self.map_data = geotiler.Map(extent=target_bounds, size=[math.ceil(x/map_scale) for x in self.get_map_size()])
        self.map_data_shading = geotiler.Map(extent=target_bounds, size=[math.ceil(x/map_scale) for x in self.get_map_size()])
        self.map_data_shading.provider = geotiler.provider.MapProvider(
            json.load(open("resources/hillshade.json", encoding='utf8', mode="r")))
        self.map_requires_rerender = True

    def render(self, place,
               population, energy_consumption,
               show_popup, popup_position, popup_dataline, popup_text,
               coverage, emission, costings,
               coverage_goal, emission_goal, costings_goal,
               coverage_sign, emission_sign, costings_sign,
               search_data, visible_statements, active_year,
               show_tutorial, show_info):
        if show_info:
            return self.energieatlas_info
        # black background
        screen = Image.new('RGBA', self.screen_size, color='black')
        # map (2423 x 2435 at 362, 172)
        self.update_map()
        screen.paste(self.map_image, self.get_map_area()[0])
        # bars (1735 x 92 at 2887,814; 2887,1123; 2887,1429) rgb(248, 215, 61)
        bar_w = 1231
        bar_h = 70
        bar_x = 3572
        bar_1 = 738
        bar_2 = 907
        bar_3 = 1081
        bar_color_default = (248, 215, 61)
        bar_color_success = (188, 247, 61)
        bar_color_failure = (247, 120, 61)
        bar_c1 = bar_color_default if (coverage_goal < 0 and coverage < 1) or coverage < coverage_goal else bar_color_success
        bar_c2 = bar_color_default if (emission_goal < 0 and emission < 1) or emission < emission_goal else bar_color_failure
        bar_c3 = bar_color_default if (costings_goal < 0 and costings < 1) or costings < costings_goal else bar_color_failure
        draw_screen = ImageDraw.Draw(screen)
        draw_screen.rectangle((bar_x, bar_1, bar_x + bar_w * coverage, bar_1 + bar_h), bar_c1)
        draw_screen.rectangle((bar_x, bar_2, bar_x + bar_w * emission, bar_2 + bar_h), bar_c2)
        draw_screen.rectangle((bar_x, bar_3, bar_x + bar_w * costings, bar_3 + bar_h), bar_c3)
        text_s = 70
        font = ImageFont.truetype('resources/MyriadPro-Regular.otf', text_s)
        if coverage_sign > 0:
            draw_screen.text((bar_x + bar_w * coverage+5, bar_1 + bar_h/2 - text_s/2), "»", bar_c1, font)
        if coverage_sign < 0:
            draw_screen.text((bar_x + bar_w * coverage+5, bar_1 + bar_h/2 - text_s/2), "«", bar_c1, font)
        if emission_sign > 0:
            draw_screen.text((bar_x + bar_w * emission+5, bar_2 + bar_h/2 - text_s/2), "»", bar_c2, font)
        if emission_sign < 0:
            draw_screen.text((bar_x + bar_w * emission+5, bar_2 + bar_h/2 - text_s/2), "«", bar_c2, font)
        if costings_sign > 0:
            draw_screen.text((bar_x + bar_w * costings+5, bar_3 + bar_h/2 - text_s/2), "»", bar_c3, font)
        if costings_sign < 0:
            draw_screen.text((bar_x + bar_w * costings+5, bar_3 + bar_h/2 - text_s/2), "«", bar_c3, font)
        # static layer (4902 x 2756)
        screen.alpha_composite(self.static_layer)
        # text (87 at 3467,195;3467,320;3467,445)
        text_s = 87
        text_1 = 170
        text_2 = 300
        text_3 = 425
        text_x = 3500
        font = ImageFont.truetype('resources/MyriadPro-Regular.otf', text_s)
        draw_screen.text((text_x, text_1), place, 'white', font)
        locale.setlocale(locale.LC_ALL, '')
        draw_screen.text((text_x, text_2), "{:n} Menschen".format(int(population)), 'white', font)
        draw_screen.text((text_x, text_3), "{:n} MWh".format(int(energy_consumption)), 'white', font)
        # lines (12 x 178) rgb(153,153,153)
        line_w = 8
        line_h = 120
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
        if costings_goal >= 0:
            line_3_y = bar_3 - (line_h - bar_h) / 2
            line_3_x = bar_x + bar_w * costings_goal
            draw_screen.rectangle((line_3_x - line_w / 2, line_3_y, line_3_x + line_w / 2, line_3_y + line_h),
                                  (153, 153, 153))

        ul_y1 = 2656
        ul_x1 = {2020: 2869, 2030: 3768, 2050: 4655}[active_year]
        ul_y2 = ul_y1 + 6
        ul_x2 = ul_x1 + 148

        draw_screen.rectangle((ul_x1, ul_y1, ul_x2 ,ul_y2), (255, 255, 255))

        if search_data is not None:
            font = ImageFont.truetype('resources/MyriadPro-Regular.otf', 42)
            draw_screen.text((2192, 2480), search_data[0], 'black', font)
            draw_screen.rectangle((2174, 2450, 2174 + 564, 2450 - len(search_data[2]) * 54), (255, 255, 255))
            if search_data[1] != -1:
                draw_screen.rectangle((2174, 2450 - search_data[1] * 54, 2174 + 564, 2450 - search_data[1] * 54 - 54),
                                      (100, 100, 255))
            for i in range(len(search_data[2])):
                draw_screen.text((2192, 2410 - i * 54), search_data[2][i], 'black', font)
        if len(visible_statements) >= 1:
            self.draw_statement(draw_screen, screen, 2896, 1360, visible_statements[0])
        if len(visible_statements) >= 2:
            self.draw_statement(draw_screen, screen, 2896, 1840, visible_statements[1])

        if show_popup:
            popup_displace = (100, -120)
            font = ImageFont.truetype('resources/MyriadPro-Regular.otf', 64)
            ppx, ppy = popup_position[0] + popup_displace[0], popup_position[1] + popup_displace[1]
            draw_screen.rectangle((ppx, ppy, ppx + 820, ppy + 340 + 72 * popup_text.count("\n")),
                                  (0, 0, 0, 178))
            draw_screen.text((ppx + 10, ppy + 10), popup_dataline, 'white', font)
            draw_screen.text((ppx + 10, ppy + 272), popup_text, 'white', font)

        if show_tutorial:
            screen.alpha_composite(self.tutorial_overlay)
        return screen

    def update_map(self):
        if self.map_requires_rerender:
            cache = Cache("tiles_cache")
            downloader = partial(caching_downloader, cache.get, cache.set, fetch_tiles)
            self.map_image = geotiler.render_map(self.map_data, downloader=downloader)
            map_shading = geotiler.render_map(self.map_data_shading, downloader=downloader)
            cache.close()
            self.map_image.alpha_composite(map_shading)
            self.map_image = self.map_image.resize(self.get_map_size())
            if self.map_data.zoom > 10:
                self.map_image = self.apply_water_overlay(
                    self.map_image)  # werden hier die Wasserkraftwerke reingeladen?
            self.map_requires_rerender = False
            if self.map_image_tex is None:
                self.map_image_tex = gen_tex(self.map_image)
            else:
                img_data = self.map_image.convert("RGBA").tobytes()
                glBindTexture(GL_TEXTURE_2D, self.map_image_tex)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.map_image.width, self.map_image.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
                glBindTexture(GL_TEXTURE_2D, 0)

    def rendergl(self, place,
                 population, energy_consumption,
                 show_popup, popup_position, popup_dataline, popup_text,
                 coverage, emission, costings,
                 coverage_goal, emission_goal, costings_goal,
                 coverage_sign, emission_sign, costings_sign,
                 search_data, visible_statements, active_year,
                 show_tutorial, show_info):
        # setup
        w = glutGetWindow()
        glutSetWindow(self.table.draw_context)
        glBindFramebuffer(GL_FRAMEBUFFER, self.table.fbo)
        glViewport(0, 0, self.table.config.table_size[0], self.table.config.table_size[1])
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.table.config.table_size[0], 0, self.table.config.table_size[1], -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # drawing
        if show_info:
            self.fullscreen_composite(self.energieatlas_info_tex)
            glFlush()
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            glutSetWindow(w)
            self.table.update_display()
            return

        # map (2423 x 2435 at 362, 172)
        self.update_map()
        self.composite(self.map_image_tex, self.map_area[0][0], self.map_area[0][1], self.map_area[1][0], self.map_area[1][1])

        # bars (1735 x 92 at 2887,814; 2887,1123; 2887,1429) rgb(248, 215, 61)
        bar_w = 1231
        bar_h = 70
        bar_x = 3572
        bar_1 = 738
        bar_2 = 907
        bar_3 = 1081
        bar_color_default = (248, 215, 61)
        bar_color_success = (188, 247, 61)
        bar_color_failure = (247, 120, 61)
        bar_c1 = bar_color_default if (coverage_goal < 0 and coverage < 1) or coverage < coverage_goal else bar_color_success
        bar_c2 = bar_color_default if (emission_goal < 0 and emission < 1) or emission < emission_goal else bar_color_failure
        bar_c3 = bar_color_default if (costings_goal < 0 and costings < 1) or costings < costings_goal else bar_color_failure
        self.draw_bar(bar_x, bar_1, bar_w, bar_h, bar_c1, coverage, coverage_sign)
        self.draw_bar(bar_x, bar_2, bar_w, bar_h, bar_c2, emission, emission_sign)
        self.draw_bar(bar_x, bar_3, bar_w, bar_h, bar_c3, costings, costings_sign)

        # static layer
        self.fullscreen_composite(self.static_layer_tex)

        # text (87 at 3467,195;3467,320;3467,445)
        text_s = 87
        text_1 = 170
        text_2 = 300
        text_3 = 425
        text_x = 3500
        locale.setlocale(locale.LC_ALL, '')
        self.draw_text(self.font_87, place, text_x, text_1, (1,1,1,1))
        self.draw_text(self.font_87, "{:n} Menschen".format(int(population)), text_x, text_2, (1,1,1,1))
        self.draw_text(self.font_87, "{:n} MWh".format(int(energy_consumption)), text_x, text_3, (1,1,1,1))

        # lines (12 x 178) rgb(153,153,153)
        line_w = 8
        line_h = 120
        if coverage_goal >= 0:
            line_1_y = bar_1 - (line_h - bar_h) / 2
            line_1_x = bar_x + bar_w * coverage_goal
            self.draw_rectangle((line_1_x - line_w / 2, line_1_y, line_1_x + line_w / 2, line_1_y + line_h),
                                  (153./255., 153./255., 153./255., 1))
        if emission_goal >= 0:
            line_2_y = bar_2 - (line_h - bar_h) / 2
            line_2_x = bar_x + bar_w * emission_goal
            self.draw_rectangle((line_2_x - line_w / 2, line_2_y, line_2_x + line_w / 2, line_2_y + line_h),
                                  (153./255., 153./255., 153./255., 1))
        if costings_goal >= 0:
            line_3_y = bar_3 - (line_h - bar_h) / 2
            line_3_x = bar_x + bar_w * costings_goal
            self.draw_rectangle((line_3_x - line_w / 2, line_3_y, line_3_x + line_w / 2, line_3_y + line_h),
                                  (153./255., 153./255., 153./255., 1))

        # underline year
        ul_y1 = 2656
        ul_x1 = {2020: 2869, 2030: 3768, 2050: 4655}[active_year]
        ul_y2 = ul_y1 + 6
        ul_x2 = ul_x1 + 148

        self.draw_rectangle((ul_x1, ul_y1, ul_x2 ,ul_y2), (1, 1, 1, 1))

        # search box
        if search_data is not None:
            self.draw_text(self.font_42, search_data[0], 2192, 2480, (0, 0, 0, 1))
            self.draw_rectangle((2174, 2450, 2174 + 564, 2450 - len(search_data[2]) * 54), (1, 1, 1, 1))
            if search_data[1] != -1:
                self.draw_rectangle((2174, 2450 - search_data[1] * 54, 2174 + 564, 2450 - search_data[1] * 54 - 54),
                                    (100./255., 100./255., 255./255., 1))
            for i in range(len(search_data[2])):
                self.draw_text(self.font_42, search_data[2][i], 2192, 2410 - i * 54, (0, 0, 0, 1))

        # statements
        if len(visible_statements) >= 1:
            self.draw_statement_gl(2896, 1360, visible_statements[0])
        if len(visible_statements) >= 2:
            self.draw_statement_gl(2896, 1840, visible_statements[1])

        # plant info popup
        if show_popup:
            popup_displace = (100, -120)
            ppx, ppy = popup_position[0] + popup_displace[0], popup_position[1] + popup_displace[1]
            self.draw_rectangle((ppx, ppy, ppx + 820, ppy + 340 + 72 * popup_text.count("\n")),
                                (0, 0, 0, 0.7))
            self.draw_text(self.font_64, popup_dataline, ppx + 10, ppy + 10, (1, 1, 1, 1))
            self.draw_text(self.font_64, popup_text, ppx + 10, ppy + 272, (1, 1, 1, 1))

        # tutorial
        if show_tutorial:
            self.fullscreen_composite(self.tutorial_overlay_tex)

        # finish
        glFlush()
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glutSetWindow(w)
        self.table.update_display()

    def draw_bar(self, bar_x, bar_y, bar_w, bar_h, bar_c, percentage, delta_sign):
        bar_c = (bar_c[0] / 255., bar_c[1] / 255., bar_c[2] / 255., 1)
        self.draw_rectangle((bar_x, bar_y, bar_x + bar_w * percentage, bar_y + bar_h), bar_c)
        if delta_sign > 0:
            self.draw_text(self.font_70, "»", bar_x + bar_w * percentage + 5, bar_y - bar_h / 2 + 70 / 2, bar_c)
        if delta_sign < 0:
            self.draw_text(self.font_70, "«", bar_x + bar_w * percentage + 5, bar_y - bar_h / 2 + 70 / 2, bar_c)

    def draw_rectangle(self, bounds, color):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor(color)
        glRectd(*bounds)
        glDisable(GL_BLEND)

    def draw_statement(self, draw_screen, screen, x, y, statement):
        icon = Image.open("resources/stakeholders/{}_{}.png".format(statement["from"], statement["temper"]))
        icon = icon.resize((270, 270))
        screen.alpha_composite(icon, (x,y))
        font = ImageFont.truetype('resources/MyriadPro-Regular.otf', 72)
        font_smaller = ImageFont.truetype('resources/MyriadPro-Regular.otf', 64)
        draw_screen.text((x+300, y-30), "(" + statement["type"] + ")", 'gray', font_smaller, spacing=16)
        draw_screen.text((x+300, y+40), statement["text"], 'white', font, spacing=16)

    def draw_statement_gl(self, x, y, statement):
        icon = self.stakeholder_icons[(statement["from"], statement["temper"])]
        self.composite(icon, x, y, x+270, y+270)
        self.draw_text(self.font_64, "(" + statement["type"] + ")", x+300, y-30, (0.5, 0.5, 0.5, 1))
        self.draw_text(self.font_72, statement["text"], x+300, y+40, (1, 1, 1, 1))

    def render_default(self):
        self.set_position(default_bounds)
        return self.render(default_name,
                           default_population, default_energy_consumption,
                           default_coverage, default_emission, default_cost,
                           default_coverage_goal, default_emission_goal, default_cost_goal,
                           0, 0, 0, None, [], 2020, False, False)

    def get_insolation(self, image_coordinates):
        return self.closest_tile(image_coordinates, self.insolation, "CODE")

    def get_wind(self, image_coordinates):
        return self.closest_tile(image_coordinates, self.wind_potential, "klasse")

    def get_water(self, image_coordinates):
        map_coordinates = self.image_coordinates_to_geocode(image_coordinates)
        x, y = map_coordinates
        spatial_index = self.water_potential.sindex
        closest = self.water_potential.iloc[
            list(spatial_index.nearest((x, y)))
        ]
        if any(closest.distance(Point(x, y)) <= 0.1):
            return closest["EEBW_WAS_6"].values[0]
        return None

    def image_coordinates_to_geocode(self, image_coordinates):
        relative_coordinates = ((image_coordinates[0] - self.get_map_area()[0][0]),
                                (image_coordinates[1] - self.get_map_area()[0][1]))
        relative_coordinates = [math.ceil(x/map_scale) for x in relative_coordinates]
        return self.map_data.geocode(relative_coordinates)

    def closest_tile(self, image_coordinates, dataframe, key):
        map_coordinates = self.image_coordinates_to_geocode(image_coordinates)
        # points, values = data_provider.sample(
        #    (self.map_data.geocode((0, 0)), self.map_data.geocode(self.get_map_size())))
        # return griddata(points, values, map_coordinates, method='cubic')
        result = self.get_closest_row(map_coordinates, dataframe)
        return result[key] if result is not None else None

    def get_closest_row(self, point, dataframe, epsilon=0.1):
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
        return (2883, 2446), (2883 + 129, 2446 + 129)

    def get_2030_area(self):
        return (3784, 2448), (3784 + 129, 2448 + 129)

    def get_2050_area(self):
        return (4674, 2442), (4674 + 129, 2442 + 129)

    def apply_water_overlay(self, base):
        # reverse geocode
        positions = []
        for data in self.water_potential.iterrows():
            img_pos = self.map_data.rev_geocode((data[1].geometry.x, data[1].geometry.y))
            img_pos = [math.ceil(x*map_scale) for x in img_pos]
            # filter points outside of map
            if 0 <= img_pos[0] <= self.get_map_size()[0] and 0 <= img_pos[1] <= self.get_map_size()[1]:
                positions.append(img_pos)
        if len(positions) == 0:
            return base  # no points to be rendered
        # plot
        plt.interactive(False)
        fig = plt.figure(figsize=self.get_map_size(), dpi=1)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        ax.imshow(base)
        x, y = zip(*positions)
        drop = parse_path("m -8.2799839,0.07233615 c 0,-4.57587425 3.70948,-8.28535115 8.28535598,-8.28535115 "
                          "4.57587602,0 8.28535582,3.7094769 8.28535562,8.28535115 C 8.2907274,4.64821 "
                          "0.00537208,19.583016 0.00537208,19.583016 c 0,0 -8.28535598,-14.934806 "
                          "-8.28535598,-19.51067985 z")
        ax.scatter(x, y, c='b', s=15000000, alpha=0.8, marker=drop)
        fig.canvas.draw()
        return Image.frombytes('RGB', fig.canvas.get_width_height(), fig.canvas.tostring_rgb())

    def fullscreen_composite(self, tex):
        self.composite(tex, 0., 0., self.table.config.table_size[0], self.table.config.table_size[1])

    def composite(self, tex, x_min, y_min, x_max, y_max):
        glColor(1., 1., 1., 1.)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glTexCoord2f(0., 0.)
        glVertex2f(x_min, y_min)
        glTexCoord2f(0., 1.)
        glVertex2f(x_min, y_max)
        glTexCoord2f(1., 1.)
        glVertex2f(x_max, y_max)
        glTexCoord2f(1., 0.)
        glVertex2f(x_max, y_min)
        glEnd()
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_BLEND)
        glBindTexture(GL_TEXTURE_2D, 0)

    def draw_text(self, font, text, x, y, color):
        glActiveTexture(GL_TEXTURE0)
        glEnable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor(color)
        glBindTexture(GL_TEXTURE_2D, font[1])
        glPushMatrix()
        glTranslate(x, y, 0)
        glPushMatrix()
        glListBase(font[0])
        glCallLists([ord(c) for c in text])
        glPopMatrix()
        glPopMatrix()
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_BLEND)
        glBindTexture(GL_TEXTURE_2D, 0)

    def makefont(self, file_name, size):
        # Load font  and check it is monotype
        face = Face(file_name)
        face.set_char_size(size * 64)

        # Determine largest glyph size
        width, height, ascender, descender = 0, 0, 0, 0
        for c in range(32, 16 * 16):
            face.load_char(chr(c), FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
            bitmap = face.glyph.bitmap
            width = max(width, bitmap.width)
            ascender = max(ascender, face.glyph.bitmap_top)
            descender = max(descender, bitmap.rows - face.glyph.bitmap_top)
        height = ascender + descender

        # Generate texture data
        Z = np.zeros((height * 14, width * 16), dtype=np.ubyte)
        widths = np.zeros((16 * 16,))
        for j in range(14):
            for i in range(16):
                face.load_char(chr(32 + j * 16 + i), FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
                bitmap = face.glyph.bitmap
                x = i * width
                y = j * height + ascender - face.glyph.bitmap_top
                Z[y:y + bitmap.rows, x:x + bitmap.width].flat = bitmap.buffer
                widths[(j + 2) * 16 + i] = bitmap.width
        lefts = np.zeros((16 * 16,))
        advs = np.zeros((16 * 16,))
        for i in range(16 * 16):
            face.load_char(chr(i), FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
            lefts[i] = face.glyph.bitmap_left
            advs[i] = face.glyph.metrics.horiAdvance

        # Bound texture
        texid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texid)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_ALPHA, Z.shape[1], Z.shape[0], 0,
                     GL_ALPHA, GL_UNSIGNED_BYTE, Z)

        # Generate display lists
        dx, dy = width / float(Z.shape[1]), height / float(Z.shape[0])
        base = glGenLists(16 * 16)
        for i in range(16 * 16):
            c = chr(i)
            x = i % 16
            y = i // 16 - 2
            glNewList(base + i, GL_COMPILE)
            if c == '\n':
                glPopMatrix()
                glTranslatef(0, height, 0)
                glPushMatrix()
            elif c == '\t':
                glTranslatef((advs[i] / 64), 0, 0)
            elif i >= 32:
                glTranslatef(lefts[i], -descender / 2, 0)
                glBegin(GL_QUADS)
                glTexCoord2f(x * dx, (y + 1) * dy), glVertex(0, height)
                glTexCoord2f(x * dx, y * dy), glVertex(0, 0)
                glTexCoord2f(x * dx + widths[i] / float(Z.shape[1]), y * dy), glVertex(widths[i], 0)
                glTexCoord2f(x * dx + widths[i] / float(Z.shape[1]), (y + 1) * dy), glVertex(widths[i], height)
                glEnd()
                glTranslatef(advs[i] / 64 - lefts[i], descender / 2, 0)
            glEndList()
        return base, texid


if __name__ == '__main__':
    ui = UI().render_default()
    print("Done. Showing result...")
    fig = plt.figure(figsize=ui.screen_size, dpi=1)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(ui)
    plt.show()
