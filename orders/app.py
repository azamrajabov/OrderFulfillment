import os
import jwt
import json
import boto3
import datetime
from orders_class import Orders
from mappings_class import Mappings
from inventory_class import Inventories
from audit_log import AuditLog
from functions import (
    render_template,
    show_content,
    generate_login_url,
    call_back,
    get_cookie_token,
    get_ups_access_token,
    get_ups_redirect_url,
)
from ups_api import UPSApi
from urllib.parse import parse_qs


def lambda_handler(event, context):
    request_context = event.get("requestContext", {})
    console_grant = event.get("console_grant") == "thisIsFromAWSConsoleRunITWOLogin"
    stage_name = request_context.get("stage")
    stage_name = "Prod" if "prod" == stage_name.lower() else "Stage"
    os.environ["state"] = stage_name
    domain_name = request_context.get("domainName")
    os.environ["app_url"] = "https://%s/%s/" % (domain_name, stage_name)
    print("*" * 50, stage_name)
    print(event)

    http_method = event["httpMethod"]
    path = event["path"]
    orders_obj = Orders()
    mapping_obj = Mappings()
    inventories_obj = Inventories()
    audit_logs_obj = AuditLog()

    print("* Getting secrets...")
    secret_var_names = (
        "UPS_CLIENT_ID",
        "UPS_CLIENT_SECRET",
        "UPS_ACCOUNT_NUMBER",
    )

    print("* Getting tokens from secret manager...")
    client = boto3.client("secretsmanager", region_name="us-east-1")
    response = client.get_secret_value(SecretId="prod/order-fulfillment/secrets")
    secrets = json.loads(response["SecretString"])
    for env_name in secret_var_names:
        # print(env_name, secrets.get(env_name))
        os.environ[env_name] = secrets.get(env_name)

    if http_method == "POST" and "/request_order" == path:
        ###
        #   ADD REQUEST ORDER
        ###
        try:
            context = orders_obj.add_request_order(json.loads(event["body"]))
        except Exception as e:
            print("Error", e)
            context = orders_obj.order_invalid_context()

        return show_content(context=context, content_type="application/json")

    if http_method == "POST" and "/request_return_order" == path:
        ###
        #   ADD REQUEST RETURN ORDER
        ###
        try:
            context = orders_obj.add_request_return_order(json.loads(event["body"]))
        except Exception as e:
            print("Error", e)
            context = orders_obj.order_invalid_context()

        return show_content(context=context, content_type="application/json")
    elif "check_shipped_orders" in path and console_grant:
        ###
        #   CHECK SHIPPED ORDERS
        ###
        orders_obj.check_shipped_orders()
        # print(orders)
        orders_page = os.environ["app_url"] + "orders"
        return show_content(
            context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
            % orders_page,
            status_code=200,
            content_type="text/html",
        )
    elif "order_status" in path:
        context = {}
        if http_method == "GET" and event["queryStringParameters"]:
            order_id = event["queryStringParameters"].get("order_id")
            if order_id:
                order = orders_obj.get_order(order_id)
            if order:
                order_status = order["orderStatus"]
                order_ups_status = UPSApi(order=order).get_order_status()
                if order_ups_status == "Delivered":
                    orders_obj.change_order_status(
                        order_id=order_id,
                        order_num=order["order_num"],
                        status=order_ups_status,
                    )
                    order_status = "Delivered"
                context = {"orderId": order_id, "orderStatus": order_status}
        return show_content(
            context=context, status_code=200, content_type="application/json"
        )
    elif "my_ip" in path:
        import requests

        url = "https://lumtest.com/myip.json"
        response = requests.request("GET", url, headers={}, data={})
        print("This is response from lumtest", response.text)
        return show_content(context=response.json(), content_type="application/json")

    access_token = ""
    # check access_token
    if "callback" not in path:
        multi_headers = event.get("multiValueHeaders", {})
        access_token = get_cookie_token(multi_headers)
    else:
        return call_back(event)

    # print("access_token", access_token)
    if not access_token:
        login_url = generate_login_url()
        return show_content(
            context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
            % login_url,
            status_code=200,
            content_type="text/html",
        )
    user_info = jwt.decode(
        access_token, algorithms=["RS256"], options={"verify_signature": False}
    )
    print(user_info, "username:", user_info["username"])
    os.environ["USERNAME"] = user_info["username"]

    if "/orders" == path or "/orders/" == path:
        ###
        #   LIST UNSHIPPED ORDERS
        ###
        orders = orders_obj.get_unshipped()
        print("Unshipped Orders Count", len(orders))
        return show_content(context={"orders": orders}, template="orders.html")
    elif "upsredirect" in path and http_method == "GET":
        if event.get("queryStringParameters"):
            qp = event.get("queryStringParameters", {})
            code = qp.get("code")
            scope = qp.get("scope")
            print("code, scope", code, scope)
            ups_access_token = get_ups_access_token(code)
            # print("ups_access_token", ups_access_token)
            print("writing tokens to ups_tokens.txt file")
            file_name = os.environ["APP_TEMP_FOLDER"] + "ups_tokens.txt"
            if os.path.exists(file_name):
                os.remove(file_name)
            else:
                print(file_name, "The file does not exist")
            file = open(file_name, "w")
            file.write(
                os.environ["UPS_ACCESS_TOKEN"] + ";" + os.environ["UPS_REFRESH_TOKEN"]
            )
            file.close()
            orders_page = os.environ["app_url"] + "orders"
            return show_content(
                context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
                % orders_page,
                status_code=200,
                content_type="text/html",
            )
        else:
            redirect_url = get_ups_redirect_url()
            if redirect_url:
                return show_content(
                    context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
                    % redirect_url
                )
            else:
                return show_content(
                    context={"Error": "While getting UPS LassoRedirectURL"},
                    content_type="application/json",
                )
    elif "/shipped" == path or "/shipped/" == path:
        ###
        #   LIST SHIPPED ORDERS
        ###
        orders = orders_obj.get_shipped()
        print("Shipped Orders Count", len(orders))
        return show_content(context={"orders": orders}, template="shipped.html")
    elif "/delivered" == path or "/delivered/" == path:
        ###
        #   LIST DELIVERED ORDERS
        ###
        get_queries = event.get("queryStringParameters", {}) or {}
        limit = int(get_queries.get("limit") or 100)
        current_page = int(get_queries.get("page") or 1)
        total = orders_obj.count_delivered()
        total_pages = total // limit + 1 if total % limit else 0
        print("Total Delivered Orders Count", total)
        orders = orders_obj.get_delivered(
            reverse=get_queries.get("reverse") or True,
            page=current_page,
            limit=limit,
        )
        print("Delivered Orders Count", len(orders))
        return show_content(
            context={
                "orders": orders,
                "total_pages": total_pages,
                "current_page": current_page,
                "limit": limit,
            },
            template="delivered.html",
        )
    elif "/delayed" == path or "/delayed/" == path:
        ###
        #   LIST Delayed ORDERS
        ###
        orders = orders_obj.get_delayed()
        print("Delayed Orders Count", len(orders))
        return show_content(context={"orders": orders}, template="delayed.html")
    elif "/returned" == path or "/returned/" == path:
        ###
        #   LIST returned ORDERS
        ###
        orders = orders_obj.get_returned()
        print("Returned Orders Count", len(orders))
        return show_content(context={"orders": orders}, template="returned.html")
    elif "/failed" == path or "/failed/" == path:
        ###
        #   LIST failed ORDERS
        ###
        orders = orders_obj.get_failed()
        print("Failed Orders Count", len(orders))
        return show_content(context={"orders": orders}, template="failed.html")
    elif "/order" == path:
        if http_method == "GET" and event["queryStringParameters"].get("export"):
            csv_data = orders_obj.export_orders(
                status=event["queryStringParameters"].get("export")
            )
            return show_content(
                context=csv_data, status_code=200, content_type="text/html"
            )
        elif http_method == "GET" and event["queryStringParameters"].get("order_id"):
            order = orders_obj.get_order(event["queryStringParameters"]["order_id"])
            if order and order["orderStatus"] == "Unshipped":
                return show_content(
                    context={"order": order}, template="order_details.html"
                )
            # return show_content(context=order['orderStatus'] + ' Order can`t be updated')
        elif http_method == "POST":
            body_dict = parse_qs(event["body"])
            order_id = body_dict["orderId"][0]
            order = orders_obj.get_order(order_id)
            if order["orderStatus"] != "Unshipped":
                return show_content(
                    context=order["orderStatus"] + " Order can`t be updated"
                )
            vehicles_adapter = {}
            for key, val in body_dict.items():
                vin = key.replace("vehicle[", "").replace("]", "")
                vehicles_adapter[vin] = val[0]
            print("vehicles_adapter", vehicles_adapter)
            vehicles = order["vehicles"]
            for vehicle in vehicles:
                if vehicle["vin"] in vehicles_adapter.keys():
                    vehicle["adapter"] = vehicles_adapter[vehicle["vin"]]
            print("updated vehicles", vehicles)
            orders_obj.update_vehicles_adapter(
                order_id=order_id, order_num=order["order_num"], vehicles=vehicles
            )

            return show_content(
                context="<html><head></head><body><script>window.location.href = '/{}/order?order_id={}';</script></body></html>".format(
                    os.environ["state"], order_id
                )
            )
    elif "/scan" == path:
        if http_method == "GET" and event["queryStringParameters"].get("order_id"):
            order = orders_obj.get_order(event["queryStringParameters"]["order_id"])
            if order:
                return show_content(context={"order": order}, template="scan.html")
    elif "/print-label" == path:
        if http_method == "GET" and event["queryStringParameters"].get("order_id"):
            order = orders_obj.get_order(event["queryStringParameters"]["order_id"])
            datetime_object = datetime.datetime.strptime(
                order["time_stamp"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )
            activate_by_date = datetime_object + datetime.timedelta(days=10)
            order["activate_by_date"] = activate_by_date.strftime("%m-%d-%Y")
            if order:
                return show_content(
                    context={"shipping_label": order["label_image"], "order": order},
                    template="print_label.html",
                )
    elif "/fulfill" == path and http_method == "POST" and "body" in event:
        body_dict = parse_qs(event["body"])
        # Now you can access the data within body_dict
        if "order_id" not in body_dict:
            return False
        order_id = body_dict.pop("order_id")[0]
        order = orders_obj.get_order(order_id)
        camera_ids = {}
        for vin, cameraId in body_dict.items():
            vin = vin.replace("cameraId[", "").replace("]", "")
            camera_ids[vin] = cameraId[0]
        print("order_id", order_id)
        print("camera_id", camera_ids)
        shipping_label = Orders().fulfill_order(
            order_id=order_id, camera_ids=camera_ids
        )
        if shipping_label:
            order = orders_obj.get_order(order_id)
            datetime_object = datetime.datetime.strptime(
                order["time_stamp"].split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )
            activate_by_date = datetime_object + datetime.timedelta(days=10)
            order["activate_by_date"] = activate_by_date.strftime("%m-%d-%Y")

            # TESTING UPS INSURANCE QUOTE
            if os.environ["APP_ENVIRONMENT"] == "test":
                orders_obj.create_a_ups_insurance_quote(order_id=order_id)

            return show_content(
                context={"shipping_label": shipping_label, "order": order},
                template="print_label.html",
            )
        return show_content(
            context="Error! can not fulfill the order, pls contact to developer"
        )
    elif "/mapping" == path:
        if http_method == "GET":
            if event["queryStringParameters"]:
                mapping_id = (
                    event["queryStringParameters"]["mapping_id"]
                    if "mapping_id" in event["queryStringParameters"]
                    else "0000"
                )
                mapping = mapping_obj.get_mapping(mapping_id)
                if mapping:
                    return show_content(
                        context={"mapping": mapping}, template="mapping_update.html"
                    )
            mappings = mapping_obj.list_mappings()
            return show_content(
                context={"mappings": mappings}, template="mappings.html"
            )
        elif http_method == "POST":
            body_dict = parse_qs(event["body"])
            vehicle = {}
            for key, val in body_dict.items():
                key = key.replace("vehicle[", "").replace("]", "")
                vehicle[key] = val[0]
            if "Note" in vehicle and (not vehicle["Note"] or vehicle["Note"] == "None"):
                vehicle["Note"] = ""
            result = mapping_obj.add_mapping(mapping=vehicle)
            mappings = mapping_obj.list_mappings()
            return show_content(
                context={"mappings": mappings}, template="mappings.html"
            )
    elif "inventories" in path:
        if http_method == "POST":
            body_dict = parse_qs(event["body"])
            print(body_dict)
            inventory_id = body_dict.get("inventory_id")[0]
            action = body_dict.get("action")[0]
            quantity = body_dict.get("quantity")[0]
            if inventory_id and quantity and action in ("Reduce", "Add"):
                if action == "Reduce":
                    inventories_obj.reduce_inventory_quantity(inventory_id, quantity)
                else:
                    inventories_obj.add_inventory_quantity(inventory_id, quantity)
        inventories = inventories_obj.list_inventories()
        audit_logs = audit_logs_obj.list_logs()
        return show_content(
            context={"inventories": inventories, "logs": audit_logs},
            template="inventories.html",
        )
    elif "/command" == path or "/command/" == path:
        context = {}
        if http_method == "GET" and event["queryStringParameters"]:
            command = event["queryStringParameters"].get("command")
            order_id = event["queryStringParameters"].get("order_id")
            if order_id:
                order = orders_obj.get_order(order_id)
            if command == "get_address" and order:
                return show_content(
                    context=order["address"],
                    status_code=200,
                    content_type="application/json",
                )
            if command == "get_status" and order:
                return show_content(
                    context=order["orderStatus"],
                    status_code=200,
                    content_type="text/html",
                )
        elif http_method == "POST":
            print(event)
            command = event["queryStringParameters"].get("command")
            print("command", command)
            body_dict = parse_qs(event["body"])
            order_id = body_dict.get("order_id")
            if order_id:
                order_id = order_id[0]
            print("body_dict", body_dict)
            if order_id:
                order = orders_obj.get_order(order_id)
            # if not order:
            #     return show_content(context={'result': 'Failed to change order address!'}, template='command.html')
            if command == "request_an_order":
                order_id = body_dict.get("orderId")[0]
                vins = body_dict.get("vin[]")
                vehicleIds = body_dict.get("vehicleId[]")
                vehicles = []
                for vin in vins:
                    vehicles.append(
                        {"vin": vin, "vehicleId": vehicleIds[vins.index(vin)]}
                    )

                request_order = {
                    "orderId": order_id,
                    "order_type": "camera",
                    "address": {
                        "addressLine1": body_dict.get("addressLine1", [""])[0],
                        "addressLine2": body_dict.get("addressLine2", [""])[0],
                        "city": body_dict.get("city", [""])[0],
                        "zipCode": str(body_dict.get("zipCode", [""])[0]),
                        "state": body_dict.get("state", [""])[0],
                        "business": body_dict.get("business", [""])[0],
                        "name": body_dict.get("name", [""])[0],
                    },
                    "vehicles": vehicles,
                }
                print("command request an order -> request_order")
                print(request_order)
                print(body_dict)
                if request_order:
                    try:
                        context = orders_obj.add_request_order(request_order)
                    except Exception as e:
                        print("Error", e)
                        context = orders_obj.order_invalid_context()
                    return show_content(
                        context=context, content_type="application/json"
                    )
            elif command == "change_order_address" and order:
                command_json = body_dict.get("command_json")
                if command_json:
                    order_address = command_json[0]
                    try:
                        orders_obj.change_order_address(
                            order_id=order_id,
                            order_num=order["order_num"],
                            address=json.loads(order_address),
                        )
                        context = {"result": "The Order address has been changed!"}
                    except Exception as e:
                        print("Error", e)
                        context = {"result": "Failed to change order address!"}
            elif command == "change_order_status" and order:
                order_status = body_dict.get("order_status")
                if order_status:
                    order_status = order_status[0]
                    try:
                        orders_obj.change_order_status(
                            order_id=order_id,
                            order_num=order["order_num"],
                            status=order_status,
                        )
                        context = {"result": "The Order status has been changed!"}
                    except Exception as e:
                        print("Error", e)
                        context = {"result": "Failed to change order status!"}
        return show_content(context=context, template="command.html")
    elif "reprocess" in path:
        context = {}
        if http_method == "GET" and event["queryStringParameters"]:
            order_id = event["queryStringParameters"].get("order_id")
            if order_id:
                order = orders_obj.get_order(order_id)
            if order["orderStatus"] == "Failed":
                return show_content(context={"order": order}, template="reprocess.html")
        elif http_method == "POST":
            # print(event)
            body_dict = parse_qs(event["body"])
            order_id = body_dict.get("order_id")
            if order_id:
                order_id = order_id[0]
            print("body_dict", body_dict)
            if order_id:
                order = orders_obj.get_order(order_id)
                validate_address = body_dict.get("validate_address")
                if (
                    order["orderStatus"] == "Failed"
                    and body_dict.get("addressLine1")[0]
                ):
                    order_address = {
                        "addressLine1": body_dict.get("addressLine1", [""])[0],
                        "addressLine2": body_dict.get("addressLine2", [""])[0],
                        "city": body_dict.get("city", [""])[0],
                        "zipCode": str(body_dict.get("zipCode", [""])[0]),
                        "state": body_dict.get("state", [""])[0],
                        "business": order["address"]["business"],
                        "name": order["address"]["name"],
                    }
                    order["address"] = order_address
                    orders_obj.move_failed_to_unshipped(
                        order=order,
                        order_address=order_address,
                        validate_address=validate_address,
                    )
        orders_page = os.environ["app_url"] + "orders"
        return show_content(
            context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
            % orders_page,
            status_code=200,
            content_type="text/html",
        )
    elif "shipping_parts" in path:
        # print(event)
        if http_method == "GET":
            parts = inventories_obj.get_parts()
            return show_content(
                context={"parts": parts}, template="shipping_parts.html"
            )
        elif http_method == "POST":
            body_dict = parse_qs(event["body"])
            parts_list = body_dict.get("parts[]")
            parts = []
            for part_item in parts_list:
                parts.append(
                    inventories_obj.get_part(
                        part_id=part_item, fields=["Id", "model", "name", "type", "SKU"]
                    )
                )
            order_parts = {
                "address": {
                    "addressLine1": body_dict.get("addressLine1", [""])[0],
                    "addressLine2": body_dict.get("addressLine2", [""])[0],
                    "city": body_dict.get("city", [""])[0],
                    "zipCode": str(body_dict.get("zipCode", [""])[0]),
                    "state": body_dict.get("state", [""])[0],
                    "business": body_dict.get("business", [""])[0],
                    "name": body_dict.get("name", [""])[0],
                },
                "parts": parts,
            }
            print(order_parts)
            print(body_dict)

            orders_obj.add_request_order_for_parts(order=order_parts)

            orders_page = os.environ["app_url"] + "orders"
            return show_content(
                context="<html><head></head><body><script>window.location.href = '%s';</script></body></html>"
                % orders_page,
                status_code=200,
                content_type="text/html",
            )
    elif "download_report" in path:
        # print(event)
        if http_method == "GET":
            parts = inventories_obj.get_parts()
            return show_content(context={}, template="download_report.html")
        elif http_method == "POST":
            body_dict = parse_qs(event["body"])
            statuses = body_dict.get("status[]")
            csv_data = ""
            for status in statuses:
                if csv_data:
                    data = orders_obj.export_orders(status=status, no_headers=True)
                else:
                    data = orders_obj.export_orders(status=status)
                if data:
                    csv_data += "\n" + data
            return {
                "statusCode": "200",
                "headers": {
                    "Content-Type": "text/csv",
                    "Access-Control-Allow-Origin": "*",
                    "Content-Disposition": 'attachment; filename="orders_report.csv"',
                },
                "body": csv_data,
                "isBase64Encoded": False,
            }
    elif "file_manager" in path:
        if http_method == "GET":
            return show_content(
                context={"files": ["file1.pdf", "file2.pdf"]},
                template="file_manager.html",
            )
        elif http_method == "POST":
            pass
    elif "comments" in path:
        if http_method == "GET" and event["queryStringParameters"]:
            order_id = event["queryStringParameters"].get("order_id")
            if order_id:
                order = orders_obj.get_order(order_id)
            if not order:
                raise Exception("Order not found")
            order_comments = order.get("comments", "")
            return show_content(
                context={"comments": order_comments}, content_type="application/json"
            )
        elif http_method == "POST":
            print(event)
            body_dict = parse_qs(event["body"])
            print("body_dict", body_dict)
            order_id = body_dict.get("order_id")
            print("order_id1", order_id)
            if order_id:
                order_id = order_id[0]
            print("order_id", order_id)
            order_comments = body_dict.get("comments")
            if order_comments:
                order_comments = order_comments[0]
            print("order_comments", order_comments)
            if order_id:
                order = orders_obj.get_order(order_id)
                if not order:
                    raise Exception("Order not found")
                print("order", order)
                result = orders_obj.update_comments(
                    order_id=order_id,
                    order_num=order["order_num"],
                    comments=order_comments,
                )
            return show_content(
                context={"success": result}, content_type="application/json"
            )
    elif "/returns" in path:
        ###
        #   LIST RETURN BOX ORDERS
        ###
        if http_method == "GET":
            get_queries = event.get("queryStringParameters", {}) or {}
            limit = int(get_queries.get("limit") or 100)
            current_page = int(get_queries.get("page") or 1)
            total = orders_obj.count_returns()
            total_pages = total // limit + 1 if total % limit else 0
            print("Total Return Orders Count", total)
            orders = orders_obj.get_returns(
                reverse=get_queries.get("reverse") or True,
                page=current_page,
                limit=limit,
            )
            print("Return Orders Count", len(orders))
            return show_content(
                context={
                    "orders": orders,
                    "total_pages": total_pages,
                    "current_page": current_page,
                    "limit": limit,
                },
                template="returns.html",
            )
    elif "/missingdata" in path:
        ###
        #   FIX MISSING DATA, VEHICLE MODEL AND ORDER_TYPE
        ###
        from vindecoder import Vindecoder

        if http_method == "GET":
            missing_order_type = []
            missing_order_model = []
            orders = orders_obj.get_all_orders()
            print("All Orders Count", len(orders))
            for order in orders:
                order_type = order.get("order_type")
                vehicles = order.get("vehicles", [])
                parts = order.get("parts", [])
                order_status = order.get("orderStatus")
                if not order_type:
                    order_type = "camera" if vehicles else "parts"
                    result = orders_obj.change_order_type(
                        order_id=order["orderId"],
                        order_num=order["order_num"],
                        order_type=order_type,
                    )
                    missing_order_type.append(
                        order["orderId"]
                        + " should be =  "
                        + order_type
                        + " Changed: "
                        + str(result)
                    )

                if vehicles:
                    missing_vehicle_model = []
                    for vehicle in vehicles:
                        vv = vehicle.get("vindecoded_values", "")
                        if vv.count(",") == 1:
                            model = ""
                            vindecoded_data = Vindecoder(
                                vin=vehicle["vin"]
                            ).get_vindecoded_fields()
                            if vindecoded_data:
                                model = vindecoded_data.get("Model", "N/A")
                            missing_vehicle_model.append(
                                vehicle["vin"] + " should be = " + vv + ", " + model
                            )
                            print(
                                "Missing Model",
                                order["orderId"],
                                vehicle["vin"],
                                vehicle["vindecoded_values"],
                                model,
                            )
                            vehicle["vindecoded_values"] = vv + ", " + model
                        if (vv.count(",") == 0 or vv.count(",") != 1) and vv.count(
                            ","
                        ) != 2:
                            missing_vehicle_model.append(
                                vehicle["vin"] + ":" + vv + " <<<<< SOMERHING WRONG"
                            )
                    if missing_vehicle_model:
                        orders_obj.update_vehicles_data(
                            order_id=order["orderId"],
                            order_num=order["order_num"],
                            vehicles=vehicles,
                        )
                        missing_order_model.append(
                            order["orderId"] + "->" + str(missing_vehicle_model)
                        )
        content = {
            "missing_order_type": missing_order_type,
            "missing_order_model": missing_order_model,
        }
        return show_content(
            context=content, status_code=200, content_type="application/json"
        )

    return show_content(
        context="Page not found", status_code=404, content_type="text/html"
    )
