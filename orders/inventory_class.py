import os
import boto3
from datetime import datetime
from audit_log import AuditLog


class Inventories:
    inventories = {}
    max_id = 0
    parts = []
    adapters = []

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = os.environ.get("INVENTORIES_TABLE")
        self.table = self.dynamodb.Table(self.table_name)
        self.list_inventories()
        self.audit_logs = AuditLog()

    def list_inventories(self):
        if not self.inventories:
            response = self.table.scan()
            items = response.get("Items", [])
            if items:
                items = sorted(items, key=lambda x: x["type"], reverse=True)
            self.inventories = items

        return self.inventories

    # def sort_inventories(self):
    #     for inventory in self.list_inventories():
    #         if inventory['type'] not in self.inventories:
    #             self.inventories[inventory['type']] = []
    #         self.inventories[inventory['type']].append(inventory)

    def get_parts(self):
        if self.parts:
            return self.parts
        for inventory in self.inventories:
            if inventory["type"] != "Camera":
                self.parts.append(inventory)
        return self.parts

    def get_adapters(self):
        if self.adapters:
            return self.adapters
        for inventory in self.inventories:
            if inventory["type"] == "Cable":
                self.adapters.append(inventory)
        return self.adapters

    def get_adapter_sku(self, adapter_name):
        for adapter in self.get_adapters():
            if adapter["name"] == adapter_name:
                return adapter["model"]
        return "NoSKUFound"

    def get_part(self, part_id, fields=[]):
        for part in self.get_parts():
            if part["Id"] == part_id:
                if fields:
                    filtered_fields = {key: part[key] for key in fields if key in part}
                    return filtered_fields
                return part
        return {}

    def get_max_inventory_id(self):
        for inventory in self.inventories:
            id_num = int(inventory["Id"])
            if id_num > self.max_id:
                self.max_id = id_num

    def add_inventory(self, inventory):
        inventory_id = str(self.get_max_inventory_id() + 1)
        if inventory_id:
            try:
                if self.get_inventory(inventory_id):
                    return self.inventory_exists_context()
                inventory["Id"] = inventory_id
                inventory["Year"] = inventory.get("name")
                inventory["Make"] = inventory.get("type")
                inventory["Engine"] = inventory.get("quantity")
                print("*" * 50, inventory)
                response = self.table.put_item(Item=inventory)
                # Handle the response
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    print("A new Inventory added successfully to:", self.table_name)
                    log = {}
                    log["ActionType"] = "Add Inventory"
                    log["ActionName"] = "Inventory added by " + os.getenv("USERNAME")
                    log["ActionBy"] = os.getenv("USERNAME")
                    now = datetime.now()
                    log["ActionDateTime"] = now.strftime("%m/%d/%Y %H:%M:%S")
                    log["ActionContent"] = "; ".join(
                        [str(v) for v in inventory.values()]
                    )
                    self.audit_logs.add_log(log=log)
                else:
                    print("Failed to add item to:", self.table_name)
            except Exception as e:
                print("Error", e)
                return self.inventory_invalid_context()

            return self.inventory_requested_context(inventory_id=inventory_id)

        return self.inventory_invalid_context()

    def inventory_invalid_context(self):
        return {"Inventory": "Failed"}

    def inventory_exists_context(self):
        return {"Inventory": "Inventory Already Exists"}

    def inventory_requested_context(self, inventory_id):
        return {"Id": inventory_id, "Status": "Added"}

    def get_inventory(self, inventory_id, fields=[]):
        try:
            response = self.table.get_item(Key={"Id": inventory_id})
            inventory = response.get("Item")
            if fields:
                filtered_fields = {
                    key: inventory[key] for key in fields if key in inventory
                }
                return filtered_fields

            return inventory
        except Exception as e:
            print("Error", e)
        return False

    def reduce_inventory_quantity_by_name(
        self, inventory_name, quantity, order_type=""
    ):
        for inventory in self.inventories:
            if inventory_name == inventory["name"]:
                if order_type == "camera":
                    if inventory_name == "J1939 Power Cord 9 Pin":
                        # JPC01: Camera, JPC01 (9 pin)
                        # Leave as is
                        quantity = 0
                    elif inventory_name == "OBD Power Cord w/type C Connector 12v":
                        # OPC01:
                        # Camera, OPC01, OBD-Split
                        # Add JPC01 into Inventory
                        # Remove OPC01 from Inventory
                        # Remove OBD-Split from Inventory
                        self.add_inventory_quantity(
                            "99-A0000114-01", 1
                        )  # Add JPC01 into Inventory
                        self.reduce_inventory_quantity_by_name(
                            "OBD2 Male Splitter to 2 Female Extension Cable", 1
                        )  # Remove OBDSPLIT from Inventory
                    if inventory_name == "OBD -> J1708 Adapter 6 Pin":
                        # ADP01:
                        # Camera, ADP01 (6 pin), OPC01
                        # Add JPC01 into Inventory
                        # Remove ADP01 from Inventory
                        # Remove OPC01 from Inventory
                        self.add_inventory_quantity(
                            "99-A0000114-01", 1
                        )  # Add JPC01 into Inventory
                        self.reduce_inventory_quantity(
                            "99-A0000045-01", 1
                        )  # Remove OPC01 from Inventory
                self.reduce_inventory_quantity(inventory["Id"], quantity)
                break

    def reduce_cam_quantity(self):
        self.reduce_inventory_quantity("99-A0000108-01", "1")

    def add_inventory_quantity_by_name(self, inventory_name, quantity):
        for inventory in self.inventories:
            if inventory_name == inventory["name"]:
                self.add_inventory_quantity(inventory["Id"], quantity)
                break

    def reduce_inventory_quantity(self, inventory_id, quantity):
        inventory = self.get_inventory(inventory_id)
        inventory["quantity"] = int(inventory["quantity"]) - int(quantity)
        self.change_inventory(inventory_id, inventory=inventory, action="Reduce")

    def add_inventory_quantity(self, inventory_id, quantity):
        inventory = self.get_inventory(inventory_id)
        inventory["quantity"] = int(inventory["quantity"]) + int(quantity)
        self.change_inventory(inventory_id, inventory=inventory, action="Add")

    def change_inventory(self, inventory_id: str, inventory, action=""):
        print("inventory_id", inventory_id, "inventory", inventory)
        inventory_key = {"Id": inventory_id}
        response = self.table.update_item(
            Key=inventory_key,
            UpdateExpression="SET #name = :name, #type = :type, #quantity = :quantity",
            ExpressionAttributeValues={
                ":name": inventory["name"],
                ":type": inventory["type"],
                ":quantity": inventory["quantity"],
            },
            ExpressionAttributeNames={
                "#name": "name",
                "#type": "type",
                "#quantity": "quantity",
            },
        )
        result = False
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            print(response)
            print("Inventory", inventory_id, "status successfully Updated")
            result = True
            log = {}
            log["ActionType"] = action + " Inventory"
            log["ActionName"] = "%s %s %s" % (
                inventory["name"],
                inventory["type"],
                action,
            )
            log["ActionBy"] = os.getenv("USERNAME")
            now = datetime.now()
            log["ActionDateTime"] = now.strftime("%m/%d/%Y %H:%M:%S")
            log["ActionContent"] = "; ".join([str(v) for v in inventory.values()])
            print("ACTION HERE", log["ActionContent"])
            log_result = self.audit_logs.add_log(log=log)
            print(log_result)
        else:
            print("Inventory update failed")
        return result
