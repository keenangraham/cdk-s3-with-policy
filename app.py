from aws_cdk import App
from aws_cdk import Stack
from aws_cdk import RemovalPolicy
from aws_cdk import SecretValue

from aws_cdk.aws_iam import AccountPrincipal
from aws_cdk.aws_iam import AccountRootPrincipal
from aws_cdk.aws_iam import ManagedPolicy
from aws_cdk.aws_iam import PolicyStatement
from aws_cdk.aws_iam import Role

from aws_cdk.aws_iam import User
from aws_cdk.aws_iam import AccessKey

from aws_cdk.aws_s3 import Bucket
from aws_cdk.aws_s3 import CorsRule
from aws_cdk.aws_s3 import HttpMethods

from aws_cdk.aws_secretsmanager import Secret

from constructs import Construct

from shared_infrastructure.cherry_lab.environments import US_WEST_2


CORS = CorsRule(
    allowed_methods=[
        HttpMethods.GET,
        HttpMethods.HEAD,
    ],
    allowed_origins=[
        '*'
    ],
    allowed_headers=[
        'Accept',
        'Origin',
        'Range',
        'X-Requested-With',
        'Cache-Control',
    ],
    exposed_headers=[
        'Content-Length',
        'Content-Range',
        'Content-Type',
    ],
    max_age=3000,
)


def generate_bucket_resource_policy(*, sid, principals, resources):
    return PolicyStatement(
        sid=sid,
        principals=principals,
        resources=resources,
        actions=[
            's3:GetObjectVersion',
            's3:GetObject',
            's3:GetBucketAcl',
            's3:ListBucket',
            's3:GetBucketLocation'
        ]
    )


class BucketStorage(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.blobs_logs_bucket = Bucket(
            self,
            'BlobsLogsBucket',
            bucket_name='test-igvf-blobs-logs-dev',
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.blobs_bucket = Bucket(
            self,
            'BlobsBucket',
            bucket_name='test-igvf-blobs-dev',
            cors=[
                CORS
            ],
            removal_policy=RemovalPolicy.RETAIN,
            server_access_logs_bucket=self.blobs_logs_bucket,
            versioned=True,
        )

        self.blobs_bucket_policy = generate_bucket_resource_policy(
            sid='Allow read from igvf-dev account',
            principals=[
                AccountPrincipal('109189702753'),
            ],
            resources=[
                self.blobs_bucket.bucket_arn,
                self.blobs_bucket.arn_for_objects('*'),
            ]
        )

        self.blobs_bucket.add_to_resource_policy(
            self.blobs_bucket_policy
        )

        self.files_logs_bucket = Bucket(
            self,
            'FilesLogsBucket',
            bucket_name='test-igvf-files-logs-dev',
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.files_bucket = Bucket(
            self,
            'FilesBucket',
            bucket_name='test-igvf-files-dev',
            cors=[
                CORS
            ],
            removal_policy=RemovalPolicy.RETAIN,
            server_access_logs_bucket=self.files_logs_bucket,
            versioned=True,
        )

        self.files_bucket_policy = generate_bucket_resource_policy(
            sid='AllowReadFromIGVFDevAccount',
            principals=[
                AccountPrincipal('109189702753'),
            ],
            resources=[
                self.files_bucket.bucket_arn,
                self.files_bucket.arn_for_objects('*'),
            ]
        )

        self.files_bucket.add_to_resource_policy(
            self.files_bucket_policy
        )


class BucketAccessPolicies(Stack):

    def __init__(self, scope: Construct, construct_id: str, bucket_storage: BucketStorage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.bucket_storage = bucket_storage

        self.download_igvf_files_policy_statement = PolicyStatement(
            sid='AllowReadFromFilesAndBlobsBuckets',
            resources=[
                self.bucket_storage.files_bucket.bucket_arn,
                self.bucket_storage.files_bucket.arn_for_objects('*'),
                self.bucket_storage.blobs_bucket.bucket_arn,
                self.bucket_storage.blobs_bucket.arn_for_objects('*'),
            ],
            actions=[
                's3:GetObjectVersion',
                's3:GetObject',
                's3:GetBucketAcl',
                's3:ListBucket',
                's3:GetBucketLocation'
            ]
        )

        self.upload_igvf_files_policy_statement = PolicyStatement(
            sid='AllowReadAndWriteToFilesAndBlobsBuckets',
            resources=[
                self.bucket_storage.files_bucket.bucket_arn,
                self.bucket_storage.files_bucket.arn_for_objects('*'),
                self.bucket_storage.blobs_bucket.bucket_arn,
                self.bucket_storage.blobs_bucket.arn_for_objects('*'),
            ],
            actions=[
                's3:PutObject',
                's3:GetObjectVersion',
                's3:GetObject',
                's3:GetBucketAcl',
                's3:ListBucket',
                's3:GetBucketLocation',
            ]
        )

        self.federated_token_policy_statement = PolicyStatement(
            sid='AllowGenerateFederatedToken',
            resources=[
                '*',
            ],
            actions=[
                'iam:PassRole',
                'sts:GetFederationToken',
            ]
        )

        self.download_igvf_files_policy = ManagedPolicy(
            self,
            'DownloadIgvfFilesPolicy',
            managed_policy_name='download-igvf-files',
            statements=[
                self.download_igvf_files_policy_statement,
            ],
        )

        self.upload_igvf_files_policy = ManagedPolicy(
            self,
            'UploadIgvfFilesPolicy',
            managed_policy_name='upload-igvf-files',
            statements=[
                self.upload_igvf_files_policy_statement,
                self.federated_token_policy_statement,
            ],
        )


class RoleWithPolicies(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        policy_from_arn = ManagedPolicy.from_managed_policy_arn(
            self,
            'PolicyFromArn',
            'arn:aws:iam::618537831167:policy/download-igvf-files'
        )

        role = Role(
            self,
            'TestRole',
            assumed_by=AccountRootPrincipal(),
            managed_policies=[
                policy_from_arn,
            ]
        )


class UserWithAccessKeyAndPolicies(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        policy_from_arn = ManagedPolicy.from_managed_policy_arn(
            self,
            'PolicyFromArn',
            'arn:aws:iam::618537831167:policy/upload-igvf-files'
        )

        user = User(
            self,
            'UploadIgvfFilesUser',
            user_name='upload-igvf-files',
            managed_policies=[
                policy_from_arn
            ]
        )

        access_key = AccessKey(
            self,
            'UploadIgvfFilesUserAccessKey',
            user=user
        )

        secret = Secret(
            self,
            'UploadIgvfFilesUserAccessKeySecret',
            secret_name='upload-igvf-files-user-access-key',
            secret_object_value={
                'access_key': SecretValue.unsafe_plain_text(access_key.access_key_id),
                'secret_access_key': access_key.secret_access_key,
            },
        )


app = App()


bucket_storage = BucketStorage(
    app,
    'BucketStorage',
    env=US_WEST_2,
    termination_protection=True,
)


bucket_access_polices = BucketAccessPolicies(
    app,
    'BucketAccessPolicies',
    bucket_storage=bucket_storage,
    env=US_WEST_2,
)


role_with_policies = RoleWithPolicies(
    app,
    'RoleWithPolicies',
    env=US_WEST_2,
)


user_with_access_keys_and_polcies = UserWithAccessKeyAndPolicies(
    app,
    'UserWithAccessKeyAndPolicies',
    env=US_WEST_2,
)


role_with_policies.add_dependency(
    bucket_access_polices
)


user_with_access_keys_and_polcies.add_dependency(
    bucket_access_polices
)


app.synth()
