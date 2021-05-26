# Energy App
This ARTable-Application is part of ViewBW. It visualizes cost and use of different energy sources by allowing 
the user to place power plants onto a map.
## Setup
Make sure you have all the dependencies for the main script and the ui. Especially GDAL, Fiona and rtree
might be difficult to install. https://www.lfd.uci.edu/~gohlke/pythonlibs/ is a good source for Windows binaries.

## Configuration and Resource Formats
The configuration is split up into several files:
### table.json
Configuration for ARTable. See ARTable documentation.
### resources/plant_types.json
Defines the plants associated with the tangibles.
Root node contains array `types` with objects having the following attributes:
* `name` : Internal name of the plant (e.g. Solarpark1)
* `type` : Type of energy produced. Influences prioritization and energy potential.
  Allowed values: solar, wind, water, bio, gas, coal, atom
* `energy_formula` : Formula for calculating the power of the plant. 
  Available variables are: `potential` (depends on type), `needed` (energy consumption), `population`.
* `cost_formula` : Formula for calculating cost incurred by energy production through the plant.
  Available variables are: `potential` (depends on type), `needed` (energy consumption), `population`,
  `power` (result of energy_formula).
* `emission_formula` : Formula for calculating emissions of the plant. 
  Available variables are: `potential` (depends on type), `needed` (energy consumption), `population`,
  `power` (result of energy_formula)
* `marker` : The marker id corresponding to this plant. Must be unique.

Example:

```json
{
  "types": [
    {
      "name": "Solarpark1",
      "type": "solar",
      "energy_formula": "population * 10000",
      "cost_formula": "power*1000*0.0824",
      "emission_formula": "power*0.0485",
      "marker": 10
    }
  ]
}
```
### resources/plant_type_names.json
Defines the display names of the energy types (same as for plant_types.json).

Example:
```json
{
  "solar": "Solaranlage",
  "wind": "Windpark",
  "water": "Wasserkraftwerk",
  "bio": "Biogasanlage",
  "gas": "Erdgaskraftwerk",
  "coal": "Kohlekraftwerk",
  "atom": "Atomkraftwerk"
}

```
### resources/places.json
Defines places that can be searched for.
Array of objects with the following attributes:
* `name` : Display/Search name
* `bounds` : [longitude_min, latitude_min, longitude_max, latitude_max]
* `population` : Number of inhabitants
* `nuts3` : NUTS3 code for the city. unused.
* `energy` : Power consumption in MWh per year.
* `emissions` : Emissions in annual tons. used to define 100% in emissions bar.

Example:
```json
[
  {
    "name": "Stadtkreis Karlsruhe",
    "bounds": [
      8.277349,
      48.94036,
      8.541143,
      49.091529
    ],
    "population": 312060,
    "nuts3": "DE122",
    "energy": 1432640.0,
    "emissions": 1485553.28704456
  }
]
```
### resources/shortcut_places.json
Defines behaviour of tangibles in the place search bar.
* `keyboard` : marker id for searching
* `places` : array of places similar to places.json. Each place has an additional 
value `marker` : marker id to change place to here.
### resources/years.json
Defines goals for 2020, 2030, 2050.
* `marker` : marker for selecting a year
* `2020`, `2030` ,`2050` : goals for the respective year 

The goals are values from 0 to 1 defining where they are shown on the bar. 
-1 is an invisible goal of 1.

Example:
```json
{
  "marker": 4,
  "2020": {
    "coverage_goal": -1,
    "emission_goal": 0.968,
    "cost_goal": -1
  },
  "2030": {
    "coverage_goal": -1,
    "emission_goal": 0.725,
    "cost_goal": -1
  },
  "2050": {
    "coverage_goal": -1,
    "emission_goal": 0.081,
    "cost_goal": -1
  }
}
```
### resources/statements.json
Defines statements displayed when a new plant is placed.

Must contain all plant types.
Must contain at least two statements per plant type.

* type : plant type, object mapping professions to statements.
    * profession : profession of statement issuer, array of statements.
        * statement: object defining a statement.
            * `temper` : one of positive, neutral, negative.
            * `text` : the statement's text, including line breaks.

Heavily truncated example:
```json
{
  "solar": {
    "economist": [
      {
        "temper": "positive",
        "text": "Die Installation ist auf bereits bebauten Flächen möglich."
      }
    ]
  }
}
```
### resources/static-layer.png
Image containing static ui elements. Overlaid onto map and bars, overlaid by info, statements etc.
### resources/stakeholders/
Contains icons for stakeholders, naming scheme is `<profession>_<temper>.png`, where profession is one of
conservationist, economist, scientist and temper is one of negative, neutral, positive. 
All combinations must exist.
### resources/windatlas_flaechen_2019.json
GeoJSON-data for wind availability.
### resources/Globalstrahlung/
Shapefile-data for insolation.
### resources/Wasserkraftpotential/
Shapefile-data for possible water plants.
### resources/MyriadPro-Regular.otf
Font used by the ui
### resources/hillshade.json
geotiler tile provider for shading
