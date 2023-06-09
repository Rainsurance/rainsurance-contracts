![Build](https://github.com/etherisc/gif-contracts/actions/workflows/build.yml/badge.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![](https://dcbadge.vercel.app/api/server/cVsgakVG4R?style=flat)](https://discord.gg/Qb6ZjgE8)

# GIF - Rainsurance Contracts

This repository holds the smart contracts, helper scripts and documentation for the Rain insurance product.

Unit tests were based on the [GIF Core Contracts](https://github.com/etherisc/gif-contracts) sample product.

The rest of this project is essentially a clone from the [GIF Sandbox](https://github.com/etherisc/gif-sandbox).

## Fully configured IDE 

To use GIF's configured IDE see the instructions at [https://github.com/etherisc/gif-sandbox/blob/master/docs/development_environment.md](https://github.com/etherisc/gif-sandbox/blob/master/docs/development_environment.md). 

In this case you can skip the next two steps as the _devcontainer_ is based on the (updated) _brownie_ image. 

## Create Brownie Docker Image

[Brownie](https://eth-brownie.readthedocs.io/en/stable) is used for development of the contracts in this repository.

Alternatively to installing a python development environment and the brownie framework, wokring with Brownie is also possible via Docker.

For building the `brownie` docker image used in the samples below, follow the instructions in [gif-brownie](https://github.com/etherisc/gif-brownie).


## Run Brownie Container

```bash
docker run -it --rm -v $PWD:/projects brownie
```

## Compile

Inside the Brownie container compile the contracts/interfaces

```bash
brownie compile --all
```

## Run Unit Tests

Run the unit tests
```bash
brownie test
```

or to execute the tests in parallel

```
brownie test -n auto
```

_Note_: Should the tests fail when running them in parallel, the test execution probably creates too much load on the system. 
In this case replace the `auto` keyword in the command with the number of executors (use at most the number of CPU cores available on your system). 

## Deployment to Polygon Mumbai Testnet

### Environment variables
Create a `.env` file based on the `.env.example` file available in this repository.

All stakeholders addresses must be updated in the file and sufficiently funded.

Polygon Oficial faucet may be used: [https://faucet.polygon.technology/](https://faucet.polygon.technology/)

### gif_instance_address.txt file

Create a `gif_instance_address.txt` file in the root directory with the link_token address for the Polygon Mumbai testnet.

All  Chainlink contract's addresses can be found [here](https://docs.chain.link/resources/link-token-contracts?parent=chainlinkFunctions).

```bash
link_token=0x326C977E6efc84E512bB9C30f76E30c160eD06FB
```

### Deploy the contracts using the brownie console

Next run brownie console as follow:

```bash
brownie console --network polygon-test
```

For a first & full deployment (including the GIF instance) run as follow.

This will deploy a regular GIF Oracle that will be replaced in the next deploy by the ChainlinkFunctions-based Oracle.

```bash
from scripts.deploy_rain import help_testnet
help_testnet()

# follow the instructions printed in the console with one small change:
all_in_1(deploy_all=True ...)
```

For the next deployments make sure to update the `gif_instance_address.txt` with the previously deployed contract addresses:

```bash
registry=0x
token=0x
link_token=0x326C977E6efc84E512bB9C30f76E30c160eD06FB
oracle=0x
```

`token` is the stable coin address

`oracle` is the ChainlinkFunctions-based GIF Oracle address that is deployed separately

Now run as follow:

```bash
from scripts.deploy_rain import help_testnet_clfunctions
help_testnet_clfunctions()

# follow closely all the instructions printed in the console

```

### To interact with an existing setup use the following helper methods as shown below.

```python
from scripts.deploy_rain import (
    from_registry,
    from_component,
)

# for the case of a known registry address, 
# eg '0xE7eD6747FaC5360f88a2EFC03E00d25789F69291'
(instance, product, oracle, riskpool) = from_registry('0xE7eD6747FaC5360f88a2EFC03E00d25789F69291')

# or for a known address of a component, eg
# eg product address '0xF039D8acecbB47763c67937D66A254DB48c87757'
(instance, product, oracle, riskpool) = from_component('0xF039D8acecbB47763c67937D66A254DB48c87757')
```

