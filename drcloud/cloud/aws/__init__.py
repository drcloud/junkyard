import collections
from collections import namedtuple
from datetime import datetime, timedelta
import json
import os
import pkg_resources
import re
import time

import awacs.aws
import awacs.sts
import botocore
import boto3
from troposphere import (AWS_REGION, Base64, FindInMap, GetAtt, Join, Output,
                         Parameter, Ref, Tags, Template)
import troposphere.autoscaling as autoscaling
import troposphere.iam as iam
import troposphere.route53 as route53
import troposphere.s3 as s3
import troposphere.sns as sns

from ... import cloud
from .. import err
from ...logger import log
from ...redist import redist
from ...token import booking_code
from ... import unix_conf_snippets


class Cloud(cloud.Cloud):
    def __init__(self, cloud, options=None, **kwargs):
        self.options = options if options else CloudOptions(**kwargs)
        assert isinstance(self.options, CloudOptions)
        self.cloud = cloud
        self.cfn = boto3.resource('cloudformation')
        self.ec2 = boto3.resource('ec2')
        self.s3 = boto3.resource('s3')
        self.stack = None

    def acquire(self):
        vpc = self.options.vpc or self.default_vpc()
        if vpc is None:
            log.error('Not able to infer a default VPC nor was one set.')
            raise Err()
        self.vpc = vpc
        self.template = InVPC(self.cloud, self.vpc.id)
        self.stack = self.stackify(self.template)
        for status, _, __, in CfnStatus(self.stack):
            pass
        if '_FAILED' in status or 'DELETE_' in status:
            log.error('(Cloud %s) %s failed (%s) %s',
                      self.cloud, self.stack.stack_name,
                      status, self.stack.stack_id)
            raise Err()
        log.info('(Cloud %s) Core CloudFormation Stack (%s) ready.',
                 self.cloud, self.stack.stack_name)

    def release(self):
        if self.stack is None:
            self.stack = self.stackify(self.template, create=False)
        if self.stack is None:
            log.notice('(Cloud %s) Never claimed resources; nothing to free.',
                       self.cloud)
            return
        self.stack.delete()
        for status, reason, __ in CfnStatus(self.stack):
            pass
        if '_FAILED' in status or 'DELETE_' not in status:
            log.error('(Cloud %s) Not able to delete stack: %s',
                      self.cloud, reason)
            raise Err()
        log.info('(Cloud %s) Freed resources for: %s',
                 self.cloud, self.stack.stack_id)

    def stackify(self, template, create=True):
        try:
            stack = self.cfn.Stack(template.name())
            stack.load()
            return self.by_arn(stack)
        except botocore.exceptions.ClientError as e:
            if 'Stack with id ' in str(e) and ' does not exist' in str(e):
                pass
            else:
                raise
        if create:
            template.cfn(self.cfn)
            return self.by_arn(template.instantiate())

    def by_arn(self, stack):
        """Resolve a named stack's ARN and return a stack with that ARN.

        This allows us to track deletion.
        """
        return self.cfn.Stack(stack.stack_id)

    def default_vpc(self):
        defaults = [_ for _ in self.ec2.vpcs.iterator() if _.is_default]
        if len(defaults) > 0:
            return defaults[0]

    def default_subnets(self, vpc=None):
        vpc = vpc or self.vpc
        if vpc is None:
            return
        defaults = [_ for _ in vpc.subnets.iterator() if _.default_for_az]
        if len(defaults) > 0:
            return defaults

    def upload_drcloud(self, to):
        outputs = CfnOutputs(self.stack)
        bucket = self.s3.Bucket(outputs['S3Bucket'])
        with redist() as h:
            destination = os.path.join(to, os.path.basename(h.name))
            try:
                bucket.upload_file(h.name, destination)
            except botocore.parsers.ResponseParserError as e:
                raise Err(underlying=e)

    def service(self):
        pass


class CloudOptions(object):
    def __init__(self, vpc=None):
        self.vpc = vpc


class Service(cloud.Service):
    def __init__(self, service, cloud, nodes=1, profile='t2.micro',
                 options=None, **kwargs):
        self.options = options if options else ServiceOptions(**kwargs)
        assert isinstance(self.options, ServiceOptions)
        self.cloud = cloud
        self.service = service
        self.nodes = nodes
        self.profile = profile
        self.subnets = self.options.subnets
        self.fqdn = '%s.%s' % (self.service, self.cloud.cloud)

    def acquire(self):
        outputs = CfnOutputs(self.cloud.stack)
        if self.subnets is None:
            self.subnets = [_.id for _ in self.cloud.default_subnets()]
        self.template = UbuntuASG(
            self.fqdn,
            self.cloud.cloud,
            nodes=self.nodes,
            size=self.profile,
            s3bucket=outputs['S3Bucket'],
            sns_topic=outputs['SNSTopic'],
            iam_profile=outputs['IAMInstanceProfile'],
            subnets=self.subnets
        )
        self.cloud.upload_drcloud(self.fqdn + '/misc/')
        self.stack = self.cloud.stackify(self.template)
        for status, _, __, in CfnStatus(self.stack):
            pass
        if '_FAILED' in status or 'DELETE_' in status:
            log.error('(Service %s) %s failed (%s) %s',
                      self.fqdn, self.stack.stack_name,
                      status, self.stack.stack_id)
            raise Err()
        log.info('(Service %s) CloudFormation Stack (%s) ready.',
                 self.fqdn, self.stack.stack_name)

    def release(self):
        if self.stack is None:
            self.stack = self.cloud.stackify(self.template, create=False)
        if self.stack is None:
            log.notice('(Service %s) Never claimed resources; '
                       'nothing to free.',
                       self.fqdn)
            return
        self.stack.delete()
        for status, reason, __ in CfnStatus(self.stack):
            pass
        if '_FAILED' in status or 'DELETE_' not in status:
            log.error('(Service %s) Not able to delete stack: %s',
                      self.fqdn, reason)
            raise Err()
        log.info('(Service %s) Freed resources for: %s',
                 self.fqdn, self.stack.stack_id)


class ServiceOptions(object):
    def __init__(self, subnets=None):
        self.subnets = subnets


class Cfn(object):
    """CloudFormation template generators.
    """
    cfn_version = '2010-09-09'
    ephemeral = True         # By default, append a unique token at each launch
    on_failure = 'ROLLBACK'              # Can be: ROLLBACK, DELETE, DO_NOTHING

    def template(self):
        """
        :rtype troposphere.Template:
        """
        raise NotImplementedError()

    def instantiate(self, name=None, tags={}, ephemeral=None,
                    on_failure=None, capabilities=None):
        ephemeral = self.ephemeral if ephemeral is None else ephemeral
        on_failure = self.on_failure if on_failure is None else on_failure
        name = (name or self.name()) + (booking_code() if ephemeral else '')
        template = self.template()
        if capabilities is None:
            acc = set()
            for _, resource in template.resources.items():
                if resource.__class__.__module__ == iam.__name__:
                    acc |= set(['CAPABILITY_IAM'])
            capabilities = list(acc)
        log.info('(Stack %s) Sending template%s...', name,
                 ' (with ' + ' '.join(capabilities) + ')'
                 if len(capabilities) > 0 else '')
        default_tags = self.tags()
        default_tags.update(tags)
        expanded_tags = Tags(**default_tags).JSONrepr()
        stack = self.cfn().create_stack(StackName=name,
                                        TemplateBody=template.to_json(),
                                        Capabilities=capabilities,
                                        TimeoutInMinutes=5,
                                        OnFailure=on_failure,
                                        Tags=expanded_tags)
        log.info('(Stack %s) CloudFormation Stack ARN: %s',
                 name, stack.stack_id)
        return self.cfn().Stack(stack.stack_id)

    def tags(self):
        return {}

    def name(self):
        return self.__class__.__name__

    def cfn(self, cfn=None):
        if not hasattr(self, '_cfn') or cfn is not None:
            setattr(self, '_cfn', cfn or boto3.resource('cloudformation'))
        return self._cfn


class CfnStatus(namedtuple('CfnStatus', 'stack')):
    def __iter__(self):
        start, timeout = datetime.utcnow(), timedelta(minutes=20)

        def cfn_status():
            name = self.stack.stack_name
            status = self.stack.stack_status
            reason = self.stack.stack_status_reason
            events = list(self.stack.events.iterator())
            events.reverse()
            diff = events[len(cfn_status.old_events):]
            cfn_status.old_events = events
            diff_s = '\n'.join(_.id for _ in diff)
            reason_s = ' ' + reason if reason else ''
            log.debug('(Stack %s) %s%s\n%s', name, status, reason_s, diff_s)
            return status, reason, diff
        cfn_status.old_events = []  # Function attributes... I laughed, I cried

        while self.stack.stack_status.endswith('_IN_PROGRESS'):
            delta = datetime.utcnow() - start
            if delta > timeout:
                raise Err('Ran out of time (%s > %s) waiting for %s.',
                          delta, timeout, self.stack_id)
            yield cfn_status()
            time.sleep(10)
            self.stack.reload()
        yield cfn_status()


class CfnOutputs(collections.Mapping):
    def __init__(self, stack):
        self._ = {}
        for kv in stack.outputs:
            k, v = kv['OutputKey'], kv['OutputValue']
            self._[k] = v

    def __len__(self):
        return self._.__len__()

    def __iter__(self):
        return self._.__iter__()

    def __getitem__(self, *args, **kwargs):
        return self._.__getitem__(*args, **kwargs)


class InVPC(Cfn):
    ephemeral = False
    description = 'IAM policies and coordination resources for Dr. Cloud.'
    on_failure = 'DELETE'

    def __init__(self,
                 cloud,
                 vpc=None,
                 with_zone=False):
        self.cloud = cloud
        self.vpc = vpc
        self.with_zone = with_zone

    def template(self):
        template = Template()

        template.add_version(self.cfn_version)
        template.add_description(self.description)

        if self.vpc is not None:
            template.add_parameter(Parameter(
                'VPC',
                Type='AWS::EC2::VPC::Id',
                Default=self.vpc
            ))
            vpc = self.vpc
        else:
            raise NotImplementedError('We presently require a VPC.')
            # TODO: Configure security group rules and subnets in our VPC.

        role = template.add_resource(iam_role())
        template.add_output(Output('IAMRole', Value=Ref(role)))
        role_name = Ref(role)
        role_arn = GetAtt(role, 'Arn')

        enable_versioning = s3.VersioningConfiguration(Status='Enabled')
        bucket = template.add_resource(s3.Bucket(
            'S3Bucket',
            VersioningConfiguration=enable_versioning,
            Tags=Tags(drcloud=self.cloud),
            DeletionPolicy='Retain'
            # NB: "Only Amazon S3 buckets that are empty can be deleted.
            #      Deletion will fail for buckets that have contents."
        ))
        template.add_output(Output(
            'S3Bucket',
            Value=Ref(bucket)
        ))
        bucket_arn = Join('', ['arn:aws:s3:::', Ref(bucket)])
        bucket_arn_star = Join('', ['arn:aws:s3:::', Ref(bucket), '/*'])

        sns_topic = template.add_resource(sns.Topic('SNSTopic'))
        template.add_output(Output(
            'SNSTopic',
            Value=Ref(sns_topic)
        ))

        if self.with_zone:
            r53 = template.add_resource(route53.HostedZone(
                'Zone',
                Name=(self.cloud.strip('.') + '.'),
                VPCs=[route53.HostedZoneVPCs(VPCId=vpc,
                                             VPCRegion=Ref(AWS_REGION))],
                HostedZoneTags=Tags(drcloud=self.cloud)
            ))
            zone_arn = Join('/', ['arn:aws:route53:::hostedzone', Ref(r53)])
            changes_arn = 'arn:aws:route53:::change/*'
            zone_policy_statements = [
                awacs.aws.Statement(
                    Effect=awacs.aws.Allow,
                    Action=[
                        awacs.aws.Action('route53',
                                         'ListResourceRecordSets'),
                        awacs.aws.Action('route53',
                                         'ChangeResourceRecordSets'),
                    ],
                    Resource=[zone_arn]
                ),
                awacs.aws.Statement(
                    Effect=awacs.aws.Allow,
                    Action=[awacs.aws.Action('route53', 'GetChange')],
                    Resource=[changes_arn]
                ),
            ]
            template.add_output(Output('Zone', Value=Ref(r53)))
        else:
            zone_policy_statements = []

        # IAM
        instance_iam = template.add_resource(iam.ManagedPolicy(
            'InstancePolicy',
            Path='/drcloud/node/',
            Roles=[role_name],
            PolicyDocument=awacs.aws.Policy(
                Version='2012-10-17',
                Statement=[
                    # TODO: Restrict write/delete by instance ID or IP
                    awacs.aws.Statement(
                        Effect=awacs.aws.Allow,
                        Action=[awacs.aws.Action('s3', '*')],
                        Resource=[bucket_arn, bucket_arn_star]
                    ),
                ],
            )
        ))
        template.add_output(Output('IAMForInstances', Value=Ref(instance_iam)))

        profile = template.add_resource(iam.InstanceProfile(
            'InstanceProfile',
            Path='/drcloud/node/',
            Roles=[role_name]
        ))
        template.add_output(Output('IAMInstanceProfile', Value=Ref(profile)))

        user_iam = template.add_resource(iam.ManagedPolicy(
            'UserPolicy',
            Path='/drcloud/user/',
            PolicyDocument=awacs.aws.Policy(
                Version='2012-10-17',
                Statement=[
                    awacs.aws.Statement(
                        Effect=awacs.aws.Allow,
                        Action=[awacs.aws.Action('iam', 'PassRole')],
                        Resource=[role_arn]
                    ),
                    awacs.aws.Statement(
                        Effect=awacs.aws.Allow,
                        Action=[awacs.aws.Action('s3', '*')],
                        Resource=[bucket_arn, bucket_arn_star]
                    ),
                ] + zone_policy_statements,
            )
        ))
        template.add_output(Output('IAMForUsers', Value=Ref(user_iam)))

        return template

    def tags(self):
        return dict(drcloud=self.cloud)

    def name(self):
        return pascalize(self.cloud)


class UbuntuASG(Cfn):
    description = 'Ubuntu LTS servers in an auto-scaling group.'
    ephemeral = False
    on_failure = 'DELETE'

    def __init__(self,
                 service,
                 cloud,
                 s3bucket,
                 sns_topic,
                 iam_profile,
                 subnets,
                 size='t2.micro',
                 nodes=1,
                 sgs=[]):
        self.service = service
        self.cloud = cloud
        self.s3bucket = s3bucket
        self.sns_topic = sns_topic
        self.iam_profile = iam_profile
        self.subnets = subnets
        self.size = size
        self.nodes = nodes
        self.sgs = sgs

    def template(self):
        template = Template()

        template.add_version(self.cfn_version)
        template.add_description(self.description)

        sshkey = template.add_parameter(Parameter(
            'SSHKey',
            Type='AWS::EC2::KeyPair::KeyName',
            Default='default'
        ))

        subnets = template.add_parameter(Parameter(
            'Subnets',
            Type='List<AWS::EC2::Subnet::Id>',
            Default=','.join(self.subnets)
        ))

        nodes = template.add_parameter(Parameter(
            'InstanceCount',
            Type='Number',
            Default=str(self.nodes)
        ))

        min_size = template.add_parameter(Parameter(
            'InstanceCountMin',
            Type='Number',
            Default=str(self.nodes)
        ))

        max_size = template.add_parameter(Parameter(
            'InstanceCountMax',
            Type='Number',
            Default=str(self.nodes + 1)
        ))

        iam_profile = template.add_parameter(Parameter(
            'InstanceIAMProfile',
            Type='String',
            Default=self.iam_profile
        ))

        cloud = template.add_parameter(Parameter(
            'Cloud',
            Type='String',
            Default=self.cloud
        ))

        service = template.add_parameter(Parameter(
            'Service',
            Type='String',
            Default=self.service
        ))

        region_ami_data = fetch('region*arch->ubuntu-ami.json')
        size_data = fetch('size->platform.json')

        size = template.add_parameter(Parameter(
            'InstanceSize',
            Type='String',
            AllowedValues=size_data.keys(),
            Default=self.size
        ))

        region_ami_map = 'AWSRegionPlatform2AMI'
        size_map = 'AWSSize2Platform'
        template.add_mapping(size_map, size_data)
        template.add_mapping(region_ami_map, region_ami_data)

        s3bucket = template.add_parameter(Parameter(
            'S3Bucket',
            Type='String',
            Default=self.s3bucket
        ))

        sns_topic = template.add_parameter(Parameter(
            'SNSTopic',
            Type='String',
            Default=self.sns_topic
        ))

        # Use the size to find the platform and use the size and platform
        # together to find the AMI ID.
        ami_expr = FindInMap(region_ami_map,
                             Ref(AWS_REGION),
                             FindInMap(size_map, Ref(size), 'Platform'))

        base_userdata = template.add_parameter(UbuntuASG.userdata_base())
        rsyslog_conf = unix_conf_snippets.fetch('formats.rsyslog')
        sync_script = fetch('drcloud-sync-var-spool')
        sync_service = fetch('drcloud-sync-var-spool.upstart')
        rx_service = fetch('drcloud-rx.upstart')

        # There is something bad in the design here because we can not really
        # test the YAML file without running this through CloudFormation.
        userdata = Join('\n', ['#cloud-config',
                               '',
                               UbuntuASG.userdata_params(
                                   drcloud=dict(cloud=Ref(cloud),
                                                service=Ref(service)),
                                   ubuntu=dict(sync_service=sync_service,
                                               rx_service=rx_service,
                                               rsyslog_conf=rsyslog_conf),
                                   aws=dict(
                                       s3=Join('', ['s3://', Ref(s3bucket)]),
                                       sync_script=sync_script,
                                   )
                               ),
                               Ref(base_userdata)])

        lc = template.add_resource(autoscaling.LaunchConfiguration(
            'ASGLaunchConfiguration',
            AssociatePublicIpAddress=True,
            IamInstanceProfile=Ref(iam_profile),
            ImageId=ami_expr,
            InstanceType=Ref(size),
            KeyName=Ref(sshkey),
            SecurityGroups=[],
            UserData=Base64(userdata),
        ))

        all_notifications = [autoscaling.EC2_INSTANCE_LAUNCH,
                             autoscaling.EC2_INSTANCE_TERMINATE,
                             autoscaling.EC2_INSTANCE_LAUNCH_ERROR,
                             autoscaling.EC2_INSTANCE_TERMINATE_ERROR,
                             autoscaling.TEST_NOTIFICATION]
        template.add_resource(autoscaling.AutoScalingGroup(
            'ASG',
            DesiredCapacity=Ref(nodes),
            MinSize=Ref(min_size),
            MaxSize=Ref(max_size),
            LaunchConfigurationName=Ref(lc),
            NotificationConfigurations=[
                autoscaling.NotificationConfigurations(
                    TopicARN=Ref(sns_topic),
                    NotificationTypes=all_notifications
                )
            ],
            VPCZoneIdentifier=Ref(subnets),
            Tags=autoscaling.Tags(Name=self.service, **self.tags()),
        ))

        return template

    @staticmethod
    def userdata_params(**kwargs):
        pieces = []
        for section, fields in kwargs.items():
            if len(fields) <= 0:
                continue
            pieces += [['%s:' % section] +
                       [UbuntuASG.yaml_kv(k, v)
                        for k, v in fields.items() if v is not None]]
        return Join('\n', [Join('\n  ', subpieces) for subpieces in pieces])

    @staticmethod
    def userdata_base():
        user_data_pieces = re.split('^###+ Generic.+$',
                                    fetch('userdata.yaml'),
                                    1,
                                    re.M)

        return Parameter(
            'UserData',
            Type='String',
            Default=user_data_pieces[-1]
        )

    @staticmethod
    def yaml_kv(k, v):
        if not isinstance(v, basestring) or '\n' not in v:
            key = '{0}: &{0}'.format(k)
            val = [v]
        else:
            key = '{0}: &{0} |'.format(k)
            val = v.splitlines()
        return Join('\n    ', [key] + val)

    def tags(self):
        return {'drcloud': self.service}

    def name(self):
        return pascalize(self.service)


class Err(err.Err):
    pass


def fetch(filename):
    """
    :type filename: str
    """
    data = pkg_resources.resource_string(__package__, filename)
    if filename.endswith('.json'):
        return json.loads(data)
    else:
        return data.strip()


def iam_role(role='IAMRole', path='/drcloud/nodes/'):
    assume_role_policy = awacs.aws.Policy(
        Statement=[
            awacs.aws.Statement(
                Effect=awacs.aws.Allow,
                Action=[awacs.sts.AssumeRole],
                Principal=awacs.aws.Principal('Service', ['ec2.amazonaws.com'])
            )
        ]
    )
    return iam.Role(role,
                    Path=path,
                    AssumeRolePolicyDocument=assume_role_policy)


def pascalize(domain_name):
    """Return a domain name in Pascal case.

    Capital camel-cases is suitable for use as a CloudFormation name. The names
    are returned big-endian so they sort reasonably relative to one another.
    """
    components = domain_name.split('.')
    components.reverse()
    return ''.join(_.capitalize() for __ in components for _ in __.split('-'))
