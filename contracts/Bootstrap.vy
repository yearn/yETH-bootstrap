# @version 0.3.7
"""
@title yETH bootstrap
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def burn(_account: address, _amount: uint256): nonpayable

interface Staking:
    def deposit(_assets: uint256) -> uint256: nonpayable

token: public(immutable(address))
staking: public(immutable(address))

applications: HashMap[address, uint256]
debt: public(uint256)
deposited: public(uint256)
deposits: public(HashMap[address, uint256]) # user => amount deposited
incentives: public(HashMap[address, HashMap[address, uint256]]) # protocol => incentive => amount
incentive_depositors: public(HashMap[address, HashMap[address, HashMap[address, uint256]]]) # protocol => incentive => depositor => amount
voted: public(uint256)
votes_used: public(HashMap[address, uint256]) # user => votes used
votes: public(HashMap[address, uint256]) # protocol => votes
winners_list: public(DynArray[address, MAX_WINNERS])
winners: public(HashMap[address, bool]) # protocol => winner?
incentive_claimed: public(HashMap[address, HashMap[address, HashMap[address, bool]]]) # winner => incentive => user => claimed?

management: public(address)
treasury: public(address)
pol: public(address)

whitelist_begin: public(uint256)
whitelist_end: public(uint256)
incentive_begin: public(uint256)
incentive_end: public(uint256)
deposit_begin: public(uint256)
deposit_end: public(uint256)
vote_begin: public(uint256)
vote_end: public(uint256)
lock_end: public(uint256)

NOTHING: constant(uint256) = 0
APPLIED: constant(uint256) = 1
WHITELISTED: constant(uint256) = 2
POL_SPLIT: constant(uint256) = 10
MAX_WINNERS: constant(uint256) = 5

@external
def __init__(_token: address, _staking: address):
    token = _token
    staking = _staking
    self.management = msg.sender
    self.treasury = msg.sender
    assert ERC20(token).approve(_staking, max_value(uint256), default_return_value=True)

@external
@payable
def apply(_protocol: address):
    assert msg.value == 1_000_000_000_000_000_000 # dev: application fee
    assert block.timestamp >= self.whitelist_begin and block.timestamp < self.whitelist_end # dev: outside application period
    assert self.applications[_protocol] == NOTHING # dev: already applied
    self.applications[_protocol] = APPLIED

@external
def incentivise(_protocol: address, _incentive: address, _amount: uint256):
    assert _amount > 0
    assert block.timestamp >= self.incentive_begin and block.timestamp < self.incentive_end # dev: outside incentive period
    assert self.applications[_protocol] == WHITELISTED # dev: not whitelisted
    self.incentives[_protocol][_incentive] += _amount
    self.incentive_depositors[_protocol][_incentive][msg.sender] += _amount
    assert ERC20(_incentive).transferFrom(msg.sender, self, _amount, default_return_value=True)

@external
@payable
def deposit():
    assert msg.value > 0
    assert block.timestamp >= self.deposit_begin and block.timestamp < self.deposit_end
    self.deposited += msg.value
    self.deposits[msg.sender] += msg.value
    Token(token).mint(self, msg.value)
    Staking(staking).deposit(msg.value)

@external
@payable
def claim(_amount: uint256):
    assert _amount > 0
    assert block.timestamp >= self.lock_end
    self.deposits[msg.sender] -= _amount
    assert ERC20(staking).transfer(msg.sender, _amount, default_return_value=True)

@external
def vote(_protocol: address, _votes: uint256):
    assert block.timestamp >= self.vote_begin and block.timestamp < self.vote_end
    assert self.applications[_protocol] == WHITELISTED
    used: uint256 = self.votes_used[msg.sender] + _votes
    assert used <= self.deposits[msg.sender]
    self.voted += _votes
    self.votes[_protocol] += _votes
    self.votes_used[msg.sender] = used

@external
def repay(_amount: uint256):
    self.debt -= _amount
    Token(token).burn(msg.sender, _amount)

@external
def split():
    assert msg.sender == self.management or msg.sender == self.treasury
    amount: uint256 = self.balance
    assert amount > 0
    treasury: address = self.treasury
    pol: address = self.pol
    assert treasury != empty(address)
    assert pol != empty(address)

    raw_call(pol, b"", value=amount/10)
    amount -= amount/10
    raw_call(treasury, b"", value=amount)

@external
def claim_incentive(_protocol: address, _incentive: address, _claimer: address = msg.sender):
    assert self.winners[_protocol] # dev: protocol is not winner
    assert not self.incentive_claimed[_protocol][_incentive][_claimer] # dev: incentive already claimed
    
    incentive: uint256 = self.incentives[_protocol][_incentive] * self.votes_used[_claimer] / self.voted
    assert incentive > 0 # dev: nothing to claim

    self.incentive_claimed[_protocol][_incentive][_claimer] = True
    assert ERC20(_incentive).transfer(_claimer, incentive, default_return_value=True)

@external
def refund_incentive(_protocol: address, _incentive: address, _depositor: address = msg.sender):
    assert len(self.winners_list) > 0 # dev: no winners declared
    assert not self.winners[_protocol] # dev: protocol is winner

    amount: uint256 = self.incentive_depositors[_protocol][_incentive][_depositor]
    assert amount > 0 # dev: nothing to refund

    self.incentive_depositors[_protocol][_incentive][_depositor] = 0
    assert ERC20(_incentive).transfer(_depositor, amount, default_return_value=True)

@external
@view
def has_applied(_protocol: address) -> bool:
    return self.applications[_protocol] > NOTHING

@external
@view
def is_whitelisted(_protocol: address) -> bool:
    return self.applications[_protocol] == WHITELISTED

# MANAGEMENT FUNCTIONS

@external
def set_whitelist_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _end > _begin
    self.whitelist_begin = _begin
    self.whitelist_end = _end

@external
def set_incentive_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.whitelist_begin
    assert _end > _begin
    self.incentive_begin = _begin
    self.incentive_end = _end

@external
def set_deposit_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.whitelist_begin
    assert _end > _begin
    self.deposit_begin = _begin
    self.deposit_end = _end

@external
def set_vote_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.deposit_begin
    assert _end > _begin
    self.vote_begin = _begin
    self.vote_end = _end

@external
def set_lock_end(_end: uint256):
    assert msg.sender == self.management
    self.lock_end = _end

@external
def set_treasury(_treasury: address):
    assert msg.sender == self.management
    assert self.treasury == empty(address)
    self.treasury = _treasury

@external
def set_pol(_pol: address):
    assert msg.sender == self.management
    assert self.pol == empty(address)
    self.pol = _pol

@external
def whitelist(_protocol: address):
    assert msg.sender == self.management
    assert self.applications[_protocol] == APPLIED # dev: has not applied
    self.applications[_protocol] = WHITELISTED

@external
def undo_whitelist(_protocol: address):
    assert msg.sender == self.management
    assert self.applications[_protocol] == WHITELISTED # dev: not whitelisted
    self.applications[_protocol] = APPLIED

@external
def declare_winners(_winners: DynArray[address, MAX_WINNERS]):
    assert msg.sender == self.management
    assert block.timestamp >= self.vote_end
    assert len(self.winners_list) == 0
    for winner in _winners:
        assert self.applications[winner] == WHITELISTED
        self.winners_list.append(winner)
        self.winners[winner] = True
