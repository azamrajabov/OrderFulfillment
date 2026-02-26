import os
import boto3


class ShippingLabels:
    bucket_name: str
    s3_resource: None

    def __init__(self) -> None:
        self.bucket_name = os.environ.get('S3_SHIPPING_LABELS')
        self.s3_resource = boto3.resource('s3')

    def upload_shipping_label_file(self, img_content: str, object_name: str):
        try:
            self.s3_resource.Bucket(self.bucket_name).put_object(Key=object_name, Body=img_content)
            print(f"Content uploaded to S3: s3://{self.bucket_name}/{object_name}")
            return ("https://%s.s3.amazonaws.com/%s") % (self.bucket_name, object_name)
        except Exception as error:
            print('An Error occurred while uploading shipping label {} to {}'.format(object_name, self.bucket_name), error)
        return ''

    def load_shipping_label_object(self, object_key: str):
        print('bucket_name', self.bucket_name)
        print('object_key', object_key)
        print('basename object_key', os.path.basename(object_key))
        try:
            obj = self.s3_resource.Object(self.bucket_name, object_key)
            return obj.get()['Body'].read()
        except Exception as e:
            print(f"Error: {str(e)}")

        return False
