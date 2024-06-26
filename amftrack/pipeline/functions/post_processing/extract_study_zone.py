import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as pltlines
from pymatreader import read_mat
import cv2
from amftrack.util.sys import get_dates_datetime, get_dirname, temp_path, path_code
import pandas as pd
from amftrack.pipeline.launching.run_super import directory_project
import ast
import os
from time import time
import imageio
import scipy
import json
from amftrack.pipeline.functions.image_processing.experiment_util import get_ROI
from shapely.geometry import shape


class DraggableRectangleCenter:
    lock = None  # only one can be animated at a time

    def __init__(self, rect, drag_orth, dist, radius):
        self.rect = rect
        self.press = None
        self.background = None
        self.drag_orth = drag_orth
        self.circle = None
        self.line = None
        self.dist = dist
        self.radius = radius

    def connect(self):
        """Connect to all the events we need."""
        self.cidpress = self.rect.figure.canvas.mpl_connect(
            "button_press_event", self.on_press
        )
        self.cidrelease = self.rect.figure.canvas.mpl_connect(
            "button_release_event", self.on_release
        )
        self.cidmotion = self.rect.figure.canvas.mpl_connect(
            "motion_notify_event", self.on_motion
        )

    def on_press(self, event):
        """Check whether mouse is over us; if so, store some data."""
        if event.inaxes != self.rect.axes or DraggableRectangleCenter.lock is not None:
            return
        contains, attrd = self.rect.contains(event)
        if not contains:
            return
        print("event contains", self.rect.xy)
        self.press = self.rect.xy, (event.xdata, event.ydata)
        DraggableRectangleCenter.lock = self

        # draw everything but the selected rectangle and store the pixel buffer
        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        self.rect.set_animated(True)
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.rect.axes.bbox)

        # now redraw just the rectangle
        axes.draw_artist(self.rect)

        # and blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_motion(self, event):
        """Move the rectangle if the mouse is over us."""
        if event.inaxes != self.rect.axes or DraggableRectangleCenter.lock is not self:
            return
        (x0, y0), (xpress, ypress) = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        self.rect.set_x(x0 + dx)
        self.rect.set_y(y0 + dy)

        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.rect)

        # blit just the redrawn area
        canvas.blit(axes.bbox)
        return ()

    def on_release(self, event):
        """Clear button press information."""
        if DraggableRectangleCenter.lock is not self:
            return

        self.press = None
        DraggableRectangleCenter.lock = None

        # turn off the rect animation property and reset the background
        self.rect.set_animated(False)
        self.background = None

        # redraw the full figure
        self.rect.figure.canvas.draw()
        x, y = self.rect.xy
        if self.circle is not None:
            self.circle.remove()
            self.rect.figure.gca().lines.pop(0)
        x1, y1 = self.drag_orth.rect.xy
        circle = plt.Circle((x, y), self.radius, alpha=0.3, color="red")
        direction = np.array((x1 - x, y1 - y))
        direction = direction / np.linalg.norm(direction)
        pos_line = np.array((x, y)) + self.dist * direction
        orth_direct = np.array([direction[1], -direction[0]])
        extension = 1000
        deb_line = pos_line + extension * orth_direct
        end_line = pos_line - extension * orth_direct
        line = pltlines.Line2D(
            (deb_line[0], end_line[0]), (deb_line[1], end_line[1]), color="red"
        )
        self.line = line
        self.circle = circle
        ax = self.rect.figure.gca()
        ax.add_patch(circle)
        ax.add_line(line)

    def disconnect(self):
        """Disconnect all callbacks."""
        self.rect.figure.canvas.mpl_disconnect(self.cidpress)
        self.rect.figure.canvas.mpl_disconnect(self.cidrelease)
        self.rect.figure.canvas.mpl_disconnect(self.cidmotion)


class DraggableRectangleOrth:
    lock = None  # only one can be animated at a time

    def __init__(self, rect):
        self.rect = rect
        self.press = None
        self.background = None
        self.line = None

    def connect(self):
        """Connect to all the events we need."""
        self.cidpress = self.rect.figure.canvas.mpl_connect(
            "button_press_event", self.on_press
        )
        self.cidrelease = self.rect.figure.canvas.mpl_connect(
            "button_release_event", self.on_release
        )
        self.cidmotion = self.rect.figure.canvas.mpl_connect(
            "motion_notify_event", self.on_motion
        )

    def on_press(self, event):
        """Check whether mouse is over us; if so, store some data."""
        if event.inaxes != self.rect.axes or DraggableRectangleOrth.lock is not None:
            return
        contains, attrd = self.rect.contains(event)
        if not contains:
            return
        print("event contains", self.rect.xy)
        self.press = self.rect.xy, (event.xdata, event.ydata)
        DraggableRectangleOrth.lock = self

        # draw everything but the selected rectangle and store the pixel buffer
        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        self.rect.set_animated(True)
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.rect.axes.bbox)

        # now redraw just the rectangle
        axes.draw_artist(self.rect)

        # and blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_motion(self, event):
        """Move the rectangle if the mouse is over us."""
        if event.inaxes != self.rect.axes or DraggableRectangleOrth.lock is not self:
            return
        (x0, y0), (xpress, ypress) = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        self.rect.set_x(x0 + dx)
        self.rect.set_y(y0 + dy)

        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.rect)

        # blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_release(self, event):
        """Clear button press information."""
        if DraggableRectangleOrth.lock is not self:
            return

        self.press = None
        DraggableRectangleOrth.lock = None

        # turn off the rect animation property and reset the background
        self.rect.set_animated(False)
        self.background = None

        # redraw the full figure
        self.rect.figure.canvas.draw()

    def disconnect(self):
        """Disconnect all callbacks."""
        self.rect.figure.canvas.mpl_disconnect(self.cidpress)
        self.rect.figure.canvas.mpl_disconnect(self.cidrelease)
        self.rect.figure.canvas.mpl_disconnect(self.cidmotion)


def place_study_zone(image, dist, radius):
    fig, ax = plt.subplots(figsize=(11, 11))

    ax.imshow(image)
    # circle = plt.Circle((2000,2000),100,alpha = 0.3)
    # ax.add_patch(circle)
    rect_center = ax.bar(500, 25, 25)[0]
    rect_orth = ax.bar(1000, 25, 25, color="red")[0]

    dr_orth = DraggableRectangleOrth(rect_orth)
    dr_orth.connect()
    dr_center = DraggableRectangleCenter(rect_center, dr_orth, dist, radius)
    dr_center.connect()
    plt.show()
    return (dr_orth, dr_center)


def get_study_zone(exp, dist, radius, i=0):
    date = exp.dates[i]
    directory_name = get_dirname(date, exp.folders)
    path_snap = exp.directory + directory_name
    im = read_mat(path_snap + "/Analysis/raw_image.mat")["raw"]
    shape_compressed = im.shape[1] * 15 // 25, im.shape[0] * 15 // 25
    im_comp = cv2.resize(im, shape_compressed)
    dr_orth, dr_center = place_study_zone(im_comp, dist, radius)
    return (dr_orth, dr_center)


def extract_study_zone(dr_orth, dr_center, exp, i=0):
    rect_orth, rect_center = dr_orth.rect, dr_center.rect
    center = rect_center.xy
    orthog = np.array(rect_orth.xy) - np.array(center)
    orthog = orthog / np.linalg.norm(orthog)
    compress = 25
    date = exp.dates[i]
    directory_name = get_dirname(date, exp.folders)
    path_snap = exp.directory + directory_name
    skel = read_mat(path_snap + "/Analysis/skeleton_pruned_realigned.mat")
    Rot = skel["R"]
    trans = skel["t"]
    skelet = skel["skeleton"]

    xc, yc = center[0], center[1]
    rottrans = np.dot(Rot, np.array([yc, xc])) + trans // compress
    pos_center = round(rottrans[1]) * compress, round(rottrans[0]) * compress
    orthog = np.flip(np.dot(Rot, np.flip(orthog)))
    exp.center, exp.orthog = pos_center, orthog


def load_study_zone(exp):
    has_center = os.path.isfile(os.path.join(exp.save_location, "center.npy"))
    if not has_center:
        loc_load = os.path.join(
            path_code, "pipeline", "functions", "post_processing", "default_param"
        )
    else:
        loc_load = exp.save_location
    exp.center = np.load(os.path.join(loc_load, "center.npy"))
    exp.orthog = np.load(os.path.join(loc_load, "orthog.npy"))
    exp.reach_out = np.load(os.path.join(loc_load, "reach_out.npy"))
    exp.num_trunk = np.load(os.path.join(loc_load, "num_trunk.npy"))


def save_study_zone(exp):
    exp.center = np.save(f"{exp.save_location}/center.npy", exp.center)
    exp.orthog = np.save(f"{exp.save_location}/orthog.npy", exp.orthog)
    # exp.reach_out = np.load(f"{exp.save_location}/reach_out.npy")
    # exp.num_trunk = np.load(f"{exp.save_location}/num_trunk.npy")


def save_ROI(exp):
    dirName = exp.save_location
    ROI = get_ROI(exp, 0)
    polygon_geojson = ROI.__geo_interface__
    path_ROI = os.path.join(dirName, "ROI.geojson")
    # Save the GeoJSON to a file
    with open(path_ROI, "w") as geojson_file:
        json.dump(polygon_geojson, geojson_file)


def load_ROI(exp):
    dirName = exp.save_location
    path_ROI = os.path.join(dirName, "ROI.geojson")

    has_ROI = os.path.isfile(path_ROI)
    if not has_ROI:
        save_ROI(exp)
    with open(path_ROI, "r") as geojson_file:
        polygon_geojson = json.load(geojson_file)
    polygon = shape(polygon_geojson)
    exp.ROI = polygon
    return polygon
