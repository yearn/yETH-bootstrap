# @version 0.3.7
"""
@title Protocol Owned Liquidity
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def burn(_account: address, _amount: uint256): nonpayable

token: public(immutable(address))
management: public(address)
debt: public(uint256)
native_allowance: public(HashMap[address, uint256])

@external
def __init__(_token: address):
    token = _token
    self.management = msg.sender

@external
@payable
def __default__():
    pass

@external
def approve(_token: address, _spender: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == empty(address):
        self.native_allowance[_spender] = _amount
    else:
        ERC20(_token).approve(_spender, _amount)

@external
def mint(_amount: uint256):
    assert msg.sender == self.management
    self.debt += _amount
    Token(token).mint(self, _amount)

@external
def burn(_amount: uint256):
    assert msg.sender == self.management
    self.debt -= _amount
    Token(token).burn(self, _amount)

@external
def send_native(_receiver: address, _amount: uint256):
    assert msg.sender == self.management
    self.native_allowance[msg.sender] -= _amount
    raw_call(_receiver, b"", value=_amount)
