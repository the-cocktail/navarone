"""Create configuration to deploy GKE cluster."""


def generate_config(context):
    """Generate YAML resource configuration."""

    name_prefix = context.env["deployment"] + "-" + context.env["name"]
    cluster_name = name_prefix
    type_name = name_prefix + "-type"
    k8s_endpoints = {"": "api/v1", "-v1beta1-extensions": "apis/extensions/v1beta1"}

    # Configuraciones por defecto
    def_oauthScopes = [
        "https://www.googleapis.com/auth/" + s
        for s in ["compute", "devstorage.read_only", "logging.write", "monitoring"]
    ]
    def_machineType = "n1-standard-4"

    # Let's hacer un cluster grande si corresponde
    clusterlocations = [context.properties["zone"]]
    try:
        context.properties["additionalLocations"]
    except KeyError:
        pass
    else:
        for i in context.properties["additionalLocations"]:
            clusterlocations.append(i)

    # Preparamos Nodepools
    nodepools = []
    for nodeKey in context.properties["clusterNodepools"].keys():
        # Configuracion de nodos
        nodeconfig = {}
        configloop = {
            "oauthScopes": "def_oauthScopes",
            "machineType": "def_machineType",
        }
        for config, defconfig in configloop.iteritems():
            try:
                context.properties["clusterNodepools"][nodeKey][config]
            except KeyError:
                nodeconfig.update({config: eval(defconfig)})
            else:
                nodeconfig.update(
                    {config: context.properties["clusterNodepools"][nodeKey][config]}
                )
        # Nodos
        # TODO: Importante, autoscaling condicional
        nodepools.append(
            {
                "name": context.properties["clusterNodepools"][nodeKey]["name"],
                "config": nodeconfig,
                "initialNodeCount": context.properties["clusterNodepools"][nodeKey][
                    "initialNodeCount"
                ],
                "autoscaling": {
                    "enabled": context.properties["clusterNodepools"][nodeKey][
                        "autoscalingEnabled"
                    ],
                    "minNodeCount": context.properties["clusterNodepools"][nodeKey][
                        "autoscalingMinNodeCount"
                    ],
                    "maxNodeCount": context.properties["clusterNodepools"][nodeKey][
                        "autoscalingMaxNodeCount"
                    ],
                },
                "management": {
                    "autoUpgrade": context.properties["clusterNodepools"][nodeKey][
                        "managementAutoUpgrade"
                    ],
                    "autoRepair": context.properties["clusterNodepools"][nodeKey][
                        "managementAutoRepair"
                    ],
                },
            }
        )

    # Al cielo con el cluster
    # TODO: Sacar el pool default y hacerlo por separado para poder hacer 'autoscale y 'management'
    resources = [
        {
            "name": cluster_name,
            "type": "container.v1.cluster",
            "properties": {
                "zone": context.properties["zone"],
                "cluster": {
                    "name": cluster_name,
                    # "initialNodeCount": context.properties["initialNodeCount"],
                    "initialClusterVersion": context.properties[
                        "initialClusterVersion"
                    ],
                    "addonsConfig": {
                        "httpLoadBalancing": {"disabled": False},
                        "kubernetesDashboard": {"disabled": True},
                    },
                    "networkPolicy": {"provider": "CALICO", "enabled": True},
                    "locations": clusterlocations,
                    # A partir de aqui, Nodos/nodepools?
                    # "nodeConfig": defaultnodeconfig,
                    "nodePools": nodepools,
                },
            },
        }
    ]

    outputs = []
    for type_suffix, endpoint in k8s_endpoints.iteritems():
        resources.append(
            {
                "name": type_name + type_suffix,
                "type": "deploymentmanager.v2beta.typeProvider",
                "properties": {
                    "options": {
                        "validationOptions": {
                            # Kubernetes API accepts ints, in fields they annotate
                            # with string. This validation will show as warning
                            # rather than failure for Deployment Manager.
                            # https://github.com/kubernetes/kubernetes/issues/2971
                            "schemaValidation": "IGNORE_WITH_WARNINGS"
                        },
                        # According to kubernetes spec, the path parameter 'name'
                        # should be the value inside the metadata field
                        # https://github.com/kubernetes/community/blob/master
                        # /contributors/devel/api-conventions.md
                        # This mapping specifies that
                        "inputMappings": [
                            {
                                "fieldName": "name",
                                "location": "PATH",
                                "methodMatch": "^(GET|DELETE|PUT)$",
                                "value": "$.ifNull("
                                "$.resource.properties.metadata.name, "
                                "$.resource.name)",
                            },
                            {
                                "fieldName": "metadata.name",
                                "location": "BODY",
                                "methodMatch": "^(PUT|POST)$",
                                "value": "$.ifNull("
                                "$.resource.properties.metadata.name, "
                                "$.resource.name)",
                            },
                            {
                                "fieldName": "Authorization",
                                "location": "HEADER",
                                "value": '$.concat("Bearer ",'
                                "$.googleOauth2AccessToken())",
                            },
                        ],
                    },
                    "descriptorUrl": "".join(
                        [
                            "https://$(ref.",
                            cluster_name,
                            ".endpoint)/swaggerapi/",
                            endpoint,
                        ]
                    ),
                },
            }
        )
        outputs.append(
            {"name": "clusterType" + type_suffix, "value": type_name + type_suffix}
        )

    return {"resources": resources, "outputs": outputs}
