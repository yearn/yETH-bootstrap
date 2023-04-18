# @version 0.3.7
"""
@title Shutdown Module
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface Pool:
    def killed() -> bool: view

interface Bootstrap:
    def repay(_amount: uint256): nonpayable

interface POL:
    def send_native(_receiver: address, _amount: uint256): nonpayable

token: public(immutable(address))
bootstrap: public(immutable(address))
pol: public(immutable(address))
pool: public(address)
management: public(address)

@external
def __init__(_token: address, _bootstrap: address, _pol: address):
    token = _token
    bootstrap = _bootstrap
    pol = _pol
    self.management = msg.sender

@external
def redeem(_amount: uint256):
    assert Pool(self.pool).killed()
    ERC20(token).transferFrom(msg.sender, self, _amount)
    Bootstrap(bootstrap).repay(_amount)
    POL(pol).send_native(msg.sender, _amount)

@external
def set_pool(_pool: address):
    assert msg.sender == self.management
    assert self.pool == empty(address)
    self.pool = _pool
    self.management = empty(address)
