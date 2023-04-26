# @version 0.3.7
"""
@title Staking Module
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface POL:
    def receive_native(): payable
    def send_native(_receiver: address, _amount: uint256): nonpayable

pol: public(immutable(address))
management: public(address)
treasury: public(address)

@external
def __init__(_pol: address, _treasury: address):
    pol = _pol
    self.management = msg.sender
    self.treasury = _treasury

@external
@payable
def __default__():
    pass

@external
def from_pol(_token: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == empty(address):
        POL(pol).send_native(self, _amount)
    else:
        assert ERC20(_token).transferFrom(pol, self, _amount, default_return_value=True)

@external
def to_pol(_token: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == empty(address):
        POL(pol).receive_native(value=_amount)
    else:
        assert ERC20(_token).transfer(pol, _amount, default_return_value=True)

@external
def to_treasury(_token: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == empty(address):
        raw_call(self.treasury, b"", value=_amount)
    else:
        assert ERC20(_token).transfer(self.treasury, _amount, default_return_value=True)

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.management = _management

@external
def set_treasury(_treasury: address):
    assert msg.sender == self.treasury
    self.treasury = _treasury
