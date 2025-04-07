import os
import mimetypes
import pulumi
import pulumi_aws as aws
import pulumi_synced_folder as synced_folder

# Import the program's configuration settings.
config = pulumi.Config()
path = config.get("path") or "./www"
index_document = config.get("indexDocument") or "index.html"
error_document = config.get("errorDocument") or "error.html"
domain = config.require("domain");
subdomain = config.require("subdomain");
domain_name = f"{subdomain}.{domain}";

# Create an S3 bucket and configure it as a website.
bucket = aws.s3.BucketV2("bucket")
bucket_website = aws.s3.BucketWebsiteConfigurationV2(
    "bucket-website",
    bucket=bucket.bucket,
    index_document={"suffix": index_document},
    error_document={"key": error_document},
)

# Set ownership controls for the new bucket
ownership_controls = aws.s3.BucketOwnershipControls(
    "ownership-controls",
    bucket=bucket.bucket,
    rule={
        "object_ownership": "BucketOwnerEnforced",
    },
)

# Configure public ACL block on the new bucket
public_access_block = aws.s3.BucketPublicAccessBlock(
    "public-access-block",
    bucket=bucket.bucket,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

# Create a CloudFront Origin Access Identity (OAI)
oai = aws.cloudfront.OriginAccessIdentity("oai")


# Upload website files to S3 bucket.
for root, _, files in os.walk(path):
    for file in files:
        file_path = os.path.join(root, file)
        key = os.path.relpath(file_path, path)
        content_type, _ = mimetypes.guess_type(file_path)

        aws.s3.BucketObject(
            key,
            bucket=bucket.bucket,
            source=pulumi.FileAsset(file_path),
            content_type=content_type or "application/octet-stream",
            opts=pulumi.ResourceOptions(depends_on=[ownership_controls, public_access_block]),
        )

# Generate an S3 Bucket Policy to allow CloudFront OAI access
bucket_policy = aws.s3.BucketPolicy(
    "bucketPolicy",
    bucket=bucket.id,
    policy=pulumi.Output.all(bucket.arn, oai.iam_arn).apply(lambda args: f"""{{
        "Version": "2012-10-17",
        "Statement": [
            {{
                "Effect": "Allow",
                "Principal": {{"AWS": "{args[1]}"}},
                "Action": "s3:GetObject",
                "Resource": "{args[0]}/*"
            }}
        ]
    }}""")
)

# Look up your existing Route 53 hosted zone.
zone = aws.route53.get_zone_output(name=domain)

# Provision a new ACM certificate.
certificate = aws.acm.Certificate(
    "certificate",
    domain_name=domain_name,
    validation_method="DNS",
    opts=pulumi.ResourceOptions(
        # ACM certificates must be created in the us-east-1 region.
        provider=aws.Provider("us-east-provider", region="us-east-1"),
    ),
);

# Validate the ACM certificate with DNS.
options = certificate.domain_validation_options.apply(lambda options: options[0])
certificate_validation = aws.route53.Record(
    "certificate-validation",
    name=options.resource_record_name,
    type=options.resource_record_type,
    records=[options.resource_record_value],
    zone_id=zone.zone_id,
    ttl=60,
);

# Create a CloudFront CDN to distribute and cache the website.
cdn = aws.cloudfront.Distribution(
    "cdn",
    enabled=True,
    default_root_object="index.html",
    origins=[
        {
            "origin_id": bucket.arn,
            "domain_name": bucket.bucket_regional_domain_name,
            "s3_origin_config": {
                "origin_access_identity": oai.cloudfront_access_identity_path,
            },
        }
    ],
    default_cache_behavior={
        "target_origin_id": bucket.arn,
        "viewer_protocol_policy": "redirect-to-https",
        "allowed_methods": [
            "GET",
            "HEAD",
            # "OPTIONS",
        ],
        "cached_methods": [
            "GET",
            "HEAD",
            # "OPTIONS",
        ],
        "default_ttl": 600,
        "max_ttl": 600,
        "min_ttl": 600,
        "forwarded_values": {
            "query_string": True,
            "cookies": {
                "forward": "all",
            },
        },
    },
    price_class="PriceClass_100",
    custom_error_responses=[
        {
            "error_code": 403,
            "response_code": 404,
            "response_page_path": f"/{error_document}",
        }
    ],
    restrictions={
        "geo_restriction": {
            "restriction_type": "none",
        },
    },
    aliases=[
        domain_name,
    ],
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=False,
        acm_certificate_arn=certificate.arn,
        ssl_support_method="sni-only",
    ),
)

# Create a Route53 alias A record to point to the CDN.
my_site = aws.route53.Record(domain_name,
    zone_id=zone.zone_id,
    name=subdomain,
    type="A",
    aliases=[
        aws.route53.RecordAliasArgs(
            name=cdn.domain_name,
            zone_id=cdn.hosted_zone_id,
            evaluate_target_health=True,
        )
    ],
    opts=pulumi.ResourceOptions(
        depends_on=certificate,
    ),
)

# Export the bucket website URL, CloudFront URL and the custom domain URL.
pulumi.export("bucket_url", pulumi.Output.concat("http://", bucket.bucket_regional_domain_name))
pulumi.export("cdnURL", pulumi.Output.concat("https://", cdn.domain_name))
pulumi.export("domainURL", f"https://{domain_name}")


# --------------------------------------------------------------------------#
# --------------------------------------------------------------------------#
# import os
# # import mimetypes
# import pulumi
# import pulumi_aws as aws
# import pulumi_synced_folder as synced_folder

# # Import the program's configuration settings.
# config = pulumi.Config()
# path = config.get("path") or "./www"
# index_document = config.get("indexDocument") or "index.html"
# error_document = config.get("errorDocument") or "error.html"


# # Create an S3 bucket and configure it as a website.
# bucket = aws.s3.BucketV2(
#     "bucket",
#     # website={             # deprecated
#     #     "index_document": index_document,
#     #     "error_document": error_document,
#     # },
# )
# bucket_website = aws.s3.BucketWebsiteConfigurationV2(
#     "bucket-website",
#     bucket=bucket.bucket,
#     index_document={"suffix": index_document},
#     error_document={"key": error_document},
# )

# # Set ownership controls for the new bucket
# ownership_controls = aws.s3.BucketOwnershipControls(
#     "ownership-controls",
#     bucket=bucket.bucket,
#     rule={
#         "object_ownership": "BucketOwnerEnforced",
#     },
# )

# # Configure public ACL block on the new bucket
# public_access_block = aws.s3.BucketPublicAccessBlock(
#     "public-access-block",
#     bucket=bucket.bucket,
#     block_public_acls=True,
#     block_public_policy=True,
#     ignore_public_acls=True,
#     restrict_public_buckets=True,
# )


# # Upload website files to S3 bucket.
# for root, _, files in os.walk(path):
#     for file in files:
#         file_path = os.path.join(root, file)
#         key = os.path.relpath(file_path, path)
#         content_type, _ = mimetypes.guess_type(file_path)
#         print(f"Uploading: {file_path} as {key}")

#         aws.s3.BucketObject(
#             key,
#             bucket=bucket.bucket,
#             source=pulumi.FileAsset(file_path),
#             content_type=content_type or "application/octet-stream",
#             opts=pulumi.ResourceOptions(depends_on=[ownership_controls, public_access_block]),
#         )

# # # Use a synced folder to manage the files of the website.
# # bucket_folder = synced_folder.S3BucketFolder(
# #     "bucket-folder",
# #     acl="public-read",
# #     bucket_name=bucket.bucket,
# #     path=path,
# #     opts=pulumi.ResourceOptions(depends_on=[ownership_controls, public_access_block]),
# # )

# # Create a CloudFront Origin Access Identity (OAI)
# oai = aws.cloudfront.OriginAccessIdentity("oai")

# # Generate an S3 Bucket Policy to allow CloudFront OAI access
# bucket_policy = aws.s3.BucketPolicy(
#     "bucketPolicy",
#     bucket=bucket.id,
#     policy=pulumi.Output.all(bucket.arn, oai.iam_arn).apply(lambda args: f"""{{
#         "Version": "2012-10-17",
#         "Statement": [
#             {{
#                 "Effect": "Allow",
#                 "Principal": {{"AWS": "{args[1]}"}},
#                 "Action": "s3:GetObject",
#                 "Resource": "{args[0]}/*"
#             }}
#         ]
#     }}""")
# )


# # Create a CloudFront CDN to distribute and cache the website.
# cdn = aws.cloudfront.Distribution(
#     "cdn",
#     enabled=True,
#     default_root_object="index.html",
#     origins=[
#         {
#             "origin_id": bucket.arn,
#             "domain_name": bucket.bucket_regional_domain_name,
#             "s3_origin_config": {
#                 "origin_access_identity": oai.cloudfront_access_identity_path,
#             },
#         }
#     ],
#     default_cache_behavior={
#         "target_origin_id": bucket.arn,
#         "viewer_protocol_policy": "redirect-to-https",
#         "allowed_methods": [
#             "GET",
#             "HEAD",
#             # "OPTIONS",
#         ],
#         "cached_methods": [
#             "GET",
#             "HEAD",
#             # "OPTIONS",
#         ],
#         "default_ttl": 600,
#         "max_ttl": 600,
#         "min_ttl": 600,
#         "forwarded_values": {
#             "query_string": True,
#             "cookies": {
#                 "forward": "all",
#             },
#         },
#     },
#     price_class="PriceClass_100",
#     custom_error_responses=[
#         {
#             "error_code": 403,
#             "response_code": 404,
#             "response_page_path": f"/{error_document}",
#         }
#     ],
#     restrictions={
#         "geo_restriction": {
#             "restriction_type": "none",
#         },
#     },
#     viewer_certificate={
#         "cloudfront_default_certificate": True,
#     },
# )

# # Export the bucket website URL and CloudFront domain name
# pulumi.export("bucket_url", pulumi.Output.concat("http://", bucket.bucket_regional_domain_name))
# pulumi.export("cdnURL", pulumi.Output.concat("https://", cdn.domain_name))


# -------------------------------------------------------------------#

# - Block all public access to the S3 bucket.
# - Remove public-read ACL on objects.
# - Create a CloudFront Origin Access Identity (OAI).
# - Update S3 bucket policy to allow access only from CloudFront.
# - Modify CloudFront origin to use the private S3 bucket.

# import pulumi
# import pulumi_aws as aws
# import pulumi_synced_folder as synced_folder

# # Import the program's configuration settings.
# config = pulumi.Config()
# path = config.get("path") or "./www"
# index_document = config.get("indexDocument") or "index.html"
# error_document = config.get("errorDocument") or "error.html"

# # Create an S3 bucket and configure it as a website.
# bucket = aws.s3.BucketV2(
#     "bucket",
#     # website={
#     #     "index_document": index_document,
#     #     "error_document": error_document,
#     # },
# )

# bucket_website = aws.s3.BucketWebsiteConfigurationV2(
#     "bucket",
#     bucket=bucket.bucket,
#     index_document={"suffix": index_document},
#     error_document={"key": error_document},
# )

# # Set ownership controls for the new bucket
# ownership_controls = aws.s3.BucketOwnershipControls(
#     "ownership-controls",
#     bucket=bucket.bucket,
#     rule={
#         "object_ownership": "ObjectWriter",
#     },
# )

# # Configure public ACL block on the new bucket
# public_access_block = aws.s3.BucketPublicAccessBlock(
#     "public-access-block",
#     bucket=bucket.bucket,
#     block_public_acls=False,
# )

# # Use a synced folder to manage the files of the website.
# bucket_folder = synced_folder.S3BucketFolder(
#     "bucket-folder",
#     acl="public-read",
#     bucket_name=bucket.bucket,
#     path=path,
#     opts=pulumi.ResourceOptions(depends_on=[ownership_controls, public_access_block]),
# )

# # Create a CloudFront CDN to distribute and cache the website.
# cdn = aws.cloudfront.Distribution(
#     "cdn",
#     enabled=True,
#     # default_root_object="index.html",
#     origins=[
#         {
#             "origin_id": bucket.arn,
#             "domain_name": bucket_website.website_endpoint,
#             "custom_origin_config": {
#                 "origin_protocol_policy": "http-only",
#                 "http_port": 80,
#                 "https_port": 443,
#                 "origin_ssl_protocols": ["TLSv1.2"],
#             },
#         }
#     ],
#     default_cache_behavior={
#         "target_origin_id": bucket.arn,
#         "viewer_protocol_policy": "redirect-to-https",
#         "allowed_methods": [
#             "GET",
#             "HEAD",
#             "OPTIONS",
#         ],
#         "cached_methods": [
#             "GET",
#             "HEAD",
#             "OPTIONS",
#         ],
#         "default_ttl": 600,
#         "max_ttl": 600,
#         "min_ttl": 600,
#         "forwarded_values": {
#             "query_string": True,
#             "cookies": {
#                 "forward": "all",
#             },
#         },
#     },
#     price_class="PriceClass_100",
#     custom_error_responses=[
#         {
#             "error_code": 404,
#             "response_code": 404,
#             "response_page_path": f"/{error_document}",
#         }
#     ],
#     restrictions={
#         "geo_restriction": {
#             "restriction_type": "none",
#         },
#     },
#     viewer_certificate={
#         "cloudfront_default_certificate": True,
#     },
# )

# # Export the URLs and hostnames of the bucket and distribution.
# # pulumi.export("originURL", pulumi.Output.concat("http://", bucket_website.website_endpoint))
# # pulumi.export("originHostname", bucket.website_endpoint)
# # pulumi.export("cdnURL", pulumi.Output.concat("https://", cdn.domain_name))
# # pulumi.export("cdnHostname", cdn.domain_name)


# pulumi.export("originURL", pulumi.Output.concat("http://", bucket.bucket_regional_domain_name))
# pulumi.export("originHostname", bucket.bucket_regional_domain_name)
# pulumi.export("cdnURL", pulumi.Output.concat("https://", cdn.domain_name))
# pulumi.export("cdnHostname", cdn.domain_name)