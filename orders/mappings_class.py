import os
import boto3
import json
import datetime
from boto3.dynamodb.conditions import Attr


class Mappings():
    mappings = {}

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.environ.get('MAPPINGS_TABLE')
        self.table = self.dynamodb.Table(self.table_name)
        self.sort_mappings()

    def list_mappings(self):
        response = self.table.scan()
        return response.get('Items', [])

    def sort_mappings(self):
        pass

    def add_mapping(self, mapping):
        mapping_id = mapping.get("Year") + mapping.get("Make") + mapping.get("Engine")
        mapping_id = mapping_id.upper()
        if mapping_id:
            try:
                if self.get_mapping(mapping_id):
                    return self.mapping_exists_context()
                mapping['Id'] = mapping_id
                mapping['Year'] = mapping.get("Year")
                mapping['Make'] = mapping.get("Make")
                mapping['Engine'] = mapping.get("Engine")
                mapping['Port'] = mapping.get("Port")
                mapping['Note'] = mapping.get("Note")
                print('*'*50, mapping)
                response = self.table.put_item(Item=mapping)
                # Handle the response
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    print('A new Mapping added successfully to:', self.table_name)
                else:
                    print('Failed to add item to:', self.table_name)
            except Exception as e:
                print('Error', e)
                return self.mapping_invalid_context()

            return self.mapping_requested_context(mapping_id=mapping_id)

        return self.mapping_invalid_context()

    def mapping_invalid_context(self):
        return {
            "Mapping": "Failed"
        }

    def mapping_exists_context(self):
        return {
            "Mapping": "Mapping Already Exists"
        }

    def mapping_requested_context(self, mapping_id):
        return {
            "Id": mapping_id,
            "Status": "Added"
        }

    def get_mapping(self, mapping_id):
        try:
            response = self.table.get_item(Key={'Id': mapping_id})
            return response.get('Item')
        except Exception as e:
            print('Error', e)
        return False

    def change_mapping(self, mapping_id: str, vehicle):
        print('mapping_id', mapping_id, 'vehicle', vehicle)
        mapping_key={'Id': mapping_id}
        update_expression = 'SET Make = :Make, Engine = :Engine, Year = :Year, Port = :Port, Note = :Note'
        expression_attribute_values = {
            ':Make': vehicle['Make'],
            ':Engine': vehicle['Engine'],
            ':Year': vehicle['Year'],
            ':Port': vehicle['Port'],
            ':Note': vehicle['Note']
        }
        response = self.table.update_item(
            Key=mapping_key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
        result = False
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(response)
            print("Mapping", mapping_id,"status successfully Updated")
            result = True
        else:
            print("Mapping update failed")
        return result
