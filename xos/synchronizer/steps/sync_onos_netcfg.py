import os
import requests
import socket
import sys
import base64
import json
from synchronizers.new_base.syncstep import SyncStep
from synchronizers.new_base.modelaccessor import *
from xos.logger import Logger, logging

logger = Logger(level=logging.INFO)

class SyncONOSNetcfg(SyncStep):
    provides=[VTNService]
    observes=VTNService
    watches=[ModelLink(Node,via='node'), ModelLink(AddressPool,via='addresspool')]
    requested_interval=0

    def __init__(self, **args):
        SyncStep.__init__(self, **args)

    def handle_watched_object(self, o):
        logger.info("handle_watched_object is invoked for object %s" % (str(o)),extra=o.tologdict())
        if (type(o) is Node): # For Node add/delete/modify
            self.call()
        if (type(o) is AddressPool): # For public gateways
            self.call()

    def get_node_tag(self, node, tagname):
        tags = Tag.objects.filter(content_type=model_accessor.get_content_type_id(node),
                                  object_id=node.id,
                                  name=tagname)
        return tags[0].value

    def get_tenants_who_want_config(self):
        tenants = []
        # attribute is comma-separated list
        for ta in ServiceInstanceAttribute.objects.filter(name="autogenerate"):
            if ta.value:
                for config in ta.value.split(','):
                    if config == "vtn-network-cfg":
                        tenants.append(ta.service_instance)
        return tenants

    def save_tenant_attribute(self, tenant, name, value):
        tas = ServiceInstanceAttribute.objects.filter(service_instance_id=tenant.id, name=name)
        if tas:
            ta = tas[0]
            if ta.value != value:
                logger.info("updating %s with attribute" % name)
                ta.value = value
                ta.save()
        else:
            logger.info("saving autogenerated config %s" % name)
            ta = model_accessor.create_obj(ServiceInstanceAttribute, service_instance=tenant, name=name, value=value)
            ta.save()

    # This function currently assumes a single Deployment and Site
    def get_onos_netcfg(self, vtn):
        privateGatewayMac = vtn.privateGatewayMac
        localManagementIp = vtn.localManagementIp
        ovsdbPort = vtn.ovsdbPort
        sshPort = vtn.sshPort
        sshUser = vtn.sshUser
        sshKeyFile = vtn.sshKeyFile
        mgmtSubnetBits = vtn.mgmtSubnetBits
        xosEndpoint = vtn.xosEndpoint
        xosUser = vtn.xosUser
        xosPassword = vtn.xosPassword

        controllerPort = vtn.controllerPort
        if ":" in controllerPort:
            (c_hostname, c_port) = controllerPort.split(":",1)
            controllerPort = socket.gethostbyname(c_hostname) + ":" + c_port
        else:
            controllerPort = ":" + controllerPort

        data = {
            "apps" : {
                "org.opencord.vtn" : {
                    "cordvtn" : {
                        "privateGatewayMac" : privateGatewayMac,
                        "localManagementIp": localManagementIp,
                        "ovsdbPort": ovsdbPort,
                        "ssh": {
                            "sshPort": sshPort,
                            "sshUser": sshUser,
                            "sshKeyFile": sshKeyFile
                        },
                        "xos": {
                            "endpoint": xosEndpoint,
                            "user": xosUser,
                            "password": xosPassword
                        },
                        "publicGateways": [],
                        "nodes" : [],
                        "controllers": [controllerPort]
                    }
                }
            }
        }

        # Generate apps->org.opencord.vtn->cordvtn->openstack
        controllers = Controller.objects.all()
        if controllers:
            controller = controllers[0]
            keystone_server = controller.auth_url
            user_name = controller.admin_user
            tenant_name = controller.admin_tenant
            password = controller.admin_password
            openstack = {
                "endpoint": keystone_server,
                "tenant": tenant_name,
                "user": user_name,
                "password": password
            }
            data["apps"]["org.opencord.vtn"]["cordvtn"]["openstack"] = openstack

        # Generate apps->org.opencord.vtn->cordvtn->nodes
        nodes = Node.objects.all()
        for node in nodes:
            nodeip = socket.gethostbyname(node.name)

            try:
                bridgeId = self.get_node_tag(node, "bridgeId")
                dataPlaneIntf = self.get_node_tag(node, "dataPlaneIntf")
                dataPlaneIp = self.get_node_tag(node, "dataPlaneIp")
            except:
                logger.error("not adding node %s to the VTN configuration" % node.name)
                continue

            node_dict = {
                "hostname": node.name,
                "hostManagementIp": "%s/%s" % (nodeip, mgmtSubnetBits),
                "bridgeId": bridgeId,
                "dataPlaneIntf": dataPlaneIntf,
                "dataPlaneIp": dataPlaneIp
            }

            # this one is optional
            try:
                node_dict["hostManagementIface"] = self.get_node_tag(node, "hostManagementIface")
            except IndexError:
                pass

            data["apps"]["org.opencord.vtn"]["cordvtn"]["nodes"].append(node_dict)

        # Generate apps->org.onosproject.cordvtn->cordvtn->publicGateways
        # Pull the gateway information from vRouter
        if model_accessor.has_model_class("VRouterService"):
            vrouters = VRouterService.objects.all()
            if vrouters:
                for gateway in vrouters[0].get_gateways():
                    gatewayIp = gateway['gateway_ip'].split('/',1)[0]
                    gatewayMac = gateway['gateway_mac']
                    gateway_dict = {
                        "gatewayIp": gatewayIp,
                        "gatewayMac": gatewayMac
                    }
                    data["apps"]["org.opencord.vtn"]["cordvtn"]["publicGateways"].append(gateway_dict)
        else:
            logger.info("No VRouter service present, not adding publicGateways to config")

        return json.dumps(data, indent=4, sort_keys=True)

    def call(self, **args):
        vtn_service = VTNService.objects.all()
        if not vtn_service:
            raise Exception("No VTN Service")

        vtn_service = vtn_service[0]

        # Check for autogenerate attribute
        netcfg = self.get_onos_netcfg(vtn_service)

        tenants = self.get_tenants_who_want_config()
        for tenant in tenants:
            self.save_tenant_attribute(tenant, "rest_onos/v1/network/configuration/", netcfg)
