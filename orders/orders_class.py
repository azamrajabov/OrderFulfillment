import os
import uuid
import json
import boto3
import base64
import requests
import datetime
import time
from ups_api import UPSApi
from vindecoder import Vindecoder
from mappings_class import Mappings
from inventory_class import Inventories
from boto3.dynamodb.conditions import Attr, Key
from shipping_labels import ShippingLabels


class Orders:
    unshipped_orders = {}
    shipped_orders = {}
    delivered_orders = {}
    returned_orders = {}
    failed_orders = {}
    delayed_orders = {}
    trash_orders = {}
    return_orders = {}
    ups_order = {}
    all_orders = {}
    shipped_fulfilled_delivered_returned = {}
    max_order_number = 0
    ups_capital_insurance_api = {
        "dev": {
            "quote_endpoint": "https://upscapi.ams1907.com/apis/list-extstg/quote/v2",
            "coverage_endpoint": "https://upscapi.ams1907.com/apis/list-extstg/coverage/v2",
        },
        "test": {
            "quote_endpoint": "https://upscapi.ams1907.com/apis/list-extstg/quote/v2",
            "coverage_endpoint": "https://upscapi.ams1907.com/apis/list-extstg/coverage/v2",
        },
        "prod": {
            "quote_endpoint": "https://upscapi.ups.com/apis/list/quote/v2",
            "coverage_endpoint": "https://upscapi.ups.com/apis/list/coverage/v2",
        },
    }
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ.get("ORDERS_TABLE")
        self.table = self.dynamodb.Table(self.table_name)
        # self.sort_orders()
        # self.get_max_order_num()
        self.shipping_labels = ShippingLabels()
        self.enviroment = os.environ["APP_ENVIRONMENT"]

    def generate_order_id(self):
        random_code = str(uuid.uuid4())
        return random_code

    def list_orders(self):
        response = self.table.scan()
        return response.get("Items", [])

    # def sort_orders(self):
    #     self.get_unshipped()
    #     self.get_shipped()
    #     self.get_delayed()
    #     self.get_delivered()
    #     self.get_returned()
    #     self.get_failed()
    #     self.get_trash()

    def max_order_num(self):
        response = self.table.scan()
        items = response.get("Items", [])
        if not items:
            return 0  # or appropriate value indicating no orders
        max_order_number = max(item["order_num"] for item in items)
        return max_order_number

    # def get_max_order_num(self):
    #     all_orders = (
    #         self.unshipped_orders
    #         + self.delivered_orders
    #         + self.delayed_orders
    #         + self.failed_orders
    #         + self.returned_orders
    #         + self.shipped_orders
    #     )
    #     for order in all_orders:
    #         order_num = int(order["order_num"])
    #         if order_num > self.max_order_number:
    #             self.max_order_number = order_num

    def export_data(self, orders: dict, status: str, no_headers: bool):
        csv_rows = []
        inventories = Inventories()
        if not no_headers:
            csv_rows.append(
                "oder_num,orderDate,orderId,orderType,business,name,address,city,state,zip,vin,year,make,model,engine,adapter,cameraId,cameraPassword,orderStatus,trackingId,shippedDate,deliveryDate,shippingCost,label_image,comments"
            )
        for order in orders:
            address2 = (
                " " + order["address"]["addressLine2"]
                if "addressLine2" in order["address"]
                and order["address"]["addressLine2"]
                else ""
            )
            address = order["address"]["addressLine1"] + address2
            date_object = datetime.datetime.fromisoformat(order["time_stamp"])
            order_date = date_object.strftime("%m/%d/%Y")
            shipped_date = order.get("shipped_date", "")
            comments = order.get("comments", "").replace('"', '"').replace("\n", " ")
            if shipped_date:
                date_object = datetime.datetime.fromisoformat(shipped_date)
                shipped_date = date_object.strftime("%m/%d/%Y")
            for vehicle in order.get("vehicles", []):
                order_type = order.get("order_type", "camera")
                vindecoded_values = vehicle.get("vindecoded_values", "").split(" ", 1)
                year = vindecoded_values[0] if len(vindecoded_values) > 0 else ""
                vindecoded_values = (
                    vindecoded_values[1].split(", ")
                    if len(vindecoded_values) > 1
                    else []
                )
                make = vindecoded_values[0] if len(vindecoded_values) > 0 else ""
                engine = vindecoded_values[1] if len(vindecoded_values) > 1 else ""
                model = vindecoded_values[2] if len(vindecoded_values) > 2 else ""
                row = '{order_num},{orderDate},{orderId},{order_type},"{business}","{name}","{address}","{city}",{state},{zipcode},{vin},{year},{make},"{model}","{engine}","{adapter}","{cameraId}","{cameraPassword}",{orderStatus},{trackingId},{shippedDate},{deliveryDate},{shippingCost},{label_image},"{comments}"'.format(
                    order_num=order["order_num"],
                    orderDate=order_date,
                    orderId=order["orderId"],
                    order_type=order_type,
                    address=address,
                    business=order["address"]["business"],
                    name=order["address"]["name"],
                    city=order["address"]["city"],
                    state=order["address"]["state"],
                    zipcode=str(order["address"]["zipCode"]),
                    vin=vehicle.get("vin", ""),
                    year=year,
                    make=make,
                    model=model,
                    engine=engine,
                    adapter=inventories.get_adapter_sku(vehicle["adapter"]),
                    cameraId=vehicle.get("cameraId", ""),
                    cameraPassword=vehicle.get("cameraPassword", ""),
                    orderStatus=order.get("orderStatus", status),
                    trackingId=order.get("trackingId", ""),
                    shippedDate=shipped_date,
                    deliveryDate=order.get("deliveryDate", ""),
                    shippingCost=order.get("shipping_cost", ""),
                    label_image=order.get("label_image", ""),
                    comments=comments,
                )
                csv_rows.append(row)
            if "parts" in order:
                order_type = order.get("order_type", "parts")
                for parts in order["parts"]:
                    row = '{order_num},{orderDate},{orderId},{order_type},"{business}","{name}","{address}","{city}",{state},{zipcode},{vin},{year},{make},"{model}","{engine}","{adapter}","{cameraId}","{cameraPassword}",{orderStatus},{trackingId},{shippedDate},{deliveryDate},{shippingCost},{label_image},"{comments}"'.format(
                        order_num=order["order_num"],
                        orderDate=order_date,
                        orderId=order["orderId"],
                        order_type=order_type,
                        address=address,
                        business=order["address"]["business"],
                        name=order["address"]["name"],
                        city=order["address"]["city"],
                        state=order["address"]["state"],
                        zipcode=str(order["address"]["zipCode"]),
                        vin=parts.get("type", ""),
                        year="",
                        make="",
                        model="",
                        engine="",
                        adapter=parts.get("model", ""),
                        cameraId="",
                        cameraPassword="",
                        orderStatus=order.get("orderStatus", status),
                        trackingId=order.get("trackingId", ""),
                        shippedDate=shipped_date,
                        deliveryDate=order.get("deliveryDate", ""),
                        shippingCost=order.get("shipping_cost", ""),
                        label_image=order.get("label_image", ""),
                        comments=comments,
                    )
                    csv_rows.append(row)

        return csv_rows

    def export_orders(self, status: str, no_headers=False):
        csv_rows = []
        if status == "Unshipped":
            csv_rows = self.export_data(
                orders=self.get_unshipped(), status=status, no_headers=no_headers
            )
        elif status == "Shipped":
            csv_rows = self.export_data(
                orders=self.get_shipped(), status=status, no_headers=no_headers
            )
        elif status == "Delivered":
            csv_rows = self.export_data(
                orders=self.get_delivered(), status=status, no_headers=no_headers
            )
        elif status == "Delayed":
            csv_rows = self.export_data(
                orders=self.get_delayed(), status=status, no_headers=no_headers
            )
        elif status == "Returned":
            csv_rows = self.export_data(
                orders=self.get_returned(), status=status, no_headers=no_headers
            )
        elif status == "Failed":
            csv_rows = self.export_data(
                orders=self.get_failed(), status=status, no_headers=no_headers
            )
        elif status == "Trash":
            csv_rows = self.export_data(
                orders=self.get_trash(), status=status, no_headers=no_headers
            )
        elif status == "Returns":
            csv_rows = self.export_data(
                orders=self.get_returns(), status=status, no_headers=no_headers
            )

        return "\n".join(csv_rows) if csv_rows else ""

    def get_unshipped(self):
        if not self.unshipped_orders:
            self.unshipped_orders = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Unshipped")
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.unshipped_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.unshipped_orders:
                self.unshipped_orders = sorted(
                    self.unshipped_orders, key=lambda x: x["order_num"]
                )

        return self.unshipped_orders

    def get_returns(self, reverse=False, page=1, limit=100):
        if not self.return_orders:
            self.return_orders = []
            scan_params = {"FilterExpression": Attr("order_type").eq("return")}
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.return_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.return_orders:
                if reverse:
                    self.return_orders = sorted(
                        self.return_orders,
                        key=lambda x: x["order_num"],
                        reverse=True,
                    )
                else:
                    self.return_orders = sorted(
                        self.return_orders, key=lambda x: x["order_num"]
                    )

        start_index = (page - 1) * limit
        end_index = start_index + limit
        return (
            self.return_orders[start_index:end_index] if limit else self.return_orders
        )

    def get_all_orders(self):
        if not self.all_orders:
            self.all_orders = []
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    response = self.table.scan(ExclusiveStartKey=last_evaluated_key)
                else:
                    response = self.table.scan()
                items = response.get("Items", [])
                if items:
                    self.all_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")

                if not last_evaluated_key:
                    break
        return self.all_orders

    def check_shipped_orders(self):
        orders = self.get_shipped_fulfilled_delivered_returned()
        today = datetime.date.today()
        ups_api = UPSApi()
        for order in orders:
            ups_api.set_order(order=order)
            ups_order_status = ups_api.get_order_status()
            print(order["orderId"], "UPS ORDER STATUS", ups_order_status)
            if ups_order_status in ("On the Way", "In Transit", "Out for Delivery"):
                ups_order_status = "Shipped"
            if "return" in ups_order_status.lower():
                ups_order_status = "Returned"
                # 'Shipment Ready for UPS' - Fulfilled
            if order["orderStatus"] != ups_order_status and ups_order_status in (
                "Shipped",
                "Delivered",
                "Returned",
                "Delayed",
            ):
                self.change_order_status(
                    order_id=order["orderId"],
                    order_num=order["order_num"],
                    status=ups_order_status,
                    order_type=order["order_type"],
                )
                order["orderStatus"] = ups_order_status
            elif order["orderStatus"] == "Fulfilled":
                delivery_date = order.get("deliveryDate")
                if delivery_date:
                    time_created = order.get("time_stamp")  # ISO 8601 format
                    if today > (
                        datetime.datetime.strptime(
                            time_created, "%Y-%m-%dT%H:%M:%S.%f"
                        ).date()
                        + datetime.timedelta(days=5)
                    ):
                        self.move_order_delayed(order)
                        order["orderStatus"] = "Delayed"

    def move_order_delayed(self, order):
        # TODO
        # 1. UPS API call and get new delivery date
        self.change_order_status(
            order_id=order["orderId"],
            order_num=order["order_num"],
            status="Delayed",
            order_type=order["order_type"],
        )

    def get_shipped_fulfilled_delivered_returned(self):
        if not self.shipped_fulfilled_delivered_returned:
            self.shipped_fulfilled_delivered_returned = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Fulfilled")
                | Attr("orderStatus").eq("Shipped")
                | Attr("orderStatus").eq("Delayed")
                | Attr("orderStatus").eq("ReturnRequested")
                | Attr("orderStatus").eq("ReturnFulfilled")
                | Attr("orderStatus").eq("ReturnDelayed")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.shipped_fulfilled_delivered_returned.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
        return self.shipped_fulfilled_delivered_returned

    def get_shipped(self):
        if not self.shipped_orders:
            self.shipped_orders = []
            scan_params = {
                "FilterExpression": (
                    Attr("orderStatus").eq("Fulfilled")
                    | Attr("orderStatus").eq("Shipped")
                )
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.shipped_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.shipped_orders:
                self.shipped_orders = sorted(
                    self.shipped_orders, key=lambda x: x["order_num"]
                )
        return self.shipped_orders

    def get_delivered(self, reverse=False, page=float("inf"), limit=0):
        if not self.delivered_orders:
            self.delivered_orders = []
            scan_params = {
                "FilterExpression": (Attr("orderStatus").eq("Delivered"))
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.delivered_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break

            if self.delivered_orders:
                if reverse:
                    self.delivered_orders = sorted(
                        self.delivered_orders,
                        key=lambda x: x["order_num"],
                        reverse=True,
                    )
                else:
                    self.delivered_orders = sorted(
                        self.delivered_orders, key=lambda x: x["order_num"]
                    )
        start_index = (page - 1) * limit
        end_index = start_index + limit
        return (
            self.delivered_orders[start_index:end_index]
            if limit
            else self.delivered_orders
        )

    def get_delayed(self):
        if not self.delayed_orders:
            self.delayed_orders = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Delayed")
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.delayed_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.delayed_orders:
                self.delayed_orders = sorted(
                    self.delayed_orders, key=lambda x: x["order_num"]
                )
        return self.delayed_orders

    def get_returned(self):
        if not self.returned_orders:
            self.returned_orders = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Returned")
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.returned_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.returned_orders:
                self.returned_orders = sorted(
                    self.returned_orders, key=lambda x: x["order_num"]
                )
        return self.returned_orders

    def get_failed(self):
        if not self.failed_orders:
            self.failed_orders = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Failed")
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.failed_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.failed_orders:
                self.failed_orders = sorted(
                    self.failed_orders, key=lambda x: x["order_num"]
                )
        return self.failed_orders

    def get_trash(self):
        if not self.trash_orders:
            self.trash_orders = []
            scan_params = {
                "FilterExpression": Attr("orderStatus").eq("Trash")
                & Attr("order_type").ne("return")
            }
            last_evaluated_key = None
            while True:
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                response = self.table.scan(**scan_params)
                items = response.get("Items", [])
                if items:
                    self.trash_orders.extend(items)
                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key:
                    break
            if self.trash_orders:
                self.trash_orders = sorted(
                    self.trash_orders, key=lambda x: x["order_num"]
                )
        return self.trash_orders

    def count_unshipped(self):
        query_params = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Unshipped"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def count_shipped(self):
        # Query for Fulfilled orders
        query_params_fulfilled = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Fulfilled"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response_fulfilled = self.table.query(**query_params_fulfilled)
        count_fulfilled = response_fulfilled.get("Count", 0)

        # Query for Shipped orders
        query_params_shipped = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Shipped"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response_shipped = self.table.query(**query_params_shipped)
        count_shipped = response_shipped.get("Count", 0)

        # Sum the counts
        total_count = count_fulfilled + count_shipped
        return total_count

    def count_delivered(self):
        query_params = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Delivered"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def count_returned(self):
        query_params = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Returned"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def count_returns(self):
        query_params = {
            "IndexName": "OrderTypeIndex",
            "KeyConditionExpression": Key("order_type").eq("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def count_failed(self):
        query_params = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Failed"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def count_delayed(self):
        query_params = {
            "IndexName": "OrderStatusIndex",
            "KeyConditionExpression": Key("orderStatus").eq("Delayed"),
            "FilterExpression": Attr("order_type").ne("return"),
            "Select": "COUNT",
        }
        response = self.table.query(**query_params)
        return response.get("Count", 0)

    def add_request_order_for_parts(self, order):
        order_id = order.get("orderId", self.generate_order_id())
        try:
            if self.get_order(order_id):
                return self.order_exists_context()
            order["orderId"] = order_id
            order["orderStatus"] = "Unshipped"
            order["order_type"] = "parts"
            current_datetime = datetime.datetime.now()
            order["time_stamp"] = current_datetime.isoformat()
            order["status_updated"] = current_datetime.isoformat()
            order["shippingVendor"] = "UPS"
            shipping = self.shipping_order(order)
            delivery_date = ""

            print("*" * 50, order)
            print("*" * 10, "shipping", shipping)
            print("*" * 10, "delivery_date", delivery_date)

            if shipping:
                print("ShipmentResponse", shipping["ShipmentResponse"])
                result = shipping["ShipmentResponse"]["ShipmentResults"]
                print("result", result)
                order["deliveryDate"] = delivery_date
                print("delivery_date", delivery_date)
                if type(result["PackageResults"]) == list:
                    package_results = result["PackageResults"][0]
                else:
                    package_results = result["PackageResults"]
                order["trackingId"] = package_results["TrackingNumber"]
                print("trackingId", order["trackingId"])
                label_img_content = package_results["ShippingLabel"]["GraphicImage"]
                # print(order["trackingId"], order["trackingId"], label_img_content)
                label_url = self.save_shipping_label_to_s3(
                    order_id=order_id, img_content=label_img_content
                )
                print("label_url", label_url)
                order["label_image"] = label_url
                try:
                    order["shipping_cost"] = result["ShipmentCharges"]["TotalCharges"][
                        "MonetaryValue"
                    ]
                except:
                    order["shipping_cost"] = "N/A"
                order["vehicles"] = {}

            else:
                order["orderStatus"] = "Failed"
            print("INSERT ORDER PARTS", order)
            order["order_num"] = self.max_order_num() + 1
            response = self.table.put_item(Item=order)
            # Handle the response
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                print("A new Order added successfully to:", self.table_name)
            else:
                print("Failed to add item to:", self.table_name)
        except Exception as e:
            print("Error while adding order to db", e)
            return self.order_invalid_context()

        return self.order_requested_context(order_id=order_id)

    def add_request_order_for_parts2(self, order):
        inventories = Inventories()
        order_id = order.get("orderId")
        vehicles = order.get("vehicles", [])
        address = order.get("address", {})
        if (
            not vehicles
            or not order_id
            or not address
            or not address.get("addressLine1")
            or not address.get("zipCode")
            or not address.get("state")
            or not address.get("business")
            or not address.get("name")
        ):
            return self.order_invalid_context()
        parts = []
        for vehicle in vehicles:
            parts_list = vehicle.get("sku", "").split(",")
            if not parts_list:
                print("No parts found in the order for vehicle", vehicle)
                return self.order_invalid_context()
            for part_item in parts_list:
                the_part = inventories.get_inventory(
                    inventory_id=part_item,
                    fields=["Id", "model", "name", "type", "SKU"],
                )
                if not the_part:
                    print(
                        "No parts found in our inventory that matches to SKU=",
                        part_item,
                    )
                    return self.order_invalid_context()
                parts.append(the_part)
        order_parts = {
            "orderId": order_id,
            "address": {
                "addressLine1": address.get("addressLine1"),
                "addressLine2": address.get("addressLine2", ""),
                "city": address.get("city", ""),
                "zipCode": str(address.get("zipCode")),
                "state": address.get("state"),
                "business": address.get("business"),
                "name": address.get("name"),
            },
            "parts": parts,
        }
        print("parts order request", order_parts)
        return self.add_request_order_for_parts(order=order_parts)

    def add_request_order(self, order):
        order_id = order.get("orderId")
        is_order_for_parts = "sku" in order.get("vehicles", [])[0]
        if is_order_for_parts:
            return self.add_request_order_for_parts2(order)
        if order_id:
            try:
                order = self.vindecode(order)
                if self.get_order(order_id):
                    return self.order_exists_context()
                order["order_type"] = "camera"
                order["orderStatus"] = "Unshipped"
                current_datetime = datetime.datetime.now()
                order["time_stamp"] = current_datetime.isoformat()
                order["status_updated"] = current_datetime.isoformat()
                order["shippingVendor"] = "UPS"
                shipping = self.shipping_order(order)
                delivery_date = ""
                print("*" * 50, order)
                print("*" * 10, "shipping", order["order_type"], shipping)
                print("*" * 10, "delivery_date", delivery_date)

                if shipping:
                    print("ShipmentResponse", shipping["ShipmentResponse"])
                    result = shipping["ShipmentResponse"]["ShipmentResults"]
                    print("result", result)
                    order["deliveryDate"] = delivery_date
                    print("delivery_date", delivery_date)
                    if type(result["PackageResults"]) == list:
                        package_results = result["PackageResults"][0]
                    else:
                        package_results = result["PackageResults"]
                    order["trackingId"] = package_results["TrackingNumber"]
                    print("trackingId", order["trackingId"])
                    label_img_content = package_results["ShippingLabel"]["GraphicImage"]
                    # print(order["trackingId"], order["trackingId"], label_img_content)
                    label_url = self.save_shipping_label_to_s3(
                        order_id=order_id, img_content=label_img_content
                    )
                    print("label_url", label_url)
                    order["label_image"] = label_url
                    try:
                        order["shipping_cost"] = result["ShipmentCharges"][
                            "TotalCharges"
                        ]["MonetaryValue"]
                    except:
                        order["shipping_cost"] = "N/A"
                else:
                    order["orderStatus"] = "Failed"
                order["order_num"] = self.max_order_num() + 1
                response = self.table.put_item(Item=order)
                # Handle the response
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    print("A new Order added successfully to:", self.table_name)
                else:
                    print("Failed to add item to:", self.table_name)
            except Exception as e:
                print("Error while adding order to db", e)
                return self.order_invalid_context()
            return self.order_requested_context(order_id=order_id)

        return self.order_invalid_context()

    def add_request_return_order(self, order):
        order_id = order.get("orderId")
        if not order_id:
            return self.order_invalid_context()
        try:
            order = self.vindecode(order)
            if self.get_order(order_id):
                return self.order_exists_context()
            order["order_type"] = "return"
            order["orderStatus"] = "ReturnRequested"
            current_datetime = datetime.datetime.now()
            order["time_stamp"] = current_datetime.isoformat()
            order["status_updated"] = current_datetime.isoformat()
            order["shippingVendor"] = "UPS"

            shipping = self.shipping_order(order)
            delivery_date = ""
            print("*" * 50, order)
            print("*" * 10, "shipping", order["order_type"], shipping)
            print("*" * 10, "delivery_date", delivery_date)

            if shipping:
                print("ShipmentResponse", shipping["ShipmentResponse"])
                result = shipping["ShipmentResponse"]["ShipmentResults"]
                print("result", result)
                order["deliveryDate"] = delivery_date
                print("delivery_date", delivery_date)
                if type(result["PackageResults"]) == list:
                    package_results = result["PackageResults"][0]
                else:
                    package_results = result["PackageResults"]
                order["trackingId"] = package_results["TrackingNumber"]
                print("trackingId", order["trackingId"])
                label_img_content = package_results["ShippingLabel"]["GraphicImage"]
                label_url = self.save_shipping_label_to_s3(
                    order_id=order_id, img_content=label_img_content
                )
                print("label_url", label_url)
                order["label_image"] = label_url
                # print(order["trackingId"], order["trackingId"], label_img_content)
                order["shipping_cost"] = "N/A"
            else:
                order["orderStatus"] = "Failed"
            order["order_num"] = self.max_order_num() + 1
            response = self.table.put_item(Item=order)
            # Handle the response
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                print("A new Order added successfully to:", self.table_name)
            else:
                print("Failed to add item to:", self.table_name)

            qr_code = None
        except Exception as e:
            print("Error while adding order to db", e)
            return self.order_invalid_context()

        return self.return_order_requested_context(order_id=order_id, qr_code=qr_code)

    def shipping_order(self, order, validate_address=True):
        self.ups_order = UPSApi(order)
        if order.get("order_type") == "return":
            validate_address = False
        if validate_address and not self.ups_order.validate_address():
            return False
        return self.ups_order.do_shipping()

    def get_delivery_date(self, order):
        return UPSApi(order).transit_times()

    def order_invalid_context(self):
        return {"orderStatus": "Failed"}

    def order_exists_context(self):
        return {"orderStatus": "Order Already Exists"}

    def order_requested_context(self, order_id):
        return {"orderId": order_id, "orderStatus": "Requested"}

    def return_order_requested_context(self, order_id, qr_code=None):
        return {
            "orderId": order_id,
            "orderStatus": "ReturnRequested",
            "qrCode": qr_code,
        }

    def get_order(self, order_id):
        try:
            response = self.table.query(
                KeyConditionExpression="orderId = :pk",
                ExpressionAttributeValues={":pk": order_id},
            )
            items = response.get("Items", [])
            return False if not items else items[0]
        except Exception as e:
            print("Error", e)
        return False

    def update_vehicles_data(self, order_id, order_num, vehicles):
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = "SET vehicles = :vehicles, status_updated = :dateTimeNow"
        current_datetime = datetime.datetime.now()
        expression_attribute_values = {
            ":vehicles": vehicles,
            ":dateTimeNow": current_datetime.isoformat(),
        }
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "vehicles successfully changed to", vehicles)
            result = True
        else:
            print("Order vehicles update failed")
        return result

    def update_vehicles_adapter(self, order_id, order_num, vehicles):
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = "SET vehicles = :vehicles, status_updated = :dateTimeNow"
        current_datetime = datetime.datetime.now()
        expression_attribute_values = {
            ":vehicles": vehicles,
            ":dateTimeNow": current_datetime.isoformat(),
        }
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "vehicles successfully changed to", vehicles)
            result = True
        else:
            print("Order vehicles update failed")
        return result

    def move_failed_to_unshipped(
        self, order: dict, order_address: dict, validate_address=True
    ):
        try:
            shipping = self.shipping_order(
                order=order, validate_address=validate_address
            )
            if shipping:
                result = shipping["ShipmentResponse"]["ShipmentResults"]
                if type(result["PackageResults"]) == list:
                    package_results = result["PackageResults"][0]
                else:
                    package_results = result["PackageResults"]
                current_datetime = datetime.datetime.now()
                tracking_id = package_results["TrackingNumber"]
                print("trackingId", tracking_id)
                label_img_content = package_results["ShippingLabel"]["GraphicImage"]
                # print(tracking_id, label_img_content)

                try:
                    shipping_cost = result["ShipmentCharges"]["TotalCharges"][
                        "MonetaryValue"
                    ]
                except:
                    shipping_cost = "N/A"

                label_url = self.save_shipping_label_to_s3(
                    order_id=order["orderId"], img_content=label_img_content
                )
                delivery_date = self.get_delivery_date(order=order)
                order_key = {
                    "orderId": order["orderId"],
                    "order_num": order["order_num"],
                }
                update_expression = "SET orderStatus = :orderStatus, address = :address, status_updated = :dateTimeNow, trackingId = :trackingId, label_image = :label_url, deliveryDate=:deliveryDate, shipping_cost=:shippingCost"
                expression_attribute_values = {
                    ":address": order_address,
                    ":dateTimeNow": current_datetime.isoformat(),
                    ":trackingId": tracking_id,
                    ":label_url": label_url,
                    ":deliveryDate": delivery_date,
                    ":shippingCost": shipping_cost,
                    ":orderStatus": "Unshipped",
                }
                response = self.table.update_item(
                    Key=order_key,
                    UpdateExpression=update_expression,
                    ExpressionAttributeValues=expression_attribute_values,
                )
                result = False
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    print(response)
                    print("Order", order["orderId"], " successfully changed to", order)
                    result = True
                else:
                    print("Order update failed")
        except Exception as e:
            print("Error while adding order to db", e)
            return False

    def update_comments(self, order_id: str, order_num: str, comments: str):
        print(
            "UPDATE COMMENTS order_id",
            order_id,
            "order_num",
            order_num,
            "comments",
            comments,
        )
        current_datetime = datetime.datetime.now()
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = (
            "SET comments = :orderComments, status_updated = :dateTimeNow"
        )
        expression_attribute_values = {
            ":orderComments": comments,
            ":dateTimeNow": current_datetime.isoformat(),
        }
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "Comments successfully changed to", comments)
            result = True
        else:
            print("Order status update failed")
        return result

    def change_order_status(
        self, order_id: str, order_num: str, status: str, order_type=None
    ):
        if order_type == "return":
            if status == "Shipped":
                status = "ReturnFulfilled"
            elif status == "Delivered":
                status = "ReturnReceived"
            elif status == "Failed":
                status = "ReturnFailed"
            elif status == "Delayed":
                status = "ReturnDelayed"

        print("order_id", order_id, "status", status)
        current_datetime = datetime.datetime.now()
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = (
            "SET orderStatus = :newOrderStatus, status_updated = :dateTimeNow"
        )
        expression_attribute_values = {
            ":newOrderStatus": status,
            ":dateTimeNow": current_datetime.isoformat(),
        }
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "status successfully changed to", status)
            result = True
        else:
            print("Order status update failed")
        return result

    def change_order_type(self, order_id: str, order_num: str, order_type: str):
        print("order_id", order_id, "order_type", order_type)
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = "SET order_type = :newOrderType"
        expression_attribute_values = {":newOrderType": order_type}
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "order_type successfully changed to", order_type)
            result = True
        else:
            print("Order order_type update failed")
        return result

    def change_order_address(self, order_id: str, order_num: str, address: dict):
        print("order_id", order_id, "address", address)
        current_datetime = datetime.datetime.now()
        order_key = {"orderId": order_id, "order_num": order_num}
        update_expression = "SET address = :address, status_updated = :dateTimeNow"
        expression_attribute_values = {
            ":address": address,
            ":dateTimeNow": current_datetime.isoformat(),
        }
        response = self.table.update_item(
            Key=order_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Order", order_id, "address successfully changed to", address)
            result = True
        else:
            print("Order address update failed")
        return result

    def get_order_vins(self):
        pass

    def vindecode(self, order):
        for vehicle in order["vehicles"]:
            if "vin" in vehicle:
                print("VINDECODING", vehicle)
                truck, adapter = Vindecoder(vin=vehicle["vin"]).get_adapter()
                print("truck", truck)
                print("adapter", adapter)
                custom_adapter = self.get_custom_adapter(truck)
                vehicle["adapter"] = custom_adapter or adapter
                vehicle["vindecoded_values"] = "{} {}, {}, {}".format(
                    truck["Year"], truck["Make"], truck["Engine"], truck["Model"]
                )
            else:
                print("Missing VIN", vehicle)
        return order

    def get_custom_adapter(self, vehicle):
        # get Spesific one
        mapping_id = vehicle["Year"] + vehicle["Make"] + vehicle["Engine"]
        custom_mapping = Mappings().get_mapping(mapping_id=mapping_id.upper())
        if not custom_mapping:
            # get Spesific one
            mapping_id = vehicle["Year"] + vehicle["Make"] + "ALL"
            custom_mapping = Mappings().get_mapping(mapping_id=mapping_id.upper())
        return (
            custom_mapping["Port"]
            if custom_mapping and "Port" in custom_mapping
            else ""
        )

    def get_orders_count(self):
        response = self.table.scan(Select="COUNT")

        # Get the count of items
        item_count = response["Count"]
        print(f"Number of items in '{self.table}': {item_count}")
        return item_count

    def fulfill_order(self, order_id: str, camera_ids: dict):
        order = self.get_order(order_id)
        if not order:
            return False
        adaptors, parts = [], []
        if "vehicles" in order:
            for vehicle in order.get("vehicles"):
                if "vin" in vehicle and vehicle["vin"] in camera_ids.keys():
                    vehicle["cameraId"], vehicle["cameraPassword"] = camera_ids[
                        vehicle["vin"]
                    ].split(",")
                    adaptors.append(vehicle["adapter"])
        if "parts" in order:
            for part in order.get("parts"):
                parts.append(part["name"])

        order["orderStatus"] = "Fulfilled"
        current_datetime = datetime.datetime.now()
        order["status_updated"] = current_datetime.isoformat()
        order["shipped_date"] = current_datetime.isoformat()
        order["deliveryDate"] = self.get_delivery_date(order=order)
        response = self.table.put_item(Item=order)
        label_image = order["label_image"]
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            inventories = Inventories()
            for adaptor in adaptors:
                inventories.reduce_inventory_quantity_by_name(
                    adaptor, 1, order_type=order["order_type"]
                )
                inventories.reduce_cam_quantity()

            for part in parts:
                inventories.reduce_inventory_quantity_by_name(
                    part, 1, order_type=order["order_type"]
                )

            return label_image
        else:
            return False

    def save_shipping_label_to_s3(self, order_id: str, img_content: str):
        decoded_data = base64.b64decode(img_content)
        object_name = "%s/%s.gif" % (os.environ["state"], order_id)
        print(order_id, decoded_data)
        return self.shipping_labels.upload_shipping_label_file(
            img_content=decoded_data, object_name=object_name
        )

    def load_shipping_label_from_s3(self, order_id: str):
        object_name = "%s/%s.gif" % (os.environ["state"], order_id)
        self.shipping_labels.load_shipping_label_object(object_key=object_name)

    def create_a_ups_insurance_quote(self, order_id: str):
        order = self.get_order(order_id)
        if (
            "vehicles" not in order
            or len(order["vehicles"]) <= 3
            or order.get("shipped_date") is None
        ):
            return None
        insurance_api = self.ups_capital_insurance_api[self.enviroment]
        # Read secrets from environment variables (loaded from Secrets Manager)
        # Dev/test use _DEV suffix, prod uses _PROD suffix
        env_suffix = "PROD" if self.enviroment == "prod" else "DEV"
        bearer = os.environ.get(f"UPSC_BEARER_{env_suffix}", "")
        client_id = os.environ.get(f"UPSC_CLIENT_ID_{env_suffix}", "")
        client_secret = os.environ.get(f"UPSC_CLIENT_SECRET_{env_suffix}", "")
        partner_id = os.environ.get(f"UPSC_PARTNER_ID_{env_suffix}", "")
        insurance_value = 100
        payload = json.dumps(
            {
                "status": "UNCONFIRMED",
                "partnerId": partner_id,
                "shipDate": order.get("shipped_date").split("T")[0],
                "bol": order["trackingId"],
                "insuredValue": str(insurance_value),
                "carrier": "UPS",
                "shipmentType": "3",
                "commodity": "400",
                "originAddress1": "2200 BIG TOWN BLVD. #180",
                "originAddress2": "",
                "originCity": "MESQUITE",
                "originState": "TX",
                "originPostalCode": "75149",
                "originCountry": "US",
                "consigneeName": order["address"]["name"],
                "destinationAddress1": order["address"]["addressLine1"],
                "destinationAddress2": order["address"].get("addressLine2", None),
                "destinationCity": order["address"]["city"],
                "destinationState": order["address"]["state"],
                "destinationPostalCode": str(order["address"]["zipCode"]),
                "destinationCountry": "US",
                "serviceLevel": None,
                "packageQuantity": len(order["vehicles"]),
                "referenceFields": "",
            }
        )
        print("INSURANCE PAYLOAD", payload)
        headers = {
            "bearer": bearer,
            "X-IBM-Client-Id": client_id,
            "X-IBM-Client-Secret": client_secret,
            "Content-Type": "application/json",
        }
        response = requests.request(
            "POST",
            insurance_api["quote_endpoint"],
            headers=headers,
            data=payload,
        )
        print("INSURANCE QUOTE API CALL RESPONSE", response.text)
        return response.json()
