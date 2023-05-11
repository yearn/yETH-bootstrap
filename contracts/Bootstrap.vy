# @version 0.3.7
"""
@title yETH bootstrap
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
@notice 
    Implements the bootstrap phase as outlined in YIP-72, summarized:
    Contract defines multiple periods
        - Whitelist period: LSD protocols apply to be whitelisted by depositing 1 ETH
        - Deposit period: anyone can deposit ETH, which mints st-yETH 1:1 locked into the contract
        - Incentive period: anyone is able to incentivise voting for a whitelisted protocol by depositing tokens
        - Vote period: depositors are able to vote on their preferred whitelisted protocol
    After the vote period up to 5 protocols are declared as winner.
    Incentives for winning protocols will be distributed over all voters according to their overall vote weight, 
    regardless whether they voted for that specific protocol or not.
    Protocols that do not win will have their incentives refunded.
    10% of deposited ETH is sent to the POL.
    90% of deposited ETH is used to buy LSDs and deposit into the newly deployed yETH pool.
    The minted yETH is used to pay off 90% of the debt in the bootstrap contract.
    Depositor's st-yETH become withdrawable after a specific time.
"""

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def burn(_account: address, _amount: uint256): nonpayable

interface Staking:
    def deposit(_assets: uint256) -> uint256: nonpayable

token: public(immutable(address))
staking: public(immutable(address))
treasury: public(immutable(address))
pol: public(immutable(address))
management: public(address)

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

whitelist_begin: public(uint256)
whitelist_end: public(uint256)
incentive_begin: public(uint256)
incentive_end: public(uint256)
deposit_begin: public(uint256)
deposit_end: public(uint256)
vote_begin: public(uint256)
vote_end: public(uint256)
lock_end: public(uint256)

event Apply:
    protocol: indexed(address)

event Whitelist:
    protocol: indexed(address)

event Incentivise:
    protocol: indexed(address)
    incentive: indexed(address)
    depositor: indexed(address)
    amount: uint256

event Deposit:
    depositor: indexed(address)
    receiver: indexed(address)
    amount: uint256

event Claim:
    claimer: indexed(address)
    receiver: indexed(address)
    amount: uint256

event Vote:
    voter: indexed(address)
    protocol: indexed(address)
    amount: uint256

event Repay:
    payer: indexed(address)
    amount: uint256

event Split:
    amount: uint256

event ClaimIncentive:
    protocol: indexed(address)
    incentive: indexed(address)
    claimer: indexed(address)
    amount: uint256

event RefundIncentive:
    protocol: indexed(address)
    incentive: indexed(address)
    depositor: indexed(address)
    amount: uint256

event SetPeriod:
    period: indexed(uint256)
    begin: uint256
    end: uint256

event Winners:
    winners: DynArray[address, MAX_WINNERS]

NOTHING: constant(uint256) = 0
APPLIED: constant(uint256) = 1
WHITELISTED: constant(uint256) = 2
POL_SPLIT: constant(uint256) = 10
MAX_WINNERS: constant(uint256) = 5

@external
def __init__(_token: address, _staking: address, _treasury: address, _pol: address):
    token = _token
    staking = _staking
    treasury = _treasury
    pol = _pol
    self.management = msg.sender
    assert ERC20(token).approve(_staking, max_value(uint256), default_return_value=True)

@external
@payable
def __default__():
    self._deposit(msg.sender)

@external
@payable
def apply(_protocol: address):
    assert msg.value == 1_000_000_000_000_000_000 # dev: application fee
    assert block.timestamp >= self.whitelist_begin and block.timestamp < self.whitelist_end # dev: outside application period
    assert self.applications[_protocol] == NOTHING # dev: already applied
    self.applications[_protocol] = APPLIED
    log Apply(_protocol)

@external
def incentivise(_protocol: address, _incentive: address, _amount: uint256):
    assert _amount > 0
    assert block.timestamp >= self.incentive_begin and block.timestamp < self.incentive_end # dev: outside incentive period
    assert self.applications[_protocol] == WHITELISTED # dev: not whitelisted
    self.incentives[_protocol][_incentive] += _amount
    self.incentive_depositors[_protocol][_incentive][msg.sender] += _amount
    assert ERC20(_incentive).transferFrom(msg.sender, self, _amount, default_return_value=True)
    log Incentivise(_protocol, _incentive, msg.sender, _amount)

@external
@payable
def deposit(_account: address = msg.sender):
    self._deposit(_account)

@internal
@payable
def _deposit(_account: address):
    assert msg.value > 0
    assert block.timestamp >= self.deposit_begin and block.timestamp < self.deposit_end
    assert self.lock_end > 0
    self.debt += msg.value
    self.deposited += msg.value
    self.deposits[_account] += msg.value
    Token(token).mint(self, msg.value)
    Staking(staking).deposit(msg.value)
    log Deposit(msg.sender, _account, msg.value)

@external
def claim(_amount: uint256, _receiver: address = msg.sender):
    assert _amount > 0
    assert block.timestamp >= self.lock_end
    self.deposited -= _amount
    self.deposits[msg.sender] -= _amount
    assert ERC20(staking).transfer(_receiver, _amount, default_return_value=True)
    log Claim(msg.sender, _receiver, _amount)

@external
def vote(_protocol: address, _votes: uint256):
    assert block.timestamp >= self.vote_begin and block.timestamp < self.vote_end
    assert self.applications[_protocol] == WHITELISTED
    used: uint256 = self.votes_used[msg.sender] + _votes
    assert used <= self.deposits[msg.sender]
    self.voted += _votes
    self.votes[_protocol] += _votes
    self.votes_used[msg.sender] = used
    log Vote(msg.sender, _protocol, _votes)

@external
def repay(_amount: uint256):
    self.debt -= _amount
    Token(token).burn(msg.sender, _amount)
    log Repay(msg.sender, _amount)

@external
def split():
    assert msg.sender == self.management or msg.sender == treasury
    amount: uint256 = self.balance
    assert amount > 0
    log Split(amount)
    raw_call(pol, b"", value=amount/10)
    amount -= amount/10
    raw_call(treasury, b"", value=amount)

@external
@view
def claimable_incentive(_protocol: address, _incentive: address, _claimer: address) -> uint256:
    if not self.winners[_protocol] or self.incentive_claimed[_protocol][_incentive][_claimer]:
        return 0
    return self.incentives[_protocol][_incentive] * self.votes_used[_claimer] / self.voted

@external
def claim_incentive(_protocol: address, _incentive: address, _claimer: address = msg.sender) -> uint256:
    assert self.winners[_protocol] # dev: protocol is not winner
    assert not self.incentive_claimed[_protocol][_incentive][_claimer] # dev: incentive already claimed
    
    incentive: uint256 = self.incentives[_protocol][_incentive] * self.votes_used[_claimer] / self.voted
    assert incentive > 0 # dev: nothing to claim

    self.incentive_claimed[_protocol][_incentive][_claimer] = True
    assert ERC20(_incentive).transfer(_claimer, incentive, default_return_value=True)
    log ClaimIncentive(_protocol, _incentive, _claimer, incentive)
    return incentive

@external
def refund_incentive(_protocol: address, _incentive: address, _depositor: address = msg.sender) -> uint256:
    assert len(self.winners_list) > 0 # dev: no winners declared
    assert not self.winners[_protocol] # dev: protocol is winner

    amount: uint256 = self.incentive_depositors[_protocol][_incentive][_depositor]
    assert amount > 0 # dev: nothing to refund

    self.incentive_depositors[_protocol][_incentive][_depositor] = 0
    assert ERC20(_incentive).transfer(_depositor, amount, default_return_value=True)
    log RefundIncentive(_protocol, _incentive, _depositor, amount)
    return amount

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
    log SetPeriod(0, _begin,  _end)

@external
def set_incentive_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.whitelist_begin
    assert _end > _begin
    self.incentive_begin = _begin
    self.incentive_end = _end
    log SetPeriod(1, _begin,  _end)

@external
def set_deposit_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.whitelist_begin
    assert _end > _begin
    self.deposit_begin = _begin
    self.deposit_end = _end
    log SetPeriod(2, _begin,  _end)

@external
def set_vote_period(_begin: uint256, _end: uint256):
    assert msg.sender == self.management
    assert _begin >= self.deposit_begin
    assert _end > _begin
    self.vote_begin = _begin
    self.vote_end = _end
    log SetPeriod(3, _begin, _end)

@external
def set_lock_end(_end: uint256):
    assert msg.sender == self.management
    self.lock_end = _end
    log SetPeriod(4, 0, _end)

@external
def whitelist(_protocol: address):
    assert msg.sender == self.management
    assert self.applications[_protocol] == APPLIED # dev: has not applied
    self.applications[_protocol] = WHITELISTED
    log Whitelist(_protocol)

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
    log Winners(_winners)
