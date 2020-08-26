import paho.mqtt.client as mqtt
from datetime import datetime
import json
import asyncio
import websockets
import numpy as np
import time
import sys
import logging

logging.basicConfig(level=logging.INFO)


class BusWx:
    """Class that listens for new weather station observations"""

    def __init__(self, station_id, device_id, rapid_id, api_key):
        self.station_id = station_id
        self.device_id = device_id
        self.rapid_id = rapid_id
        self.api_key = api_key
        self.fail_count = 0
        self.fail_max = 30
        self.run()

    async def wx_connect(self, ws):
        """Connects to weatherstation"""
        await ws.send(
            '{"type":"listen_start", "device_id":'
            + self.device_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        await ws.send(
            '{"type":"listen_start", "device_id":'
            + self.rapid_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )
        await ws.send(
            '{"type":"listen_rapid_start", "device_id":'
            + self.rapid_id
            + ', "id":"'
            + self.station_id
            + '"}'
        )

    async def wx_on_message(self, ws):
        """Publishes each weatherstation observation to MQTT bus"""
        while True:
            message = await ws.recv()
            message = json.loads(message)
            if message["type"] == "evt_precip":
                msg = {}
                msg["type"] = "wx_precip"
                msg["timestamp"] = datetime.utcnow().isoformat()
                try:
                    self.client.publish(
                        "kk6gpv_bus/wx/precip", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

            if message["type"] == "evt_strike":
                msg = {}
                msg["type"] = "wx_strike"
                msg["timestamp"] = datetime.utcnow().isoformat()
                msg["distance"] = message["evt"][1]
                msg["energy"] = message["evt"][2]
                try:
                    self.client.publish(
                        "kk6gpv_bus/wx/strike", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

            if message["type"] == "device_status":
                msg = {}
                msg["type"] = "wx_status"
                msg["voltage"] = message["voltage"]
                try:
                    self.client.publish(
                        "kk6gpv_bus/wx/status", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

            if message["type"] == "obs_air":
                msg = {}
                msg["type"] = "wx_air"
                msg["timestamp"] = datetime.utcnow().isoformat()
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
                    self.client.publish(
                        "kk6gpv_bus/wx/air", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

            if message["type"] == "obs_sky":
                msg = {}
                msg["type"] = "wx_sky"
                msg["timestamp"] = datetime.utcnow().isoformat()
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
                    self.client.publish(
                        "kk6gpv_bus/wx/sky", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

            if message["type"] == "rapid_wind":
                msg = {}
                msg["type"] = "wx_wind"
                msg["timestamp"] = datetime.utcnow().isoformat()
                msg["wind_degrees"] = str(message["ob"][2])
                msg["wind_mph"] = str(np.round(message["ob"][1] * 1.94384, 2))
                try:
                    self.client.publish(
                        "kk6gpv_bus/wx/wind", json.dumps(msg), retain=True
                    )
                    logging.info(msg)
                except Exception:
                    pass

    async def weatherstation(self):
        """Initial websocket connection to weatherstation"""
        uri = "wss://ws.weatherflow.com/swd/data?" + "api_key=" + self.api_key
        async with websockets.connect(uri) as ws:
            await self.wx_connect(ws)
            await self.wx_on_message(ws)

    def fail_check(self):
        self.fail_count += 1
        logging.warning(
            "couldn't connect {0} time(s)".format(str(self.fail_count))
        )
        if self.fail_count > self.fail_max - 1:
            logging.error("exiting...")
            sys.exit(1)

    def run(self):
        """Async loop running the function"""
        while True:
            try:
                self.client = mqtt.Client(
                    client_id="kk6gpv-bus-wx", clean_session=False
                )
                self.client.connect("broker.mqttdashboard.com", 1883)
                asyncio.get_event_loop().run_until_complete(
                    self.weatherstation()
                )
                self.fail_count = 0
            except Exception:
                time.sleep(2)
                self.fail_check()


if __name__ == "__main__":
    bus = BusWx(
        station_id="2098388936",
        device_id="54051",
        rapid_id="54053",
        api_key="20c70eae-e62f-4d3b-b3a4-8586e90f3ac8",
    )
