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
available: public(uint256)
debt: public(uint256)
native_allowance: public(HashMap[address, uint256])
mint_allowance: public(HashMap[address, uint256])
burn_allowance: public(HashMap[address, uint256])

NATIVE: constant(address) = 0x0000000000000000000000000000000000000001
MINT: constant(address)   = 0x0000000000000000000000000000000000000002
BURN: constant(address)   = 0x0000000000000000000000000000000000000003

@external
def __init__(_token: address):
    token = _token
    self.management = msg.sender

@external
@payable
def __default__():
    self.available += msg.value
    pass

@external
@payable
def receive_native():
    # dont increase debt ceiling here
    pass

@external
def send_native(_receiver: address, _amount: uint256):
    assert _amount > 0
    self.native_allowance[msg.sender] -= _amount
    raw_call(_receiver, b"", value=_amount)

@external
def mint(_amount: uint256):
    assert _amount > 0
    self.mint_allowance[msg.sender] -= _amount
    debt: uint256 = self.debt + _amount
    assert debt <= self.available
    self.debt = debt
    Token(token).mint(self, _amount)

@external
def burn(_amount: uint256):
    assert _amount > 0
    self.burn_allowance[msg.sender] -= _amount
    self.debt -= _amount
    Token(token).burn(self, _amount)

# MANAGEMENT FUNCTIONS

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.management = _management

@external
def approve(_token: address, _spender: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == NATIVE:
        self.native_allowance[_spender] = _amount
    elif _token == MINT:
        self.mint_allowance[_spender] = _amount
    elif _token == BURN:
        self.burn_allowance[_spender] = _amount
    else:
        ERC20(_token).approve(_spender, _amount)
