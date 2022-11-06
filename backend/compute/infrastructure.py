# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import pathlib

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_efs as efs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
from constructs import Construct

import constants


class Compute(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        efs_access_point: efs.AccessPoint,
        efs_file_system_id: str,
        vpc: ec2.IVpc,
    ):
        super().__init__(scope, id_)

        efs_mount_path = "/mnt/app"
        efs_mount_path_env_var_name = "EFS_MOUNT_PATH"

        server = Server(
            self,
            "Server",
            efs_access_point_id=efs_access_point.access_point_id,
            efs_file_system_id=efs_file_system_id,
            efs_mount_path=efs_mount_path,
            vpc=vpc,
        )
        self.ec2_instance = server.ec2_instance

        container = Container(
            self,
            "Container",
            efs_access_point_id=efs_access_point.access_point_id,
            efs_file_system_id=efs_file_system_id,
            efs_mount_path=efs_mount_path,
            efs_mount_path_env_var_name=efs_mount_path_env_var_name,
            vpc=vpc,
        )
        self.ecs_fargate_service = container.ecs_fargate_service
        self.ecs_fargate_service.node.add_dependency(self.ec2_instance)

        function = Function(
            self,
            "Function",
            efs_access_point=efs_access_point,
            efs_mount_path=efs_mount_path,
            efs_mount_path_env_var_name=efs_mount_path_env_var_name,
            vpc=vpc,
        )
        self.lambda_function = function.lambda_function
        self.lambda_function.node.add_dependency(self.ec2_instance)


class Server(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        efs_access_point_id: str,
        efs_file_system_id: str,
        efs_mount_path: str,
        vpc: ec2.IVpc,
    ):
        super().__init__(scope, id_)

        self.ec2_instance = ec2.Instance(
            self,
            "EC2Instance",
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ec2.MachineImage.from_ssm_parameter(
                # pylint: disable=line-too-long
                "/aws/service/canonical/ubuntu/server/20.04/stable/current/amd64/hvm/ebs-gp2/ami-id"
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )
        self._add_permissions()
        self._add_user_data(efs_access_point_id, efs_file_system_id, efs_mount_path)

    def _add_permissions(self) -> None:
        # Enable AWS Systems Manager Session Manager
        self.ec2_instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore",
            )
        )
        # Enable access to Amazon EFS
        self.ec2_instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonElasticFileSystemClientReadWriteAccess",
            )
        )

    def _add_user_data(
        self, efs_access_point_id: str, efs_file_system_id: str, efs_mount_path: str
    ) -> None:
        self._apt_get_update_and_upgrade()
        self._install_efs_utils()
        self._mount_efs(efs_access_point_id, efs_file_system_id, efs_mount_path)
        self._install_rust_and_wasm()
        self._install_spin()
        self._seed_data_to_efs(efs_mount_path)
        self._start_spin(efs_mount_path)

    def _apt_get_update_and_upgrade(self) -> None:
        self.ec2_instance.user_data.add_commands(
            "apt-get -y update",
            "apt-get -y upgrade",
        )

    def _install_efs_utils(self) -> None:
        self.ec2_instance.user_data.add_commands(
            "apt-get -y install git binutils",
            "git clone https://github.com/aws/efs-utils",
            "cd efs-utils",
            "./build-deb.sh",
            "apt-get -y install ./build/amazon-efs-utils*deb",
            "cd -",
        )

    def _mount_efs(
        self, efs_access_point_id: str, efs_file_system_id: str, efs_mount_path: str
    ) -> None:
        self.ec2_instance.user_data.add_commands(
            f"mkdir -p {efs_mount_path}",
            # pylint: disable=line-too-long
            f"mount -t efs -o tls,accesspoint={efs_access_point_id} {efs_file_system_id}:/ {efs_mount_path}",
        )

    def _install_rust_and_wasm(self) -> None:
        self.ec2_instance.user_data.add_commands(
            "echo Installing Rust / WASM dev toolchain and its requirements...",
            "apt-get -y install build-essential",
            "curl https://sh.rustup.rs -sSf | bash -s -- -y",
            "/root/.cargo/bin/rustup target add wasm32-wasi",
        )

    def _install_spin(self) -> None:
        self.ec2_instance.user_data.add_commands(
            # pylint: disable=line-too-long
            "curl -L -O https://github.com/fermyon/spin/releases/download/v0.6.0/spin-v0.6.0-linux-amd64.tar.gz",
            "tar -zxvf spin-v0.6.0-linux-amd64.tar.gz",
            "mv spin /usr/local/bin/spin",
        )

    def _seed_data_to_efs(self, efs_mount_path: str) -> None:
        self.ec2_instance.user_data.add_commands(
            f"cd {efs_mount_path}",
            "echo Creating and building a small application...",
            "spin templates install --git https://github.com/fermyon/spin",
            # pylint: disable=line-too-long
            "[[ -d spin-hello-world ]] || spin new http-rust spin-hello-world --value project-description='Rust http service' --value http-base=/ --value http-path=/",
            # pylint: disable=line-too-long
            "/root/.cargo/bin/cargo build --manifest-path ./spin-hello-world/Cargo.toml --target wasm32-wasi --release",
            "cd -",
        )

    def _start_spin(self, efs_mount_path: str) -> None:
        self.ec2_instance.user_data.add_commands(
            "echo Launching Spin...",
            # pylint: disable=line-too-long
            f"spin up --listen 0.0.0.0:{constants.SPIN_PORT} --disable-cache --file {efs_mount_path}/spin-hello-world/spin.toml",
        )


class Container(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        efs_access_point_id: str,
        efs_file_system_id: str,
        efs_mount_path: str,
        efs_mount_path_env_var_name: str,
        vpc: ec2.IVpc,
    ):
        super().__init__(scope, id_)

        ecs_fargate_task_definition = self._create_ecs_fargate_task_definition(
            efs_access_point_id,
            efs_file_system_id,
            efs_mount_path,
            efs_mount_path_env_var_name,
        )
        ecs_cluster = ecs.Cluster(self, "ECSCluster", vpc=vpc)
        self.ecs_fargate_service = ecs.FargateService(
            self,
            "ECSFargateService",
            assign_public_ip=True,
            cluster=ecs_cluster,
            task_definition=ecs_fargate_task_definition,
        )

    def _create_ecs_fargate_task_definition(
        self,
        efs_access_point_id: str,
        efs_file_system_id: str,
        efs_mount_path: str,
        efs_mount_path_env_var_name: str,
    ) -> ecs.FargateTaskDefinition:
        ecs_fargate_task_definition = ecs.FargateTaskDefinition(
            self,
            "ECSFargateTaskDefinition",
            cpu=256,
            memory_limit_mib=512,
        )
        ecs_fargate_task_definition.task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonElasticFileSystemClientReadWriteAccess",
            )
        )
        efs_volume_name = "efs"
        Container._add_volume(
            ecs_fargate_task_definition,
            efs_access_point_id,
            efs_file_system_id,
            efs_volume_name,
        )
        Container._add_container(
            ecs_fargate_task_definition,
            efs_mount_path,
            efs_mount_path_env_var_name,
            efs_volume_name,
        )
        return ecs_fargate_task_definition

    @staticmethod
    def _add_volume(
        task_definition: ecs.FargateTaskDefinition,
        efs_access_point_id: str,
        efs_file_system_id: str,
        efs_volume_name: str,
    ) -> None:
        efs_volume_configuration = ecs.EfsVolumeConfiguration(
            authorization_config=ecs.AuthorizationConfig(
                access_point_id=efs_access_point_id,
                iam="ENABLED",
            ),
            file_system_id=efs_file_system_id,
            transit_encryption="ENABLED",
        )
        task_definition.add_volume(
            name=efs_volume_name, efs_volume_configuration=efs_volume_configuration
        )

    @staticmethod
    def _add_container(
        ecs_fargate_task_definition: ecs.FargateTaskDefinition,
        efs_mount_path: str,
        efs_mount_path_env_var_name: str,
        efs_volume_name: str,
    ) -> None:
        container_definition = ecs_fargate_task_definition.add_container(
            "Spin",
            image=ecs.ContainerImage.from_asset(
                str(pathlib.Path(__file__).parent.joinpath("runtime").resolve()),
            ),
            environment={efs_mount_path_env_var_name: efs_mount_path},
            logging=ecs.LogDriver.aws_logs(stream_prefix=constants.APP_NAME),
            port_mappings=[ecs.PortMapping(container_port=constants.SPIN_PORT)],
        )
        efs_mount_point = ecs.MountPoint(
            container_path=efs_mount_path,
            read_only=False,
            source_volume=efs_volume_name,
        )
        container_definition.add_mount_points(efs_mount_point)


class Function(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        efs_access_point: efs.AccessPoint,
        efs_mount_path: str,
        efs_mount_path_env_var_name: str,
        vpc: ec2.IVpc,
    ):
        super().__init__(scope, id_)
        self.lambda_function = lambda_.DockerImageFunction(
            self,
            "LambdaFunction",
            allow_public_subnet=True,
            code=lambda_.DockerImageCode.from_image_asset(
                str(pathlib.Path(__file__).parent.joinpath("runtime").resolve()),
            ),
            environment={
                efs_mount_path_env_var_name: efs_mount_path,
            },
            filesystem=lambda_.FileSystem.from_efs_access_point(
                efs_access_point,
                mount_path=efs_mount_path,
            ),
            vpc=vpc,
        )
