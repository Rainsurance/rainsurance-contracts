#!/bin/bash
brownie networks add Local ganache host=http://ganache:7545 chainid=1234

.devcontainer/scripts/deploy-gif.sh 

echo '>>>> Compiling contracts ...'
echo "" > .env 
rm -rf build/
brownie compile --all 

if grep -q "token=" "/workspace/gif_instance_address.txt"; then
    echo ">>>> gif_instance_address.txt exists. No deployment needed."
    exit 0
fi

# deploy USDC, DIP and save addresses
echo "Deploying the USD contracts to ganache ..."
brownie console --network=ganache <<EOF
from brownie import Usdc, DIP
token = Usdc.deploy({'from': accounts[0]})
dip = DIP.deploy({'from': accounts[0]})
f = open("/workspace/gif_instance_address.txt", "a")
f.writelines("token=%s\n" % (token.address))
f.writelines("dip=%s\n" % (dip.address))
f.close()
EOF
