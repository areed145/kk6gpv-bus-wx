import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import urllib.request
import json
import asyncio
from websockets import connect
import numpy as np
import time
import logging
import os
import sys
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)


class WxWebSocket:
    """Class for the weather station websocket"""

    def __init__(self):
        self.logger = logging.getLogger("kk6gpv-bus-wx")
        self.token = "2f933732-46c2-45d1-8704-fbff9b350bf8"
        self.devices_uri = (
            "https://swd.weatherflow.com/swd/rest/stations?token=" + self.token
        )
        self.ws_uri = "wss://ws.weatherflow.com/swd/data?token=" + self.token
        self.get_devices()

    def get_devices(self):
        hdr = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) \
            AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 \
            Safari/537.36"
        }
        req = urllib.request.Request(self.devices_uri, headers=hdr)
        msg = urllib.request.urlopen(req).read()
        msg = json.loads(msg)
        devices = msg["stations"][0]["devices"]
        for device in devices:
            if device["device_type"] == "HB":
                self.station_id = str(device["device_id"])
            if device["device_type"] == "ST":
                self.device_id = str(device["device_id"])
        self.logger.info("websocket: {}".format(self.ws_uri))
        self.logger.info("station id: {}".format(self.station_id))
        self.logger.info("device id: {}".format(self.device_id))

    async def __aenter__(self):
        """Initial websocket connection to weatherstation"""
        self.con = connect(self.ws_uri)
        self.websocket = await self.con.__aenter__()
        return self

    async def __aexit__(self, *args, **kwargs):
        """Exits weather station connection"""
        await self.con.__aexit__(*args, **kwargs)

    async def wx_connect(self):
        """Connects to weatherstation"""
        self.bus_client = mqtt.Client(
            client_id="kk6gpv-bus-wx", clean_session=False
        )
        self.bus_client.connect("broker.mqttdashboard.com", 1883)
        await self.websocket.send(
            '{"type":"listen_start", "device_id":'
            + self.device_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        await self.websocket.send(
            '{"type":"listen_rapid_start", "device_id":'
            + self.device_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        self.logger.info("connecting...")

    async def wx_on_message(self):
        """Publishes each weatherstation observation to MQTT bus"""
        while True:
            message = await self.websocket.recv()
            message = json.loads(message)
            if "type" not in message:
                print(message)
                self.logger.error(message)
            else:
                if message["type"] == "evt_precip":
                    msg = {}
                    msg["type"] = "wx_precip"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/precip",
                            json.dumps(msg),
                            retain=True,
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "evt_strike":
                    msg = {}
                    msg["type"] = "wx_strike"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["distance"] = message["evt"][1]
                    msg["energy"] = message["evt"][2]
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/strike",
                            json.dumps(msg),
                            retain=True,
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)
                    try:
                        client = MongoClient(os.environ["MONGODB_CLIENT"])
                        db = client.wx
                        db_lightning = db.lightning
                        db_lightning.insert_one(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "device_status":
                    msg = {}
                    msg["type"] = "wx_status"
                    msg["voltage"] = message["voltage"]
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/status",
                            json.dumps(msg),
                            retain=True,
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "obs_air":
                    msg = {}
                    msg["type"] = "wx_air"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["temp_f"] = str(
                        np.round((message["obs"][0][2] * (9 / 5) + 32), 2)
                    )
                    msg["dewpoint_f"] = str(
                        np.round(
                            (
                                message["obs"][0][2]
                                - (100 - message["obs"][0][3]) / 5
                            )
                            * (9 / 5)
                            + 32,
                            2,
                        )
                    )
                    msg["relative_humidity"] = str(
                        np.round(message["obs"][0][3], 2)
                    )
                    msg["pressure_in"] = str(
                        np.round(message["obs"][0][1] * 0.029693, 3)
                    )
                    msg["pressure_trend"] = str(
                        message["summary"]["pressure_trend"]
                    )
                    try:
                        msg["strike_count_3h"] = str(
                            message["summary"]["strike_count_3h"]
                        )
                    except Exception:
                        pass
                    try:
                        msg["strike_last_dist"] = str(
                            message["summary"]["strike_last_dist"]
                        )
                    except Exception:
                        pass
                    try:
                        msg["strike_last_epoch"] = str(
                            message["summary"]["strike_last_epoch"]
                        )
                    except Exception:
                        pass
                    msg["feels_like"] = str(message["summary"]["feels_like"])
                    msg["heat_index"] = str(message["summary"]["heat_index"])
                    msg["wind_chill"] = str(message["summary"]["wind_chill"])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/air", json.dumps(msg), retain=True
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "obs_sky":
                    msg = {}
                    msg["type"] = "wx_sky"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["wind_degrees"] = str(message["obs"][0][7])
                    msg["wind_mph"] = str(
                        np.round(message["obs"][0][5] * 1.94384, 2)
                    )
                    msg["wind_gust_mph"] = str(
                        np.round(message["obs"][0][6] * 1.94384, 2)
                    )
                    msg["precip_today_in"] = str(
                        np.round(message["obs"][0][11] * 0.0393701, 3)
                    )
                    msg["solar_radiation"] = str(message["obs"][0][10])
                    msg["uv"] = str(message["obs"][0][2])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/sky", json.dumps(msg), retain=True
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "obs_st":
                    msg = {}
                    msg["type"] = "wx_air"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["temp_f"] = str(
                        np.round((message["obs"][0][7] * (9 / 5) + 32), 2)
                    )
                    msg["dewpoint_f"] = str(
                        np.round(
                            (
                                message["obs"][0][7]
                                - (100 - message["obs"][0][8]) / 5
                            )
                            * (9 / 5)
                            + 32,
                            2,
                        )
                    )
                    msg["relative_humidity"] = str(
                        np.round(message["obs"][0][8], 2)
                    )
                    msg["pressure_in"] = str(
                        np.round(message["obs"][0][6] * 0.029693, 3)
                    )
                    msg["pressure_trend"] = str(
                        message["summary"]["pressure_trend"]
                    )
                    msg["strike_count_3h"] = str(
                        message["summary"]["strike_count_3h"]
                    )
                    try:
                        msg["strike_last_dist"] = str(
                            message["summary"]["strike_last_dist"]
                        )
                    except Exception:
                        pass
                    try:
                        msg["strike_last_epoch"] = str(
                            message["summary"]["strike_last_epoch"]
                        )
                    except Exception:
                        pass
                    msg["feels_like"] = str(message["summary"]["feels_like"])
                    msg["heat_index"] = str(message["summary"]["heat_index"])
                    msg["wind_chill"] = str(message["summary"]["wind_chill"])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/air", json.dumps(msg), retain=True
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                    msg = {}
                    msg["type"] = "wx_sky"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["wind_degrees"] = str(message["obs"][0][4])
                    msg["wind_mph"] = str(
                        np.round(message["obs"][0][2] * 1.94384, 2)
                    )
                    msg["wind_gust_mph"] = str(
                        np.round(message["obs"][0][3] * 1.94384, 2)
                    )
                    if message["obs"][0][18] is not None:
                        msg["precip_today_in"] = str(
                            np.round(message["obs"][0][18] * 0.0393701, 3)
                        )
                    else:
                        msg["precip_today_in"] = 0
                    msg["solar_radiation"] = str(message["obs"][0][11])
                    msg["uv"] = str(message["obs"][0][10])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/sky", json.dumps(msg), retain=True
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                elif message["type"] == "rapid_wind":
                    msg = {}
                    msg["type"] = "wx_wind"
                    msg["timestamp"] = datetime.now(timezone.utc).isoformat()
                    msg["wind_degrees"] = str(message["ob"][2])
                    msg["wind_mph"] = str(
                        np.round(message["ob"][1] * 1.94384, 2)
                    )
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/wind", json.dumps(msg), retain=True
                        )
                        self.logger.info(msg)
                    except Exception:
                        self.logger.warning(msg)

                else:
                    self.logger.error(str(message))


class BusWx:
    """Class that listens for new weather station observations"""

    def __init__(self):
        """Initialize class"""
        self.fail_init()
        self.fail_max = 30
        self.wws = WxWebSocket()
        self.loop = asyncio.get_event_loop()
        self.run()

    def fail_init(self):
        """Initialize check for failure"""
        self.fail_count = 0
        with open("healthy", "w") as fp:
            fp.write("healthy")
            pass

    def fail_check(self):
        """Check for failure count"""
        self.fail_count += 1
        self.logger.warning(
            "couldn't connect {0} time(s)".format(str(self.fail_count))
        )
        if self.fail_count > self.fail_max - 1:
            self.logger.error("exiting...")
            os.remove("healthy")
            sys.exit(1)

    def run(self):
        """Run the bus"""
        while True:
            try:
                self.loop.run_until_complete(self.__async__run())
                self.fail_init()
            except Exception as e:
                self.logger.error(str(e))
                time.sleep(10)
                self.fail_check()

    async def __async__run(self):
        """async run"""
        async with self.wws as ws:
            await ws.wx_connect()
            await ws.wx_on_message()


if __name__ == "__main__":
    bus = BusWx()
