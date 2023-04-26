# @version 0.3.7
"""
@title Staking Module
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

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
    if msg.value > 0:
        POL(pol).receive_native(value=self.balance)

@external
def to_treasury(_amount: uint256):
    assert msg.sender == self.management
    POL(pol).send_native(self.treasury, _amount)

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.management = _management

@external
def set_treasury(_treasury: address):
    assert msg.sender == self.treasury
    self.treasury = _treasury
