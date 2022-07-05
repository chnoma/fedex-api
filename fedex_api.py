# -*- coding: utf-8 -*-
"""
Created on Sun Feb 13 17:21:17 2022

@author: Adrian J. Arnett

Created for Colossal Contracting, LLC.
"""

import configparser
from datetime import date
from dataclasses import dataclass

import requests

@dataclass
class Package():
    isValid: bool
    packageType: str
    deliveryDate: str
    shipDate: str
    json: dict

class FedexAPI():
    """Wrapper class for the Fedex tracking API"""
    def __init__(self, apiKey, secretKey):
        """Initialization function - attempts to obtain auth key"""
        self.API_URL = "https://apis.fedex.com/"
        self.AUTH_URL = "oauth/token"
        self.TRACK_URL = "track/v1/trackingnumbers"
        self.API_KEY = apiKey
        self.SECRET_KEY = secretKey
        authrequest = requests.post(self.API_URL + self.AUTH_URL, 
                                   headers = {"Content-type":"application/x-www-form-urlencoded"},
                                   data = {"grant_type":"client_credentials",
                                           "client_id":self.API_KEY,
                                             "client_secret":self.SECRET_KEY})
        self.AUTH_KEY = authrequest.json()['access_token']
        print("Obtained authentication key: ", self.AUTH_KEY,"\n_________________________________________________________________________________\n\n\n")

    def trackbynumber(self, number):
        payload = {"trackingInfo": [{"trackingNumberInfo": {"trackingNumber": str(number)}}], "includeDetailedScans": "False"}
        headers = {"Content-type":"application/json", 
                   "Authorization":f"Bearer {self.AUTH_KEY}"}
        trackrequest = requests.request("POST", self.API_URL + self.TRACK_URL,
                                     data = str(payload).replace("'", '"'),
                                     headers = headers)
        try:
            trackrequest = trackrequest.json()
            if trackrequest["output"]["completeTrackResults"][0]["trackResults"][0]["latestStatusDetail"]["code"] != "DL":
                print(f"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\nWARNING: Package {number} has not been delivered.\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
            ship = "Unavailable"
    
            for entry in trackrequest["output"]["completeTrackResults"][0]["trackResults"][0]["dateAndTimes"]:
                if entry["type"] == "SHIP":
                    ship = entry["dateTime"]
                if entry["type"] == "ACTUAL_DELIVERY":
                    deliverDate = entry["dateTime"]
            ship = ship[:ship.find("T")]
            deliverDate = deliverDate[:deliverDate.find("T")]
            trackresult = Package(True,
                                  trackrequest["output"]["completeTrackResults"][0]["trackResults"][0][
                                      "packageDetails"]["physicalPackagingType"],
                                  date.fromisoformat(deliverDate).strftime("%m/%d/%Y"), date.fromisoformat(ship).strftime("%m/%d/%Y"), trackrequest)
        except:
            trackresult = Package(False, "Invalid Tracking Information", "Invalid Tracking Information", "")
            
        return trackresult