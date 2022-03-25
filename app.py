import dataclasses
import re
import threading
from datetime import datetime
from typing import List, Optional

import requests
from dataclasses_json import LetterCase, dataclass_json
from flask import Flask, render_template, send_from_directory, abort, request
from flask_minify import Minify

import config

app = Flask("bus", template_folder="flask_templates")
Minify(app=app, html=True, js=True, cssless=True)

image_re: str = ""
image_rt: str = ""


@app.route("/favicon.ico")
def favicon():
    return send_from_directory('public', "favicon.jpg")


@app.route("/public/<path:path>")
def public(path: str):
    return send_from_directory('public', path)


TIME_UNIT_CONVERSION_TABLE = {
    "%UNIT_MIN%": "min"
}


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclasses.dataclass
class Alert:
    pass


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclasses.dataclass
class Route:
    alerts: List[Alert]
    authority: str
    directions: List[str]
    id: str
    name: str
    route_type: str
    short_name: str


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclasses.dataclass
class StopInfo:
    actual_relative_time: int
    direction: str
    mixed_time: str
    passageid: str
    pattern_text: str
    planned_time: str
    route_id: str
    status: str
    trip_id: str
    vias: Optional[List[str]] = None
    time_class: str = "punctual"
    mixed_time_unit: str = ""
    actual_time: str = ""
    vehicle_id: str = ""
    vehicle_type: str = ""
    route: Optional[Route] = None

    def update(self, routes: List[Route] = None):
        self.update_mixed_time()
        self.set_time_class()
        self.update_vias()

        route = [route for route in routes if route.short_name == self.pattern_text]
        if route:
            self.route = route[0]
            self.set_route_information()

    def update_vias(self):
        if self.vias:
            self.vias = [via.replace("via ", "") for via in self.vias]

    def set_route_information(self):
        self.vehicle_type = self.route.route_type.capitalize()

    def update_mixed_time(self):
        s = self.mixed_time.split(" ")
        if len(s) < 2:
            return

        self.mixed_time = s[0]
        self.mixed_time_unit = TIME_UNIT_CONVERSION_TABLE[s[1]]

    def set_time_class(self):
        if self.actual_time is None or self.mixed_time_unit == "":
            return

        planned = datetime.strptime(self.planned_time, "%H:%M")
        actual = datetime.strptime(self.actual_time, "%H:%M")

        diff = planned - actual
        if diff.days < 0:
            if abs(diff.seconds) > 300:
                self.time_class = "delayed"
            else:
                self.time_class = "late"
        else:
            if diff.seconds != 0:
                self.time_class = "early"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclasses.dataclass
class Stop:
    actual: List[StopInfo]
    stop_name: str
    stop_short_name: str
    routes: List[Route]


def get_stop(stop_number: int = 180):
    req = requests.get(
        f"https://www.swp-potsdam.de/internetservice/services/passageInfo/stopPassages/stop?stop={stop_number}&mode=departure&language=en")

    if req.ok:
        js = req.json()
        return Stop.from_dict(js)

    return None


@app.route("/webcam/session", methods=["UPDATE"])
def update_image_session_parameter(
        base_url: str = "https://www.mobil-potsdam.de/de/verkehrsmeldungen/webcams-desktop/"):
    global image_re
    global image_rt
    req = requests.get(base_url)
    if req.ok:
        if match := re.findall(r"re=(.*?)&rt=(.*?)&", req.content.decode("utf-8")):
            match = match[0]
            image_re, image_rt = match[0], match[1]
    else:
        print("failed to renew webcam session parameter")


@app.route('/webcam/image/', defaults={'stop_number': "180"})
@app.route("/webcam/image/<stop_number>")
def webcam_image(stop_number: str):
    if webcam_id := config.STOP_WEBCAM_ID_TABLE.get(stop_number):
        timestamp = int(datetime.now().timestamp())
        url = f"https://www.mobil-potsdam.de/fileadmin/templates_webcams/get_image2.php?type=1&pic={webcam_id}&re={image_re}&rt={image_rt}&{timestamp}"
        return url
    else:
        abort(404)


@app.route('/', defaults={'stop_number': 180})
@app.route('/<stop_number>')
def index(stop_number: int):
    content: Stop = get_stop(stop_number)

    try:
        [info.update(content.routes) for info in content.actual]
    except AttributeError:
        return "This stop doesn't exist"

    webcam_url = None
    if webcam_id := config.STOP_WEBCAM_ID_TABLE.get(content.stop_short_name):
        global image_re
        global image_rt
        timestamp = int(datetime.now().timestamp() / 1000)
        webcam_url = f"https://www.mobil-potsdam.de/fileadmin/templates_webcams/get_image2.php?type=1&pic={webcam_id}&re={image_re}&rt={image_rt}&{timestamp}"

    show_image = request.cookies.get('showImage')
    kwargs = {
        "stop": content,
        "time": datetime.now().strftime("%H:%M"),
        "stops_map": config.STOPS_CONVERSION_TABLE,
        "webcam_url": webcam_url,
        "show_image": show_image == "true"
    }

    # PyCharm doesn't recognize the changed templates folder
    # noinspection PyUnresolvedReferences
    return render_template("index.html", **kwargs)


threading.Timer(interval=10.0, function=update_image_session_parameter).start()
