from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError



@dataclass
class AwsSelfTestResult:
    ok: bool
    error: Optional[str] = None          # machine-friendly
    detail: Optional[str] = None         # human-friendly (log/UI)
    data: Optional[Dict[str, Any]] = None

def _get_bucket_region(s3, bucket: str) -> Optional[str]:
    # Returns region like "eu-west-1" or None if unknown
    try:
        r = s3.get_bucket_location(Bucket=bucket)
        loc = r.get("LocationConstraint")
        # AWS returns None or '' for us-east-1
        return loc or "us-east-1"
    except Exception:
        return None


def _client_error_code(err: ClientError) -> str:
    try:
        return err.response.get("Error", {}).get("Code", "ClientError")
    except Exception:
        return "ClientError"


def run_aws_selftest(
    *,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    region_name: str,
    bucket: Optional[str],
    prefix: str,
    collection_id: str,
) -> AwsSelfTestResult:
    """Sync AWS connectivity self-test (safe + minimal)."""

    # 1) STS: validate credentials
    try:
        sts = boto3.client(
            "sts",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        ident = sts.get_caller_identity()
    except ClientError as e:
        code = _client_error_code(e)
        if code in ("InvalidClientTokenId", "SignatureDoesNotMatch"):
            return AwsSelfTestResult(False, "invalid_auth", f"STS auth failed: {code}")
        return AwsSelfTestResult(False, "cannot_connect", f"STS error: {code}")

    # 2) Rekognition: collection exists
    try:
        rek = boto3.client(
            "rekognition",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        rek.describe_collection(CollectionId=collection_id)

    except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError):
        return AwsSelfTestResult(False, "cannot_connect", "Unable to reach AWS Rekognition endpoint. Check network/region.")

    except ClientError as e:
        code = _client_error_code(e)

        # Wrong region is not always detectable here, but we can improve messaging:
        # If the user also provided an S3 bucket, we can infer region mismatch later.
        if code == "ResourceNotFoundException":
            # Could be wrong region OR wrong collection id. We'll decide later if bucket is present.
            # For now mark as "collection_or_region" and refine after S3 checks.
            rekognition_missing = True
        else:
            rekognition_missing = False

        if code in ("AccessDeniedException", "AccessDenied"):
            return AwsSelfTestResult(False, "access_denied", "Access denied on Rekognition. Check IAM policy.")
        if not rekognition_missing:
            return AwsSelfTestResult(False, "cannot_connect", f"Rekognition error: {code}")
        
    # track whether Rekognition collection looked missing (might be wrong region)
    rekognition_missing = locals().get("rekognition_missing", False)



    # 3) S3: bucket exists + write/delete test (only if bucket provided)
    if bucket:
        try:
            s3 = boto3.client(
                "s3",
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

            # HEAD bucket (permission + existence)
            s3.head_bucket(Bucket=bucket)

            # If collection looked missing, try infer region mismatch using bucket region
            if rekognition_missing:
                b_region = _get_bucket_region(s3, bucket)
                if b_region and b_region != region_name:
                    return AwsSelfTestResult(
                        False,
                        "wrong_region",
                        f"Region mismatch. Stack/bucket is in {b_region}, but you configured {region_name}.",
                    )
                # Bucket region matches configured region -> collection is truly missing
                return AwsSelfTestResult(False, "collection_not_found", f"Collection not found: {collection_id}")

            # Put/Delete test object under prefix
            p = (prefix or "").strip("/")
            test_key = f"{p}/_afr_test.txt" if p else "_afr_test.txt"
            s3.put_object(Bucket=bucket, Key=test_key, Body=b"ok")
            s3.delete_object(Bucket=bucket, Key=test_key)

        except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError):
            return AwsSelfTestResult(False, "cannot_connect", "Unable to reach AWS S3 endpoint. Check network/region.")

        except ClientError as e:
            code = _client_error_code(e)

            status = None
            try:
                status = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode"))
            except Exception:
                status = None

            if code in ("NoSuchBucket", "NotFound", "404") or status == 404:
                return AwsSelfTestResult(False, "bucket_not_found", f"S3 bucket not found: {bucket}")


            if code in ("AccessDenied", "AccessDeniedException", "403"):
                return AwsSelfTestResult(False, "access_denied", "Access denied on S3. Check IAM policy.")

            # Some region mismatches surface as PermanentRedirect / 301
            if code in ("PermanentRedirect", "301"):
                # Try to tell the user the real bucket region
                b_region = _get_bucket_region(s3, bucket)
                if b_region and b_region != region_name:
                    return AwsSelfTestResult(False, "wrong_region", f"Bucket is in {b_region}, not {region_name}.")
                return AwsSelfTestResult(False, "wrong_region", "Bucket exists but region mismatch. Check Region.")

            return AwsSelfTestResult(False, "cannot_connect", f"S3 error: {code}")
    if (not bucket) and rekognition_missing:
        # With no bucket we cannot infer region; treat as collection not found
        return AwsSelfTestResult(False, "collection_not_found", f"Collection not found: {collection_id}")

