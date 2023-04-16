# @version 0.3.7
"""
@title yETH bootstrap
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable

applications: HashMap[address, uint256]
deposited: HashMap[address, uint256]
token: public(immutable(address))
management: public(address)
whitelist_begin: public(uint256)
whitelist_end: public(uint256)
incentive_begin: public(uint256)
incentive_end: public(uint256)
deposit_begin: public(uint256)
deposit_end: public(uint256)
vote_begin: public(uint256)
vote_end: public(uint256)

NOTHING: constant(uint256) = 0
APPLIED: constant(uint256) = 1
WHITELISTED: constant(uint256) = 2

@external
def __init__(_token: address):
    token = _token
    self.management = msg.sender

@external
@payable
def apply(_asset: address):
    assert msg.value == 1_000_000_000_000_000_000
    assert self.applications[_asset] == NOTHING

@external
def whitelist(_asset: address):
    assert msg.sender == self.management
    assert self.applications[_asset] == APPLIED
    self.applications[_asset] = WHITELISTED

@external
@payable
def deposit():
    assert msg.value > 0
    self.deposited[msg.sender] += msg.value
    Token(token).mint(self, msg.value)

@external
@view
def has_applied(_asset: address) -> bool:
    return self.applications[_asset] > NOTHING

@external
@view
def is_whitelisted(_asset: address) -> bool:
    return self.applications[_asset] == WHITELISTED

@external
def set_whitelist_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    self.whitelist_begin = _begin
    self.whitelist_end = _end

@external
def set_incentive_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    self.incentive_begin = _begin
    self.incentive_end = _end

@external
def set_deposit_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    self.deposit_begin = _begin
    self.deposit_end = _end

@external
def set_vote_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    self.vote_begin = _begin
    self.vote_end = _end
