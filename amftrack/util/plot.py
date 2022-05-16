from typing import List
import numpy as np

from matplotlib import image
import matplotlib.pyplot as plt
from amftrack.util.aliases import coord_int


def show_image(image_path: str) -> None:
    """Plot an image, from image path"""
    # TODO(FK): distinguish between extensions
    im = image.imread(image_path)
    plt.imshow(im)


def show_image_with_segment(image_path: str, x1, y1, x2, y2):
    """Show the image with a segment drawn on top of it"""
    show_image(image_path)
    plt.plot(y1, x1, marker="x", color="white")
    plt.plot(y2, x2, marker="x", color="white")
    plt.plot([y1, y2], [x1, x2], color="white", linewidth=2)


def pixel_list_to_matrix(pixels: List[coord_int], margin=0) -> np.array:
    """
    Returns a binary image of the Edge
    :param margin: white border added around edge pixels
    """
    x_max = np.max([pixel[0] for pixel in pixels])
    x_min = np.min([pixel[0] for pixel in pixels])
    y_max = np.max([pixel[1] for pixel in pixels])
    y_min = np.min([pixel[1] for pixel in pixels])
    M = np.zeros((x_max - x_min + 1 + 2 * margin, (y_max - y_min + 1 + 2 * margin)))
    for pixel in pixels:
        M[pixel[0] - x_min + margin][pixel[1] - y_min + margin] = 1
    return M


def crop_image(matrix: np.array, region: List[coord_int]):
    """
    Crops the image to the given region.
    This is a robust function to avoid error when regions are out of bound.
    Coordinates of region are in the form [x, y]
    The lower bound are included, the upper bound is not.
    :param region: [[1, 2], [10, 10]] for example
    """

    dim_x = matrix.shape[0]
    dim_y = matrix.shape[1]
    x_min = np.min([np.max([0, np.min([region[0][0], region[1][0]])]), dim_x])
    x_max = np.max([np.min([dim_x, np.max([region[0][0], region[1][0]])]), 0])
    y_min = np.min([np.max([0, np.min([region[0][1], region[1][1]])]), dim_y])
    y_max = np.max([np.min([dim_y, np.max([region[0][1], region[1][1]])]), 0])

    return matrix[x_min:x_max, y_min:y_max]
