// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract Usdc is ERC20 {

    // https://etherscan.io/address/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48#readProxyContract
    string public constant NAME = "USD Coin - DUMMY";
    string public constant SYMBOL = "USDC";
    uint8 public constant DECIMALS = 6;

    uint256 public constant INITIAL_SUPPLY = 10**24;

    event LogUsdcTransfer(address from, address to, uint256 amount, uint256 time, uint256 blockNumber);
    event LogUsdcTransferFrom(address from, address to, uint256 amount, uint256 time, uint256 blockNumber);

    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }

    function decimals() public pure override returns(uint8) {
        return DECIMALS;
    }

    function transfer(address to, uint256 amount) public virtual override returns (bool) {
        address from = _msgSender();
        // solhint-disable-next-line not-rely-on-time
        emit LogUsdcTransferFrom(from, to, amount, block.timestamp, block.number);
        return super.transfer(to, amount);
    }
    
    function transferFrom(address from, address to, uint256 amount) 
        public virtual override returns (bool) 
    {
        // solhint-disable-next-line not-rely-on-time
        emit LogUsdcTransferFrom(from, to, amount, block.timestamp, block.number);
        return super.transferFrom(from, to, amount);
    }  
}