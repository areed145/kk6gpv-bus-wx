import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import json
import asyncio
from websockets import connect
import numpy as np
import time
import sys
import logging
import os

logging.basicConfig(level=logging.INFO)


class WxWebSocket:
    """Class for the weather station websocket"""

    async def __aenter__(self):
        """Initial websocket connection to weatherstation"""
        self.station_id = "2098388936"
        self.device_id = "54051"
        self.rapid_id = "54053"
        self.api_key = "32f5918d-0c17-4b52-ac4e-6a6cf5dd3be0"  # "20c70eae-e62f-4d3b-b3a4-8586e90f3ac8"
        self.uri = (
            "wss://ws.weatherflow.com/swd/data?" + "api_key=" + self.api_key
        )

        self.bus_client = mqtt.Client(
            client_id="kk6gpv-bus-wx", clean_session=False
        )
        self.bus_client.connect("broker.mqttdashboard.com", 1883)

        self.con = connect(self.uri)
        self.websocket = await self.con.__aenter__()
        return self

    async def __aexit__(self, *args, **kwargs):
        """Exits weather station connection"""
        await self.con.__aexit__(*args, **kwargs)

    async def wx_connect(self):
        """Connects to weatherstation"""
        await self.websocket.send(
            '{"type":"listen_start", "device_id":'
            + self.device_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        await self.websocket.send(
            '{"type":"listen_start", "device_id":'
            + self.rapid_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        await self.websocket.send(
            '{"type":"listen_rapid_start", "device_id":'
            + self.rapid_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        logging.info("connecting...")

    async def wx_on_message(self):
        """Publishes each weatherstation observation to MQTT bus"""
        while True:
            message = await self.websocket.recv()
            message = json.loads(message)
            if "type" not in message:
                logging.error(message)
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
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)

                if message["type"] == "evt_strike":
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
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)

                if message["type"] == "device_status":
                    msg = {}
                    msg["type"] = "wx_status"
                    msg["voltage"] = message["voltage"]
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/status",
                            json.dumps(msg),
                            retain=True,
                        )
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)

                if message["type"] == "obs_air":
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
                    msg["strike_count_3h"] = str(
                        message["summary"]["strike_count_3h"]
                    )
                    msg["strike_last_dist"] = str(
                        message["summary"]["strike_last_dist"]
                    )
                    msg["strike_last_epoch"] = str(
                        message["summary"]["strike_last_epoch"]
                    )
                    msg["feels_like"] = str(message["summary"]["feels_like"])
                    msg["heat_index"] = str(message["summary"]["heat_index"])
                    msg["wind_chill"] = str(message["summary"]["wind_chill"])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/air", json.dumps(msg), retain=True
                        )
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)

                if message["type"] == "obs_sky":
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
                    msg["wind_degrees"] = str(message["obs"][0][7])
                    try:
                        self.bus_client.publish(
                            "kk6gpv_bus/wx/sky", json.dumps(msg), retain=True
                        )
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)

                if message["type"] == "rapid_wind":
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
                        logging.info(msg)
                    except Exception:
                        logging.warning(msg)


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
        with open("/healthy", "w") as fp:
            fp.write("healthy")
            pass

    def fail_check(self):
        """Check for failure count"""
        self.fail_count += 1
        logging.warning(
            "couldn't connect {0} time(s)".format(str(self.fail_count))
        )
        if self.fail_count > self.fail_max - 1:
            logging.error("exiting...")
            os.remove("/healthy")
            sys.exit(1)

    def run(self):
        """Run the bus"""
        while True:
            try:
                self.loop.run_until_complete(self.__async__run())
                self.fail_init()
            except Exception:
                time.sleep(2)
                self.fail_check()

    async def __async__run(self):
        """async run"""
        async with self.wws as ws:
            await ws.wx_connect()
            await ws.wx_on_message()


if __name__ == "__main__":
    bus = BusWx()
