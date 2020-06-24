from PIL import Image
import math


# Line class
class Line:
    # Constructor
    def __init__(self, axis, gradient, intercept):
        self.axis = axis
        self.gradient = gradient
        self.intercept = intercept
        self.endpoints = []

    def serialize(self):
        return {"axis": self.axis, "gradient": self.gradient, "intercept": self.intercept}

    # Given a point (x_0, y_0), get the expected value of y(x_0) on the line (or x(y_0))
    def get_expected(self, point):
        return self.gradient * point[self.axis] + self.intercept

    # Get the point of intersection with another line
    def get_intersect(self, other, record=False):
        x_point = (self.intercept * other.gradient + other.intercept) / (1 - self.gradient * other.gradient)
        y_point = self.gradient * x_point + self.intercept

        point = (y_point, x_point) if self.axis else (x_point, y_point)

        if record:
            self.endpoints.append(point)
            other.endpoints.append(point)

        return point

    # Get the angle (degrees) between the line and the positive x axis
    def get_angle(self):
        return (1 - 2 * self.axis) * math.degrees(math.atan(self.gradient))

    # Get the length of the line from its endpoints
    def get_length(self):
        x_diff = self.endpoints[1][0] - self.endpoints[0][0]
        y_diff = self.endpoints[1][1] - self.endpoints[0][1]

        return math.sqrt(x_diff**2 + y_diff**2)

    # Create best fit line from points, with given axis
    @staticmethod
    def best_fit(points, axis):
        if len(points) == 0:
            return False

        x_mean = sum([point[axis] for point in points]) / len(points)
        y_mean = sum([point[1 - axis] for point in points]) / len(points)

        try:
            gradient = sum([(point[axis] - x_mean) * (point[1 - axis] - y_mean) for point in points]) / sum([(point[axis] - x_mean)**2 for point in points])
        except ZeroDivisionError:
            gradient = 10000

        intercept = y_mean - gradient * x_mean

        return Line(axis, gradient, intercept)


# Get all rectangles formed by current cropping lines
def get_rects_from_lines(lines, width, height):
    divisions = ([0], [0])
    for line in lines:
        divisions[1 - line["axis"]].append(line["pos"] / [height, width][line["axis"]])
    divisions[0].append(1)
    divisions[1].append(1)
    divisions[0].sort()
    divisions[1].sort()

    rects = []
    for x in range(len(divisions[0]) - 1):
        for y in range(len(divisions[1]) - 1):
            rects.append((divisions[0][x], divisions[1][y], divisions[0][x + 1], divisions[1][y + 1]))

    return rects


# Detect and crop out small white margins from an image
def remove_margins(image, options):
    to_crop = [0, 0, image.width, image.height]
    # Iterate over the 4 edges
    for axis in [0, 1]:
        for direction in [1, -1]:
            # Setup start/step for scanning image
            scan_start = [0, 0]
            if direction < 0:
                scan_start[1 - axis] = [image.height, image.width][axis] - 1
            scan_step = [0, 0]
            scan_step[axis] = 1
            avg_end, prop_end = 0, 0

            # Scan pixels line by line
            for i in range(0, [image.height, image.width][axis]):
                scan_start[1 - axis] += direction * (i > 0)

                x = scan_start[0]
                y = scan_start[1]
                levels = []

                # Scan line and get brightness of each pixel
                while x >= 0 and x < image.width and y >= 0 and y < image.height:
                    level = sum(image.getpixel((x, y))) / 765
                    levels.append(level)

                    x += scan_step[0]
                    y += scan_step[1]

                # Get average level and proportion of levels which qualify as "white"
                proportion = len(list(filter(lambda v: v > options["post-margin-color"], levels))) / len(levels)
                average = sum(levels) / len(levels)

                # If both proportion and average are too low then mark end of margin
                if proportion < options["post-margin-pct"] / 100 and not prop_end:
                    prop_end = i
                if average < options["post-margin-color"] and not avg_end:
                    avg_end = i
                if (prop_end and avg_end) or i >= options["post-margin-size"]:
                    break

            # Update crop region
            to_crop[1 - axis + 2 * (direction < 0)] += max(prop_end, avg_end) * direction

    return image.crop(tuple(to_crop))


# Scan image on one line for the edge of a photo
def edge_scan(image, start, step, threshold):
    x = image.width * start[0]
    y = image.height * start[1]
    average, count = 0, 0

    # Scan pixels in line
    while x >= 0 and x < image.width and y >= 0 and y < image.height:
        level = sum(image.getpixel((x, y))) / 765

        # If brightness differs sufficiently from average so far
        if (count > 0 and abs(level - average) / (average or 1 / 2) > threshold / 100):
            # If step size is 1, return result
            # Otherwise, half step size and iterate from previous step
            if abs(step[0] * image.width) + abs(step[1] * image.height) < 2:
                return (round(x), round(y))
            else:
                return edge_scan(image, (x / image.width - step[0], y / image.height - step[1]), (step[0] / 2, step[1] / 2), threshold)

        # Track average brightness
        average = (average * count + level) / (count + 1)
        x += image.width * step[0]
        y += image.height * step[1]
        count += 1

    return False


# Find a complete edge of the rectangle
def find_edge(image, step, threshold, error, requirement, axis, direction):
    # Setup start/step for scanning image
    scan_start = [0, 0]
    if direction < 0:
        scan_start[1 - axis] = 1 - 1 / [image.height, image.width][axis]
    scan_step = [0, 0]
    allPoints = []

    # For each point on line parallel to expected edge, scan for edge at this point
    for i in range(0, int(1 / step[0])):
        scan_start[axis] = i * step[0]
        scan_step[1 - axis] = step[1] * direction

        result = edge_scan(image, scan_start, scan_step, threshold)
        if result:
            allPoints.append(result)

    # Sort points and remove outliers based on quartiles
    ordered = sorted(allPoints, key=lambda p: p[1 - axis])
    quartiles = [ordered[int((len(ordered) + 1) * i)] for i in [1 / 4, 2 / 4, 3 / 4]]
    valid_points = list(
        filter(
            lambda point: abs(point[1 - axis] - quartiles[1][1 - axis]) < 2 * min(
                [abs(quartiles[2][1 - axis] - quartiles[1][1 - axis]), abs(quartiles[1][1 - axis] - quartiles[0][1 - axis])]), allPoints))

    # Get best fit line for points
    if len(valid_points) > 5:
        line = Line.best_fit(valid_points, axis)
    else:
        line = Line.best_fit(quartiles, axis)

    # Filter for points which are sufficiently close to best fit line
    final_points = []
    for point in allPoints:
        expected = line.get_expected(point)
        if abs(point[1 - axis] - expected) < [image.height, image.width][axis] * error:
            final_points.append(point)

    # If not enough points are accurate then reduce step size to 1 pixel
    if len(final_points) / len(allPoints) < requirement / 100:
        return find_edge(image, (step[0], 1 / (image.width, image.height)[1 - axis]), threshold, error, 0, axis, direction)

    return Line.best_fit(final_points, axis)


# Find the edges of a photo within a cropped portion of the image
def get_rect_edges(image, step, threshold, error, requirement):
    edges = []
    for axis in [0, 1]:
        for direction in [1, -1]:
            edges.append(find_edge(image, step, threshold, error, requirement, axis, direction))

    if not all(edges):
        return False

    edges = [edges[i] for i in [0, 2, 1, 3]]

    return edges


# Find the corners of a photo within a cropped portion of the image
def get_rect_points(image, step, threshold, error, requirement):
    edges = get_rect_edges(image, step, threshold, error, requirement)
    if not edges:
        return False, None, None

    points = []
    for i in range(len(edges)):
        points.append(edges[i].get_intersect(edges[(i + 1) % len(edges)], True))

    width = int((edges[0].get_length() + edges[2].get_length()) / 2)
    height = int((edges[1].get_length() + edges[3].get_length()) / 2)

    return points, width, height


# Extract a photo from a cropped portion of the image
def get_rect_image(image, bounds, step, threshold, error, requirement):
    image = image.crop((image.width * bounds[0], image.height * bounds[1], image.width * (1 - bounds[0]), image.height * (1 - bounds[1])))

    points, width, height = get_rect_points(image, step, threshold, error, requirement)
    if not points:
        return False

    quadrilateral = sum(points, ())

    quadImage = image.transform((width, height), Image.QUAD, quadrilateral, Image.BICUBIC)

    finalImage = remove_margins(quadImage, {"post-margin-color": 0.75, "post-margin-size": 10, "post-margin-pct": 40})

    return finalImage


# Get locations of all photos given cropping lines
def get_image_rects(filename, lines, width, height):
    rects = get_rects_from_lines(lines, width, height)
    # TODO options
    bounds = (1 / 40, 1 / 40)
    step = (1 / 100, 1 / 100)
    threshold = 2
    error = 1 / 100
    requirement = 50

    page = Image.open(filename)

    img_rects = []

    for rect in rects:
        rect_w = (rect[2] - rect[0]) * page.width
        rect_h = (rect[3] - rect[1]) * page.height
        rect_x1 = rect[0] * page.width + bounds[0] * rect_w
        rect_x2 = rect[2] * page.width - bounds[0] * rect_w
        rect_y1 = rect[1] * page.height + bounds[1] * rect_h
        rect_y2 = rect[3] * page.height - bounds[1] * rect_h
        image = page.crop((rect_x1, rect_y1, rect_x2, rect_y2))

        rect_points, _w, _h = get_rect_points(image, step, threshold, error, requirement)
        if rect_points:
            img_rects.append([(p[0] + rect_x1, p[1] + rect_y1) for p in rect_points])

    return img_rects
