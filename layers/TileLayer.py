"""Folium tile layer with the map-management interface used by this app."""

from folium import TileLayer as FoliumTileLayer


class TileLayer(FoliumTileLayer):
	"""A Folium tile layer that can be added to or removed from a map."""

	def add_to_map(self, folium_map):
		"""Add this tile layer to ``folium_map`` and return it."""
		return self.add_to(folium_map)

	def remove_from_map(self, folium_map):
		"""Remove this tile layer from ``folium_map`` if it is present."""
		folium_map._children.pop(self._name, None)
