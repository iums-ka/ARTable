from functools import partial

import geotiler
from geotiler.tile.io import fetch_tiles
from PIL import Image, ImageDraw, ImageFont
from xml.etree.ElementTree import parse
from geotiler.cache import caching_downloader
import matplotlib.pyplot as plt

from energy_app.geotiler_shelvecache import Cache

default_target = "Karlsruhe"
default_population = 313092
default_energy_consumption = 9100
default_coverage = 1
default_emission = .4
default_cost = .75
default_coverage_goal = .97
default_emission_goal = .45
default_cost_goal = .55


def find_bounds_for_name(target):
    # areas: http://overpass-api.de/api/interpreter?data=area(3600062611);rel["boundary"="administrative"](area);out tags center bb;
    print("Finding %s..." % target)
    areas = parse('resources/areas_bw.osm').getroot()
    parent_map = {c: p for p in areas.iter() for c in p}
    target_bounds = None
    for area in areas.iter('tag'):
        if area.attrib['k'] == 'name' and area.attrib['v'] == target:
            bb = parent_map[area].find('bounds').attrib
            target_bounds = (bb['minlon'], bb['minlat'], bb['maxlon'], bb['maxlat'])
            break
    if target_bounds is None:
        print("%s not found!" % target)
    return tuple(float(s) for s in target_bounds)


def render(target_bounds,
           population, energy_consumption,
           coverage, emission, cost,
           coverage_goal, emission_goal, cost_goal):
    # hint: lon, lat instead of lat, lon
    map_data = geotiler.Map(extent=target_bounds, size=(2423, 2435))
    map_data.zoom += 2
    print("Rendering map...")
    cache = Cache("tiles_cache")
    downloader = partial(caching_downloader, cache.get, cache.set, fetch_tiles)
    map_image = geotiler.render_map(map_data, downloader=downloader)
    cache.close()
    print("Drawing image...")
    # black background
    screen = Image.new('RGBA', (4902, 2756), color='black')
    # map (2423 x 2435 at 362, 172)
    screen.paste(map_image, (362, 172))
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
    screen.alpha_composite(Image.open('resources/static-layer.png'))
    # text (87 at 3467,195;3467,320;3467,445)
    text_s = 87
    text_1 = 195
    text_2 = 320
    text_3 = 445
    text_x = 3467
    font = ImageFont.truetype('MyriadPro-Regular.otf', text_s)
    draw_screen.text((text_x, text_1), default_target, 'white', font)
    import locale
    locale.setlocale(locale.LC_ALL, '')
    draw_screen.text((text_x, text_2), "{:n} Menschen".format(int(population)), 'white', font)
    draw_screen.text((text_x, text_3), "{:n} GWh".format(energy_consumption), 'white', font)
    # lines (12 x 178) rgb(153,153,153)
    line_w = 12
    line_h = 178
    line_1_y = bar_1 - (line_h - bar_h) / 2
    line_1_x = bar_x + bar_w * coverage_goal
    line_2_y = bar_2 - (line_h - bar_h) / 2
    line_2_x = bar_x + bar_w * emission_goal
    line_3_y = bar_3 - (line_h - bar_h) / 2
    line_3_x = bar_x + bar_w * cost_goal
    draw_screen.rectangle((line_1_x - line_w / 2, line_1_y, line_1_x + line_w / 2, line_1_y + line_h), (153, 153, 153))
    draw_screen.rectangle((line_2_x - line_w / 2, line_2_y, line_2_x + line_w / 2, line_2_y + line_h), (153, 153, 153))
    draw_screen.rectangle((line_3_x - line_w / 2, line_3_y, line_3_x + line_w / 2, line_3_y + line_h), (153, 153, 153))
    return screen


def render_default():
    return render(find_bounds_for_name(default_target),
                  default_population, default_energy_consumption,
                  default_coverage, default_emission, default_cost,
                  default_coverage_goal, default_emission_goal, default_cost_goal)


if __name__ == '__main__':
    ui = render_default()
    print("Done. Showing result...")
    fig = plt.figure(figsize=(4902, 2756), dpi=1)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(ui)
    plt.show()
