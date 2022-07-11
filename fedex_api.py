# -*- coding: utf-8 -*-
"""
Created on Sun Feb 13 17:21:17 2022

@author: Adrian J. Arnett

Created for Colossal Contracting, LLC.
"""

from datetime import date, datetime
from enum import Enum
from dataclasses import dataclass

import requests
from requests import HTTPError

API_AUTHORITY = "https://apis.fedex.com/"
AUTH_PATH = "oauth/token"
TRACK_PATH = "track/v1/trackingnumbers"
TIMEOUT = 10


class AuthenticationError(Exception):
    """
    Generic authentication exception class
    """
    pass


class InvalidRequestError(Exception):
    """
    Generic invalid HTTP request exception class
    """
    pass


class Event(Enum):
    ACTUAL_DELIVERY = "ACTUAL_DELIVERY"
    ACTUAL_PICKUP = "ACTUAL_PICKUP"
    ACTUAL_TENDER = "ACTUAL_TENDER"
    ANTICIPATED_TENDER = "ANTICIPATED_TENDER"
    APPOINTMENT_DELIVERY = "APPOINTMENT_DELIVERY"
    ATTEMPTED_DELIVERY = "ATTEMPTED_DELIVERY"
    COMMITMENT = "COMMITMENT"
    ESTIMATED_ARRIVAL_AT_GATEWAY = "ESTIMATED_ARRIVAL_AT_GATEWAY"
    ESTIMATED_DELIVERY = "ESTIMATED_DELIVERY"
    ESTIMATED_PICKUP = "ESTIMATED_PICKUP"
    ESTIMATED_RETURN_TO_STATION = "ESTIMATED_RETURN_TO_STATION"
    SHIP = "SHIP"
    SHIPMENT_DATA_RECEIVED = "SHIPMENT_DATA_RECEIVED"


class PackageType(Enum):
    BAG = "BAG"
    BARREL = "BARREL"
    BASKET = "BASKET"
    BOX = "BOX"
    BUCKET = "BUCKET"
    BUNDLE = "BUNDLE"
    CAGE = "CAGE"
    CARTON = "CARTON"
    CASE = "CASE"
    CHEST = "CHEST"
    CONTAINER = "CONTAINER"
    CRATE = "CRATE"
    CYLINDER = "CYLINDER"
    DRUM = "DRUM"
    ENVELOPE = "ENVELOPE"
    HAMPER = "HAMPER"
    OTHER = "OTHER"
    PACKAGE = "PACKAGE"
    PAIL = "PAIL"
    PALLET = "PALLET"
    PARCEL = "PARCEL"
    PIECE = "PIECE"
    REEL = "REEL"
    ROLL = "ROLL"
    SACK = "SACK"
    SHRINK_WRAPPED = "SHRINK_WRAPPED"
    SKID = "SKID"
    TANK = "TANK"
    TOTE_BIN = "TOTE_BIN"
    TUBE = "TUBE"
    UNIT = "UNIT"


@dataclass
class DateAndTimeEvent:
    datetime: datetime
    type: Event


@dataclass
class Package:
    type: PackageType
    count: int


@dataclass
class TrackingResult:
    is_valid: bool
    tracking_number: str = None
    unique_id: str = None
    carrier_code: str = None
    is_delivered: bool = None
    is_shipped: bool = None
    date_ship: date = None
    date_delivery: date = None  # EST Delivery date if not delivered.
    latest_status: DateAndTimeEvent = None
    events: list = None
    package: Package = None


def _download_file(url, filename):
    with requests.get(url, stream=False) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return filename


class FedexAPI:

    def __init__(self, api_key, secret_key, api_authority=API_AUTHORITY, auth_path=AUTH_PATH, track_path=TRACK_PATH):
        if secret_key == "" or api_key == "":
            raise AuthenticationError("\nInvalid key supplied")
        self.API_URL = api_authority
        self.AUTH_URL = api_authority + auth_path
        self.TRACK_URL = api_authority + track_path
        self.API_KEY = api_key
        self.SECRET_KEY = secret_key
        request = requests.post(self.AUTH_URL,
                                headers={"Content-type": "application/x-www-form-urlencoded"},
                                data={"grant_type": "client_credentials",
                                      "client_id": self.API_KEY,
                                      "client_secret": self.SECRET_KEY})
        try:
            self.AUTH_KEY = request.json()['access_token']
        except IndexError:
            raise AuthenticationError("\nInvalid authentication request.")
        print("Obtained authentication key: ", self.AUTH_KEY,
              "\n_________________________________________________________________________________\n\n\n")

    def track_by_number(self, number: str) -> TrackingResult:
        payload = {"trackingInfo": [{"trackingNumberInfo": {"trackingNumber": str(number)}}],
                   "includeDetailedScans": "False"}
        headers = {"Content-type": "application/json",
                   "Authorization": f"Bearer {self.AUTH_KEY}"}
        response = requests.request("POST", self.TRACK_URL,
                                    data=str(payload).replace("'", '"'),
                                    headers=headers)
        try:
            response.raise_for_status()
        except HTTPError:
            return TrackingResult(False)
        response_data = response.json()
        if "errors" in response_data:
            return TrackingResult(False)
        tracking_results = []
        for track_index in response_data["output"]["completeTrackResults"]:
            track_results = track_index["trackResults"]
            for tracking_result in track_results:
                tracking_number_info = tracking_result["trackingNumberInfo"]
                tracking_number = tracking_number_info["trackingNumber"]
                unique_id = tracking_number_info["trackingNumberUniqueId"]
                carrier_code = tracking_number_info["carrierCode"]
                shipped = False
                delivered = False
                ship_date = None  # declare out of the loop scope to preserve
                delivery_date = None  # declare out of the loop scope to preserve
                latest_date = None  # declare out of the loop scope to preserve
                latest_type = None  # declare out of the loop scope to preserve
                events = []
                if "dateAndTimes" not in tracking_result:
                    return TrackingResult(False)
                for event in tracking_result["dateAndTimes"]:
                    event_type = Event[event["type"]]
                    event_date = datetime.fromisoformat(event["dateTime"])
                    if event_type == Event.SHIP:
                        shipped = True
                        ship_date = event_date
                    elif event_type == Event.ACTUAL_DELIVERY:
                        delivered = True
                        delivery_date = event_date
                    elif event_type == Event.ESTIMATED_DELIVERY:
                        delivery_date = event_date
                    if latest_type is None or event_date > latest_date:
                        latest_date = event_date
                        latest_type = event_type
                    new_event = DateAndTimeEvent(event_date, event_type)
                    events.append(new_event)
                latest_event = DateAndTimeEvent(latest_date, latest_type)
                # package = Package(PackageType[tracking_result["packageDetails"]["physicalPackagingType"]],
                #                   int(tracking_result["packageDetails"]["count"]))
                new_tracking_result = TrackingResult(
                    is_valid=True,
                    tracking_number=tracking_number,
                    unique_id=unique_id,
                    carrier_code=carrier_code,
                    is_delivered=delivered,
                    is_shipped=shipped,
                    date_ship=ship_date,
                    date_delivery=delivery_date,
                    latest_status=latest_event,
                    events=events)
                tracking_results.append(new_tracking_result)
        # prevent duplicate errors
        latest_date = None  # declare out of the loop scope to preserve
        latest_result = None  # declare out of the loop scope to preserve
        for result in tracking_results:
            if latest_result is None or result.latest_status.datetime > latest_date:
                latest_date = result.latest_status.datetime
                latest_result = result
        return latest_result

    def download_pod(self, unique_id, new_filename):
        if len(unique_id.split('~')) == 1:
            result = self.track_by_number(unique_id)
            if not result.is_valid:
                raise InvalidRequestError(f"\nInvalid request for tracking number: {unique_id}")
            unique_id = result.unique_id
        qualifier = unique_id.split('~')[0]
        tracking_number = unique_id.split('~')[1]
        _download_file(
            f"https://www.fedex.com/trackingCal/retrievePDF.jsp?accountNbr=&anon=true&appType=&destCountry=&locale=en_US&shipDate=&trackingCarrier=FDXA&trackingNumber={tracking_number}&trackingQualifier={qualifier}&type=SPOD",
            new_filename)
