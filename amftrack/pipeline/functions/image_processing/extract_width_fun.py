from skimage.measure import profile_line
import numpy as np
from scipy.optimize import curve_fit
from typing import Tuple, List, Dict
import os
import logging
from random import choice

from amftrack.notebooks.analysis.util import *
from amftrack.util.aliases import coord, coord_int
from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    Experiment,
    Edge,
)
from amftrack.util.other import get_section_segment
from amftrack.util.image_analysis import is_in_image

logger = logging.getLogger(os.path.basename(__file__))

a = 2.3196552


def generate_pivot_indexes(n: int, resolution=3, offset=5) -> List[int]:
    """
    From the length of the pixel list, determine which pixel will be chosen to compute width
    :param n: length of the list of pixels
    :param resolution: step between two chosen points
    :param offset: offset at the begining and at the end where no points will be selected
    """
    x_min = offset
    x_max = n - 1 - offset
    # Small case
    if x_min > x_max:
        return [n // 2]
    # Normal case
    k_max = (x_max - x_min) // resolution
    l = [x_min + k * resolution for k in range(k_max + 1)]
    return l


def compute_section_coordinates(
    pixel_list: List[coord_int], pivot_indexes: List, step: int, target_length=120
) -> List[Tuple[coord_int, coord_int]]:
    """
    Compute the coordinates of each segment section where the width will be computed
    :param pivot_indexes: list of indexes in the pixel_list
    :param step: this determine which neibooring points to use for computing the tangent
    :param target_length: the approximate target_length that we want for the segment
    WARNING: taget_length is not exact as the coordinates are ints
    NB: the coordinates are all in the general referential
    """
    # TODO(FK): handle case where the step is bigger than the offset, raise error instead of logging
    if step > pivot_indexes[0]:
        logger.error("The step is bigger than the offset. Offset should be raised")
    list_of_segments = []
    for i in pivot_indexes:
        pivot = pixel_list[i]
        before = pixel_list[i - step]
        after = pixel_list[i + step]
        orientation = np.array(before) - np.array(after)
        list_of_segments.append(get_section_segment(orientation, pivot, target_length))
    return list_of_segments


def find_source_images(
    section_coord_list: List[Tuple[coord_int]], exp: Experiment, t: int
):
    """
    In this function we determine (and chose) an image for each section.
    This image will then be used to extract the profile section.
    :return
    - List of image indexes for each section
    - List of coordinates of the segment in their respective image
    """
    # TODO(FK): could maybe only check the center of the segment
    # TODO(FK): could chose image further from the border
    image_indexes = []  # map each segment to the index of its image in `images`
    new_section_coord_list = []

    current_image = [np.inf, np.inf]
    current_index = 0
    for (point1, point2) in section_coord_list:
        # convert to timestep referential
        point1_ = exp.general_to_image_coords(point1, t)
        point2_ = exp.general_to_image_coords(point2, t)
        # check if the current image contains the segment
        if is_in_image(
            current_image[0], current_image[1], point1_[0], point1_[1]
        ) and is_in_image(current_image[0], current_image[1], point2_[0], point2_[1]):
            index = current_index
        else:
            logging.debug("New image needed")
            images1 = exp.find_im_indexes(point1_[0], point1_[1], t)
            images2 = exp.find_im_indexes(point2_[0], point2_[1], t)
            possible_choices = list(set(images1) & set(images2))
            if possible_choices == []:
                logging.debug(
                    "This section is not contained in a single original image. The section won't be used"
                )
                # index = choice(list(set(images1) | set(images2)))
                index = None
                new_section_coord_list.append(None)
            else:
                index = choice(possible_choices)
                current_image = exp.image_coordinates[t][index]
                current_index = index
                image_indexes.append(index)
                # compute the coordinates of the segment in the image ref
                point1__ = [
                    point1_[0] - current_image[0],
                    point1_[1] - current_image[1],
                ]
                point2__ = [
                    point2_[0] - current_image[0],
                    point2_[1] - current_image[1],
                ]
                new_section_coord_list.append([point1__, point2__])
    return image_indexes, new_section_coord_list


def extract_section_profiles_for_edge(
    exp: Experiment,
    t: int,
    edge: Edge,
    resolution=5,
    offset=4,
    step=3,
    target_length=120,
) -> np.array:
    """
    Main function to extract section profiles of an edge.
    Given an Edge of Experiment at timestep t, returns a np array
    of dimension (target_length, m) where m is the number of section
    taken on the hypha.
    :param resolution: distance between two measure points along the hypha
    :param offset: distance at the end and the start where no point is taken
    :param step: step in pixel to compute the tangent to the hypha
    :target_length: length of the section extracted in pixels
    """
    pixel_list = edge.pixel_list(t)
    offset = max(
        offset, step
    )  # avoiding index out of range at start and end of pixel_list
    pixel_indexes = generate_pivot_indexes(
        len(pixel_list), resolution=resolution, offset=offset
    )
    list_of_segments = compute_section_coordinates(
        pixel_list, pixel_indexes, step=step, target_length=target_length + 1
    )  # target_length + 1 to be sure to have length all superior to target_length when cropping
    # TODO (FK): is a +1 enough?
    image_indexes, new_section_coord_list = find_source_images(list_of_segments, exp, t)
    images = {}
    for im_index in set(image_indexes):
        images[im_index] = exp.get_image(t, im_index)
    l = []
    for i, sect in enumerate(new_section_coord_list):
        im = images[image_indexes[i]]
        # WARNING: profile_line has a different order for x an y
        # This is way point1 and point2 have shape (y, x)
        point1 = np.array([sect[0][0], sect[0][1]])
        point2 = np.array([sect[1][0], sect[1][1]])
        profile = profile_line(im, point1, point2, mode="constant")[:target_length]
        profile = profile.reshape((1, len(profile)))
        # TODO(FK): Add thickness of the profile here
        l.append(profile)
    return np.concatenate(l, axis=0)


def get_source_image(
    experiment: Experiment, pos: coord, t: int, local: bool, force_selection=None
):
    """
    Return a source image from the Experiment object for the position `pos`.
    If force_selection is None, it returns the image in which the point is
    further away from the border.
    Otherwise, it returns the image the closest to the `force_selection` coordinates
    :param pos: (x,y) position
    :param local: useless parameter boolean
    :param force_selection: (x,y) position
    :return: image along with its coordinates
    """
    x, y = pos[0], pos[1]
    ims, posimg = experiment.find_image_pos(x, y, t, local)

    if force_selection is None:
        dist_border = [
            min([posimg[1][i], 3000 - posimg[1][i], posimg[0][i], 4096 - posimg[0][i]])
            for i in range(posimg[0].shape[0])
        ]
        j = np.argmax(dist_border)
    else:
        dist_last = [
            np.linalg.norm(
                np.array((posimg[1][i], posimg[0][i])) - np.array(force_selection)
            )
            for i in range(posimg[0].shape[0])
        ]
        j = np.argmin(dist_last)
    logger.info("Getting images")
    return (ims[j], (posimg[1][j], posimg[0][j]))


def get_width_pixel(
    edge: Edge,
    index,
    im,
    pivot,
    before: coord,
    after: coord,
    t,
    size=20,
    width_factor=60,
    averaging_size=100,
    threshold_averaging=10,
):
    """
    Get a width value for a given pixel on the hypha
    :param index: TO REMOVE
    :param im:
    :param pivot:
    :param before, after: coordinates of point after and before to compute the tangent
    :param size:
    :param width_factor:
    :param averaging_size:
    :param threshold_averaging:
    :return: the width computed
    """
    # TODO(FK): remove this line
    imtab = im
    #     print(imtab.shape)
    #     print(int(max(0,pivot[0]-averaging_size)),int(pivot[0]+averaging_size))
    orientation = np.array(before) - np.array(after)
    # TODO(FK): all this into another function
    perpendicular = (
        [1, -orientation[0] / orientation[1]] if orientation[1] != 0 else [0, 1]
    )
    perpendicular_norm = np.array(perpendicular) / np.sqrt(
        perpendicular[0] ** 2 + perpendicular[1] ** 2
    )
    point1 = np.around(np.array(pivot) + width_factor * perpendicular_norm)
    point2 = np.around(np.array(pivot) - width_factor * perpendicular_norm)
    point1 = point1.astype(int)
    point2 = point2.astype(int)
    p = profile_line(imtab, point1, point2, mode="constant")  # TODO(FK): solve error
    xdata = np.array(range(len(p)))
    ydata = np.array(p)

    background = np.mean(
        (np.mean(p[: width_factor // 6]), np.mean(p[-width_factor // 6 :]))
    )
    width_pix = -np.sum(
        (np.log10(np.array(p) / background) <= 0) * np.log10(np.array(p) / background)
    )

    return a * np.sqrt(max(0, np.linalg.norm(point1 - point2) * (width_pix) / len(p)))


def get_width_edge(
    edge: Edge, resolution: int, t: int, local=False, threshold_averaging=10
) -> Dict[coord, float]:
    """
    Compute the width of the given edge for each point that is chosen on the hypha.
    :param resolution: if resolution = 3 the width is computed every 3 pixel on the edge
    :return: a dictionnary with the width for each point chosen on the hypha
    """
    pixel_conversion_factor = 1.725  # TODO(FK): use the designated function instead
    pixel_list = edge.pixel_list(t)
    pixels = []
    indexes = []
    source_images = []
    poss = []
    widths = {}
    # Long edges
    if len(pixel_list) > 3 * resolution:
        for i in range(0, len(pixel_list) // resolution):
            index = i * resolution
            indexes.append(index)
            pixel = pixel_list[index]
            pixels.append(pixel)
            source_img, pos = get_source_image(
                edge.experiment, pixel, t, local
            )  # TODO(FK): very not efficient
            source_images.append(source_img)
            poss.append(pos)
    # Small edges
    else:
        indexes = [0, len(pixel_list) // 2, len(pixel_list) - 1]
        for index in indexes:
            pixel = pixel_list[index]
            pixels.append(pixel)
            source_img, pos = get_source_image(edge.experiment, pixel, t, local)
            source_images.append(source_img)
            poss.append(pos)
    #     print(indexes)
    for i, index in enumerate(indexes[1:-1]):
        source_img = source_images[i + 1]
        pivot = poss[i + 1]
        _, before = get_source_image(edge.experiment, pixels[i], t, local, pivot)
        _, after = get_source_image(edge.experiment, pixels[i + 2], t, local, pivot)
        #         plot_t_tp1([0,1,2],[],{0 : pivot,1 : before, 2 : after},None,source_img,source_img)
        width = get_width_pixel(
            edge,
            index,
            source_img,
            pivot,
            before,
            after,
            t,
            threshold_averaging=threshold_averaging,
        )
        #         print(width*pixel_conversion_factor)
        widths[pixel_list[index]] = width * pixel_conversion_factor
    #         if i>=1:
    #             break
    edge.experiment.nx_graph[t].get_edge_data(edge.begin.label, edge.end.label)[
        "width"
    ] = widths
    return widths


def get_width_info(experiment, t, resolution=50, skip=False):
    print(not skip)
    edge_width = {}
    graph = experiment.nx_graph[t]
    #     print(len(list(graph.edges)))
    # print(len(graph.edges))
    for edge in graph.edges:
        if not skip:
            #         print(edge)
            edge_exp = Edge(
                Node(edge[0], experiment), Node(edge[1], experiment), experiment
            )
            mean = np.mean(list(get_width_edge(edge_exp, resolution, t).values()))
            #         print(np.mean(list(get_width_edge(edge_exp,resolution,t).values())))
            edge_width[edge] = mean
            # print(mean)
        else:
            # Maybe change to Nan if it doesnt break the rest
            edge_width[edge] = 40
    return edge_width


if __name__ == "__main__":

    from amftrack.util.sys import (
        update_plate_info_local,
        update_plate_info,
        get_current_folders,
        get_current_folders_local,
        data_path,
    )
    from amftrack.pipeline.functions.image_processing.experiment_util import (
        get_random_edge,
    )
    import os
    from random import choice

    plate_name = "20220330_2357_Plate19"

    directory = data_path + "/"
    ## Set up experiment object
    update_plate_info_local(directory)
    # update_plate_info(data_path)
    folder_df = get_current_folders_local(directory)
    selected_df = folder_df.loc[folder_df["folder"] == plate_name]
    i = 0
    plate = 19
    folder_list = list(selected_df["folder"])
    directory_name = folder_list[i]
    exp = Experiment(plate, directory)
    exp.load(selected_df.loc[selected_df["folder"] == directory_name], labeled=False)

    ## Select a random Edge at time 0
    (G, pos) = exp.nx_graph[0], exp.positions[0]
    edge = choice(list(G.edges))
    edge_exp = Edge(Node(edge[0], exp), Node(edge[1], exp), exp)

    ## Run the width function
    edge = get_random_edge(exp, 0)
    extract_section_profiles_for_edge(exp, 0, edge)
