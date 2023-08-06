// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface ERC677ReceiverInterface {
  function onTokenTransfer(
    address sender,
    uint256 amount,
    bytes calldata data
  ) external;
}
