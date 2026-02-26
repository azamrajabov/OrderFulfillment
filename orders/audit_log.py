import os
import boto3
import json
import time
import datetime


class AuditLog():
    logs = {}
    max_id = 0

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.environ.get('AUDIT_TABLE')
        self.table = self.dynamodb.Table(self.table_name)
        self.list_logs()

    def list_logs(self, force_load=0):
        if not self.logs or force_load:
            self.logs = []
            response = self.table.scan()
            logs = response.get('Items', [])
            if logs:
                self.logs = sorted(logs, key=lambda x: int(x['Id']), reverse=True)
                self.logs = self.logs[:500]
        return self.logs

    def get_max_id(self):
        self.list_logs(force_load=1)
        for log in self.logs:
            id_num = int(log['Id'])
            if id_num > self.max_id:
                self.max_id = id_num
        return self.max_id

    def add_log(self, log):
        log_id = str(self.get_max_id() + 1)
        print('New Log ID', log_id, log)
        if log_id:
            try:
                if self.get_log(log_id):
                    return self.log_exists_context()
                log['Id'] = log_id
                log['ActionTime'] = int(time.time())
                log['ActionType'] = log.get("ActionType")
                log['ActionName'] = log.get("ActionName")
                log['ActionBy'] = log.get("ActionBy")
                log['ActionDateTime'] = log.get("ActionDateTime")
                log['ActionContent'] = log.get("ActionContent")

                print('*'*50, log)
                response = self.table.put_item(Item=log)
                # Handle the response
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    print('A new Log added successfully to:', self.table_name)
                else:
                    print('Failed to add item to:', self.table_name)
            except Exception as e:
                print('Error', e)
                return self.log_invalid_context()

            return self.log_requested_context(log_id=log_id)

        return self.log_invalid_context()

    def log_invalid_context(self):
        return {
            "Log": "Failed"
        }

    def log_exists_context(self):
        return {
            "AuditLog": "Log Already Exists"
        }

    def log_requested_context(self, log_id):
        return {
            "Id": log_id,
            "Status": "Added"
        }

    def get_log(self, log_id):
        try:
            response = self.table.query(
                KeyConditionExpression='Id = :pk',
                ExpressionAttributeValues={':pk': log_id}
            )
            items = response.get('Items', [])
            return False if not items else items[0]
        except Exception as e:
            print('Error', e)
        return False
