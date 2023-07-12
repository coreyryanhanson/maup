import pandas
import geopandas
# Added numpy import to handle output of STRtree query
import numpy

from shapely.prepared import prep
from shapely.strtree import STRtree
from .progress_bar import progress


def get_geometries(geometries):
    return getattr(geometries, "geometry", geometries)


class IndexedGeometries:
    def __init__(self, geometries):
        self.geometries = get_geometries(geometries)
# Lines commented out because this won't work in shapely 2; geometries are now immutable.
# (But I don't really understand why it was ever here because it isn't needed!)
#        for i, geometry in self.geometries.items():  
#            geometry.index = i                        
        self.spatial_index = STRtree(self.geometries)
        self.index = self.geometries.index


    def query(self, geometry):  
# Edited because STRTree queries are handled differently in shapely 2; they return 
# a list of INTEGER INDICES (i.e., RangeIndex) of relevant geometries instead of the 
# geometries themselves.
# IMPORTANT EDGE CASE: When "geometry" is multi-part, this query will return a
# (2 x n) array instead of a (1 x n) array, so it's safest to flatten the query
# output before proceeding.
#        relevant_indices = [geom.index for geom in self.spatial_index.query(geometry)]
        relevant_integer_index_array = self.spatial_index.query(geometry)
        relevant_integer_indices = [*set(numpy.ndarray.flatten(relevant_integer_index_array))]
        relevant_geometries = self.geometries.iloc[relevant_integer_indices]
        return relevant_geometries

    def intersections(self, geometry):  
        relevant_geometries = self.query(geometry)  
        intersections = relevant_geometries.intersection(geometry)
        return intersections[-(intersections.is_empty | intersections.isna())]

    def covered_by(self, container):   
        relevant_geometries = self.query(container)
        prepared_container = prep(container)

        if len(relevant_geometries) == 0:  # in case nothing is covered
            return relevant_geometries
        else:
            selected_geometries = relevant_geometries.apply(prepared_container.covers)
            return relevant_geometries[selected_geometries]

    def assign(self, targets):  
        target_geometries = get_geometries(targets)
        groups = [
            self.covered_by(container).apply(lambda x: container_index)
            for container_index, container in progress(
                target_geometries.items(), len(target_geometries)
            )
        ]
        if groups:
            return pandas.concat(groups).reindex(self.index)
        else:
            return geopandas.GeoSeries()


    def enumerate_intersections(self, targets):
        target_geometries = get_geometries(targets)
        for i, target in progress(target_geometries.items(), len(target_geometries)):
            for j, intersection in self.intersections(target).items():
                yield i, j, intersection
