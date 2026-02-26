import os
import json
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth


class UPSApi:
    access_token = ""
    payload_json = {}
    order = {}
    service_level = "GND"
    ups_api = "https://onlinetools.ups.com/"
    ups_insurance_api = "https://upscapi.ams1907.com/apis/list-extstg/quote/v2"

    def __init__(self, order: dict = None):
        self.client_id = os.environ["UPS_CLIENT_ID"]
        self.client_secret = os.environ["UPS_CLIENT_SECRET"]
        self.generate_token()

        self.shipper_name = "Letronics"  # TODO: Update when UPS account is updated for Order Fulfillment
        self.shipper_phone = "(214) 381-8507"
        self.shipper_fax = "(214) 381-8507"
        self.shipper_tax_number = "752962874"
        self.shipper_number = os.environ["UPS_ACCOUNT_NUMBER"]
        self.shipper_address_line = "2200 BIG TOWN BLVD. #180"
        self.shipper_city = "MESQUITE"
        self.shipper_state = "TX"
        self.shipper_zip = "75149"
        self.shipper_country = "US"
        if order:
            self.set_order(order)

    def set_order(self, order: dict):
        self.order = order
        if self.order["order_type"] == "return":
            self.shipper_name = self.order["address"]["name"]
            self.ship_from_name = self.order["address"]["name"]
            self.shipper_city = self.order["address"]["city"]
            self.ship_from_city = self.order["address"]["city"]
            self.shipper_state = self.order["address"]["state"]
            self.ship_from_state = self.order["address"]["state"]
            zip_code = str(self.order["address"]["zipCode"])
            self.shipper_zip = zip_code
            self.ship_from_zipcode = zip_code
            self.shipper_country = "US"
            self.ship_from_country = "US"
            self.ship_from_phone = self.shipper_phone
            self.ship_from_fax = self.shipper_fax
            address_line2 = (
                " " + self.order["address"]["addressLine2"]
                if "addressLine2" in self.order["address"]
                and self.order["address"]["addressLine2"]
                else ""
            )
            full_address = self.order["address"]["addressLine1"] + address_line2
            self.ship_from_address_line = self.shipper_address_line = full_address
            print("RETURN from address_lines", full_address)
        else:
            self.ship_from_name = "Letronics"  # TODO: Update when UPS account is updated for Order Fulfillment
            self.ship_from_phone = "(214) 381-8507"
            self.ship_from_phone = "(214) 381-8507"
            self.ship_from_address_line = "2200 BIG TOWN BLVD. #180"
            self.ship_from_city = "MESQUITE"
            self.ship_from_state = "TX"
            self.ship_from_zipcode = "75149"
            self.ship_from_country = "US"
        self.generate_payload_json()

    @property
    def camera_count(self):
        # Camera count is equal to vehicles count
        return len(self.order.get("vehicles", {}))

    @property
    def package_dimensions(self):
        length, width, height = "9", "7", "5"
        if self.camera_count == 2:
            length, width, height = "10", "10", "10"
        elif self.camera_count == 3 or self.camera_count == 4:
            length, width, height = "13", "13", "13"
        elif self.camera_count > 4:
            length, width, height = "15", "15", "15"

        return {"Length": length, "Width": width, "Height": height}

    @property
    def package_lbs(self):
        lbs = "1"
        if self.camera_count == 2:
            lbs = "3"
        elif self.camera_count == 3 or self.camera_count == 4:
            lbs = "5"
        elif self.camera_count > 4:
            lbs = "7"
        return lbs

    def post_request(self, url: str, payload: dict):
        print("post_request called")
        print("url", url)
        print("payload below")
        print(payload)
        headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
            "transId": "string",
            "transactionSrc": "production",
        }
        # print("headers", headers)
        result = {}
        try:
            payload = json.dumps(payload, indent=4)
            response = requests.request("POST", url, headers=headers, data=payload)
            print(response.text)
            result = response.json()
        except Exception as err:
            print("An Error accured while posting date to UPS Api", err)

        return result

    def do_shipping(self):
        return self.post_request(
            url=self.ups_api
            + "api/shipments/v1/ship?additionaladdressvalidation="
            + self.order["address"]["city"],
            payload=self.payload_json,
        )

    def generate_token(self):
        # if os.environ.get('UPS_ACCESS_TOKEN'):
        #   self.access_token = os.environ.get('UPS_ACCESS_TOKEN')
        if self.access_token:
            return
        url = self.ups_api + "security/v1/oauth/token"
        payload = "grant_type={}&code={}&redirect_uri={}".format(
            "client_credentials",
            self.client_secret,
            "https%3A%2F%2Fwww.google.com%2Foauth",
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "x-merchant-id": os.environ["UPS_CLIENT_ID"],
        }
        response = requests.request(
            "POST",
            url,
            headers=headers,
            data=payload,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
        )

        # print(response.text)
        self.access_token = response.json()["access_token"]
        # print("UPS ACCESS TOKEN", self.access_token)

    @property
    def ship_from(self):
        address_lines = []
        words = self.ship_from_address_line.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= 35:
                current_line += word + " "
            else:
                address_lines.append(current_line.strip())
                current_line = word + " "
        address_lines.append(current_line.strip())
        print("address_lines", address_lines)
        return {
            "Name": self.ship_from_name,
            "AttentionName": " ",
            "Phone": {"Number": self.ship_from_phone},
            "FaxNumber": self.ship_from_phone,
            "Address": {
                "AddressLine": address_lines,
                "City": self.ship_from_city,
                "StateProvinceCode": self.ship_from_state,
                "PostalCode": self.ship_from_zipcode,
                "CountryCode": self.ship_from_country,
            },
        }

    @property
    def shipper(self):
        return {
            "Name": self.shipper_name,
            "AttentionName": self.shipper_name
            if self.order["order_type"] == "return"
            else "FULFILLMENT CENTER",
            "TaxIdentificationNumber": self.shipper_tax_number,
            "Phone": {"Number": self.shipper_phone, "Extension": ""},
            "ShipperNumber": self.shipper_number,
            "FaxNumber": self.shipper_fax,
            "Address": {
                "AddressLine": [self.shipper_address_line],
                "City": self.shipper_city,
                "StateProvinceCode": self.shipper_state,
                "PostalCode": self.shipper_zip,
                "CountryCode": self.shipper_country,
            },
        }

    @property
    def ship_to(self):
        address_lines = []
        address_line2 = (
            " " + self.order["address"]["addressLine2"]
            if "addressLine2" in self.order["address"]
            and self.order["address"]["addressLine2"]
            else ""
        )
        full_address = self.order["address"]["addressLine1"] + address_line2
        words = full_address.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= 35:
                current_line += word + " "
            else:
                address_lines.append(current_line.strip())
                current_line = word + " "
        address_lines.append(current_line.strip())
        print("ship to address_lines", address_lines)
        name = (
            "Returns"
            if self.order["order_type"] == "return"
            else self.order["address"]["business"]
        )
        attentionName = (
            ""
            if self.order["order_type"] == "return"
            else self.order["address"]["name"]
        )
        address_lines = (
            ["2200 Big Town Blvd #180"]
            if self.order["order_type"] == "return"
            else address_lines
        )
        city = (
            "Mesquite"
            if self.order["order_type"] == "return"
            else self.order["address"]["city"]
        )
        state = (
            "TX"
            if self.order["order_type"] == "return"
            else self.order["address"]["state"]
        )
        zipcode = (
            "75149"
            if self.order["order_type"] == "return"
            else str(self.order["address"]["zipCode"])
        )
        return {
            "Name": name,
            "AttentionName": attentionName,
            "Phone": {
                # missing reciever phone number # 214.381.8507, it is required field
                "Number": "(214) 381-8507"
            },
            "Address": {
                "AddressLine": address_lines,
                "City": city,
                "StateProvinceCode": state,
                "PostalCode": str(zipcode),
                "CountryCode": "US",
            },
            "Residential": " ",
        }

    @property
    def payment_information(self):
        return {
            "ShipmentCharge": {
                "Type": "01",
                "BillShipper": {"AccountNumber": self.shipper_number},
            }
        }

    def generate_payload_json(self):
        self.payload_json = {
            "ShipmentRequest": {
                "Request": {
                    "SubVersion": "1801",
                    "RequestOption": "nonvalidate",
                    "TransactionReference": {"CustomerContext": "Order Fulfillment"},
                },
                "Shipment": {
                    "Description": "Ship WS test",
                    "ReturnService": None,
                    "Shipper": self.shipper,
                    "ShipTo": self.ship_to,
                    "ShipFrom": self.ship_from,
                    "PaymentInformation": self.payment_information,
                    "Service": {"Code": "03", "Description": "Express"},
                    "Package": {
                        "Description": " ",
                        # "ReferenceNumber": [],
                        "Packaging": {"Code": "02", "Description": "Nails"},
                        "Dimensions": {
                            "UnitOfMeasurement": {
                                "Code": "IN",
                                "Description": "Inches",
                            },
                            "Length": self.package_dimensions["Length"],
                            "Width": self.package_dimensions["Width"],
                            "Height": self.package_dimensions["Height"],
                        },
                        "PackageWeight": {
                            "UnitOfMeasurement": {
                                "Code": "LBS",
                                "Description": "Pounds",
                            },
                            "Weight": self.package_lbs,
                        },
                    },
                },
                "LabelSpecification": {
                    "LabelImageFormat": {"Code": "GIF", "Description": "GIF"},
                    "HTTPUserAgent": "Mozilla/4.5",
                },
            }
        }
        if self.order["order_type"] == "return":
            self.payload_json["ShipmentRequest"]["Shipment"]["ReturnService"] = {
                "Code": "9",
                "Description": "Return Service",
            }
            self.payload_json["ShipmentRequest"]["Shipment"]["Package"][
                "ReferenceNumber"
            ] = [{"BarCodeIndicator": None, "Value": "AY10909"}]
            self.payload_json["ShipmentRequest"]["Shipment"]["Package"][
                "Description"
            ] = "Return Service"

        print("payload_json", self.payload_json)

    def transit_times(self):
        url = self.ups_api + "api/shipments/v1/transittimes"
        ship_date = datetime.today().strftime("%Y-%m-%d")  # today
        payload = {
            "originCountryCode": self.shipper_country,
            "originStateProvince": self.shipper_state,
            "originCityName": self.shipper_city,
            "originTownName": "",
            "originPostalCode": self.shipper_zip,
            "destinationCountryCode": "US",
            "destinationStateProvince": self.order["address"]["state"],
            "destinationCityName": self.order["address"]["city"],
            "destinationTownName": "",
            "destinationPostalCode": str(self.order["address"]["zipCode"]),
            "weight": self.package_lbs,
            "weightUnitOfMeasure": "LBS",
            "shipmentContentsValue": self.package_lbs,
            "shipmentContentsCurrencyCode": "USD",
            "billType": "03",
            "shipDate": ship_date,
            "shipTime": "",
            "residentialIndicator": "",
            "avvFlag": True,
            "numberOfPackages": "1",
        }

        response = self.post_request(url=url, payload=payload)
        print("Got the result from transittime", response)
        shipping_service = {}
        if response:
            for service in response["emsResponse"]["services"]:
                if service["serviceLevel"] == self.service_level:
                    shipping_service = service
        if not shipping_service:
            print("Service", self.service_level, "Not found")
        elif shipping_service.get("deliveryDate"):
            input_date = datetime.strptime(
                shipping_service.get("deliveryDate"), "%Y-%m-%d"
            )
            return input_date.strftime("%m/%d/%Y")
        return ""

    def validate_address(self):
        url = self.ups_api + "api/addressvalidation/v1/2"
        region = "{city},{state},{zip_code}".format(
            city=self.order["address"]["city"],
            state=self.order["address"]["state"],
            zip_code=str(self.order["address"]["zipCode"]),
        )
        addressLine2 = (
            self.order["address"]["addressLine2"]
            if "addressLine2" in self.order["address"]
            and self.order["address"]["addressLine2"]
            else ""
        )
        payload = {
            "XAVRequest": {
                "AddressKeyFormat": {
                    "ConsigneeName": self.order["address"]["name"],
                    "BuildingName": self.order["address"]["business"],
                    "AddressLine": [
                        self.order["address"]["addressLine1"],
                        addressLine2,
                        self.order["address"]["business"],
                    ],
                    "Region": region,
                    "PoliticalDivision2": self.order["address"]["city"],
                    "PoliticalDivision1": "CA",
                    "PostcodePrimaryLow": str(self.order["address"]["zipCode"]),
                    "PostcodeExtendedLow": "",
                    "Urbanization": "",
                    "CountryCode": "US",
                }
            }
        }
        result = self.post_request(url=url, payload=payload)
        print("validate_address", result)
        if "XAVResponse" not in result:
            return False
        classification = result["XAVResponse"].get("AddressClassification", {})
        code = classification.get("Code", False)
        return False if code == "0" else code

    def get_order_status(self):
        if not self.order["trackingId"]:
            return False
        url = self.ups_api + "api/track/v1/details/" + self.order["trackingId"]
        headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json",
            "transId": "string",
            "transactionSrc": "production",
        }
        payload = {"locale": "en_US", "returnSignature": "false"}
        response = requests.get(url, headers=headers, params=payload)
        result_json = response.json()
        print("tracking_package", result_json)
        status = ""
        try:
            status = result_json["trackResponse"]["shipment"][0]["package"][0][
                "currentStatus"
            ]["description"]
        except Exception as err:
            print("Got error while checking the status", err)
            if self.order["type"] == "return":
                return "NotReturned"
            # return "Unknown"
        return status
