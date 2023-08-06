from brownie import accounts

# === GIF platform ========================================================== #

# GIF release
GIF_RELEASE = '2.0.0'

# GIF modules
ACCESS_NAME = 'Access'
BUNDLE_NAME = 'Bundle'
COMPONENT_NAME = 'Component'

REGISTRY_CONTROLLER_NAME = 'RegistryController'
REGISTRY_NAME = 'Registry'

ACCESS_CONTROLLER_NAME = 'AccessController'
ACCESS_NAME = 'Access'

LICENSE_CONTROLLER_NAME = 'LicenseController'
LICENSE_NAME = 'License'

POLICY_CONTROLLER_NAME = 'PolicyController'
POLICY_NAME = 'Policy'

POLICY_DEFAULT_FLOW_NAME = 'PolicyDefaultFlow'
POOL_NAME = 'Pool'

QUERY_NAME = 'Query'

RISKPOOL_CONTROLLER_NAME = 'RiskpoolController'
RISKPOOL_NAME = 'Riskpool'
TREASURY_NAME = 'Treasury'

# GIF services
COMPONENT_OWNER_SERVICE_NAME = 'ComponentOwnerService'
PRODUCT_SERVICE_NAME = 'ProductService'
RISKPOOL_SERVICE_NAME = 'RiskpoolService'
ORACLE_SERVICE_NAME = 'OracleService'
INSTANCE_OPERATOR_SERVICE_NAME = 'InstanceOperatorService'
INSTANCE_SERVICE_NAME = 'InstanceService'

# GIF States

# enum BundleState {Active, Locked, Closed, Burned}
BUNDLE_STATE = {
    0: "Active",
    1: "Locked",
    2: "Closed",
    3: "Burned",
}

# enum ApplicationState {Applied, Revoked, Underwritten, Declined}
APPLICATION_STATE = {
    0: "Applied",
    1: "Revoked",
    2: "Underwritten",
    3: "Declined",
}

# enum PolicyState {Active, Expired, Closed}
POLICY_STATE = {
    0: "Active",
    1: "Expired",
    2: "Closed",
}

# enum ComponentState {
#     Created,
#     Proposed,
#     Declined,
#     Active,
#     Paused,
#     Suspended,
#     Archived
# }
COMPONENT_STATE = {
    0: "Created",
    1: "Proposed",
    2: "Declined",
    3: "Active",
    4: "Paused",
    5: "Suspended",
    6: "Archived"
}

# === Global registry/staking  =========================================================== #

# enum ObjectState {
#     Undefined,
#     Proposed,
#     Approved,
#     Suspended,
#     Archived,
#     Burned
# }
OBJECT_STATE = {
    0: "Undefined",
    1: "Proposed",
    2: "Approved",
    3: "Suspended",
    4: "Archived",
    5: "Burned",
}

# GIF ecosystem actors
INSTANCE_OPERATOR = 'instanceOperator'
INSTANCE_WALLET = 'instanceWallet'
ORACLE_PROVIDER = 'oracleProvider'
CHAINLINK_NODE_OPERATOR = 'chainlinkNodeOperator'
RISKPOOL_KEEPER = 'riskpoolKeeper'
RISKPOOL_WALLET = 'riskpoolWallet'
INVESTOR = 'investor'
PRODUCT_OWNER = 'productOwner'
INSURER = 'insurer'
CUSTOMER1 = 'customer1'
CUSTOMER2 = 'customer2'
REGISTRY_OWNER = 'registryOwner'
STAKING = 'staking'
STAKER = 'staker'
STAKER2 = 'staker2'
OUTSIDER = 'outsider'

GIF_ACTOR = {
    INSTANCE_OPERATOR: 0,
    INSTANCE_WALLET: 1,
    ORACLE_PROVIDER: 2,
    CHAINLINK_NODE_OPERATOR: 3,
    RISKPOOL_KEEPER: 4,
    RISKPOOL_WALLET: 5,
    INVESTOR: 6,
    PRODUCT_OWNER: 7,
    INSURER: 8,
    CUSTOMER1: 9,
    CUSTOMER2: 10,
    REGISTRY_OWNER: 13,
    STAKER: 14,
    STAKER2: 15,
    OUTSIDER: 19,
}

DIP_TOKEN = 'dipToken'
ERC20_TOKEN = 'erc20Token'
INSTANCE = 'instance'
INSTANCE_SERVICE = 'instanceService'
INSTANCE_OPERATOR_SERVICE = 'instanceOperatorService'
COMPONENT_OWNER_SERVICE = 'componentOwnerService'
PRODUCT = 'product'
ORACLE = 'oracle'
RISKPOOL = 'riskpool'

# === GIF testing =========================================================== #

# ZERO_ADDRESS = accounts.at('0x0000000000000000000000000000000000000000')
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
COMPROMISED_ADDRESS = '0x0000000000000000000000000000000000000013'

# TEST account values
ACCOUNTS_MNEMONIC = 'candy maple cake sugar pudding cream honey rich smooth crumble sweet treat'

# TEST oracle/rikspool/product values
PRODUCT_NAME = 'Test.Product'
RISKPOOL_NAME = 'Test.Riskpool'
ORACLE_NAME = 'Test.Oracle'
ORACLE_INPUT_FORMAT = '(bytes input)'
ORACLE_OUTPUT_FORMAT = '(bool output)'
