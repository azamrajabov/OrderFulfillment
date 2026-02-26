import os
import json
import time
import datetime
import requests
from orders_class import Orders
from jinja2 import Environment, FileSystemLoader
from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from inventory_class import Inventories


def render_template(template_name, context):
    # Set up Jinja2 environment with the appropriate template folder
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template")
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["order_date_formatter"] = order_date_formatter
    # Load the template and render it with the provided context
    template = env.get_template(template_name)
    return template.render(context)


def order_date_formatter(datestr):
    return datetime.datetime.strptime(datestr, "%Y-%m-%d").strftime("%m-%d-%Y")


def generate_logout_url():
    app_url = os.getenv("app_url")
    cognito_url = os.getenv("COGNITO_URL")
    cognito_client_id = os.getenv("COGNITO_APP_CLIENT_ID")
    logout_pattern = os.getenv("COGNITO_LOGOUT_URL")
    logout_call_back = app_url + "callback?logout=1"
    return logout_pattern % (cognito_url, cognito_client_id, logout_call_back)


def generate_login_url():
    app_url = os.getenv("app_url")
    cognito_url = os.getenv("COGNITO_URL")
    cognito_client_id = os.getenv("COGNITO_APP_CLIENT_ID")
    login_pattern = os.getenv("COGNITO_LOGIN_URL")
    login_call_back = app_url + "callback"
    return login_pattern % (cognito_url, cognito_client_id, login_call_back)


def show_content(context, status_code=200, template="", content_type="text/html"):
    if template and content_type == "text/html":
        context["env_name"] = os.getenv("state")
        context["app_url"] = os.getenv("app_url")
        context["logout_url"] = generate_logout_url()
        context["login_url"] = generate_login_url()
        inventories = Inventories().list_inventories()
        context["inventories"] = inventories
        context["username"] = os.getenv("USERNAME")
        context["inventories_quantity"] = sum(
            [inventory["quantity"] for inventory in inventories]
        )
        # if not ups_tokens_status():
        #     context['ups_tokens_status'] = 'red'
        #     context['ups_accees_token'], context['ups_refresh_token'] = '',''
        # else:
        #     ups_tokens = get_ups_tokens()
        #     if isinstance(ups_tokens, list) and len(ups_tokens) == 2:
        #         context['ups_tokens_status'] = 'blue'
        #         context['ups_accees_token'], context['ups_refresh_token'] = ups_tokens
        #     else:
        #         context['ups_tokens_status'] = 'red'
        #         context['ups_accees_token'], context['ups_refresh_token'] = '',''

        orders = Orders()
        context["count_unshipped"] = orders.count_unshipped()
        context["count_shipped"] = orders.count_shipped()
        context["count_delivered"] = orders.count_delivered()
        context["count_returned"] = orders.count_returned()
        context["count_returns"] = orders.count_returns()
        context["count_failed"] = orders.count_failed()
        context["count_delayed"] = orders.count_delayed()
        context["app_environment"] = os.environ["APP_ENVIRONMENT"]
        response = render_template(template, context)
    else:
        if content_type == "application/json":
            response = json.dumps(context)
        else:
            response = context
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": content_type, "Access-Control-Allow-Origin": "*"},
        "body": response,
        "isBase64Encoded": False,
    }


def ups_tokens_status():
    ups_tokens = get_ups_tokens()
    if not ups_tokens:
        return False
    try:
        access_token, refresh_token = ups_tokens
        os.putenv("UPS_ACCESS_TOKEN", access_token)
        os.putenv("UPS_REFRESH_TOKEN", refresh_token)
        return True
    except Exception as err:
        print(err)
    return False


def get_ups_tokens():
    print("reading tokens from ups_tokens.txt file")
    try:
        file_name = os.getenv("APP_TEMP_FOLDER") + "ups_tokens.txt"
        file = open(file_name, mode="r")
        content = file.read()
        file.close()
        return content.split(";")
    except Exception as err:
        print(err)
    return False


def call_back(event):
    http_method = event["httpMethod"]
    is_logout = False
    if http_method == "GET" and event.get("queryStringParameters"):
        is_logout = event["queryStringParameters"].get("logout")
    print(event["queryStringParameters"])
    print("is_logout", is_logout)
    if is_logout:
        return show_content(
            context="<html><head></head><body><script>document.cookie = `access_token=0; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/`;document.cookie = `id_token=0; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/`;</script>You logged out!, bye-bye!</body></html>",
            status_code=200,
            content_type="text/html",
        )
    elif http_method == "GET":
        print("Callback has been called")
        return show_content(
            context={"redirect_page": "orders"}, template="callback.html"
        )


def get_cookie_token(multi_headers):
    cookie = multi_headers.get("Cookie", [])
    if not cookie:
        return False
    cookie_vals = cookie[0].split("; ")
    print(cookie, cookie_vals)
    id_token = ""
    access_token = ""
    for cookie_key_val in cookie_vals:
        if "access_token=" in cookie_key_val:
            access_token = cookie_key_val.split("access_token=")[1]
        if "id_token=" in cookie_key_val:
            id_token = cookie_key_val.split("id_token=")[1]

    # print('access_token', access_token)
    # print("id_token", id_token)
    if len(access_token) < 10 or not id_token:
        return False

    # # Define the Cognito user pool ID (replace with your Cognito user pool ID)
    # user_pool_id = os.getenv('COGNITO_USER_POOL_ID')

    # # Define the AWS region where your Cognito user pool is hosted
    # aws_region = 'us-east-1'

    # # Define the Cognito issuer URL
    # cognito_issuer = f'https://cognito-idp.{aws_region}.amazonaws.com/{user_pool_id}'

    # try:
    #     # Validate the ID token
    #     decoded_token = jwt.decode(
    #         access_token,
    #         options={
    #             'verify_exp': True,  # Check token expiration
    #             'verify_aud': True,  # Check audience (client ID)
    #             'verify_iss': True,  # Check issuer
    #             'require_at_hash': True  # Check Access Token hash
    #         },
    #         audience=os.getenv('COGNITO_APP_CLIENT_ID'),
    #         issuer=cognito_issuer
    #     )

    #     # If the token is valid, decoded_token will contain the token claims
    #     print("Token is valid")
    #     print("Decoded Claims:", decoded_token)
    #     # os.putenv('USER', decoded_token['username'])
    # except jwt.ExpiredSignatureError:
    #     print("Token has expired")
    #     return False
    # except jwt.InvalidTokenError:
    #     print("Token is invalid")
    #     return False
    # except Exception as e:
    #     print("An error occurred:", str(e))
    #     return False

    return access_token


def get_ups_redirect_url():
    redirect_uri = quote(os.getenv("app_url") + "upsredirect", safe="")
    url = (
        "https://wwwcie.ups.com/security/v1/oauth/validate-client"
        "?client_id={client_id}&redirect_uri={redirect_uri}".format(
            client_id=os.getenv("UPS_CLIENT_ID"), redirect_uri=redirect_uri
        )
    )
    response = requests.request("GET", url)
    response_json = response.json()
    ups_redirect_url = response_json.get("LassoRedirectURL")
    print("url", url)
    print("get_ups_redirect_url", response_json)
    if not ups_redirect_url:
        # print(response_json)
        return False
    ups_redirect_url += "?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=read&type=ups_com_api".format(
        client_id=os.getenv("UPS_CLIENT_ID"), redirect_uri=redirect_uri
    )
    print("ups_redirect_url", ups_redirect_url)
    return ups_redirect_url


def get_ups_access_token(code):
    redirect_uri = quote(os.getenv("app_url") + "upsredirect", safe="")
    url = "https://wwwcie.ups.com/security/v1/oauth/token"
    payload = "grant_type=authorization_code&code={}&redirect_uri={}".format(
        code, redirect_uri
    )
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.request(
        "POST",
        url,
        headers=headers,
        data=payload,
        auth=HTTPBasicAuth(os.getenv("UPS_CLIENT_ID"), os.getenv("UPS_CLIENT_SECRET")),
    )
    # print(url, payload, headers)
    response_json = response.json()
    # print(response.text)
    os.putenv("UPS_ACCESS_TOKEN", response_json.get("access_token"))
    os.putenv("UPS_REFRESH_TOKEN", response_json.get("refresh_token"))
    return os.getenv("UPS_ACCESS_TOKEN")
