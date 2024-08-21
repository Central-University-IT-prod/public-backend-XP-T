import asyncio
import math
from io import BytesIO
import aiohttp

from PIL import Image
from PIL.ImageDraw import ImageDraw


class StaticMap:
    def __init__(self):
        self.session = aiohttp.ClientSession()

        self.markers = []
        self.lines = []

    def add_line(self, line) -> None:
        self.lines.append(line)

    def add_marker(self, marker) -> None:
        self.markers.append(marker)

    def x_to_pixels(self, x):
        center = self.center()
        px = (x - center[0]) * 256 + 1000
        return int(round(px))

    def y_to_pixels(self, y):
        center = self.center()
        px = (y - center[1]) * 256 + 600
        return int(round(px))

    def lon_to_pixels(self, lon, zoom):
        center = self.center()
        px = (((lon + 180) / 360) * pow(2, zoom) - center[0]) * 256 + 1000
        return int(round(px))

    def lat_to_pixels(self, lat, zoom):
        center = self.center()
        px = ((1 - math.log(math.tan(lat * math.pi / 180) + 1 /
                            math.cos(lat * math.pi / 180)) /
               math.pi) / 2 * pow(2, zoom) - center[1]) * 256 + 600
        return int(round(px))

    async def create(self):
        image = Image.new(mode="RGB", size=(2000, 1200), color='white')
        pic = await self.generate_map()
        drawn = await self.render_ui()

        image.paste(pic, mask=pic)
        image.paste(drawn, mask=drawn)
        pic = BytesIO()
        pic.name = 'route.png'
        image.save(pic, 'PNG')
        pic.seek(0)

        return pic

    async def generate_map(self):
        image = Image.new(mode="RGBA", size=(2000, 1200), color=(0, 0, 0, 0))
        zoom = self.zoom()
        center_x, center_y = self.center()
        x_max = int(math.ceil(center_x + (1000 / 256)))
        y_max = int(math.ceil(center_y + (600 / 256)))
        x_min = int(math.floor(center_x - (1000 / 256)))
        y_min = int(math.floor(center_y - (600 / 256)))

        tiles = []
        for x in range(x_min, x_max):
            for y in range(y_min, y_max):
                tiles.append((x, y, zoom))

        tasks = [self.api_tile(tile) for tile in tiles]

        responses = await asyncio.gather(*tasks)

        for i in range(len(tiles)):
            tile = tiles[i]
            img = responses[i]
            image.paste(
                im=img,
                box=(
                    self.x_to_pixels(tile[0]),
                    self.y_to_pixels(tile[1]),
                    self.x_to_pixels(tile[0] + 1),
                    self.y_to_pixels(tile[1] + 1),
                )
            )

        return image

    async def render_ui(self):
        zoom = self.zoom()
        image = Image.new(mode="RGBA", size=(2000, 1200), color=(0, 0, 0, 0))
        draw = ImageDraw(image)

        for line in self.lines:
            points = [(
                    self.lon_to_pixels(cord[0], zoom),
                    self.lat_to_pixels(cord[1], zoom),
                ) for cord in line['cords']]

            draw.line(points, fill=line['color'], width=line['width'])

        for marker in self.markers:
            point = (
                self.lon_to_pixels(marker['cords'][0], zoom),
                self.lat_to_pixels(marker['cords'][1], zoom)
            )
            draw.ellipse((
                point[0] - marker['width'],
                point[1] - marker['width'],
                point[0] + marker['width'],
                point[1] + marker['width']
            ), fill=marker['color'])

        return image

    def zoom(self):
        lon_min = min(marker['cords'][0] for marker in self.markers)
        lon_max = max(marker['cords'][0] for marker in self.markers)
        lat_min = min(marker['cords'][1] for marker in self.markers)
        lat_max = max(marker['cords'][1] for marker in self.markers)

        zoom_lon = math.log(
            350.0 / 256.0 * 1499 /
            (lon_max - lon_min)
        ) / math.log(2)
        zoom_lat = math.log(
            170.0 / 256.0 * 1499 /
            (lat_max - lat_min)
        ) / math.log(2)

        return int(min(zoom_lon, zoom_lat))

    def center(self):
        lon_min = min(marker['cords'][0] for marker in self.markers)
        lon_max = max(marker['cords'][0] for marker in self.markers)
        lat_min = min(marker['cords'][1] for marker in self.markers)
        lat_max = max(marker['cords'][1] for marker in self.markers)

        zoom = self.zoom()
        lon_center = (lon_max + lon_min) / 2
        lat_center = (lat_max + lat_min) / 2
        center_x = ((lon_center + 180) / 360) * pow(2, zoom)
        center_y = (1 - math.log(math.tan(lat_center * math.pi / 180) +
                                 1 / math.cos(lat_center * math.pi / 180)
                                 ) / math.pi) / 2 * pow(2, zoom)

        return center_x, center_y

    async def api_tile(self, tile):
        x = tile[0]
        y = tile[1]
        zoom = tile[2]

        async with self.session.get(
            f"https://tile.openstreetmap.de/{zoom}/{x}/{y}.png"
        ) as resp:
            pic = BytesIO(await resp.read())
            return Image.open(pic).convert("RGBA")
