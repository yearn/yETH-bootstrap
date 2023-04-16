# @version 0.3.7
"""
@title yETH bootstrap
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable

token: public(immutable(address))

applications: HashMap[address, uint256]
debt: public(uint256)
deposited: public(uint256)
deposits: public(HashMap[address, uint256])
incentives: public(HashMap[address, HashMap[address, uint256]])
voted: public(uint256)
votes_used: public(HashMap[address, uint256])
votes: public(HashMap[address, uint256])

management: public(address)
treasury: public(address)

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
    self.treasury = msg.sender

@external
@payable
def apply(_protocol: address):
    assert msg.value == 1_000_000_000_000_000_000
    assert block.timestamp >= self.whitelist_begin and block.timestamp < self.whitelist_end
    assert self.applications[_protocol] == NOTHING
    self.applications[_protocol] = APPLIED

@external
def whitelist(_protocol: address):
    assert msg.sender == self.management
    assert self.applications[_protocol] == APPLIED
    self.applications[_protocol] = WHITELISTED

@external
def undo_whitelist(_protocol: address):
    assert msg.sender == self.management
    assert self.applications[_protocol] == WHITELISTED
    self.applications[_protocol] = APPLIED

@external
def incentivise(_protocol: address, _incentive: address, _amount: uint256):
    assert _amount > 0
    assert block.timestamp >= self.incentive_begin and block.timestamp < self.incentive_end
    assert self.applications[_protocol] == WHITELISTED
    self.incentives[_protocol][_incentive] += _amount
    assert ERC20(_incentive).transferFrom(msg.sender, self, _amount, default_return_value=True)

@external
@payable
def deposit():
    assert msg.value > 0
    assert block.timestamp >= self.deposit_begin and block.timestamp < self.deposit_end
    self.deposited += msg.value
    self.deposits[msg.sender] += msg.value
    Token(token).mint(self, msg.value)

@external
def vote(_protocol: address, _votes: uint256):
    assert block.timestamp >= self.vote_begin and block.timestamp < self.vote_end
    assert self.applications[_protocol] == WHITELISTED
    used: uint256 = self.votes_used[msg.sender] + _votes
    assert used <= self.deposits[msg.sender]
    self.voted += _votes
    self.votes[_protocol] += _votes

@external
@view
def has_applied(_protocol: address) -> bool:
    return self.applications[_protocol] > NOTHING

@external
@view
def is_whitelisted(_protocol: address) -> bool:
    return self.applications[_protocol] == WHITELISTED

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
