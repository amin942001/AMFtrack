import numpy as np


def expand_segment(point1, point2, factor):
    """
    From the segment [point1, point2], return a new segment dilated by `factor`
    and centered on the same point.
    """
    x1, y1 = point1[0], point1[1]
    x2, y2 = point2[0], point2[1]
    vx = x2 - x1
    vy = y2 - y1
    x_mid = (x1 + x2) / 2
    y_mid = (y1 + y2) / 2
    x1_, y1_ = [x_mid - factor * vx / 2, y_mid - factor * vy / 2]
    x2_, y2_ = [x_mid + factor * vx / 2, y_mid + factor * vy / 2]
    return [x1_, y1_], [x2_, y2_]


def compute_factor(point1, point2, target_length):
    """
    Determine the dilation factor to reach the target_length
    """
    x1, y1 = point1[0], point1[1]
    x2, y2 = point2[0], point2[1]
    vx = x2 - x1
    vy = y2 - y1
    length = np.sqrt(vx**2 + vy**2)

    return target_length / length


def convert_to_micrometer(pixel_length, magnification=2):
    camera_res = 3.45
    return pixel_length * camera_res / magnification


if __name__ == "__main__":

    point1 = [0, 0]
    point2 = [2, 4]
    assert expand_segment(point1, point2, 0.5) == ([0.5, 1.0], [1.5, 3.0])
    assert expand_segment(point1, point2, 2) == ([-1.0, -2.0], [3.0, 6.0])
    assert expand_segment(point2, point1, 2) == ([3.0, 6.0], [-1.0, -2.0])

    assert compute_factor([0, 0], [0, 3], 6) == 2
    assert compute_factor([1, 0], [10, 0], 4.5) == 0.5

    assert convert_to_micrometer(10) == 17.25
