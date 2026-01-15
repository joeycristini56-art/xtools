from .advanced_image_grid_solver import AdvancedImageGridSolver
from .object_identification_solver import ObjectIdentificationSolver

ImageGridSolver = AdvancedImageGridSolver
ImageSolver = AdvancedImageGridSolver

__all__ = ["ImageGridSolver", "AdvancedImageGridSolver", "ObjectIdentificationSolver", "ImageSolver"]