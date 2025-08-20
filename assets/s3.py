import datetime as dt
import uuid
from urllib.parse import urljoin

import boto3
from botocore.client import Config
from django.conf import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=(settings.AWS_S3_REGION_NAME or None),
        config=Config(signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4")),
        use_ssl=bool(getattr(settings, "AWS_S3_USE_SSL", False)),
        verify=bool(getattr(settings, "AWS_S3_USE_SSL", False)),
    )


def build_storage_key(owner_id: str, asset_type: str, ext: str) -> str:
    today = dt.datetime.utcnow().strftime("%Y/%m/%d")
    # rule: assets/{type}/{yyyy/mm/dd}/{owner}/{uuid}.{ext}
    return f"assets/{asset_type}/{today}/{owner_id}/{uuid.uuid4()}.{ext}"


def presign_put_url(key: str, content_type: str, expires: int | None = None) -> str:
    client = _client()
    params = {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key, "ContentType": content_type}
    return client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires or 600, HttpMethod="PUT")


def head_object(key: str) -> dict:
    client = _client()
    return client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)


def public_url(key: str) -> str:
    # path-style: http://endpoint:9000/<bucket>/<key>
    base = settings.AWS_S3_ENDPOINT_URL.rstrip("/") + "/"
    path = f"{settings.AWS_STORAGE_BUCKET_NAME}/{key.lstrip('/')}"
    return urljoin(base, path)
