import aiohttp

from PIL import UnidentifiedImageError

from map.static_map import StaticMap


class Route:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def build_routes(self, places: tuple[str, str]):
        static_map = StaticMap()
        points = []
        steps = []

        for i in range(len(places) - 1):
            route = await self.get_route_callback(
                from_lat=places[i][0],
                from_lon=places[i][1],
                to_lat=places[i+1][0],
                to_lon=places[i+1][1],
            )
            if route['code'] != 'Ok':
                return 0

            points += route['waypoints']
            steps += route['routes'][0]['legs'][0]['steps']

        await self.session.close()

        static_map.add_marker(
                {
                    'cords': points[0]['location'],
                    'width': 10,
                    'color': 'green'
                }
            )
        for point in points[1:]:
            static_map.add_marker(
                {
                    'cords': point['location'],
                    'width': 10,
                    'color': 'red'
                }
            )
        for step in steps:
            static_map.add_line(
                {
                    'cords': step['geometry']['coordinates'],
                    'width': 5,
                    'color': 'blue'
                }
            )
        try:
            map_photo = await static_map.create()
        except UnidentifiedImageError:
            return 0

        return map_photo

    async def get_route_callback(
            self,
            from_lat: str,
            from_lon: str,
            to_lat: str,
            to_lon: str,
    ):
        params = [
            ('overview', 'false'),
            ('geometries', 'geojson'),
            ('steps', 'true')
        ]
        async with self.session.get(
            f'https://routing.openstreetmap.de/routed-car/route/v1/driving/'
            f'{from_lon},{from_lat};{to_lon},{to_lat}?',
            params=params
        ) as resp:
            response = await resp.json()

            return response
